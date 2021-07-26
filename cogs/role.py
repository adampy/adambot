from discord.ext import commands
import discord
from discord import Embed, errors

"""
    TODO:
      - See about making member (nick)name args be case-insensitive where possible (preferably without being a gigantic mess)
      - Allow mass adding/removals of roles with more than one condition (e.g. can we have everyone with role A or role B receive role C)?
      - More role manipulation?
"""

class Verbosity: # Using enum.Enum means that '>' and '<' operations cannot be performed, e.g. Verbosity.ALL > Verbosity.MINIMAL
    SILENT = 0
    MINIMAL = 1
    ALL = 2

class CheckedRoleChangeResult: # Used for the results of the `Role.checked_role_change()` func
    SUCCESS = 0
    FAILURE = 1
    MISSING_ROLE = 1.1 # TODO: Would it be better to change these to integers??
    HAS_ROLE = 1.2
    CRITICAL_ERROR = 2

class Role(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- UTILITY FUNCTIONS ---

    async def find_closest_role(self, ctx, role, verbosity: Verbosity = Verbosity.SILENT):
        """
        Verbosity:
          0: Silence
          1: Send embeds
          2: Raise errors where appropriate

        Attempts to find roles within a guild that are closest to the 'role' provided.
        """

        possible = []
        equals = []
        for guild_role in ctx.guild.roles[1:]:
            if role.lower() in guild_role.name.lower() or role == str(guild_role.id):
                possible.append(guild_role)
                if role.lower() == guild_role.name.lower():
                    equals.append(guild_role)

        if equals:
            possible = equals  # solves the whole problem of typing "moderator" and it not realising you want "Moderator" and asking you if you meant Moderator or Head Moderator

        if len(possible) > 1 and verbosity > Verbosity.SILENT:
            await ctx.send(possible)
            title = 'Multiple roles found. Please try again by entering one of the following roles.'
            desc = '\n'.join([f"•  {role.name}" + (f" (Role ID: {role.id})" if [a_role.name.lower() for a_role in possible].count(role.name.lower()) > 1 else "") for role in possible])
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, title, desc=desc)

        elif len(possible) == 0 and verbosity > Verbosity.MINIMAL:
            raise commands.RoleNotFound(role)

        return possible

    async def manage_roles_check(self, ctx, action, role: discord.Role=None, verbosity=Verbosity.ALL, error_title="default"):  # verbose toggle e.g. in multi-role changes
        """
        Error checking to see if whatever action can be performed.

        Verbosity:
          0: Nothing
          1: Manage Roles barf embed
          2: Everything

        Returns:
          0: Humanity is fine
          Anything else: Alien invasion
        """

        error_title = f"Couldn't {action} the role!" if error_title == "default" else error_title
        if not ctx.me.guild_permissions.manage_roles:  # was originally gonna separate this all out but given discord rate-limits are stupid you can't work on the assumption that you've retained permissions
            if verbosity > Verbosity.SILENT:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, error_title, desc="Please give me **Manage Roles** permissions")
            return 3
        if role:
            if role.managed or role.is_bot_managed() or role.is_premium_subscriber() or role.is_integration() or role.is_default():
                """
                Basically checks if the role is a nitro booster role, or is an integration-managed role.
                """
                if verbosity == Verbosity.ALL:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, error_title,
                                                                     desc=f"A user cannot {action} this role")
                return 2
            if ctx.me.top_role < role:
                if verbosity == Verbosity.ALL:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, error_title, desc=f"I can't add roles higher than me to members :sob:" if action == "add"
                                                            else "I can't remove roles higher than me from members :sob:")
                return 1
        return 0

    async def checked_role_change(self, ctx, role: discord.Role, member: discord.Member, action: str, tracker: discord.Message=None, part_of_more=False, single_output=True):
        """
        Returns:
            0: Everything fine
            1: Something non-critical went wrong, carry on but note a failure
                1.1: Member didn't have 'role' to remove
                1.2: Member already has 'role'
            2: Something critical went wrong, run around screaming like a lunatic
            None: Oi gimme valid action
        """

        if action not in ["add", "remove"]:
            return

        verb = "added" if action == "add" else "removed"
        reason=f"Requested by {ctx.author}"
        check = await self.manage_roles_check(ctx, action, role=role, error_title="Operation aborted!" if part_of_more else "default")
        return_check = CheckedRoleChangeResult.SUCCESS if check == 0 else CheckedRoleChangeResult.CRITICAL_ERROR # This variable gets returned
        if check == 0:
            try:
                if action == "remove":
                    if role in member.roles:
                        await member.remove_roles(role, reason=reason)
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Removed role", desc=f"Removed {role.mention} from {member.mention}")
                    else:
                        return_check = CheckedRoleChangeResult.MISSING_ROLE
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Didn't remove role", desc=f"{member.mention} doesn't have the {role.mention} role")

                if action == "add":
                    if role not in member.roles:
                        await member.add_roles(role, reason=reason)
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Added role", desc=f"Added {role.mention} to {member.mention}")
                    else:
                        return_check = CheckedRoleChangeResult.HAS_ROLE
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Didn't add role", desc=f"{member.mention} already has the {role.mention} role")

            except errors.NotFound as e:
                if "Role" in str(e):
                    await tracker.delete()
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Operation aborted!",
                                                                     desc=f"The role to be {verb} is no longer available!")
                    return_check = CheckedRoleChangeResult.CRITICAL_ERROR
                else:
                    return_check = CheckedRoleChangeResult.FAILURE
            except errors.Forbidden:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Operation aborted!",
                                                                 desc="Please give me **Manage Roles** permissions")
                return_check = CheckedRoleChangeResult.CRITICAL_ERROR

        elif tracker:
            await tracker.delete()

        return return_check

    # --- COMMANDS ---

    @commands.group()
    @commands.guild_only()
    async def role(self, ctx):
        """
        'role' command group definition.
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

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """
        Error handler that checks for errors within this specific command group.
        Saves repeated error checks literally everywhere.
        """

        if not ctx.command:
            return  # begone you typoeth cretins!

        if ctx.command.full_parent_name == "role":  # this cog should only care about its own commands' errors
            if isinstance(error, commands.RoleNotFound):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Couldn't find one of the roles you specified!", desc=error)

            elif isinstance(error, commands.MemberNotFound):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Couldn't find one of the members you specified!", desc=error)

            elif isinstance(error, commands.MissingRequiredArgument):
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Usage", desc=ctx.command.help)
            else:

                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, f"An internal error occurred unexpectedly", desc="Contact the bot owner if this persists.")
                raise error
        else:
            """
            Error MUST be re-raised if not handled. in this case, any errors outside of the 'role' command group won't get handled.
            Whilst the bot's 'on_command_error' listener can see the existence of the cog's listener, it's nothing more than that.
            
            Why is this here specifically? First place I added this lol
            """
            raise error

    @role.command(
        brief="role info <role> - Display role info",

        help =
        """
            role info <role>
            
            <role> can be: @role, role_id or role name
        """
    )
    @commands.guild_only()
    async def info(self, ctx, *, role):
        """
        Displays various details about a specified role.
        Works with a role mention, role name or role ID.
        """
        role = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)
        if len(role) > 1:
            return
        role = role[0]

        embed = Embed(title=f"Role info ~ {role.name}", colour=role.colour)
        embed.add_field(name="Created at", value=self.bot.correct_time(role.created_at))

        embed.add_field(name="Members", value=len(role.members))

        embed.add_field(name="Position", value=role.position)

        embed.add_field(name="Displays separately", value=role.hoist)

        embed.add_field(name="Mentionable", value=role.mentionable)

        embed.add_field(name="Colour", value=role.colour)

        embed.add_field(name="Role ID", value=role.id)

        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format),
                         icon_url=ctx.author.avatar_url)

        await ctx.send(embed=embed)

    @role.command(
        name="list",
        brief="role list - lists all the roles on the server currently",

        help=
        """
            role list
        """
    )
    @commands.guild_only()
    async def list_server_roles(self, ctx):
        """
        Lists all the roles on the server.
        """

        embed = self.bot.EmbedPages(
            self.bot.PageTypes.ROLE_LIST,
            ctx.guild.roles[1:][::-1],
            f":information_source: Roles in {ctx.guild.name}",
            ctx.author.colour,
            self.bot,
            ctx.author,
            ctx.channel,
            thumbnail_url=ctx.guild.icon_url,
            icon_url=ctx.author.avatar_url,
            footer=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format)
        )

        await embed.set_page(1)
        await embed.send()


    @role.command(
        brief="role members <role> - List all members with a role",

        help=
        """
            role members <role>
            
            <role> can be: @role, role_id or role name
        """
    )
    @commands.guild_only()
    async def members(self, ctx, *, role_name):
        """
        Lists all the members that have a specified role.
        Works with a role mention, role name or role ID.
        """

        possible = await self.find_closest_role(ctx, role_name, verbosity=Verbosity.ALL)

        if len(possible) > 1:
            return

        message = "\n".join([f'`{member.id}` **{member.name}**' for member in possible[0].members]) + \
                  f"\n------------------------------------\n:white_check_mark: I found **{len(possible[0].members)}** member{'' if len(possible[0].members) == 1 else 's'} with the **{possible[0].name}** role."

        await self.bot.send_text_file(message, ctx.channel, "roles", "txt") if len(message) > 2000 else await ctx.send(message)

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
    async def add(self, ctx, role, *, member: discord.Member):
        """
        Staff role required.
        Add a specific role to a specified member.
        Order is specifically add ROLE **TO** MEMBER
        Works with @role, role_id or role name and @member, member_id, member username or member nickname

        NOTE: Names have to be case-sensitive and without spaces currently.
        """

        if not (ctx.author.guild_permissions.manage_roles or await self.bot.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        role = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)
        if len(role) > 1:
            return

        await self.checked_role_change(ctx, role[0], member, "add")

    @role.command(
        brief="role remove <role> <member> - Remove a role from a member",
        help=single_role_change_help.replace("add", "remove")
    )
    @commands.guild_only()
    async def remove(self, ctx, role, member: discord.Member):
        """
        Staff role required.
        Remove a specific role from a specified member.
        Order is specifically remove ROLE **FROM** MEMBER
        Works with @role, role_id or role name and @member, member_id, member username or member nickname

        NOTE: Names have to be case-sensitive and without spaces currently.
        """

        if not (ctx.author.guild_permissions.manage_roles or await self.bot.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        role = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)
        if len(role) > 1:
            return

        await self.checked_role_change(ctx, role[0], member, "remove")

    @role.command(
        brief="role swap <from> <to> - Shift members from one role to another",

        help=
        """
            __**Staff role required**__
            
            role swap <role to swap from> <role to swap to>
            
            Both roles can be: @role, role_id or role name
            
            Example: role swap @A @B
            
            **NOTE:** *Names must not contain spaces.*
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__
        """
    )
    @commands.guild_only()
    async def swap(self, ctx, swap_from, *, swap_to):
        """
        Staff role required.
        Allows shifting/swapping of roles.

        Example: role swap @A @B - removes role A from every member that has it, and applies role B to those same members
        Works with @role, role_id or role name (can be interchangeable)

        """

        swap_from = await self.find_closest_role(ctx, swap_from, verbosity=Verbosity.ALL)
        if len(swap_from) > 1:
            return
        swap_from = swap_from[0]

        swap_to = await self.find_closest_role(ctx, swap_to, verbosity=Verbosity.ALL)
        if len(swap_to) > 1:
            return
        swap_to = swap_to[0]

        if not (ctx.author.guild_permissions.manage_roles or await self.bot.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if swap_from == swap_to:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Why would we do that then", desc="Try again with 2 different roles!")
            return

        if not len(swap_from.members):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Nothing to do!", desc="Nobody has this role!")
            return

        tracker = await ctx.reply(f"Swapped **0/{len(swap_from.members)}**")

        no_swap_role = 0
        already_got_dest_role = 0
        members = swap_from.members
        done = 0
        for member in members:
            result_1 = await self.checked_role_change(ctx, swap_from, member, "remove", part_of_more=True)
            result_2 = await self.checked_role_change(ctx, swap_to, member, "add", tracker=tracker, part_of_more=True)

            if result_1 == CheckedRoleChangeResult.SUCCESS and result_2 == CheckedRoleChangeResult.SUCCESS:
                done += 1
                await tracker.edit(content=f"Swapped **{done}/{len(members)}**")
            elif result_1 == CheckedRoleChangeResult.CRITICAL_ERROR:
                return
            if result_1 == CheckedRoleChangeResult.MISSING_ROLE:
                no_swap_role += 1
            if result_2 == CheckedRoleChangeResult.HAS_ROLE:
                already_got_dest_role += 1

        await tracker.delete()
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Operation successful", desc=f"Successfully swapped **{done}** members from {swap_from.mention} to {swap_to.mention}"
                                                                                                       + ("" if done == len(members) else f" ({len(members) - done} failed)")
                                                                                                       + ("" if no_swap_role == 0 else f" ({no_swap_role} didn't have {swap_from.mention})")
                                                                                                       + ("" if already_got_dest_role == 0 else f" ({already_got_dest_role} already had {swap_to.mention})"))

    @role.command(
        brief="role removeall <role> - Remove a role from all members who have it",

        help=
        """
            __**Staff role required**__
            
            role removeall <role>
            
            <role> can be: @role, role_id or role name
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__
        """
    )
    @commands.guild_only()
    async def removeall(self, ctx, *, role):
        """
        Staff role required.
        Allows removing a role from all members who have it.

        Works with a role mention, role name or role ID.
