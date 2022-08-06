import datetime
import json
import os
import time
from typing import Callable, Optional

import asyncpg
import discord
import pandas
import pytz
from discord import Interaction
from discord.app_commands import AppCommandError
from discord.ext import commands
from discord.ext.commands import Bot, when_mentioned_or, when_mentioned
from tzlocal import get_localzone

import libs.db.database_handle as database_handle  # not strictly a lib rn but hopefully will be in the future
import libs.misc.utils as utils
from libs.misc.decorators import MissingStaffError, MissingDevError, MissingStaffSlashError, MissingDevSlashError
from libs.misc.utils import DefaultEmbedResponses, ContextTypes, unbox_context
from scripts.utils import cog_handler


class AdamTree(discord.app_commands.tree.CommandTree):
    def __init__(self, client: discord.Client) -> None:
        self.client = client
        self.maps = {}
        super().__init__(client)

    def map(self, error: AppCommandError, method: Callable) -> None:
        """
        Allows for mapping custom AppCommandErrors to custom handler methods.
        """

        self.maps[error] = method

    async def on_error(self, interaction: Interaction, error: AppCommandError) -> None:
        """
        Custom error handler for AppCommandErrors. If a custom handler is mapped to the error, it will be called.
        Otherwise, the error will be raised as normal.
        """

        if isinstance(error, MissingStaffSlashError) or isinstance(error, MissingDevSlashError):
            await DefaultEmbedResponses.invalid_perms(self.client, interaction)
        else:
            mapped_method = self.maps.get(error.__class__, None)
            if callable(mapped_method):
                await mapped_method(interaction, error)
            else:
                raise error


