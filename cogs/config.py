from discord.ext import commands
from discord import Embed, Colour
from enum import Enum
from asyncpg.exceptions import UniqueViolationError

ERROR_RED = Colour.from_rgb(255,7,58)
SUCCESS_GREEN = Colour.from_rgb(57, 255, 20)
INFORMATION_BLUE = Colour.from_rgb(32, 141, 177)

class Validation(Enum):
    Channel = 1     # Is a channel that the bot can read/write in
    Role = 2        # Is a valid role
    Integer = 3     # Is a valid integer
    String = 4      # String less than 2000 chars

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CONFIG = { # Stores each column of the config table, the type of validation it is, and a short description of how its used
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
            "prefix": [Validation.String, f"The prefix the bot uses, default is '-'"]
        }

    # EMBED RESPONSES

    async def _invalid_config(self, ctx):
        """Internal procedure that is executed when an invalid config option is produced"""
        embed = Embed(title = f':x: That is not a valid configuration option!', color = ERROR_RED)
        embed.set_footer(text = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url = ctx.author.avatar_url)
        await ctx.send(embed = embed)

    async def _invalid_perms(self, ctx):
        """Internal procedure that is executed when a user has invalid perms"""
        embed = Embed(title = f':x: You do not have permissions to do that!', description = "You are but a weakling.", color = ERROR_RED)
        embed.set_footer(text = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url = ctx.author.avatar_url)
        await ctx.send(embed = embed)

    async def _error_embed(self, ctx, title, desc = ""):
        embed = Embed(title = f':x: {title}', description = desc, color = ERROR_RED)
        embed.set_footer(text = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url = ctx.author.avatar_url)
        await ctx.send(embed = embed)

    async def _success_embed(self, ctx, title, desc = ""):
        embed = Embed(title = f':white_check_mark: {title}', description = desc, color = SUCCESS_GREEN)
        embed.set_footer(text = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url = ctx.author.avatar_url)
        await ctx.send(embed = embed)

    async def _information_embed(self, ctx, title, desc = ""):
        embed = Embed(title = f':information_source: {title}', description = desc, color = INFORMATION_BLUE)
        embed.set_footer(text = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url = ctx.author.avatar_url)
        await ctx.send(embed = embed)

    # INTERNAL CONFIG
    
    async def _add_guild_to_config(self, guild_id):
        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute("INSERT INTO config (guild_id) VALUES ($1);", guild_id)
            except UniqueViolationError: # config already exists
                pass

    # LISTENERS

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Listener that adds a guild when it first joins it"""
        await self._add_guild_to_config(guild.id)

    @commands.Cog.listener()
    async def on_ready(self):
        """Listener that adds all guilds when the bot starts - incase the bot was added to any guilds whilst offline"""
        while True:
            async with self.bot.pool.acquire() as connection:
                exists = await connection.fetchval("""SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE  table_name   = 'config'
                );""")

                if exists:
                    for guild in self.bot.guilds:
                        await self._add_guild_to_config(guild.id)
                    break

    # COMMANDS

    @commands.group()
    @commands.guild_only()
    async def config(self, ctx):
        """View the current configuration settings of the guild"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await self._invalid_perms(ctx)
            return

        if ctx.invoked_subcommand is None:
            # User is staff and no subcommand => send embed

            p = self.bot.configs[ctx.guild.id]["prefix"]
            embed = Embed(
                title = f":tools:  {ctx.guild.name} ({ctx.guild.id}) configuration",
                color = ctx.author.color, 
                description = f"Below are the configurable options for {ctx.guild.name}. To change one, do `{p}config set <key> <value>` where <key> is the option you'd like to change, e.g. `{p}config set qotd_limit 2`."
            ) # TODO: Make bot colours global - e.g. in a config json

            config_dict = self.bot.configs[ctx.guild.id]
            for key in config_dict.keys():
                name = f"{str(key)} ({self.CONFIG[key][1]})"

                if self.CONFIG[key][0] == Validation.Channel:
                    channel = ctx.guild.get_channel(config_dict[key])
                    if channel:
                        embed.add_field(name = name, value = f"{channel.mention} ({config_dict[key]})", inline = False)
                    else:
                        embed.add_field(name = name, value = "*N/A*", inline = False)

                elif self.CONFIG[key][0] == Validation.Role:
                    role = ctx.guild.get_role(config_dict[key])
                    if role:
                        embed.add_field(name = name, value = f"{role.mention} ({config_dict[key]})", inline = False)
                    else:
                        embed.add_field(name = name, value = "*N/A*", inline = False)
                else:
                    embed.add_field(name = name, value = config_dict[key] if config_dict[key] else "*N/A*", inline = False)

            embed.set_thumbnail(url = ctx.guild.icon_url)
            embed.set_footer(text = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url = ctx.author.avatar_url)
            await ctx.send(embed = embed)

    @config.command(pass_context=True)
    @commands.guild_only()
    async def set(self, ctx, key=None, *, value=None):  # consume then you don't have to wrap phrases in quotes
        """Sets a configuration variable"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await self._invalid_perms(ctx)
            return

        if not key:
            await self._error_embed(ctx, "Validation error!", "You must specify a key to set!")
            return

        if not value:
            await self._error_embed(ctx, "Validation error!", "You must specify a value to set the key to!")
            return


        key = key.lower()
        if key not in self.CONFIG.keys():
            await self._invalid_config(ctx)
            return

        validation_type = self.CONFIG[key][0]
        if validation_type == Validation.Role:
            try:
                role = await commands.RoleConverter().convert(ctx, value)
                value = role
            except commands.errors.RoleNotFound:
                await self._error_embed(ctx, "That role cannot be found!")
                return
            
        elif validation_type == Validation.Channel:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, value)
                if not channel.permissions_for(ctx.guild.me).send_messages:
                    await self._error_embed(ctx, "I do not have send message permissions in that channel!")
                    return
                value = channel
            except commands.errors.ChannelNotFound:
                await self._error_embed(ctx, "That channel cannot be found!")
                return
            
        elif validation_type == Validation.Integer:
            if not value.isdigit():
                await self._error_embed(ctx, "Validation error!", f"Please give me an integer")
                return
            value = int(value)
        
        elif validation_type == Validation.String:
            if len(value) >= 1000:
                await self._error_embed(ctx, "Validation error!", f"The string provided needs to be less than 1000 characters")
                return

        # At this point, the input is valid and can be changed
        if validation_type == Validation.Channel or validation_type == Validation.Role:
            self.bot.configs[ctx.guild.id][key] = value.id
            await self.bot.propagate_config(ctx.guild.id)
            await self._success_embed(ctx, f"{key} has been updated!", f"It has been changed to {value.mention}") # Value is either a TextChannel or Role
        else:
            self.bot.configs[ctx.guild.id][key] = value
            await self.bot.propagate_config(ctx.guild.id)
            await self._success_embed(ctx, f"{key} has been updated!", f"It has been changed to **{value}**")

    @config.command(pass_context = True)
    @commands.guild_only()
    async def remove(self, ctx, key):
        """Removes a configuration variable"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await self._invalid_perms(ctx)
            return


        config_dict = self.bot.configs[ctx.guild.id]
        key = key.lower()
        if key not in self.CONFIG.keys():
            await self._invalid_config(ctx)
            return

        if key == "prefix":
            await self._error_embed(ctx, "Validation error!", "The prefix cannot be removed")
            return

        self.bot.configs[ctx.guild.id][key] = None
        await self.bot.propagate_config(ctx.guild.id)
        await self._success_embed(ctx, f"{key} has been updated!", f"It has been changed to ***N/A***")

    @config.command(pass_context = True)
    @commands.guild_only()
    async def current(self, ctx, key = None):
        """Shows the current configuration variable"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await self._invalid_perms(ctx)
            return

        if not key:
            await ctx.invoke(self.bot.get_command("config"))
        else:

            config_dict = self.bot.configs[ctx.guild.id]
            key = key.lower()
            if key not in self.CONFIG.keys():
                await self._invalid_config(ctx)
                return

            if self.CONFIG[key][0] == Validation.Channel:
                current = ctx.guild.get_channel(config_dict[key])
                await self._information_embed(ctx, f"Current value of {key}",  current.mention if current else "***N/A***")
            elif self.CONFIG[key][0] == Validation.Role:
                current = ctx.guild.get_role(config_dict[key])
                await self._information_embed(ctx, f"Current value of {key}",  current.mention if current else "***N/A***")
            else:
                await self._information_embed(ctx, f"Current value of {key}",  config_dict[key] if config_dict[key] else "***N/A***")

    @commands.command(pass_context = True)
    @commands.guild_only()
    async def prefix(self, ctx, new_prefix = None):
        """View the current prefix or change it"""
        await self.bot.add_config(ctx.guild.id)
        if new_prefix is None:
            prefix = self.bot.configs[ctx.guild.id]["prefix"]
            await self._information_embed(ctx, f"Current value of prefix",  prefix)
        else:
            if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
                await self._invalid_perms(ctx)
            else:
                await ctx.invoke(self.bot.get_command("config set"), "prefix", new_prefix)

    @commands.command(pass_context = True)
    @commands.guild_only()
    async def staffcmd(self, ctx):
        """Tests whether the staff role is set up correctly"""
        if await self.bot.is_staff(ctx):
            await ctx.send("Hello staff member!")
        else:
            await ctx.send("You are not staff!")

def setup(bot):
    bot.add_cog(Config(bot))
