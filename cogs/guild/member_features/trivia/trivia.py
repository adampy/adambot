from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from libs.misc.decorators import is_staff, is_staff_slash
from . import trivia_handlers


class Trivia(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the trivia cog with a provided bot.

        Loads and initialises the TriviaHandlers class
        """

        self.bot = bot
        self.Handlers = trivia_handlers.TriviaHandlers(bot)

    @commands.group()
    @commands.guild_only()
    async def trivia(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}trivia list```")

    trivia_slash = app_commands.Group(name="trivia", description="Start or manage trivia matches")

    @trivia.command()
    async def trivia_list(self, ctx: commands.Context) -> None:
        """
        View the list of currently available trivias.
        """

        await self.Handlers.trivia_list(ctx)

    @trivia_slash.command(
        name="list",
        description="List the available trivias on this server"
    )
    async def trivia_list_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command list.
        """

        await self.Handlers.trivia_list(interaction)

    @trivia.command()
    async def start(self, ctx: commands.Context, trivia: Optional[str] = None) -> None:
        """
        Command that starts a new trivia game in the currently set trivia channel
        """

        await self.Handlers.start(ctx, trivia)

    @trivia_slash.command(
        name="start",
        description="Start a trivia session"
    )
    @app_commands.describe(
        trivia="The name of the trivia to start"
    )
    async def start_slash(self, interaction: discord.Interaction, trivia: str) -> None:
        """
        Slash equivalent of the classic command start.
        """

        await self.Handlers.start(interaction, trivia)

    @trivia.command(aliases=["finish", "end"])
    async def stop(self, ctx: commands.Context) -> None:
        """
        Command that stops a current trivia game
        """

        await self.Handlers.stop(ctx)

    @trivia_slash.command(
        name="stop",
        description="Stop the current trivia session"
    )
    async def stop_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command stop.
        """

        await self.Handlers.stop(interaction)

    @trivia.command(aliases=["answers", "cheat"])
    @is_staff()
    async def answer(self, ctx: commands.Context) -> None:
        """
        Command that allows staff to see the correct answer
        """

        await self.Handlers.answer(ctx)

    @trivia_slash.command(
        name="answer",
        description="Find out the answer to the current question"
    )
    @is_staff_slash()
    async def answer_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command answer.
        """

        await self.Handlers.answer(interaction)

    @trivia.command()
    async def skip(self, ctx: commands.Context) -> None:
        """
        Command that skips a question - a point is given to the bot
        """

        await self.Handlers.skip(ctx)

    @trivia_slash.command(
        name="skip",
        description="Skip the current question"
    )
    async def skip_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command skip.
        """

        await self.Handlers.skip(interaction)

    @trivia.command(aliases=["lb"])
    async def leaderboard(self, ctx: commands.Context) -> None:
        """
        Command that shows the leaderboard for the current trivia game
        """

        await self.Handlers.leaderboard(ctx)

    @trivia_slash.command(
        name="leaderboard",
        description="Display the leaderboard for the current trivia game"
    )
    async def leaderboard_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command leaderboard.
        """

        await self.Handlers.leaderboard(interaction)


async def setup(bot) -> None:
    await bot.add_cog(Trivia(bot))