class AdamBot(Bot):
    async def get_context(self, message: discord.Message, *, cls=commands.Context) -> commands.Context:
        return await super().get_context(message, cls=cls) if cls else None

    async def determine_prefix(self, bot, message: discord.Message) -> list[str]:
        """
        Procedure that determines the prefix for a guild. This determines the prefix when a global one is not being used
        "bot" is a required argument but also pointless since each AdamBot object isn't going to be trying to handle *other* AdamBot objects' prefixes
        """

        watch_prefixes = [await self.get_config_key(message, "prefix") if message.guild else None, self.global_prefix]
        if watch_prefixes != [None] * len(watch_prefixes):
            return when_mentioned_or(*tuple([prefix for prefix in watch_prefixes if type(prefix) is str]))(self,
                                                                                                           message)  # internal conf prefix or guild conf prefix can be used
        else:
            # Config tables aren't loaded yet or internal config doesn't specify another prefix, temporarily set to mentions only
            return when_mentioned(self, message)

    async def get_used_prefixes(self, ctx: commands.Context | discord.Interaction | discord.Message | discord.Guild) -> \
            list[str]:
        """
        Gets the prefixes that can be used to invoke a command in the guild where the message is from
        """

        if not hasattr(self, "get_config_key"):
            return []  # config cog not loaded yet

        guild_prefix = await self.get_config_key(ctx, "prefix")
        return [prefix for prefix in [self.user.mention, self.global_prefix if self.global_prefix else None,
                                      guild_prefix if guild_prefix else None] if type(prefix) is str]

    def __init__(self, start_time: float, config_path: str = "config.json", command_prefix: str = "", *args,
                 **kwargs) -> None:
        self.ContextType = ContextTypes
        self.unbox_context = unbox_context
        self.internal_config = self.load_internal_config(config_path)
        self.cog_handler = cog_handler.CogHandler(self)
        self.kwargs = kwargs
        self.global_prefix = self.internal_config.get("global_prefix")
        self.kwargs["command_prefix"] = self.determine_prefix if not command_prefix else when_mentioned_or(
            command_prefix)

        self.cog_handler.preload_core_cogs()

        cog_dict = pandas.json_normalize(self.internal_config.get("cogs", {}), sep=".").to_dict(orient="records")[0]
        if cog_dict:
            self.cog_handler.preload_cogs(
                pandas.json_normalize(self.internal_config["cogs"], sep=".").to_dict(orient="records")[0])
        else:
            print("[X]    No cogs specified.")

        super().__init__(*args,
                         intents=self.cog_handler.make_intents(list(dict.fromkeys(self.cog_handler.intent_list))),
                         tree_cls=AdamTree, **kwargs)
        self.db_start = time.time()

        print("Creating DB pool...")
        self.db_url = self.internal_config.get("database_url", "")
        if not self.db_url:
            self.db_url = os.environ.get("DATABASE_URL", "")
        self.connections = kwargs.get("connections", 10)  # Max DB pool connections

        self.online = False  # Start at False, changes to True once fully initialised
        self.LOCAL_HOST = False if os.environ.get("REMOTE", None) else True
        self.display_timezone = pytz.timezone("Europe/London")
        self.timezone = get_localzone()
        self.ts_format = "%A %d/%m/%Y %H:%M:%S"
        self.start_time = start_time
        self._init_time = time.time()
        self.last_active = {}  # Used for ensuring bots do not respond or invoke commands

        print(f"BOT INITIALISED {self._init_time - start_time} seconds")

    async def shutdown(self,
                       ctx: commands.Context | discord.Interaction = None) -> None:  # ctx = None because this is also called upon CTRL+C in command line
        """
        Procedure that closes down AdamBot, using the standard client.close() command, as well as some database handling methods.
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        self.online = False  # This is set to false to prevent DB things going on in the background once bot closed
        user = f"{self.user.mention} " if self.user else ""
        p_s = f"Beginning process of shutting {user}down. DB pool shutting down..."

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(p_s)
        elif ctx_type == self.ContextTypes.Interaction:
            await ctx.response.send_message(p_s)
        print(p_s)

        if hasattr(self, "pool"):
            self.pool.terminate()  # TODO: Make this more graceful

        c_s = "Closing connection to Discord..."

        if ctx_type != self.ContextTypes.Unknown:
            await ctx.channel.send(c_s)
        print(c_s)

        try:
            await self.change_presence(status=discord.Status.offline)
        except AttributeError:
            pass  # hasattr returns true but then you get yelled at if you use it

        await super().close()
        time.sleep(1)  # stops bs RuntimeError spam at the end
        print(f"Bot closed after {time.time() - self.start_time} seconds")

    @staticmethod
    def load_internal_config(config_path: str) -> dict:
        """
        Loads bot's internal config from specified location.

        Perhaps in the future have a "default" config generated e.g. with all cogs auto-detected, rather than it being specifically included in the repo?
        """

        config = config_file = None
        try:
            config_file = open(config_path)
        except Exception as e:
            error_msg = f"Config is inaccessible! See the error below for more details\n{type(e).__name__}: {e}"
            print(error_msg)
        try:
            config = json.loads(config_file.read())
        except json.decoder.JSONDecodeError as e:
            print(f"The JSON in the config is invalid! See the error below for more details\n{type(e).__name__}: {e}")
            config_file.close()
            exit()
        config_file.close()
        return config

    async def start_up(self) -> None:
        """
        Command that starts AdamBot, is run in AdamBot.__init__
        """

        print("Loading utils into the bot instance...")
        self.__dict__.update(utils.__dict__)  # Bring all of utils into the bot - prevents referencing utils in cogs
        print("Setting flag handlers...")
        self.set_flag_handlers()

        print("Loading cogs...")
        await self.cog_handler.load_cogs()
        self.cog_load = time.time()
        print(
            f"\nLoaded all cogs in {self.cog_load - self._init_time} seconds ({self.cog_load - self.start_time} seconds total)")

        # Moved to here as it makes more sense to not load everything then tell the user they did an oopsies
        print(f"Bot fully setup! ({time.time() - self.start_time} seconds total)")
        print("Logging into Discord...")

        token = self.internal_config.get("token", "")
        if not token:
            token = os.environ.get("TOKEN", "")

        token = token if token else self.kwargs.get("token", "")
        if not token:
            print("No token provided!")
            return

        self.internal_config = []
        self.pool: \
            asyncpg.pool.Pool = await asyncpg.create_pool(self.db_url + "?sslmode=require", max_size=self.connections)

        await database_handle.introduce_tables(self.pool, self.cog_handler.db_tables)
        await database_handle.insert_cog_db_columns_if_not_exists(self.pool, self.cog_handler.db_tables)
        print(f"DB took {time.time() - self.db_start} seconds to connect to")

        try:
            await self.start(token)
        except Exception as e:
            print(
                f"Something went wrong handling the token!\nThe error was {type(e).__name__}: {e}")  # overridden close cleans this up neatly

    async def on_ready(self) -> None:
        """
        Event that sets the bot instance's status and online presence
        """
        self.login_time = time.time()
        print(f"Bot logged into Discord ({self.login_time - self.start_time} seconds total)")
        await self.tree.sync()
        await self.change_presence(activity=discord.Game(name=f"in {len(self.guilds)} servers | Type `help` for help"),
                                   status=discord.Status.online)
        self.online = True

    async def on_message(self, message: discord.Message) -> None:
        """
        Event that has checks that stop bots from executing commands
        """

        if type(message.channel) == discord.DMChannel or message.author.bot:
            return
        if message.guild.id not in self.last_active:
            self.last_active[message.guild.id] = []  # create the dict key for that guild if it doesn't exist
        last_active_list = self.last_active[message.guild.id]
        if message.author in last_active_list:
            last_active_list.remove(message.author)
        last_active_list.insert(0, message.author)

        # Now run commands, due to overriding of default bot `on_message` doesn't do this automatically
        await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error) -> None:
        print(error)  # added back for the sake of retaining sanity when debugging
        if isinstance(error, MissingStaffError) or isinstance(error, MissingDevError):
            await self.DefaultEmbedResponses.invalid_perms(ctx.bot, ctx)

    def set_flag_handlers(self) -> None:
        self.flag_handler = self.flags()
        self.flag_handler.set_flag("time", {"flag": "t", "post_parse_handler": self.flag_methods.str_time_to_seconds})
        self.flag_handler.set_flag("reason", {"flag": "r"})

    def correct_time(self, conv_time: Optional[datetime.datetime] = None,
                     timezone_: str = "system") -> datetime.datetime:
        if not conv_time:
            conv_time = datetime.datetime.now()
        if timezone_ == "system" and conv_time.tzinfo is None:
            tz_obj = self.timezone
        elif conv_time.tzinfo is not None:
            tz_obj = pytz.timezone(conv_time.tzinfo.tzname(conv_time))  # conv_time.tzinfo isn't a pytz.tzinfo object
        else:
            tz_obj = pytz.timezone(timezone_)

        try:
            return tz_obj.localize(conv_time.replace(tzinfo=None)).astimezone(self.display_timezone)
        except AttributeError:  # TODO: Sometimes on local env throws exception (AttributeError: 'zoneinfo.ZoneInfo' object has no attribute 'localize') / potential fix?
            return conv_time
