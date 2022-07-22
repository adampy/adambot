import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from . import config_handlers


class Config(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the config cog with a provided bot.

        Loads and initialises the ConfigHandlers class
        """

        self.bot = bot
        self.Handlers = config_handlers.ConfigHandlers(bot, self)
        self.bot.configs = {}
        self.bot.config_cog = self
        self.bot.update_config = self.Handlers.update_config
        self.bot.register_config_key = self.Handlers.register_config_key
        self.bot.is_staff = self.Handlers.is_staff  # is_staff defined here
        self.bot.get_config_key = self.Handlers.get_config_key
        self.CONFIG = {
            # Stores each column of the config table, the type of validation it is, and a short description of how its used - the embed follows the same order as this
            "staff_role": [self.Handlers.Validation.Role, "The role that designates bot perms"],  # CORE
            "log_channel": [self.Handlers.Validation.Channel, "Where the main logs go"],  # CORE
            "prefix": [self.Handlers.Validation.String, "The prefix the bot uses for this guild"],  # CORE
        }

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        while not self.bot.online:
            await asyncio.sleep(1)  # Wait else DB won't be available

        await self.Handlers.add_all_guild_configs()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Adds configs to a certain guild - executed upon joining a new guild
        """

        await self.Handlers.add_config(guild.id)

        # General configuration workflow:
        # 1) Make any edits directly to bot.configs[guild.id]
        # 2) Call bot.propagate_config(guild.id) which propagates any edits to the DB

    # COMMANDS
    @commands.command()
    @commands.guild_only()
    async def what_prefixes(self, ctx: commands.Context) -> None:
        """
        A command which sends a list of prefixes that the bot is listening to.
        """

        await self.Handlers.what_prefixes(ctx)

    @app_commands.command(
        name="what_prefixes",
        description="Get the prefixes that the bot is currently listening to"
    )
    async def what_prefixes_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command what_prefixes
        """

        await self.Handlers.what_prefixes(interaction)

    config_slash = app_commands.Group(name="config", description="View and manage the server config")

    @commands.group()
    @commands.guild_only()
    async def config(self, ctx: commands.Context) -> None:
        """
        View the current configuration settings of the guild
        """

        if ctx.invoked_subcommand is None:  # User is staff and no subcommand => send embed

            await self.Handlers.view(ctx)

    @config_slash.command(
        name="view",
        description="View the server's configuration"
    )
    async def view_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash adaptation of the classic command group definition config
        """

        if not (interaction.user.guild_permissions.administrator or await self.Handlers.is_staff(interaction)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, interaction)
            return

        await self.Handlers.view(interaction)

    @config.command()
    @commands.guild_only()
    async def set(self, ctx: commands.Context, key: str = "", *,
                  value: str = "") -> None:  # consume then you don't have to wrap phrases in quotes
        """
        Sets a configuration variable
        """

        await self.Handlers.set(ctx, key=key, value=value)

    @config_slash.command(
        name="set",
        description="Set a configuration variable for this server"
    )
    @app_commands.describe(
        key="The config key to set",
        value="The value to set the config key to"
    )
    async def set_slash(self, interaction: discord.Interaction, key: str, value: str) -> None:
        """
        Slash equivalent of the classic command set.
        """

        await self.Handlers.set(interaction, key=key, value=value)

    @config.command()
    @commands.guild_only()
    async def remove(self, ctx: commands.Context, key: str) -> None:
        """
        Removes a configuration variable
        """

        await self.Handlers.remove(ctx, key)

    @config_slash.command(
        name="remove",
        description="Remove the value stored for a configuration variable for this server"
    )
    @app_commands.describe(
        key="The name of the config key to remove the value of"
    )
    async def remove_slash(self, interaction: discord.Interaction, key: str) -> None:
        """
        Slash equivalent of the classic command remove.
        """

        await self.Handlers.remove(interaction, key)

    @config.command()
    @commands.guild_only()
    async def current(self, ctx: commands.Context, key: str = "") -> None:
        """
        Shows the current configuration variable
        """

        await self.Handlers.current(ctx, key)

    @config_slash.command(
        name="current",
        description="Get the current value of a configuration variable for this server"
    )
    @app_commands.describe(
        key="The name of the key to get the current value of"
    )
    async def current_slash(self, interaction: discord.Interaction, key: str) -> None:
        """
        Slash equivalent of the classic command current.
        """

        await self.Handlers.current(interaction, key)

    @commands.command()
    @commands.guild_only()
    async def prefix(self, ctx: commands.Context, new_prefix: str = "") -> None:
        """
        Change the current prefix
        """

        await self.Handlers.prefix(ctx, new_prefix=new_prefix)

    @app_commands.command(
        name="prefix",
        description="Set the server-specific prefix"
    )
    @app_commands.describe(
        new_prefix="The new prefix to set for this server"
    )
    async def prefix_slash(self, interaction: discord.Interaction, new_prefix: str) -> None:
        """
        Slash equivalent of the classic command prefix.
        """

        await self.Handlers.prefix(interaction, new_prefix=new_prefix)

    @commands.command()
    @commands.guild_only()
    async def staffcmd(self, ctx: commands.Context) -> None:
        """
        Tests whether the staff role is set up correctly
        """

        await self.Handlers.staffcmd(ctx)

    @app_commands.command(
        name="staffcmd",
        description="Test whether or not you are correctly detected as staff"
    )
    async def staffcmd_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command staffcmd.
        """

        await self.Handlers.staffcmd(interaction)


async def setup(bot) -> None:
    await bot.add_cog(Config(bot))
