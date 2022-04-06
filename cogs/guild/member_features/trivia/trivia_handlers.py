import discord
from discord.ext import commands

from .trivia_session import TRIVIAS, TriviaSession


from adambot import AdamBot


class TriviaHandlers:
    def __init__(self, bot: AdamBot):
        self.bot = bot
        self.trivia_sessions = {}

    async def trivia_list(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the list commands.
        """

        desc = ""
        for trivia in TRIVIAS:
            desc += "• " + trivia + ("" if trivia == TRIVIAS[-1] else "\n")
        await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Available trivias", desc=desc)

    async def start(self, ctx: commands.Context | discord.Interaction, trivia: str) -> None:
        """
        Handler for the start commands.
        """

        trivia_channel_id = await self.bot.get_config_key(ctx, "trivia_channel")
        session = self.trivia_sessions.get(ctx.guild.id, None)
        if session and session.running:  # TriviaSession.stop() cannot remove from this dict, only change self.running, so we only need to check that
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Trivia game already happening",
                                                                   desc="Please wait until the current trivia is over before starting a new one")
            return

        if trivia_channel_id is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                             f"{ctx.guild.name} does not have a trivia channel set!")
            return

        if trivia is None or trivia not in TRIVIAS:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                             f"You must choose a trivia from `{ctx.prefix}trivia list`",
                                                             desc="(Trivia names are case-sensitive)")
            return

        trivia_channel = self.bot.get_channel(trivia_channel_id)
        session = TriviaSession(self.bot, trivia_channel, trivia)
        self.trivia_sessions[ctx.guild.id] = session
        await session.start_trivia()

    async def stop(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the stop commands.
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return
        await session.stop(ctx.author)
        del self.trivia_sessions[ctx.guild.id]  # Delete it from dict, and memory

    async def answer(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the answer commands.
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return

        desc = ""
        for ans in session.answers:
            desc += "• " + ans + ("" if ans == session.answers[-1] else "\n")
        await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Answers to: '{session.question}'",
                                                               desc=desc)

    async def skip(self, ctx: commands.Context | discord.Interaction):
        """
        Handler for the skip commands.
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return
        session.increment_score(self.bot.user)
        await session.ask_next_question()

    async def leaderboard(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the leaderboard commands.
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return
        await session.trivia_end_leaderboard(reset=False)
