import discord
from discord import app_commands
from discord.ext import commands

from libs.misc.decorators import is_staff, is_staff_slash
from . import support_handlers
from .support_connection_manager import SupportConnectionManager


class Support(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the support cog with a provided bot.

        Loads and initialises an instance of the SupportConnectionManager class
        Loads and initialises the SupportHandlers class
        """

        self.bot = bot
        self.support_manager = SupportConnectionManager(self.bot)
        self.Handlers = support_handlers.SupportHandlers(bot, self)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.bot.loop.create_task(self.support_manager.refresh_connections())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Listens for DMs to start or participate in a ticket.
        """

        await self.Handlers.on_message(message)

    @commands.Cog.listener()
    async def on_typing(self, channel: discord.DMChannel | discord.TextChannel | discord.Thread, user: discord.User,
                        *args) -> None:
        """
        A handle for typing events between DMs, so that the typing presence can go through the DMs via the bot.
        """

        await self.Handlers.on_typing(channel, user)

    @commands.group()
    async def support(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(
                f"```{ctx.prefix}help support``` for more commands. If you want to open a ticket type ```{ctx.prefix}support start```")

    support_slash = app_commands.Group(name="support", description="View and manage the server's support connections")

    @support.command()
    @commands.guild_only()
    @is_staff()
    async def accept(self, ctx: commands.Context, ticket: str) -> None:
        """
        Accepts a support ticket.

        Staff role required.
        """

        await self.Handlers.accept(ctx, ticket)

    @support_slash.command(
        name="accept",
        description="Accept a given support ticket"
    )
    @app_commands.describe(
        ticket="The ID of the ticket to accept"
    )
    @is_staff_slash()
    async def accept_slash(self, interaction: discord.Interaction, ticket: int) -> None:
        """
        Slash equivalent of the classic command accept.
        """

        await self.Handlers.accept(interaction, ticket)

    @support.command()
    @commands.guild_only()
    @is_staff()
    async def connections(self, ctx: commands.Context) -> None:
        """
        Shows all current support connections with member info redacted
        """

        await self.Handlers.connections(ctx)

    @support_slash.command(
        name="connections",
        description="View the ongoing support connections in this server"
    )
    @is_staff_slash()
    async def connections_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command connections.
        """

        await self.Handlers.connections(interaction)


async def setup(bot) -> None:
    await bot.add_cog(Support(bot))
