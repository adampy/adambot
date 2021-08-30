import discord
from discord.ext.commands import Bot, when_mentioned_or, when_mentioned
import asyncpg
import time
import os
import pytz
import pandas
import json
import argparse
import libs.db.database_handle as database_handle  # not strictly a lib rn but hopefully will be in the future

start_time = time.time()


class AdamBot(Bot):

    async def determine_prefix(self, bot, message):
        """
        Procedure that determines the prefix for a guild. This determines the prefix when a global one is not being used
        'bot' is a required argument but also pointless since each AdamBot object isn't going to be trying to handle *other* AdamBot objects' prefixes
        """

        watch_prefixes = [self.configs.get(message.guild.id, {}).get("prefix", None) if message.guild else None, self.global_prefix]
        if watch_prefixes != [None] * len(watch_prefixes):
            return when_mentioned_or(*tuple([prefix for prefix in watch_prefixes if type(prefix) is str]))(self, message)  # internal conf prefix or guild conf prefix can be used
        else:
            # Config tables aren't loaded yet or internal config doesn't specify another prefix, temporarily set to mentions only
            return when_mentioned(self, message)

    async def get_used_prefixes(self, message):
        """
        Gets the prefixes that can be used to invoke a command in the guild where the message is from
        """

        guild_prefix = await self.get_config_key(message, "prefix")
        return [prefix for prefix in [self.user.mention, self.global_prefix if self.global_prefix else None, guild_prefix if guild_prefix else None] if type(prefix) is str]

    def __init__(self, start_time, config_path="config.json", command_prefix=None, *args, **kwargs):
        self.internal_config = self.load_internal_config(config_path)
        kwargs["command_prefix"] = self.determine_prefix if not command_prefix else when_mentioned_or(command_prefix)

        super().__init__(*args, **kwargs)
        self.load_core_cogs()

        self.global_prefix = self.internal_config.get("global_prefix", None)  # Stores the global prefix, or None if not set / using guild specific one

        self.connections = kwargs.get("connections", 10)  # Max DB pool connections
        self.online = False  # Start at False, changes to True once fully initialised
        self.LOCAL_HOST = False if os.environ.get("REMOTE", None) else True
        self.display_timezone = pytz.timezone('Europe/London')
        self.ts_format = '%A %d/%m/%Y %H:%M:%S'
        self.start_time = start_time
        self._init_time = time.time()
        print(f"BOT INITIALISED {self._init_time - start_time} seconds")
        self.start_up(kwargs)  # kwargs passed here specifically to prevent leak of sensitive stuff passed in

    async def close(self, ctx=None):  # ctx = None because this is also called upon CTRL+C in command line
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
    def load_internal_config(config_path):
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

    def start_up(self, kwargs):
        """
        Command that starts AdamBot, is run in AdamBot.__init__
        """

        print("Loading cogs...")
        self.load_cogs()
        self.cog_load = time.time()
        print(f"\nLoaded all cogs in {self.cog_load - self._init_time} seconds ({self.cog_load - self.start_time} seconds total)")
        print("Creating DB pool...")
        db_url = os.environ.get('DATABASE_URL') if not type(self.internal_config.get("database_url", None)) is str else \
            self.internal_config["database_url"]

        self.pool:\
            asyncpg.pool.Pool = self.loop.run_until_complete(asyncpg.create_pool(db_url + "?sslmode=require", max_size=self.connections))

        # Moved to here as it makes more sense to not load everything then tell the user they did an oopsies
        print(f'Bot fully setup!\nDB took {time.time() - self.cog_load} seconds to connect to ({time.time() - self.start_time} seconds total)')
        print("Logging into Discord...")
        token = os.environ.get('TOKEN', None) if not type(self.internal_config.get('token', None)) is str else \
            self.internal_config['token']

        token = token if token else kwargs.get("token", None)
        if not token:
            print("No token provided!")
            return

        self.internal_config = []
        try:
            self.run(token)
        except Exception as e:
            print(f"Something went wrong handling the token!\nThe error was {type(e).__name__}: {e}")  # overridden close cleans this up neatly

    def load_core_cogs(self):
        """
        Non-negotiable.
        """

        print("Loading core cogs...")

        cogs = [
            "core.config.config",
            "core.tasks.tasks",
            "libs.misc.temp_utils_cog"
            # as the name suggests, this is temporary, will be moved/split up at some point, just not right now
        ]

        for cog in cogs:
            try:
                self.load_extension(cog)
                print(f'\n[+]    {cog}')
            except Exception as e:
                print(
                    f"\n\n\n[-]   {cog} could not be loaded due to an error! See the error below for more details\n\n{type(e).__name__}: {e}\n\n\n")
                exit()

    def load_cogs(self):
        """
        Procedure that loads all the cogs, from tree in config file
        """

        if "cogs" not in self.internal_config:
            print("[X]    No cogs loaded since none were specified.")
            return

        cog_config = pandas.json_normalize(self.internal_config["cogs"], sep=".").to_dict(orient="records")[0]  # flatten
        for key in cog_config:
            if type(cog_config[key]) is list:  # random validation checks yay
                for filename in cog_config[key]:
                    if type(filename) is str:
                        try:
                            self.load_extension(f"cogs.{key}.{filename}")
                            print(f'\n[+]    {f"cogs.{key}.{filename}"}')
                        except Exception as e:
                            print(f"\n\n\n[-]   cogs.{key}.{filename} could not be loaded due to an error! See the error below for more details\n\n{type(e).__name__}: {e}\n\n\n")
                    else:
                        print(f"[X]    Ignoring cogs.{key}[{filename}] since it isn't text")
            else:
                print(f"[X]    Ignoring flattened key cogs.{key} since it doesn't have a text list of filenames under <files> as required.")

    async def on_ready(self):
        await database_handle.create_tables_if_not_exists(self.pool)  # Makes tables if they do not exist
        self.login_time = time.time()
        print(f'Bot logged into Discord ({self.login_time - self.start_time} seconds total)')
        await self.change_presence(activity=discord.Game(name=f'In {len(self.guilds)} servers | Type `help` for help'), status=discord.Status.online)
        self.online = True

    async def on_command_error(self, ctx, error):
        if not hasattr(ctx.cog, "on_command_error"):  # don't re-raise if ext handling
            raise error  # re-raise error so cogs can mess around but not block every single error. Does duplicate traceback but error tracebacks are a bloody mess anyway


intents = discord.Intents.default()
for intent in ["members", "presences", "reactions", "typing", "dm_messages", "guilds"]:
    intents.__setattr__(intent, True)

parser = argparse.ArgumentParser()
# todo: make this more customisable
parser.add_argument("-p", "--prefix", nargs="?", default=None)
parser.add_argument("-t", "--token", nargs="?", default=None)  # can change token on the fly/keep env clean
parser.add_argument("-c", "--connections", nargs="?", default=10)  # DB pool max_size (how many concurrent connections the pool can have)
args = parser.parse_args()

bot = AdamBot(start_time, token=args.token, connections=args.connections, intents=intents,
              command_prefix=args.prefix)  # If the prefix given == None use the guild ones, otherwise use the given prefix