.
        """

        role = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)
        if len(role) > 1:
            return
        role = role[0]

        if not (ctx.author.guild_permissions.manage_roles or await self.bot.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if not len(role.members):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Nothing to do!", desc="Nobody has this role!")
            return

        members = role.members
        tracker = await ctx.reply(f"Removed role from **0/{len(members)}** members")
        done = 0
        fail = 0
        for member in members:
            result = await self.checked_role_change(ctx, role, member, "remove", tracker=tracker, part_of_more=True)
            if result == CheckedRoleChangeResult.SUCCESS:
                done += 1
                await tracker.edit(content=f"Removed role from **{done}/{len(members)}** members")
            elif result == CheckedRoleChangeResult.CRITICAL_ERROR:
                return
            elif result == CheckedRoleChangeResult.MISSING_ROLE:
                fail += 1
        await tracker.delete()
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Operation completed!", desc=f"Successfully removed {role.mention} from **{done}** members"
                                                                                                       + ("" if done == len(members) else f" ({len(members) - done} failed)")
                                                                                                       + ("" if fail == 0 else f" ({fail} already had {role.mention} removed, but not by the bot)"))

    @role.command(
        brief="role addall <with> <add> - Adds role to members with another role",

        help=
        """
            __**Staff role required**__
            
            role addall <with role> <role to add>
            
            Both roles can be: @role, role_id or role name
            
            **NOTE:** *Names must not contain spaces.*   
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__         
        """
    )
    @commands.guild_only()
    async def addall(self, ctx, ref_role, *, add_role):
        """
        Staff role required.
        Allows adding a role to all members who have another role.

        Works with a role mention, role name or role ID.

        NOTE: Names have to be without spaces currently.

        Example: role addall @A @B - this will add role B to all members that have role A
        """

        ref_role = await self.find_closest_role(ctx, ref_role, verbosity=Verbosity.ALL)
        if len(ref_role) > 1:
            return
        ref_role = ref_role[0]

        add_role = await self.find_closest_role(ctx, add_role, verbosity=Verbosity.ALL)
        if len(add_role) > 1:
            return
        add_role = add_role[0]

        if not (ctx.author.guild_permissions.manage_roles or await self.bot.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if ref_role == add_role:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Why would we do that then", desc="Try again with 2 different roles!")
            return

        if not len(ref_role.members):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Nothing to do!", desc="Nobody has this role!")
            return
        
        members = ref_role.members
        tracker = await ctx.reply(f"Added role to **0/{len(members)}** members")
        done = 0
        fail = 0
        for member in members:
            result = await self.checked_role_change(ctx, add_role, member, "add", tracker=tracker, part_of_more=True)
            if result == CheckedRoleChangeResult.SUCCESS:
                done += 1
                await tracker.edit(content=f"Added role to **{done}/{len(members)}** members")
            elif result == CheckedRoleChangeResult.CRITICAL_ERROR:
                return
            elif result == CheckedRoleChangeResult.HAS_ROLE:
                fail += 1

        await tracker.delete()
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Operation completed!", desc=f"Successfully added {add_role.mention} to **{done}** members with {ref_role.mention} "
                                                                                                       + ("" if done == len(members) else f" ({len(members) - done} failed)")
                                                                                                       + ("" if fail == 0 else f" ({fail} already had {add_role.mention})"))

    @role.command(
        brief="role clear <member> - Removes all of a member's removeable roles",

        help=
        """
            __**Staff role required**__
        
            role clear <member>
        
            <member> can be: @member, member_id, member username or member nickname
        
            **NOTE:** *Names are case-sensitive currently*
            
            **WARNING**: __**Due to Discord rate-limits, this process can take a while**__
        """
    )
    @commands.guild_only()
    async def clear(self, ctx, *, member: discord.Member):
        """
        Staff role required.
        Allows removing all roles from a user.

        Works with @member, member_id, member username or member nickname

        NOTE: Names have to be case-sensitive currently.
        """

        if not (ctx.author.guild_permissions.manage_roles or await self.bot.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if not ctx.me.guild_permissions.manage_roles:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Couldn't remove roles!", desc="Please give me **Manage Roles** permissions")
            return

        if len(member.roles) == 1:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "No roles were removed!", desc=f"{member.mention} already has no roles!")
            return


        fail = []

        roles = member.roles[1:]
        for i in range(len(roles)):
            try:
                if await self.manage_roles_check(ctx, "remove", role=roles[i], verbosity=Verbosity.SILENT) == 0: # Then no errors will occur
                    await member.remove_roles(roles[i], reason=f"Requested by {ctx.author}")
                else:
                    fail.append(roles[i].name)
            except errors.NotFound:
                fail.append("Unavailable role")
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Roles removed successfully!", desc=f"All roles have been removed from {member.mention}" + (f" except for **{(', '.join(fail[:len(fail) - 1]) + f' and {fail[len(fail) - 1]}') if len(fail) > 1 else fail[0]}**, which could not be removed." if fail else ""))


def setup(bot):
    bot.add_cog(Role(bot))