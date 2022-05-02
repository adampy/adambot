from typing import Callable, Optional

import discord
from discord import app_commands
from discord.app_commands import AppCommandError
from discord.ext import commands

from libs.misc.utils import DefaultEmbedResponses
from . import qotd_handlers


class MissingQOTDError(commands.CheckFailure):
    def __init__(self, message=None, *args):
        super().__init__(message=message, *args)


class MissingQOTDSlashError(app_commands.CheckFailure):
    def __init__(self, *args):
        super().__init__(*args)


async def qotd_predicate(ctx: commands.Context | discord.Interaction):
    is_ctx = type(ctx) is commands.Context
    bot = ctx.bot if is_ctx else ctx.client
    author = ctx.author if is_ctx else ctx.user

    qotd_role_id = await bot.get_config_key(ctx, "qotd_role")
    staff_role_id = await bot.get_config_key(ctx, "staff_role")
    role_ids = [y.id for y in author.roles]
    if qotd_role_id in role_ids or staff_role_id in role_ids or author.guild_permissions.administrator:
        return True
    else:
        raise MissingQOTDError if is_ctx else MissingQOTDSlashError


def qotd_perms() -> Callable:
    """
    Decorator that allows the command to only be executed by people with QOTD perms / staff / administrators.
    This needs to be placed underneath the @command.command() decorator, and can only be used for commands in a cog

    Usage:
        @commands.command()
        @qotd_perms()
        async def ping(self, ctx):
            await ctx.send("Pong!")
    """

    async def predicate(ctx) -> Optional[bool]:
        return await qotd_predicate(ctx)

    return commands.check(predicate)


def qotd_slash_perms() -> Callable:
    async def predicate(interaction: discord.Interaction) -> Optional[bool]:
        return await qotd_predicate(interaction)

    return app_commands.check(predicate)


class QOTD(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the QOTD cog with a provided bot.

        Loads and initialises the QOTDHandlers class
        """

        self.bot = bot
        self.Handlers = qotd_handlers.QOTDHandlers(bot)
        self.bot.tree.map(MissingQOTDSlashError, self.qotd_error_slash_handler)

    async def qotd_error_slash_handler(self, interaction: discord.Interaction, error: AppCommandError) -> None:
        await DefaultEmbedResponses.invalid_perms(self.bot, interaction)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error) -> None:
        if isinstance(error, MissingQOTDError):
            await DefaultEmbedResponses.invalid_perms(ctx.bot, ctx)

    @commands.group()
    async def qotd(self, ctx: commands.Context) -> None:
        """
        Command group for the qotd commands.
        """

        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}qotd submit <question>```")

    qotd_slash = app_commands.Group(name="qotd", description="View, submit and manage the servers QOTDs")

    @qotd.command()
    @commands.guild_only()
    async def submit(self, ctx: commands.Context, *, qotd: str) -> None:
        """
        Submit a QOTD.

        Can be limited by the config key `qotd_limit`
        """

        await self.Handlers.submit(ctx, qotd)

    @qotd_slash.command(
        name="submit",
        description="Submit a QOTD"
    )
    @app_commands.describe(
        qotd="The question you want to ask"
    )
    async def submit_slash(self, interaction: discord.Interaction, qotd: str) -> None:
        """
        Slash equivalent of the classic command submit.
        """

        await self.Handlers.submit(interaction, qotd)

    @qotd.command(name="list")
    @commands.guild_only()
    @qotd_perms()
    async def qotd_list(self, ctx: commands.Context, page_num: int = 1) -> None:
        """
        Get a list of all of the QOTDs within the context guild.
        """

        await self.Handlers.qotd_list(ctx, page_num=page_num)

    @qotd_slash.command(
        name="list",
        description="List the server's QOTDs"
    )
    @app_commands.describe(
        page_num="The page number of the QOTD embed to start on"
    )
    @qotd_slash_perms()
    async def qotd_list_slash(self, interaction: discord.Interaction, page_num: int = 1) -> None:
        """
        Slash equivalent of the classic command list.
        """

        await self.Handlers.qotd_list(interaction, page_num=page_num)

    @qotd.command(aliases=["remove"])
    @commands.guild_only()
    @qotd_perms()
    async def delete(self, ctx: commands.Context, *, question_ids: str) -> None:
        """
        Delete one or more of the server's QOTDs.

        IDs are supplied as 1 2 3 4 to delete multiple QOTDs.

        QOTD perms required.
        """

        await self.Handlers.delete(ctx, question_ids)

    @qotd_slash.command(
        name="delete",
        description="Delete QOTDs"
    )
    @app_commands.describe(
        question_ids="The question(s) to delete by their IDs (written like 1 2 3 4)"
    )
    @qotd_slash_perms()
    async def delete_slash(self, interaction: discord.Interaction, question_ids: str) -> None:
        """
        Slash equivalent of the classic command delete.
        """

        await self.Handlers.delete(interaction, question_ids)

    @qotd.command(aliases=["choose"])
    @commands.guild_only()
    @qotd_perms()
    async def pick(self, ctx: commands.Context, question_id: str) -> None:
        """
        Choose one of the context guild's QOTDs.

        QOTD perms required.
        """

        await self.Handlers.pick(ctx, question_id)

    @qotd_slash.command(
        name="pick",
        description="Pick a QOTD"
    )
    @app_commands.describe(
        question_id="The question ID of the question to pick, or 'random' to pick a random question"
    )
    @qotd_slash_perms()
    async def pick_slash(self, interaction: discord.Interaction, question_id: str) -> None:
        """
        Slash equivalent of the classic command pick.
        """

        await self.Handlers.pick(interaction, question_id)


async def setup(bot) -> None:
    await bot.add_cog(QOTD(bot))
