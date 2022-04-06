import discord
from discord import app_commands
from discord.ext import commands

from . import bot_handlers

from adambot import AdamBot


class BotCog(commands.Cog):
    def __init__(self, bot: AdamBot) -> None:
        """
        Sets up the bot cog with a provided bot.

        Loads and initialises the BotHandlers class
        """

        self.bot = bot
        self.Handlers = bot_handlers.BotHandlers(bot)

    @commands.command()
    @commands.guild_only()
    async def botinfo(self, ctx: commands.Context) -> None:
        """
        Displays information about the bot

        These include things like uptime, discord.py version, Python version, host OS etc.
        """

        await self.Handlers.botinfo(ctx)

    @app_commands.command(
        name="botinfo",
        description="Displays information about the bot"
    )
    async def botinfo_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command botinfo
        """

        await self.Handlers.botinfo(interaction)

    @commands.command()
    async def host(self, ctx: commands.Context) -> None:
        """
        Check if the bot is hosted locally or remotely
        """

        await self.Handlers.host(ctx)

    @app_commands.command(
        name="host",
        description="Find out if the bot is hosted locally or remotely"
    )
    async def host_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command host.
        """

        await self.Handlers.host(interaction)

    @commands.command()
    async def ping(self, ctx: commands.Context) -> None:
        """
        Get the bot's current latency
        """

        await self.Handlers.ping(ctx)

    @app_commands.command(
        name="ping",
        description="Find out the bot's current latency"
    )
    async def ping_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command ping.
        """

        await self.Handlers.ping(interaction)

    @commands.command()
    async def uptime(self, ctx: commands.Context) -> None:
        """
        View how long the bot has been running for
        """

        await self.Handlers.uptime(ctx)

    @app_commands.command(
        name="uptime",
        description="View how long the bot has been running for"
    )
    async def uptime_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command uptime.
        """

        await self.Handlers.uptime(interaction)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Changes the status to represent new server number on guild join
        """

        if guild.system_channel:
            await guild.system_channel.send(
                f"Hey there! To get started, do `{self.bot.global_prefix}help` or `{self.bot.global_prefix}config`.")
        await self.bot.change_presence(
            activity=discord.Game(name=f"in {len(self.bot.guilds)} servers | Type `help` for help"),
            status=discord.Status.online)  # TODO: Would it be more efficient to store len(self.guilds) inside adambot on init, then update that?

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """
        Changes the status to represent new server number on guild leave
        """

        await self.bot.change_presence(
            activity=discord.Game(name=f"in {len(self.bot.guilds)} servers | Type `help` for help"),
            status=discord.Status.online)


async def setup(bot: AdamBot) -> None:
    await bot.add_cog(BotCog(bot))
