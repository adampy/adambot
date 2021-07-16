from discord.ext import commands
from enum import Enum
from .utils import DefaultEmbedResponses, EmbedPages, PageTypes
import copy

class Validation(Enum):
    Channel = 1     # Is a channel that the bot can read/write in
    Role = 2        # Is a valid role
    Integer = 3     # Is a valid integer
    String = 4      # String less than 2000 chars

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CONFIG = { # Stores each column of the config table, the type of validation it is, and a short description of how its used - the embed follows the same order as this
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

    # COMMANDS

    @commands.group()
    @commands.guild_only()
    async def config(self, ctx):
        """View the current configuration settings of the guild"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if ctx.invoked_subcommand is None: # User is staff and no subcommand => send embed
            # To get the config options
            # 1. Copy self.CONFIG into a new variable
            # 2. Foreach config option, append the option to the list under the specific option's key (this is the embed value)
            # 3. Pass the dict into EmbedPages for formatting
            data = copy.deepcopy(self.CONFIG)
            config_dict = self.bot.configs[ctx.guild.id]
            for key in config_dict.keys():
                if key not in data.keys():
                    continue # This clause ensures that variables, e.g. "bruhs", that are in the DB but not in self.CONFIG, do not appear
                
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
            embed = EmbedPages(
                PageTypes.CONFIG,
                data,
                f":tools:  {ctx.guild.name} ({ctx.guild.id}) configuration",
                ctx.author.colour,
                self.bot,
                ctx.author,
                ctx.channel,
                desc=desc,
                thumbnail_url = ctx.guild.icon_url,
                icon_url = ctx.author.avatar_url,
                footer = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format)
            )
            await embed.set_page(1) # Default first page
            await embed.send()

    @config.command(pass_context=True)
    @commands.guild_only()
    async def set(self, ctx, key = None, *, value = None):  # consume then you don't have to wrap phrases in quotes
        """Sets a configuration variable"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if not key:
            await DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", "You must specify a key to set!")
            return

        if not value:
            await DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", "You must specify a value to set the key to!")
            return


        key = key.lower()
        if key not in self.CONFIG.keys():
            await DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
            return

        validation_type = self.CONFIG[key][0]
        if validation_type == Validation.Role:
            try:
                role = await commands.RoleConverter().convert(ctx, value)
                value = role
            except commands.errors.RoleNotFound:
                await DefaultEmbedResponses.error_embed(self.bot, ctx, "That role cannot be found!")
                return
            
        elif validation_type == Validation.Channel:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, value)
                if not channel.permissions_for(ctx.guild.me).send_messages:
                    await DefaultEmbedResponses.error_embed(self.bot, ctx, "I do not have send message permissions in that channel!")
                    return
                value = channel
            except commands.errors.ChannelNotFound:
                await DefaultEmbedResponses.error_embed(self.bot, ctx, "That channel cannot be found!")
                return
            
        elif validation_type == Validation.Integer:
            if not value.isdigit():
                await DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", f"Please give me an integer")
                return
            value = int(value)
        
        elif validation_type == Validation.String:
            if len(value) >= 1000:
                await DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", f"The string provided needs to be less than 1000 characters")
                return

        # At this point, the input is valid and can be changed
        if validation_type == Validation.Channel or validation_type == Validation.Role:
            self.bot.configs[ctx.guild.id][key] = value.id
            await self.bot.propagate_config(ctx.guild.id)
            await DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!", f'It has been changed to "{value.mention}"') # Value is either a TextChannel or Role
        else:
            self.bot.configs[ctx.guild.id][key] = value
            await self.bot.propagate_config(ctx.guild.id)
            await DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!", f'It has been changed to "{value}"')

    @config.command(pass_context = True)
    @commands.guild_only()
    async def remove(self, ctx, key):
        """Removes a configuration variable"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        key = key.lower()
        if key not in self.CONFIG.keys():
            await DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
            return

        if key == "prefix":
            await DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!", "The prefix cannot be removed")
            return

        self.bot.configs[ctx.guild.id][key] = None
        await self.bot.propagate_config(ctx.guild.id)
        await DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!", f"It has been changed to ***N/A***")

    @config.command(pass_context = True)
    @commands.guild_only()
    async def current(self, ctx, key = None):
        """Shows the current configuration variable"""
        if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if not key:
            await ctx.invoke(self.bot.get_command("config"))
        else:

            config_dict = self.bot.configs[ctx.guild.id]
            key = key.lower()
            if key not in self.CONFIG.keys():
                await DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
                return

            if self.CONFIG[key][0] == Validation.Channel:
                current = ctx.guild.get_channel(config_dict[key])
                await DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",  current.mention if current else "***N/A***")
            elif self.CONFIG[key][0] == Validation.Role:
                current = ctx.guild.get_role(config_dict[key])
                await DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",  current.mention if current else "***N/A***")
            else:
                await DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",  config_dict[key] if config_dict[key] else "***N/A***")

    @commands.command(pass_context = True)
    @commands.guild_only()
    async def prefix(self, ctx, new_prefix = None):
        """View the current prefix or change it"""
        await self.bot.add_config(ctx.guild.id)
        if new_prefix is None:
            prefix = self.bot.configs[ctx.guild.id]["prefix"]
            await DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of prefix",  prefix)
        else:
            if not (ctx.author.guild_permissions.administrator or await self.bot.is_staff(ctx)):
                await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
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
