from discord.ext import commands
from enum import Enum
import copy
import asyncpg
import asyncio


class Validation(Enum):
    Channel = 1     # Is a channel that the bot can read/write in
    Role = 2        # Is a valid role
    Integer = 3     # Is a valid integer
    String = 4      # String less than 2000 chars


class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.configs = {}
        self.CONFIG = {  # Stores each column of the config table, the type of validation it is, and a short description of how its used - the embed follows the same order as this
            "welcome_channel": [Validation.Channel, "Where the welcome message is sent"],
            "welcome_msg": [Validation.String, "What is sent when someone new joins (<user> tags the new user)"],
            "support_log_channel": [Validation.Channel, "Where the logs from the support module go"],
            "staff_role": [Validation.Role, "The role that designates bot perms"],
            "qotd_role": [Validation.Role, "The role that designates QOTD perms (show, pick, delete)"],
            "qotd_limit": [Validation.Integer, "How many QOTDs people can submit per day"],
            "qotd_channel": [Validation.Channel, "Where the QOTDs are displayed when picked"],
            "muted_role": [Validation.Role, "The role that prevents someone from talking"],
            "mod_log_channel": [Validation.Channel, "Where the main logs go"],
            "invite_log_channel": [Validation.Channel, "Where invites are logged"],
            "prefix": [Validation.String, "The prefix the bot uses, default is '-'"],
            "rep_award_banned": [Validation.Role, "The role that blocks people giving reputation"],
            "rep_receive_banned": [Validation.Role, "The role that blocks people receiving reputation"],
            "jail_role": [Validation.Role, "The role that puts people into jail"],
            "trivia_channel": [Validation.Channel, "Where trivias get played"]
        }

    async def add_all_guild_configs(self):
        """Adds configs to all guilds - executed on startup"""
        for guild in self.bot.guilds:
            await self.add_config(guild.id)

    async def is_staff(self, ctx):
        """
        Method that checks if a user is staff in their guild or not. `ctx` may be `discord.Message` or `discord.ext.commands.Context`
        """
        try:
            staff_role_id = self.bot.configs[ctx.guild.id]["staff_role"]
            return staff_role_id in [y.id for y in ctx.author.roles]
        except Exception:  # usually ends up being a KeyError. would be neater if all that's relevant can be caught instead
            return False  # prevents daft spam before bot is ready with configs

    @commands.Cog.listener()
    async def on_ready(self):
        while not self.bot.online:
            await asyncio.sleep(1)  # Wait else DB won't be available

        await self.add_all_guild_configs()
        self.bot.update_config = self.update_config
        self.bot.get_config_key = self.get_config_key
        self.bot.is_staff = self.is_staff

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """
        Adds configs to a certain guild - executed upon joining a new guild
        """

        await self.add_config(guild.id)

        # General configuration workflow:
        # 1) Make any edits directly to bot.configs[guild.id]
        # 2) Call bot.propagate_config(guild.id) which propagates any edits to the DB

    async def add_config(self, guild_id):
        """
        Method that gets the configuraton for a guild and puts it into self.bot.configs dictionary (with the guild ID as the key). The data
        is stored in the `config` table. If no configuration is found, a new record is made and a blank configuration dict.
        """

        if guild_id not in self.bot.configs:  # This check (to see if a DB call is needed) is okay because any updates made will be directly made to self.bot.configs (before DB propagation) TODO: Perhaps limit number of items in this
            async with self.bot.pool.acquire() as connection:
                record = await connection.fetchrow("SELECT * FROM config WHERE guild_id = $1;", guild_id)
                if not record:
                    try:
                        await connection.execute("INSERT INTO config (guild_id) VALUES ($1);", guild_id)
                    except asyncpg.exceptions.UniqueViolationError:  # config already exists
                        pass
                    finally:
                        record = await connection.fetchrow("SELECT * FROM config WHERE guild_id = $1;",
                                                           guild_id)  # Fetch configuration record

            keys = list(record.keys())[1:]
            values = list(record.values())[1:]  # Include all keys and values apart from the first one (guild_id)
            self.bot.configs[guild_id] = dict(
                zip(keys, values))  # Turns the record into a dictionary (column name = key, value = value)

    async def update_config(self, ctx, key, value):
        if ctx.guild.id in self.bot.configs:
            self.bot.configs[ctx.guild.id][key] = value
            await self.propagate_config(ctx.guild.id)

    async def get_config_key(self, ctx, key):
        return self.bot.configs.get(ctx.guild.id, {}).get(key, None)

    async def propagate_config(self, guild_id):
        """
        Method that sends the config data stored in self.bot.configs and propagates them to the DB.
        Should only be called internally ideally.
        """

        data = self.bot.configs[guild_id]
        length = len(data.keys())

        # Make SQL
        sql_part = ""
        keys = list(data)  # List of the keys (current column names in the database)
        for i in range(length):
            sql_part += f"{keys[i]} = (${i + 1})"  # For each key, add "{nth key_name} = $n+1"
            if i != length - 1:
                sql_part += ", "  # If not the last element, add a ", "

        sql = f"UPDATE config SET {sql_part} WHERE guild_id = {guild_id};"
        async with self.bot.pool.acquire() as connection:
            await connection.execute(sql, *data.values())

    # COMMANDS
    @commands.command()
    @commands.guild_only()
    async def what_prefixes(self, ctx):
        await ctx.send(await self.bot.get_used_prefixes(ctx))

    @commands.group()
    @commands.guild_only()
    async def config(self, ctx):
        """
        View the current configuration settings of the guild
        """

        if not (ctx.author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if ctx.invoked_subcommand is None:  # User is staff and no subcommand => send embed
            """
             To get the config options
             1. Copy self.CONFIG into a new variable
             2. Foreach config option, append the option to the list under the specific option's key (this is the embed value)
             3. Pass the dict into EmbedPages for formatting
            """

            data = copy.deepcopy(self.CONFIG)
            config_dict = self.bot.configs[ctx.guild.id]
            for key in config_dict.keys():
                if key not in data.keys():
                    continue  # This clause ensures that variables, e.g. "bruhs", that are in the DB but not in self.CONFIG, do not appear
                
                if data[key][0] == Validation.Channel:
                    channel = ctx.guild.get_channel(config_dict[key])
                    data[key].append(f"{channel.mention} ({config_dict[key]})" if channel else "*N/A*")

                elif data[key][0] == Validation.Role:
                    role = ctx.guild.get_role(config_dict[key])
                    data[key].append(f"{role.mention} ({config_dict[key]})" if role else "*N/A*")
                
                else:
                    data[key].append(config_dict[key] if config_dict[key] else "*N/A*")
            
            p = config_dict["prefix"]
            desc = f"Below are the configurable options for {ctx.guild.name}. To change one, do `{p}config set <key> <value>` where <key> is the option you'd like to change, e.g. `{p}config set qotd_limit 2`"
            embed = self.bot.EmbedPages(
                self.bot.PageTypes.CONFIG,
                data,
                f":tools:  {ctx.guild.name} ({ctx.guild.id}) configuration",
                ctx.author.colour,
                self.bot,
                ctx.author,
                ctx.channel,
                desc=desc,
                thumbnail_url=ctx.guild.icon_url,
                icon_url=ctx.author.avatar_url,
                footer=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format)
            )
            await embed.set_page(1)  # Default first page
            await embed.send()

    @config.command(pass_context=True)
    @commands.guild_only()
    async def set(self, ctx, key=None, *, value=None):  # consume then you don't have to wrap phrases in quotes
        """
        Sets a configuration variable
        """

        if not (ctx.author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if not key:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", "You must specify a key to set!")
            return

        if not value:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", "You must specify a value to set the key to!")
            return

        key = key.lower()
        if key not in self.CONFIG.keys():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
            return

        validation_type = self.CONFIG[key][0]
        if validation_type == Validation.Role:
            try:
                role = await commands.RoleConverter().convert(ctx, value)
                value = role
            except commands.errors.RoleNotFound:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That role cannot be found!")
                return
            
        elif validation_type == Validation.Channel:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, value)
                if not channel.permissions_for(ctx.guild.me).send_messages:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "I do not have send message permissions in that channel!")
                    return
                value = channel
            except commands.errors.ChannelNotFound:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That channel cannot be found!")
                return
            
        elif validation_type == Validation.Integer:
            if not value.isdigit():
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", f"Please give me an integer")
                return
            value = int(value)
        
        elif validation_type == Validation.String:
            if len(value) >= 1000:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", f"The string provided needs to be less than 1000 characters")
                return

        # At this point, the input is valid and can be changed
        if validation_type == Validation.Channel or validation_type == Validation.Role:
            self.bot.configs[ctx.guild.id][key] = value.id
            await self.propagate_config(ctx.guild.id)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!", f'It has been changed to "{value.mention}"')  # Value is either a TextChannel or Role
        else:
            self.bot.configs[ctx.guild.id][key] = value
            await self.propagate_config(ctx.guild.id)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!", f'It has been changed to "{value}"')

    @config.command(pass_context=True)
    @commands.guild_only()
    async def remove(self, ctx, key):
        """
        Removes a configuration variable
        """

        if not (ctx.author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        key = key.lower()
        if key not in self.CONFIG.keys():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
            return

        if key == "prefix":
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", "The prefix cannot be removed")
            return

        self.bot.configs[ctx.guild.id][key] = None
        await self.propagate_config(ctx.guild.id)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!", f"It has been changed to ***N/A***")

    @config.command(pass_context=True)
    @commands.guild_only()
    async def current(self, ctx, key=None):
        """
        Shows the current configuration variable
        """

        if not (ctx.author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if not key:
            await ctx.invoke(self.bot.get_command("config"))
        else:

            config_dict = self.bot.configs[ctx.guild.id]
            key = key.lower()
            if key not in self.CONFIG.keys():
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
                return

            if self.CONFIG[key][0] == Validation.Channel:
                current = ctx.guild.get_channel(config_dict[key])
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",  current.mention if current else "***N/A***")
            elif self.CONFIG[key][0] == Validation.Role:
                current = ctx.guild.get_role(config_dict[key])
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",  current.mention if current else "***N/A***")
            else:
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",  config_dict[key] if config_dict[key] else "***N/A***")

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def prefix(self, ctx, new_prefix=None):
        """
        View the current prefix or change it
        """

        await self.add_config(ctx.guild.id)

        if new_prefix is None:
            prefix = self.bot.configs[ctx.guild.id]["prefix"]
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of prefix",  prefix)
        else:
            if not (ctx.author.guild_permissions.administrator or await self.is_staff(ctx)):
                await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            else:
                await ctx.invoke(self.bot.get_command("config set"), "prefix", new_prefix)

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def staffcmd(self, ctx):
        """
        Tests whether the staff role is set up correctly
        """

        if await self.is_staff(ctx):  # can just use self ref
            await ctx.send("Hello staff member!")
        else:
            await ctx.send("You are not staff!")


def setup(bot):
    bot.add_cog(Config(bot))
