import discord
from discord.ext import commands
from .utils import Permissions
import asyncio
import asyncpg

class Demographics(commands.Cog): # Tracks the change in specific roles. This works over multiple guilds, but cannot function like that due to utils.Permissions.
    def __init__(self, bot):
        self.bot = bot

    async def _get_roles(self, guild: discord.Guild):
        """Returns all the role IDs that are tracked for a given `guild`."""
        async with self.bot.pool.acquire() as connection:
            roles = await connection.fetch("SELECT role_id FROM demographic_todos WHERE guild_id = $1;", (guild.id)) # Returns a list of Record type
        return [x["role_id"] for x in roles]

    async def _add_role(self, role: discord.Role, sample_rate):
        """Adds a role to the demographic todo table such that it gets sampled regularly."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO demographic_todos (sample_rate, guild_id, role_id) VALUES ($1, $2, $3);", sample_rate, role.guild.id, role.id)

    async def _remove_role(self, role: discord.Role):
        """Removes a role from the demographic todo table - all samples are also removed upon this action."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM demographic_todos WHERE role_id = $1;", role.id)

    async def _role_error(self, ctx, error):
        """Executes on addrole.erorr and removerole.error."""
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
        if ctx.invoked_subcommand == None:
            await ctx.send("To see the commands availiable, type `-help demographics`")
            return

    @demographics.command(pass_context = True)
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def viewroles(self, ctx):
        """Gets all the roles that are tracked in a guild."""
        role_ids = await self._get_roles(ctx.guild)
        roles = [ctx.guild.get_role(x).name for x in role_ids]
        await ctx.send("Currently tracked roles are: " + ', '.join(roles))

    @demographics.command(pass_context = True)
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def addrole(self, ctx, role: discord.Role, sample_rate: int = 1):
        """Adds a role to the server's demographic samples. `sample_rate` shows how many days are inbetween each sample, and by default is 1."""
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        if role.id in await self._get_roles(ctx.guild):
            await ctx.send("This role is already being tracked!")
            return

        question = await ctx.send(f"Do you want to add {role.name} to {role.guild.name}'s demographics? It'll be sampled every {sample_rate} day(s)? (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check = check, timeout = 300) # 5 minute timeout
        except asyncio.TimeoutError:
            await question.edit(content = "Demographic command timed out. :sob:")
            return
        
        if response.content.lower() == "yes":
            # Add to DB
            await self._add_role(role, sample_rate)
            await ctx.send(f"{role.name} has been added to the demographics, it'll be sampled for the first time at midnight today!")
        elif response.content.lower() == "no":
            await ctx.send(f"{role.name} has not been added. :sob:")
        else:
            question.edit("Unknown response, please try again. :sob:")

    @demographics.command(pass_context = True)
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def removerole(self, ctx, role: discord.Role):
        """Gets all the roles that are tracked in a guild."""
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        if role.id not in await self._get_roles(ctx.guild):
            await ctx.send("This role is not currently being tracked!")
            return

        question = await ctx.send(f"Are you sure you want to remove {role.name} from {role.guild.name}'s demographics? All previous samples will be deleted too. (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check = check, timeout = 300) # 5 minute timeout
        except asyncio.TimeoutError:
            await question.edit(content = "Demographic command timed out. :sob:")
            return
        
        if response.content.lower() == "yes":
            # Remove from DB
            await self._remove_role(role)
            await ctx.send(f"{role.name}, and all its previous samples, have been removed from the demographics")
        else:
            await question.edit(content = "No action taken.")

    # Error handlers
    @addrole.error
    async def addrole_error(self, ctx, error):
        await self._role_error(ctx, error)
    @removerole.error
    async def removerole_error(self, ctx, error):
        await self._role_error(ctx, error)

    # Old command
    @demographics.command(pass_context = True)
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def show(self, ctx):
        """View server demographics."""
        numbers = []
        numbers.append(len(ctx.guild.members))
        for role in ['Post-GCSE', 'Y11', 'Y10', 'Y9']:
            numbers.append(len([x for x in ctx.guild.members if role in [y.name for y in x.roles]]))
        message = """We have {} members.
        
{} Post-GCSE
{} Year 11s
{} Year 10s
{} Year 9s
*The demographics system is currently undergoing maintenance, and there will soon be new features added.*""".format(*numbers)
        await ctx.send(message)


def setup(bot):
    bot.add_cog(Demographics(bot))