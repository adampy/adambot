import discord
from discord import app_commands
from discord.ext import commands

from libs.misc.decorators import is_staff, is_staff_slash
from . import waitingroom_handlers


class WaitingRoom(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the waitingroom cog with a provided bot.

        Loads and initialises the WaitingroomHandlers class
        """

        self.bot = bot
        self.welcome_message = ""
        self.welcome_channel = None

        self.Handlers = waitingroom_handlers.WaitingroomHandlers(bot, self)

    lurker_slash = app_commands.Group(name="lurker", description="Manage the server's lurkers")

    @staticmethod
    async def get_parsed_welcome_message(welcome_msg: str, new_user: discord.Member | discord.User) -> str:
        """
        Method that gets the parsed welcome message, with channel and role mentions.
        """

        return welcome_msg.replace("<user>", new_user.mention)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        raw_msg = await self.bot.get_config_key(member, "welcome_msg")
        channel_id = await self.bot.get_config_key(member, "welcome_channel")

        if raw_msg and channel_id:
            message = await self.get_parsed_welcome_message(raw_msg, member)
            channel = self.bot.get_channel(channel_id)
            await channel.send(message)

    # -----WELCOME MESSAGE TEST-----

    @commands.command()
    @commands.guild_only()
    @is_staff()
    async def testwelcome(self, ctx: commands.Context, to_ping: discord.Member | discord.User = None) -> None:
        """
        Command that returns the welcome message, and pretends the command invoker is the new user.
        """

        await self.Handlers.testwelcome(ctx, to_ping)

    @app_commands.command(
        name="testwelcome",
        description="Test the welcome message"
    )
    @app_commands.describe(
        member="The member to test the welcome message on"
    )
    @is_staff_slash()
    async def testwelcome_slash(self, interaction: discord.Interaction,
                                member: discord.Member | discord.User = None) -> None:
        """
        Slash equivalent of the testwelcome command.
        """

        await self.Handlers.testwelcome(interaction, member)

    # -----LURKERS-----

    @commands.group(aliases=["lurker"])
    @is_staff()
    async def lurkers(self, ctx: commands.Context, *phrase: str) -> None:
        """
        Ping all the people without a role so you can grab their attention. Optional, first argument is `message` is the phrase you want to send to lurkers.
        """

        await self.Handlers.lurker(ctx, *phrase)

    @app_commands.command(
        name="lurkers",
        description="Ping all the people who have no role"
    )
    @app_commands.describe(
        phrase="The phrase to mention lurkers with"
    )
    @is_staff_slash()
    async def lurkers_slash(self, interaction: discord.Interaction, phrase: str) -> None:
        """
        Slash equivalent of the lurkers command.
        """

        await self.Handlers.lurker(interaction, phrase)

    @lurkers.command(name="kick")  # Name parameter defines the name of the command the user will use
    @commands.guild_only()
    @is_staff()
    async def lurker_kick(self, ctx: commands.Context, days: str = "7") -> None:
        # days is specifically "7" as default and not 7 since if you specify an integer it barfs if you supply a non-int value
        """
        Command that kicks people without a role, and joined 7 or more days ago.
        """

        await self.Handlers.lurker_kick(ctx, days)

    @lurker_slash.command(
        name="kick",
        description="Kick all the lurkers from the server that have been here more than a number of days"
    )
    @app_commands.describe(
        days="The number of days by which to kick a user"
    )
    @is_staff_slash()
    async def lurker_kick_slash(self, interaction: discord.Interaction, days: int = 7) -> None:
        """
        Slash equivalent of the lurkers kick command.
        """

        await self.Handlers.lurker_kick(interaction, days)


async def setup(bot) -> None:
    await bot.add_cog(WaitingRoom(bot))
