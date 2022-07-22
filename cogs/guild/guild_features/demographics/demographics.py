from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from adambot import AdamBot
from libs.misc.decorators import is_staff, is_staff_slash
from . import demographics_handlers


class Demographics(commands.Cog):
    """
    Tracks the change in specific roles
    """

    demographics_slash = app_commands.Group(name="demographics", description="View the server demographics")

    def __init__(self, bot: AdamBot) -> None:
        """
        Sets up the demographics cog with a provided bot.

        Loads and initialises the DemographicsHandlers class
        """

        self.bot = bot
        self.Handlers = demographics_handlers.DemographicsHandlers(bot, self)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        A method which listens for the bot to be ready.

        Syncs the application commands here.
        """

        await self.bot.tasks.register_task_type("demographic_sample", self.handle_demographic_sample,
                                                needs_extra_columns={"demographic_role_id": "bigint"})

    async def handle_demographic_sample(self, data: dict) -> None:
        """
        Method to handle taking a demographics sample
        """

        async with self.bot.pool.acquire() as connection:
            demographic_role_id = data["demographic_role_id"]
            results = await connection.fetch(
                "SELECT role_id, guild_id, sample_rate FROM demographic_roles WHERE id = $1", demographic_role_id)

            guild = self.bot.get_guild(results[0][1])
            role_id = results[0][0]
            sample_rate = results[0][2]
            n = len([x for x in guild.members if role_id in [y.id for y in x.roles]])

            await connection.execute("INSERT INTO demographic_samples (n, role_reference) VALUES ($1, $2)", n,
                                     demographic_role_id)

            if data["task_name"] == "demographic_sample":  # IF NOT A ONE OFF SAMPLE, PERFORM IT AGAIN
                await self.bot.tasks.submit_task("demographic_sample", datetime.utcnow() + timedelta(days=sample_rate),
                                                 extra_columns={"demographic_role_id": demographic_role_id})

    async def _get_roles(self, guild: discord.Guild) -> list[int]:
        """
        Returns all the role IDs that are tracked for a given `guild`.
        """

        async with self.bot.pool.acquire() as connection:
            roles = await connection.fetch("SELECT role_id FROM demographic_roles WHERE guild_id = $1;",
                                           guild.id)  # Returns a list of Record type
        return [x["role_id"] for x in roles]

    async def _add_role(self, role: discord.Role, sample_rate: int) -> None:
        """
        Adds a role to the demographic todo table such that it gets sampled regularly.
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute(
                "INSERT INTO demographic_roles (sample_rate, guild_id, role_id) VALUES ($1, $2, $3);", sample_rate,
                role.guild.id, role.id)
            demographic_role_id = await connection.fetchval("SELECT MAX(id) FROM demographic_roles;")

            now = datetime.utcnow()
            midnight = datetime(now.year, now.month, now.day, 23, 59, 59)  # Midnight of the current day
            await self.bot.tasks.submit_task("demographic_sample", midnight,
                                             extra_columns={"demographic_role_id": demographic_role_id})

    async def _require_sample(self, role: discord.Role) -> None:
        """
        Adds a TODO saying that a sample is required ASAP.
        """

        async with self.bot.pool.acquire() as connection:
            demographic_role_id = await connection.fetchval("SELECT id from demographic_roles WHERE role_id = $1",
                                                            role.id)
            await self.bot.tasks.submit_task("demographic_sample", datetime.utcnow(),
                                             extra_columns={"demographic_role_id": demographic_role_id})

    async def _remove_role(self, role: discord.Role) -> None:
        """
        Removes a role from the demographic todo table - all samples are also removed upon this action.
        """

        async with self.bot.pool.acquire() as connection:
            demographic_role_id = await connection.fetchval("SELECT id FROM demographic_roles WHERE role_id = $1;",
                                                            role.id)
            await connection.execute("DELETE FROM demographic_roles WHERE role_id = $1;", role.id)
            await connection.execute("DELETE FROM tasks WHERE demographic_role_id = $1", demographic_role_id)

    @staticmethod
    async def _role_error(ctx: commands.Context, error: commands.CommandError) -> None:
        """
        Executes on addrole.error and removerole.error.
        """

        if isinstance(error, commands.RoleNotFound):
            await ctx.send("Role not found!")
            return

        else:
            await ctx.send("Oops, that's not possible.")
            print(error)

    # ----- COMMANDS -----

    @commands.group()
    @commands.guild_only()
    async def demographics(self, ctx: commands.Context) -> None:
        if not ctx.invoked_subcommand:
            await ctx.invoke(self.bot.get_command("demographics show"))  # Runs
            return

    @demographics.command()
    @commands.guild_only()
    @is_staff()
    async def viewroles(self, ctx: commands.Context) -> None:
        """
        Gets all the roles that are tracked in a guild.
        """

        await self.Handlers.viewroles(ctx)

    @demographics_slash.command(
        name="viewroles",
        description="Get a list of all the tracked role in this server"
    )
    @is_staff_slash()
    async def viewroles_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command equivalent of the classic command viewroles
        """

        await self.Handlers.viewroles(interaction)

    @demographics.command()
    @commands.guild_only()
    @is_staff()
    async def addrole(self, ctx: commands.Context, role: discord.Role, sample_rate: int = 1) -> None:
        """
        Adds a role to the server's demographic samples.
        `sample_rate` shows how many days are in between each sample, and by default is 1.
        """

        await self.Handlers.addrole(ctx, role, sample_rate=sample_rate)

    @demographics_slash.command(
        name="addrole",
        description="Add a role for sampling on this server"
    )
    @app_commands.describe(
        role="The role to start tracking",
        sample_rate="How many days between each sample"
    )
    @is_staff_slash()
    async def addrole_slash(self, interaction: discord.Interaction, role: discord.Role, sample_rate: int = 1) -> None:
        """
        Slash command equivalent of the classic command addrole.
        """

        await self.Handlers.addrole(interaction, role, sample_rate=sample_rate)

    @demographics.command()
    @commands.guild_only()
    @is_staff()
    async def removerole(self, ctx: commands.Context, role: discord.Role) -> None:
        """
        Remove a role from tracking for the guild.
        """

        await self.Handlers.removerole(ctx, role)

    @demographics_slash.command(
        name="removerole",
        description="Remove a role from tracking for this server"
    )
    @app_commands.describe(
        role="The role to stop tracking"
    )
    @is_staff_slash()
    async def removerole_slash(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """
        Slash command equivalent of the classic command removerole.
        """

        await self.Handlers.removerole(interaction, role)

    @demographics.command()
    @commands.guild_only()
    @is_staff()
    async def takesample(self, ctx: commands.Context, role: discord.Role = None) -> None:
        """
        Adds a TODO saying that a sample is required ASAP. If `role` == None then all guild demographics are sampled.
        """

        await self.Handlers.takesample(ctx, role)

    @demographics_slash.command(
        name="takesample",
        description="Take a sample for a role now"
    )
    @app_commands.describe(
        role="The role to take a sample for"
    )
    @is_staff_slash()
    async def takesample_slash(self, interaction: discord.Interaction, role: discord.Role = None) -> None:
        """
        Slash equivalent of the classic command takesample.
        """
        await self.Handlers.takesample(interaction, role)

    @demographics.command()
    @commands.guild_only()
    @is_staff()
    async def removeallsamples(self, ctx: commands.Context) -> None:
        """
        Removes all samples from the `demographic_samples` table.
        """

        await self.Handlers.removeallsamples(ctx)

    @demographics_slash.command(
        name="removeallsamples",
        description="Remove all samples for this server"
    )
    @is_staff_slash()
    async def removeallsamples_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command removeallsamples.
        """

        await self.Handlers.removeallsamples(interaction)

    # Error handlers
    @addrole.error
    async def addrole_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await self._role_error(ctx, error)

    @removerole.error
    async def removerole_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await self._role_error(ctx, error)

    @takesample.error
    async def takesample_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await self._role_error(ctx, error)

    @demographics.command()
    @commands.guild_only()
    async def show(self, ctx: commands.Context) -> None:  # DO NOT REMOVE THIS METHOD (if you plan on removing, remove dependency in demographics command group declaration)
        """
        View server demographics.
        """

        await self.Handlers.show(ctx)

    @demographics_slash.command(
        name="show",
        description="View this server's demographics"
    )
    async def show_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command show.
        """

        await self.Handlers.show(interaction)

    @demographics.command()
    @commands.guild_only()
    async def chart(self, ctx: commands.Context) -> None:
        """
        View a guild's demographics over time
        """

        await self.Handlers.chart(ctx)

    @demographics_slash.command(
        name="chart",
        description="View this server's demographics chart"
    )
    async def chart_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command chart.
        """

        await self.Handlers.chart(interaction)


async def setup(bot: AdamBot) -> None:
    await bot.add_cog(Demographics(bot))
