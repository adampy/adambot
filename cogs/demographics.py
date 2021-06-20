import discord
from discord.ext import commands
from .utils import Todo, send_image_file
import asyncio
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter


class Demographics(commands.Cog):
    """Tracks the change in specific roles"""
    def __init__(self, bot):
        self.bot = bot

    async def _get_roles(self, guild: discord.Guild):
        """Returns all the role IDs that are tracked for a given `guild`."""
        async with self.bot.pool.acquire() as connection:
            roles = await connection.fetch("SELECT role_id FROM demographic_roles WHERE guild_id = $1;", guild.id)  # Returns a list of Record type
        return [x["role_id"] for x in roles]

    async def _add_role(self, role: discord.Role, sample_rate):
        """Adds a role to the demographic todo table such that it gets sampled regularly."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO demographic_roles (sample_rate, guild_id, role_id) VALUES ($1, $2, $3);", sample_rate, role.guild.id, role.id)
            demographic_role_id = await connection.fetchval("SELECT MAX(id) FROM demographic_roles;")

            now = datetime.utcnow()
            midnight = datetime(now.year, now.month, now.day, 23, 59, 59)  # Midnight of the current day
            await connection.execute("INSERT INTO todo (todo_id, todo_time, member_id) VALUES ($1, $2, $3)", Todo.DEMOGRAPHIC_SAMPLE, midnight, demographic_role_id)  # Place the role reference in the member_id field.

    async def _require_sample(self, role: discord.Role):
        """Adds a TODO saying that a sample is required ASAP."""
        async with self.bot.pool.acquire() as connection:
            demographic_role_id = await connection.fetchval("SELECT id from demographic_roles WHERE role_id = $1", role.id)
            await connection.execute("INSERT INTO todo (todo_id, todo_time, member_id) VALUES ($1, $2, $3)", Todo.DEMOGRAPHIC_SAMPLE, datetime.utcnow(), demographic_role_id)  # Placing the role reference in the member_id field.

    async def _remove_role(self, role: discord.Role):
        """Removes a role from the demographic todo table - all samples are also removed upon this action."""
        async with self.bot.pool.acquire() as connection:
            demographic_role_id = await connection.fetchval("SELECT id FROM demographic_roles WHERE role_id = $1;", role.id)
            await connection.execute("DELETE FROM demographic_roles WHERE role_id = $1;", role.id)
            await connection.execute("DELETE FROM todo WHERE member_id = $1", demographic_role_id)

    async def _role_error(self, ctx, error):
        """Executes on addrole.error and removerole.error."""
        if isinstance(error, commands.RoleNotFound):
            await ctx.send("Role not found!")
            return
        else:
            await ctx.send("Oops, that's not possible.")
            print(error)

    # ----- COMMANDS -----

    @commands.group()
    @commands.guild_only()
    async def demographics(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.invoke(self.bot.get_command("demographics show"))  # Runs
            return

    @demographics.command(pass_context=True)
    @commands.guild_only()
    async def viewroles(self, ctx):
        """Gets all the roles that are tracked in a guild."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You need the staff role to do this :sob:")
            return

        role_ids = await self._get_roles(ctx.guild)
        roles = [ctx.guild.get_role(x).name for x in role_ids]
        await ctx.send("Currently tracked roles are: " + ', '.join(roles))

    @demographics.command(pass_context=True)
    @commands.guild_only()
    async def addrole(self, ctx, role: discord.Role, sample_rate: int = 1):
        """Adds a role to the server's demographic samples.
        `sample_rate` shows how many days are inbetween each sample, and by default is 1."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You need the staff role to do this :sob:")
            return

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        if role.id in await self._get_roles(ctx.guild):
            await ctx.send("This role is already being tracked!")
            return

        question = await ctx.send(f"Do you want to add {role.name} to {role.guild.name}'s demographics? It'll be sampled every {sample_rate} day(s)? (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check=check, timeout=300)  # 5 minute timeout
        except asyncio.TimeoutError:
            await question.edit(content="Demographic command timed out. :sob:")
            return
        
        if response.content.lower() == "yes":
            # Add to DB
            await self._add_role(role, sample_rate)
            await ctx.send(f"{role.name} has been added to the demographics, it'll be sampled for the first time at midnight today!")
        elif response.content.lower() == "no":
            await ctx.send(f"{role.name} has not been added. :sob:")
        else:
            question.edit("Unknown response, please try again. :sob:")

    @demographics.command(pass_context=True)
    @commands.guild_only()
    async def removerole(self, ctx, role: discord.Role):
        """Gets all the roles that are tracked in a guild."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You need the staff role to do this :sob:")
            return

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        if role.id not in await self._get_roles(ctx.guild):
            await ctx.send("This role is not currently being tracked!")
            return

        question = await ctx.send(f"Are you sure you want to remove {role.name} from {role.guild.name}'s demographics? All previous samples will be deleted too. (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check=check, timeout=300)  # 5 minute timeout
        except asyncio.TimeoutError:
            await question.edit(content="Demographic command timed out. :sob:")
            return
        
        if response.content.lower() == "yes":
            # Remove from DB
            await self._remove_role(role)
            await ctx.send(f"{role.name}, and all its previous samples, have been removed from the demographics")
        else:
            await question.edit(content="No action taken.")

    @demographics.command(pass_context=True)
    @commands.guild_only()
    async def takesample(self, ctx, role: discord.Role = None):
        """Adds a TODO saying that a sample is required ASAP. If `role` == None then all guild demographics are sampled."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You need the staff role to do this :sob:")
            return

        guild_tracked_roles = await self._get_roles(ctx.guild)
        if not role:
            # Take a sample of all roles
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            question = await ctx.send(f"No role given, would you like to take a sample of all this guild's roles? (Type either 'yes' or 'no')")
            try:
                response = await self.bot.wait_for("message", check=check, timeout=300)  # 5 minute timeout
            except asyncio.TimeoutError:
                await question.edit(content="Demographic command timed out. :sob:")
                return

            if response.content.lower() == "yes":
                for role in guild_tracked_roles:
                    await self._require_sample(ctx.guild.get_role(role))
                await ctx.send("All roles sampled! :ok_hand:")
            elif response.content.lower() == "no":
                await ctx.send("Operation cancelled.")
            else:
                await ctx.send("Unknown response - operation cancelled.")
            return  # return here means return does not need to be placed inside each condition

        if role.id not in await guild_tracked_roles:
            await ctx.send("This role is not currently being tracked!")
            return

        await self._require_sample(role)
        await ctx.send("A sample has been taken, it may take a few seconds to be registered in the database. :ok_hand:")

    @demographics.command(pass_context=True)
    @commands.guild_only()
    async def removeallsamples(self, ctx):
        """Removes all samples from the `demographic_samples` table."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You need the staff role to do this :sob:")
            return

        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM demographic_samples WHERE role_reference IN (SELECT id FROM demographic_roles WHERE guild_id = $1);", ctx.guild.id) # Removes samples for that guild
        await ctx.send("All samples have been deleted. :sob:")

    # Error handlers
    @addrole.error
    async def addrole_error(self, ctx, error):
        await self._role_error(ctx, error)

    @removerole.error
    async def removerole_error(self, ctx, error):
        await self._role_error(ctx, error)

    @takesample.error
    async def takesample_error(self, ctx, error):
        await self._role_error(ctx, error)

    @demographics.command(pass_context=True)
    @commands.guild_only()
    async def show(self, ctx):
        """View server demographics."""  # DO NOT REMOVE THIS METHOD (if you plan on removing, remove dependency in demographics command group declaration)
        tracked_roles = [ctx.guild.get_role(r) for r in await self._get_roles(ctx.guild) if ctx.guild.get_role(r) is not None]
        message = f"There are a total of **{ctx.guild.member_count}** users in **{ctx.guild.name}**."

        double_newline = True
        for role in tracked_roles:
            n = len(role.members)
            if double_newline:
                message += "\n"
                double_newline = False # Adds an extra new line on the first iteration
            message += f"\n•**{n}** {role.name}"


        p = self.bot.configs[ctx.guild.id]["prefix"]
        message += f"\n*Note: do `{p}demographics chart` to view change in demographics over time!*"
        await ctx.send(message)

    @demographics.command(pass_context=True)
    @commands.guild_only()
    async def chart(self, ctx):
        """View a guild's demographics over time"""
        fig, ax = plt.subplots()
        async with self.bot.pool.acquire() as connection:
            role_data = await connection.fetch("SELECT role_id, id FROM demographic_roles WHERE guild_id = $1", ctx.guild.id)
            
            for role in role_data:
                data = await connection.fetch("SELECT taken_at, n FROM demographic_samples WHERE role_reference = $1", role[1])
                role = ctx.guild.get_role(role[0])
                rgb_scaled_tuple = tuple(x/255 for x in role.color.to_rgb())  # Scale 0-255 integers down to 0-1 floats

                ax.plot([x[0] for x in data], [x[1] for x in data], 'b-o', linewidth=1, markersize=2, color=rgb_scaled_tuple, label=role.name)

        ax.set(xlabel='Time', ylabel='Frequency', title=f"{ctx.guild.name}'s  demographics ({ctx.guild.member_count} members)")
        ax.grid()
        ax.legend(loc="upper left")
        ax.set_ylim(bottom=0)
        ax.fmt_xdata = DateFormatter('% Y-% m-% d % H:% M:% S') 
        fig.autofmt_xdate()

        await send_image_file(fig, ctx.channel, "demographics-data")


def setup(bot):
    bot.add_cog(Demographics(bot))
