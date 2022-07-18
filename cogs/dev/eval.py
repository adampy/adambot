import discord
from discord import app_commands
from discord.ext import commands

from adambot import AdamBot
from libs.misc.decorators import is_dev, is_dev_slash
from . import eval_handlers


class Eval(commands.Cog):

    def __init__(self, bot: AdamBot) -> None:
        """
        Sets up the eval cog with a provided bot.

        Loads and initialises the EvalHandlers class
        """

        self.bot = bot
        self.Handlers = eval_handlers.EvalHandlers(bot)

    @commands.command(name="eval")
    @is_dev()
    async def evaluate(self, ctx: commands.Context, *,
                       command: str = "") -> None:  # command is kwarg to stop it flooding the console when no input is provided
        """
        Evaluate some input for testing purposes.

        Dev needed.
        """

        await self.Handlers.evaluate(ctx, command=command)

    @app_commands.command(
        name="eval",
        description="Evaluate input"
    )
    @app_commands.describe(
        command="The Python string to evaluate"
    )
    @is_dev_slash()
    async def evaluate_slash(self, interaction: discord.Interaction, command: str = "") -> None:
        """
        Slash equivalent of the classic command evaluate.
        """

        await self.Handlers.evaluate(interaction, command=command)

    @commands.group()
    @commands.guild_only()
    async def sql(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}help sql```")

    sql_slash = app_commands.Group(name="sql", description="Make SQL queries")

    @sql.command()
    @is_dev()
    async def execute(self, ctx: commands.Context, *, command: str) -> None:
        """
        Allows the execution of SQL queries for testing.

        Dev role needed.
        """

        await self.Handlers.execute(ctx, command)

    @sql_slash.command(
        name="execute",
        description="Execute an SQL query"
    )
    @app_commands.describe(
        command="The SQL query to execute"
    )
    @is_dev_slash()
    async def execute_slash(self, interaction: discord.Interaction, command: str) -> None:
        """
        Slash equivalent of the classic command execute.
        """

        await self.Handlers.execute(interaction, command=command)

    @sql.command()
    @is_dev()
    async def fetch(self, ctx: commands.Context, *, command: str) -> None:
        """
        Allows performing SQL FETCH queries.

        Dev needed.
        """

        await self.Handlers.fetch(ctx, command=command)

    @sql_slash.command(
        name="fetch",
        description="Perform an SQL FETCH"
    )
    @app_commands.describe(
        command="The SQL fetch query to execute"
    )
    @is_dev_slash()
    async def fetch_slash(self, interaction: discord.Interaction, command: str) -> None:
        """
        Slash equivalent of the classic command fetch.
        """

        await self.Handlers.fetch(interaction, command=command)


async def setup(bot: AdamBot) -> None:
    await bot.add_cog(Eval(bot))
