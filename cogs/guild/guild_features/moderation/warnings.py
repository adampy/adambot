import discord
from discord import app_commands
from discord.ext import commands

from libs.misc.decorators import is_staff, is_staff_slash
from . import warnings_handlers


class Warnings(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.Handlers = warnings_handlers.WarningHandlers(bot, self)

    @commands.command()
    @commands.guild_only()
    @is_staff()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "") -> None:
        """
        Gives a member a warning, a reason is optional but recommended.
        """

        await self.Handlers.warn(ctx, member, reason)

    @app_commands.command(
        name="warn",
        description="Give a warning to a user"
    )
    @app_commands.describe(
        member="The member to warn",
        reason="Reason for the warning"
    )
    @is_staff_slash()
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member | discord.User,
                         reason: str = "") -> None:
        await self.Handlers.warn(interaction, member, reason)

    @commands.command()
    @commands.guild_only()
    async def warns(self, ctx: commands.Context, member: discord.Member = None) -> None:
        """
        Shows a user their warnings, or shows staff members all/a single persons warnings
        """

        await self.Handlers.warns(ctx, member)

    @app_commands.command(
        name="warns",
        description="View your warns. Staff can view all warns."
    )
    @app_commands.describe(
        member="The member to view the warns for"
    )
    async def warns_slash(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        await self.Handlers.warns(interaction, member)

    @commands.command(aliases=["warndelete"])
    @commands.guild_only()
    @is_staff()
    async def warnremove(self, ctx: commands.Context, warnings: str) -> None:
        """
        Remove warnings with this command, can do `warnremove <warnID>` or `warnremove <warnID1> <warnID2> ... <warnIDn>`.
        """

        await self.Handlers.warnremove(ctx, warnings)

    @app_commands.command(
        name="warnremove",
        description="Remove a warn or several warns"
    )
    @app_commands.describe(
        warnings="The ID of the warning(s) to remove"
    )
    @is_staff_slash()
    async def warnremove_slash(self, interaction: discord.Interaction, warnings: str) -> None:
        await self.Handlers.warnremove(interaction, warnings)


async def setup(bot) -> None:
    await bot.add_cog(Warnings(bot))
