import discord
from discord import app_commands
from discord.ext import commands

from libs.misc.decorators import is_staff, is_staff_slash
from . import reputation_handlers


class Reputation(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the reputation cog with a provided bot.

        Loads and initialises the ReputationHandlers class
        """

        self.bot = bot
        self.Handlers = reputation_handlers.ReputationHandlers(bot)

    # -----------------------REP COMMANDS------------------------------
    rep_slash = app_commands.Group(name="rep", description="Award, view or manage server members' reputation points")

    @commands.group()
    @commands.guild_only()
    async def rep(self, ctx: commands.Context) -> None:
        """
        Reputation module
        """

        subcommands = []
        for command in self.rep.walk_commands():
            subcommands.append(command.name)
            for alias in command.aliases:
                subcommands.append(alias)

        if ctx.subcommand_passed not in subcommands:
            args = ctx.message.content.replace(f"{ctx.prefix}rep", "").strip()
            await ctx.invoke(self.rep.get_command("award"), **{"args": args})

    @rep.error
    async def rep_error(self, ctx: commands.Context, error) -> None:
        """
        Error handler for the rep grouped commands.
        """

        if isinstance(error, commands.CheckFailure):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                             f"You cannot award reputation points in {ctx.guild.name}")
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Unexpected error!", desc=error)

    @rep.command(aliases=["give", "point"])
    @commands.guild_only()
    async def award(self, ctx: commands.Context, *, args: discord.Member | discord.User | str) -> None:
        """
        Gives the member a reputation point. Aliases are give and point
        """

        await self.Handlers.award(ctx, args=args)

    @rep_slash.command(
        name="award",
        description="Award a user a reputation point"
    )
    @app_commands.describe(
        member="The member to award a reputation point to"
    )
    async def award_slash(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """
        Slash equivalent of the classic command award.
        """

        await self.Handlers.award(interaction, member=member)

    @rep.command(aliases=["lb"])
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context) -> None:
        """
        Displays the leaderboard of reputation points
        """

        await self.Handlers.leaderboard(ctx)

    @rep_slash.command(
        name="leaderboard",
        description="View server reputation leaderboard"
    )
    async def leaderboard_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command leaderboard.
        """

        await self.Handlers.leaderboard(interaction)

    reset_slash = app_commands.Group(name="rep_reset",
                                     description="Manage the resetting of reputation points")  # no provision currently for nested slash command groups unless I'm blind

    @rep.group()
    @commands.guild_only()
    async def reset(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}rep reset all```")

    @reset.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def all(self, ctx: commands.Context) -> None:
        """
        Resets everyone's reps.
        """

        await self.Handlers.all(ctx)

    @reset_slash.command(
        name="all",
        description="Reset all server members' reputation points"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def all_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command all.
        """

        await self.Handlers.all(interaction)

    @rep.command()
    @commands.guild_only()
    @is_staff()
    async def set(self, ctx: commands.Context, user: discord.Member | discord.User, rep: str) -> None:
        """
        Sets a specific members reps to a given value.
        """

        await self.Handlers.set(ctx, user, rep)

    @rep_slash.command(
        name="set",
        description="Set a members' reputation points to a particular number"
    )
    @app_commands.describe(
        user="The member to set the reputation points of",
        rep="The number to set their reputation points to"
    )
    @is_staff_slash()
    async def set_slash(self, interaction: discord.Interaction, user: discord.Member | discord.User, rep: int) -> None:
        """
        Slash equivalent of the classic command set.
        """

        await self.Handlers.set(interaction, user, rep)

    @rep.command()
    @commands.guild_only()
    @is_staff()
    async def hardset(self, ctx: commands.Context, user_id: str, rep: str) -> None:
        """
        Sets a specific member's reps to a given value via their ID.
        """

        await self.Handlers.hardset(ctx, user_id, rep)

    @rep_slash.command(
        name="hardset",
        description="Set a specific user's reputation points via their user ID without them needing to be in the server"
    )
    @app_commands.describe(
        user_id="The user ID of the user to set the reputation points of",
        rep="The number to set their reputation points to"
    )
    @is_staff_slash()
    async def hardset_slash(self, interaction: discord.Interaction, user_id: str, rep: int) -> None:
        """
        Slash equivalent of the classic command hardset.
        """

        await self.Handlers.hardset(interaction, user_id, rep)

    @rep.command(aliases=["count"])
    @commands.guild_only()
    async def check(self, ctx: commands.Context, *, args: str = "") -> None:
        """
        Checks a specific person reps, or your own if user is left blank
        """

        await self.Handlers.check(ctx, args=args)

    @rep_slash.command(
        name="check",
        description="Check a member's reputation points"
    )
    @app_commands.describe(
        member="The member to check the reputation points of"
    )
    async def check_slash(self, interaction: discord.Interaction, member: discord.Member | discord.User = None) -> None:
        """
        Slash equivalent of the classic command check.
        """

        await self.Handlers.check(interaction, member=member)

    @rep.command()
    @commands.guild_only()
    async def data(self, ctx: commands.Context) -> None:
        """
        Display the reputation data for the context guild.
        """

        await self.Handlers.data(ctx)

    @rep_slash.command(
        name="data",
        description="Display the reputation data for this server"
    )
    async def data_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command data.
        """

        await self.Handlers.data(interaction)


async def setup(bot) -> None:
    await bot.add_cog(Reputation(bot))
