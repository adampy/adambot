import time

start_time = time.time()

__import__("importlib").import_module("scripts.utils.handle_dependencies").handle_dependencies()

import discord
from discord.ext import commands
from discord.ext.commands import Bot, when_mentioned_or, when_mentioned
import asyncpg
import os
import pytz
import datetime
from tzlocal import get_localzone
import pandas
import json
import argparse
import libs.db.database_handle as database_handle  # not strictly a lib rn but hopefully will be in the future

class AdamBot(Bot):
    async def get_context(self, message: discord.Message, *, cls=commands.Context) -> commands.Context:
        return await super().get_context(message, cls=cls) if cls else None

    async def determine_prefix(self, bot, message: discord.Message) -> list[str]:
        """
        Procedure that determines the prefix for a guild. This determines the prefix when a global one is not being used
        'bot' is a required argument but also pointless since each AdamBot object isn't going to be trying to handle *other* AdamBot objects' prefixes
        """

        watch_prefixes = [await self.get_config_key(message, "prefix") if message.guild else None, self.global_prefix]
        if watch_prefixes != [None] * len(watch_prefixes):
            return when_mentioned_or(*tuple([prefix for prefix in watch_prefixes if type(prefix) is str]))(self,
                                                                                                           message)  # internal conf prefix or guild conf prefix can be used
        else:
            # Config tables aren't loaded yet or internal config doesn't specify another prefix, temporarily set to mentions only
            return when_mentioned(self, message)

    async def get_used_prefixes(self, message: discord.Message) -> list[str]:
        """
        Gets the prefixes that can be used to invoke a command in the guild where the message is from
        """

        if not hasattr(self, "get_config_key"):
            return []  # config cog not loaded yet

        guild_prefix = await self.get_config_key(message, "prefix")
        return [prefix for prefix in [self.user.mention, self.global_prefix if self.global_prefix else None,
                                      guild_prefix if guild_prefix else None] if type(prefix) is str]

    def __init__(self, start_time: float, config_path: str = "config.json", command_prefix: str = "", *args,
                 **kwargs) -> None:
        self.internal_config = self.load_internal_config(config_path)
        self.cog_list = {}
        kwargs["command_prefix"] = self.determine_prefix if not command_prefix else when_mentioned_or(command_prefix)

        self.core_cogs = [
            "core.config.config",
            "core.tasks.tasks",
            "libs.misc.temp_utils_cog"
            # as the name suggests, this is temporary, will be moved/split up at some point, just not right now
        ]

        super().__init__(*args, **kwargs)
        self.preload_core_cogs()
        self.preload_cogs()
        self.global_prefix = self.internal_config.get("global_prefix",
                                                      None)  # Stores the global prefix, or None if not set / using guild specific one

        self.connections = kwargs.get("connections", 10)  # Max DB pool connections
        self.online = False  # Start at False, changes to True once fully initialised
        self.LOCAL_HOST = False if os.environ.get("REMOTE", None) else True
        self.display_timezone = pytz.timezone('Europe/London')
        self.timezone = get_localzone()
        self.ts_format = '%A %d/%m/%Y %H:%M:%S'
        self.start_time = start_time
        self._init_time = time.time()

        print(f"BOT INITIALISED {self._init_time - start_time} seconds")
        self.start_up(kwargs)  # kwargs passed here specifically to prevent leak of sensitive stuff passed in

    async def close(self,
                    ctx: commands.Context = None) -> None:  # ctx = None because this is also called upon CTRL+C in command line
        """
        Procedure that closes down AdamBot, using the standard client.close() command, as well as some database handling methods.
        """

        self.online = False  # This is set to false to prevent DB things going on in the background once bot closed
        user = f"{self.user.mention} " if self.user else ""
        p_s = f"Beginning process of shutting {user}down. DB pool shutting down..."
        (await ctx.send(p_s), print(p_s)) if ctx else print(p_s)
        if hasattr(self, "pool"):
            self.pool.terminate()  # TODO: Make this more graceful
        c_s = "Closing connection to Discord..."
        (await ctx.send(c_s), print(c_s)) if ctx else print(c_s)
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

    def start_up(self, kwargs: dict) -> None:
        """
        Command that starts AdamBot, is run in AdamBot.__init__
        """

        print("Loading cogs...")
        self.load_cogs()
        self.cog_load = time.time()
        print(
            f"\nLoaded all cogs in {self.cog_load - self._init_time} seconds ({self.cog_load - self.start_time} seconds total)")
        print("Creating DB pool...")
        db_url = self.internal_config.get("database_url", "")
        if not db_url:
            db_url = os.environ.get("DATABASE_URL", "")

        self.pool: \
            asyncpg.pool.Pool = self.loop.run_until_complete(
            asyncpg.create_pool(db_url + "?sslmode=require", max_size=self.connections))

        # Moved to here as it makes more sense to not load everything then tell the user they did an oopsies
        print(
            f'Bot fully setup!\nDB took {time.time() - self.cog_load} seconds to connect to ({time.time() - self.start_time} seconds total)')
        print("Logging into Discord...")

        token = self.internal_config.get("token", "")
        if not token:
            token = os.environ.get("TOKEN", "")

        token = token if token else kwargs.get("token", "")
        if not token:
            print("No token provided!")
            return

        self.internal_config = []
        try:
            self.run(token)
        except Exception as e:
            print(
                f"Something went wrong handling the token!\nThe error was {type(e).__name__}: {e}")  # overridden close cleans this up neatly

    def preload_cog(self, key: str, filename: str, base="cogs") -> list[bool, Exception]:
        loader = None
        cog_config = {}
        if type(filename) is str and type(key) is str:
            try:
                try:
                    cog_config_file = open(f"./{base.replace('.', '/')}/{key.replace('.', '/')}/config_{filename}.json")
                    cog_config = json.loads(cog_config_file.read())
                    loader = cog_config.get("loader", None)
                except Exception:
                    pass  # probably not found

                if type(loader) is str and os.path.abspath(f"{base}/{loader}").startswith(
                        os.path.abspath(f"./{base.replace('.', '/')}/{key.replace('.', '/')}")):  # restrict paths
                    try:
                        loader = os.path.relpath(loader)
                        loader = loader.replace(chr(92), "/").replace("/", ".")
                        while ".." in loader:
                            loader = loader.replace("..", ".")
                    except Exception:
                        pass
                else:
                    loader = filename
                final = f"{base}.{key}.{loader}"
                self.cog_list[final] = cog_config
                if final in self.core_cogs:
                    self.cog_list[final]["core"] = True
                else:
                    self.cog_list[final]["core"] = False
                return [True, None]
            except Exception as e:
                print(
                    f"\n\n\n[-]   {base}.{key}.{loader} could not be preloaded due to an error! See the error below for more details\n\n{type(e).__name__}: {e}\n\n\n")
                return [False, e]
        else:
            print(f"[X]    Ignoring {base}.{key} since it isn't text")
        return [False, None]

    def load_cog(self, name) -> list[bool, Exception]:
        e = None
        if name in self.cog_list:
            try:
                self.load_extension(name)
                print(f'\n[+]    {name}')
            except Exception as e:
                return [False, e]
        else:
            print(f"\n\n\n[-]   {name} ignored since it wasn't registered")
            return [False, None]
        return [True, None]

    def load_cogs(self):
        for name in self.cog_list:
            result = self.load_cog(name)
            if not result[0]:
                print(f"\n\n\n[-]   {name} could not be loaded due to an error! " + f"See the error below for more details\n\n{type(result[1]).__name__}: {result[1]}" if result[1] else "")
                if name in self.core_cogs:
                    print(f"Exiting since a core cog could not be loaded...")
                    exit()

    def preload_core_cogs(self) -> None:
        """
        Non-negotiable.
        """

        print("Loading core cogs...")

        for cog in self.core_cogs:
            temp = cog.split(".")
            self.preload_cog(".".join(temp[1:-1]), temp[-1], base=temp[0])

    def preload_cogs(self) -> None:
        """
        Procedure that loads all the cogs, from tree in config file
        """

        if "cogs" not in self.internal_config:
            print("[X]    No cogs loaded since none were specified.")
            return

        cog_list = pandas.json_normalize(self.internal_config["cogs"], sep=".").to_dict(orient="records")[
            0]  # flatten

        for key in cog_list:
            if type(cog_list[key]) is list:  # random validation checks yay
                for filename in cog_list[key]:
                    self.preload_cog(key, filename)
            else:
                print(
                    f"[X]    Ignoring flattened key cogs.{key} since it doesn't have a text list of filenames under <files> as required.")

    async def on_ready(self) -> None:
        await database_handle.create_tables_if_not_exists(self.pool)  # Makes tables if they do not exist
        self.login_time = time.time()
        print(f'Bot logged into Discord ({self.login_time - self.start_time} seconds total)')
        await self.change_presence(activity=discord.Game(name=f'in {len(self.guilds)} servers | Type `help` for help'),
                                   status=discord.Status.online)
        self.online = True

    async def on_command_error(self, ctx: commands.Context, error) -> None:
        if not hasattr(ctx.cog, "on_command_error"):  # don't re-raise if ext handling
            raise error  # re-raise error so cogs can mess around but not block every single error. Does duplicate traceback but error tracebacks are a bloody mess anyway

    def correct_time(self, conv_time: datetime.datetime | None = None,
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


intents = discord.Intents.default()
for intent in ["members", "presences", "reactions", "typing", "dm_messages", "guilds"]:
    intents.__setattr__(intent, True)

parser = argparse.ArgumentParser()
# todo: make this more customisable
parser.add_argument("-p", "--prefix", nargs="?", default=None)
parser.add_argument("-t", "--token", nargs="?", default=None)  # can change token on the fly/keep env clean
parser.add_argument("-c", "--connections", nargs="?",
                    default=10)  # DB pool max_size (how many concurrent connections the pool can have)
args = parser.parse_args()

bot = AdamBot(start_time, token=args.token, connections=args.connections, intents=intents,
              command_prefix=args.prefix)  # If the prefix given == None use the guild ones, otherwise use the given prefix
