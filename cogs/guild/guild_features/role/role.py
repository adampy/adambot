import discord
from discord import app_commands
from discord.ext import commands

from adambot import AdamBot
from libs.misc.decorators import is_staff, is_staff_slash
from . import role_handlers

"""
    TODO:
      - See about making member (nick)name args be case-insensitive where possible (preferably without being a gigantic mess)
      - Allow mass adding/removals of roles with more than one condition (e.g. can we have everyone with role A or role B receive role C)?
      - More role manipulation?
"""

"""
    long_op - use this in command decorators in this cog to specify that it should be concurrently limited (BucketType is p/guild as of rn)
    
    Perhaps do this as a global standard in the bot at some point?
"""


class Role(commands.Cog):
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.Handlers = role_handlers.RoleHandlers(bot)

    # --- UTILITY FUNCTIONS ---

    # --- COMMANDS ---

    @commands.command(enabled=False, hidden=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def concurr_dummy(self, ctx: commands.Context) -> None:
        """
        Hack of the century
        """

        self.concurr_dummy.update(enabled=False, hidden=True)  # not even the FBI can find me!

    role_slash = app_commands.Group(name="role", description="View and manage the server roles")

    @commands.group()
    @commands.guild_only()
    async def role(self, ctx: commands.Context) -> None:
        """
        "role" command group definition.
        Checks if subcommand passed matches anything within the group.
        If no matching subcommand is found, the help command is displayed.
        """

        subcommands = []
        for command in self.role.walk_commands():
            subcommands.append(command.name)
            for alias in command.aliases:
                subcommands.append(alias)

        if ctx.subcommand_passed not in subcommands:
            await ctx.send_help(ctx.command)

        elif ctx.invoked_subcommand.__original_kwargs__.get("long_op",
                                                            False):  # only execute if you actually know a command is being invoked, else None
            ctx.invoked_subcommand._max_concurrency = self.concurr_dummy._max_concurrency  # hack of the decade. also, no getter available for Command object so shut up PyCharm

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error) -> None:
        """
        Error handler that checks for errors within this specific command group.
        Saves repeated error checks literally everywhere.
        """

        if not ctx.command:
            return  # begone you typoeth cretins!

        if ctx.command.full_parent_name == "role":  # this cog should only care about its own commands" errors
            if isinstance(error, commands.RoleNotFound):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                 "Couldn't find one of the roles you specified!",
                                                                 desc=error)

            elif isinstance(error, commands.MemberNotFound):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                 "Couldn't find one of the members you specified!",
                                                                 desc=error)

            elif isinstance(error, commands.MissingRequiredArgument):
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Usage", desc=ctx.command.help)
            elif isinstance(error, commands.MaxConcurrencyReached):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                 "There's already a large roles operation in progress!",
                                                                 desc="""
                                                                        **Why are you seeing this?**
                                                                        
                                                                        Some of the operations can take a while and use a lot of resources.
                                                                        Some of them have the potential to screw up your server if conflicts happen.
                                                                        
                                                                        So for the sake of everyone's sanity, these types of operations are limited to **one per server** at any given time.
                                                                        
                                                                        *Please wait for the current operation to finish before trying again.*
                                                                 """)
            else:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                 f"An internal error occurred unexpectedly",
                                                                 desc="Contact the bot owner if this persists.")
                raise error
        else:
            """
            Error MUST be re-raised if not handled. in this case, any errors outside of the "role" command group won't get handled.
            Whilst the bot's "on_command_error" listener can see the existence of the cog's listener, it"s nothing more than that.
            
            Why is this here specifically? First place I added this lol
            """
            raise error

    @role.command(
        brief="role info <role> - Display role info",

        help="""
        
            role info <role>
            
            <role> can be: @role, role_id or role name
        """
    )
    @commands.guild_only()
    async def info(self, ctx: commands.Context, *, role: discord.Role | str) -> None:
        """
        Displays various details about a specified role.
        Works with a role mention, role name or role ID.
        """

        await self.Handlers.info(ctx, role)

    @role_slash.command(
        name="info",
        description="View information about a role"
    )
    @app_commands.describe(
        role="The role to view info of"
    )
    async def info_slash(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """
        Slash equivalent of the classic command info.
        """

        await self.Handlers.info(interaction, role)

    @role.command(
        name="list",
        brief="role list - lists all the roles on the server currently",

        help="""
        
            role list
        """
    )
    @commands.guild_only()
    async def list_server_roles(self, ctx: commands.Context) -> None:
        """
        Lists all the roles on the server.
        """

        await self.Handlers.list_server_roles(ctx)

    @role_slash.command(
        name="list",
        description="List all the roles on the server currently"
    )
    async def list_server_roles_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command list.
        """

        await self.Handlers.list_server_roles(interaction)

    @role.command(
        brief="role members <role> - List all members with a role",

        help="""

            role members <role>
            
            <role> can be: @role, role_id or role name
        """
    )
    @commands.guild_only()
    async def members(self, ctx: commands.Context, *, role: discord.Role | str) -> None:
        """
        Lists all the members that have a specified role.
        Works with a role mention, role name or role ID.
        """

        await self.Handlers.members(ctx, role)

    @role_slash.command(
        name="members",
        description="Get a list of all the members with a role"
    )
    @app_commands.describe(
        role="The role to get the list of members of"
    )
    async def members_slash(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """
        Slash equivalent of the classic command members.
        """

        await self.Handlers.members(interaction, role)

    single_role_change_help = \
        """
            __**Staff role required**__

            role add <role> <member>

            <role> can be: @role, role_id or role name

            <member> can be: @member, member_id, member username or member nickname

            **NOTE:** *Names are case-sensitive and must not contain spaces.*
        """

    @role.command(
        brief="role add <role> <member> - Add a role to a member",
        help=single_role_change_help
    )  # sorry we don't have a world-beating AI to beat these types of problems just yet
    @commands.guild_only()
    @is_staff()
    async def add(self, ctx: commands.Context, role: discord.Role | str, *, member: discord.Member) -> None:
        """
        Staff role required.
        Add a specific role to a specified member.
        Order is specifically add ROLE **TO** MEMBER
        Works with @role, role_id or role name and @member, member_id, member username or member nickname

        NOTE: Names have to be case-sensitive and without spaces currently.
        """

        await self.Handlers.add(ctx, role, member)

    @role_slash.command(
        name="add",
        description="Add a role to a member"
    )
    @app_commands.describe(
        role="The role to add",
        member="The member to add the role to"
    )
    @is_staff_slash()
    async def add_slash(self, interaction: discord.Interaction, role: discord.Role, member: discord.Member) -> None:
        """
        Slash equivalent of the classic command add.
        """

        await self.Handlers.add(interaction, role, member)

    @role.command(
        brief="role remove <role> <member> - Remove a role from a member",
        help=single_role_change_help.replace("add", "remove")
    )
    @commands.guild_only()
    @is_staff()
    async def remove(self, ctx: commands.Context, role: discord.Role | str, member: discord.Member) -> None:
        """
        Staff role required.
        Remove a specific role from a specified member.
        Order is specifically remove ROLE **FROM** MEMBER
        Works with @role, role_id or role name and @member, member_id, member username or member nickname

        NOTE: Names have to be case-sensitive and without spaces currently.
        """

        await self.Handlers.remove(ctx, role, member)

    @role_slash.command(
        name="remove",
        description="Remove a role from a member"
    )
    @app_commands.describe(
        role="The role to remove",
        member="The member to remove the role from"
    )
    @is_staff_slash()
    async def remove_slash(self, interaction: discord.Interaction, role: discord.Role, member: discord.Member) -> None:
        """
        Slash equivalent of the classic command remove.
        """

        await self.Handlers.remove(interaction, role, member)

    @role.command(
        long_op=True,  # todo: figure out how to do this for slash commands

        brief="role swap <from> <to> - Shift members from one role to another",

        help="""
        
            __**Staff role required**__
            
            role swap <role to swap from> <role to swap to>
            
            Both roles can be: @role, role_id or role name
            
            Example: role swap @A @B
            
            **NOTE:** *Names must not contain spaces.*
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__
        """
    )
    @commands.guild_only()
    @is_staff()
    async def swap(self, ctx: commands.Context, swap_from: discord.Role | str, *, swap_to: discord.Role | str) -> None:
        """
        Staff role required.
        Allows shifting/swapping of roles.

        Example: role swap @A @B - removes role A from every member that has it, and applies role B to those same members
        Works with @role, role_id or role name (can be interchangeable)

        """

        await self.Handlers.swap(ctx, swap_from, swap_to)

    @role_slash.command(
        name="swap",
        description="Swap every member from role A to role B"
    )
    @app_commands.describe(
        swap_from="The role to remove from each member",
        swap_to="The role to give to each member with the first role"
    )
    @is_staff_slash()
    async def swap_slash(self, interaction: discord.Interaction, swap_from: discord.Role,
                         swap_to: discord.Role) -> None:
        """
        Slash equivalent of the slash command swap.
        """

        await self.Handlers.swap(interaction, swap_from, swap_to)

    @role.command(
        long_op=True,

        brief="role removeall <role> - Remove a role from all members who have it",

        help="""
        
            __**Staff role required**__
            
            role removeall <role>
            
            <role> can be: @role, role_id or role name
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__
        """
    )
    @commands.guild_only()
    @is_staff()
    async def removeall(self, ctx: commands.Context, *, role: discord.Role | str) -> None:
        """
        Staff role required.
        Allows removing a role from all members who have it.

        Works with a role mention, role name or role ID.
.
        """

        await self.Handlers.removeall(ctx, role)

    @role_slash.command(
        name="removeall",
        description="Remove a role from all members"
    )
    @app_commands.describe(
        role="The role to remove from all members"
    )
    @is_staff_slash()
    async def removeall_slash(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """
        Slash equivalent of the classic command removeall.
        """

        await self.Handlers.removeall(interaction, role)

    @role.command(
        long_op=True,

        brief="role addall <with> <add> - Adds role to members with another role",

        help="""
        
            __**Staff role required**__
            
            role addall <with role> <role to add>
            
            Both roles can be: @role, role_id or role name
            
            **NOTE:** *Names must not contain spaces.*   
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__         
        """
    )
    @commands.guild_only()
    @is_staff()
    async def addall(self, ctx: commands.Context, ref_role: discord.Role | str, *,
                     add_role: discord.Role | str) -> None:
        """
        Staff role required.
        Allows adding a role to all members who have another role.

        Works with a role mention, role name or role ID.

        NOTE: Names have to be without spaces currently.

        Example: role addall @A @B - this will add role B to all members that have role A
        """

        await self.Handlers.addall(ctx, ref_role, add_role)

    @role_slash.command(
        name="addall",
        description="Add role B to all users with role A"
    )
    @app_commands.describe(
        ref_role="The reference role",
        add_role="The role to add to all members with the reference role"
    )
    @is_staff_slash()
    async def addall_slash(self, interaction: discord.Interaction, ref_role: discord.Role,
                           add_role: discord.Role) -> None:
        """
        Slash equivalent of the classic command addall.
        """

        await self.Handlers.addall(interaction, ref_role, add_role)

    @role.command(
        long_op=True,

        brief="role clear <member> - Removes all of a member's removeable roles",

        help="""
        
            __**Staff role required**__
        
            role clear <member>
        
            <member> can be: @member, member_id, member username or member nickname
        
            **NOTE:** *Names are case-sensitive currently*
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__
        """
    )
    @commands.guild_only()
    @is_staff()
    async def clear(self, ctx: commands.Context, *, member: discord.Member) -> None:
        """
        Staff role required.
        Allows removing all roles from a user.

        Works with @member, member_id, member username or member nickname

        NOTE: Names have to be case-sensitive currently.
        """

        await self.Handlers.clear(ctx, member)

    @role_slash.command(
        name="clear",
        description="Remove all the removeable roles from a user"
    )
    @app_commands.describe(
        member="The member to remove all roles from"
    )
    @is_staff_slash()
    async def clear_slash(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """
        Slash equivalent of the classic command clear.
        """

        await self.Handlers.clear(interaction, member)


async def setup(bot: AdamBot) -> None:
    await bot.add_cog(Role(bot))
