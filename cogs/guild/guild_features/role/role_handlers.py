from typing import Optional

import discord
from discord import Embed, errors
from discord.ext import commands

from adambot import AdamBot
from libs.misc.decorators import unbox_context
from libs.misc.utils import ContextTypes, get_user_avatar_url, get_guild_icon_url


class Verbosity:  # Using enum.Enum means that ">" and "<" operations cannot be performed, e.g. Verbosity.ALL > Verbosity.MINIMAL
    SILENT = 0
    MINIMAL = 1
    ALL = 2


class CheckedRoleChangeResult:  # Used for the results of the `Role.checked_role_change()` func
    SUCCESS = 0
    FAILURE = 1
    MISSING_ROLE = 1.1  # TODO: Would it be better to change these to integers??
    HAS_ROLE = 1.2
    CRITICAL_ERROR = 2


class RoleHandlers:
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.ContextTypes = self.bot.ContextTypes

    @unbox_context
    async def checked_role_change(self, ctx_type: ContextTypes, author: discord.User | discord.Member,
                                  ctx: commands.Context | discord.Interaction, role: discord.Role,
                                  member: discord.Member, action: str, tracker: discord.Message = None,
                                  part_of_more: bool = False, single_output: bool = True) -> Optional[int | float]:
        """
        Returns:
            0: Everything fine
            1: Something non-critical went wrong, carry on but note a failure
                1.1: Member didn't have "role" to remove
                1.2: Member already has "role"
            2: Something critical went wrong, run around screaming like a lunatic
            None: Oi gimme valid action
        """

        if action not in ["add", "remove"]:
            return

        verb = "added" if action == "add" else "removed"
        reason = f"Requested by {author}"
        check = await self.manage_roles_check(ctx, action, role=role,
                                              error_title="Operation aborted!" if part_of_more else "default")
        return_check = CheckedRoleChangeResult.SUCCESS if check == 0 else CheckedRoleChangeResult.CRITICAL_ERROR  # This variable gets returned
        if check == 0:
            try:
                if action == "remove":
                    if role in member.roles:
                        await member.remove_roles(role, reason=reason)
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Removed role",
                                                                               desc=f"Removed {role.mention} from {member.mention}")
                    else:
                        return_check = CheckedRoleChangeResult.MISSING_ROLE
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Didn't remove role",
                                                                             desc=f"{member.mention} doesn't have the {role.mention} role")

                if action == "add":
                    if role not in member.roles:
                        await member.add_roles(role, reason=reason)
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Added role",
                                                                               desc=f"Added {role.mention} to {member.mention}")
                    else:
                        return_check = CheckedRoleChangeResult.HAS_ROLE
                        if not part_of_more and single_output:
                            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Didn't add role",
                                                                             desc=f"{member.mention} already has the {role.mention} role")

            except errors.NotFound as e:
                if "Role" in str(e):
                    if ctx_type == self.ContextTypes.Context:
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
            if ctx_type == self.ContextTypes.Context:
                await tracker.delete()

        return return_check

    async def manage_roles_check(self, ctx: commands.Context, action: str, role: discord.Role = None,
                                 verbosity=Verbosity.ALL,
                                 error_title="default") -> int:  # verbose toggle e.g. in multi-role changes
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
        if not ctx.guild.me.guild_permissions.manage_roles:  # was originally gonna separate this all out but given discord rate-limits are stupid you can't work on the assumption that you"ve retained permissions
            if verbosity > Verbosity.SILENT:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, error_title,
                                                                 desc="Please give me **Manage Roles** permissions")
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
            if ctx.guild.me.top_role < role:
                if verbosity == Verbosity.ALL:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, error_title,
                                                                     desc=f"I can't add roles higher than me to members :sob:" if action == "add"
                                                                     else "I can't remove roles higher than me from members :sob:")
                return 1
        return 0

    async def find_closest_role(self, ctx: commands.Context | discord.Interaction, role: str,
                                verbosity: int = Verbosity.SILENT) -> list[discord.Role]:
        """
        Verbosity:
          0: Silence
          1: Send embeds
          2: Raise errors where appropriate

        Attempts to find roles within a guild that are closest to the "role" provided.
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
            title = "Multiple roles found. Please try again by entering one of the following roles."
            desc = "\n".join([f"•  {role.name}" + (
                f" (Role ID: {role.id})" if [a_role.name.lower() for a_role in possible].count(
                    role.name.lower()) > 1 else "") for role in possible])
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, title, desc=desc)

        elif len(possible) == 0 and verbosity > Verbosity.MINIMAL:
            raise commands.RoleNotFound(role)

        return possible

    @unbox_context
    async def info(self, ctx_type: ContextTypes, author: discord.User | discord.Member, ctx: commands.Context | discord.Interaction, role: discord.Role | str) -> None:
        """
        Handler for the info commands.
        """

        if type(role) is not discord.Role:
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
        icon_url = get_guild_icon_url(ctx.guild)
        if icon_url:
            embed.set_thumbnail(url=icon_url)
        embed.set_footer(text=f"Requested by: {author.display_name} ({author})\n" + self.bot.correct_time().strftime(
            self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)

    @unbox_context
    async def list_server_roles(self, ctx_type: ContextTypes, author: discord.User | discord.Member, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the list commands.
        """

        embed = self.bot.EmbedPages(
            self.bot.PageTypes.ROLE_LIST,
            ctx.guild.roles[1:][::-1],
            f":information_source: Roles in {ctx.guild.name}",
            author.colour,
            self.bot,
            author,
            ctx.channel,
            thumbnail_url=get_guild_icon_url(ctx.guild),
            icon_url=get_user_avatar_url(author, mode=1)[0],
            footer=f"Requested by: {author.display_name} ({author})\n" + self.bot.correct_time().strftime(
                self.bot.ts_format),
            ctx=ctx
        )

        await embed.set_page(1)
        await embed.send()

    @unbox_context
    async def members(self, ctx_type: ContextTypes, author: discord.User | discord.Member, ctx: commands.Context | discord.Interaction, role: discord.Role | str) -> None:
        """
        Handler for the members commands.
        """

        if type(role) is not discord.Role:
            possible = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)

            if len(possible) > 1:
                return

            role = possible[0]

        message = "\n".join([f"`{member.id} **{member.name}**`" for member in role.members]) + \
                  f"\n------------------------------------\n:white_check_mark: I found **{len(role.members)}** member{'' if len(role.members) == 1 else 's'} with the **{role.name}** role."

        if len(message) > 2000:
            await self.bot.send_text_file(ctx, message, ctx.channel, "roles", "txt")
        elif ctx_type == self.ContextTypes.Context:
            await ctx.send(message)
        else:
            await ctx.response.send_message(message)

    async def add(self, ctx: commands.Context | discord.Interaction, role: discord.Role | str,
                  member: discord.Member) -> None:
        """
        Handler for the add commands.
        """

        if type(role) is not discord.Role:  # no point wasting time if it's of the correct type already

            role = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)

            if len(role) > 1:
                return

            role = role[0]

        await self.checked_role_change(ctx, role, member, "add")

    async def remove(self, ctx: commands.Context | discord.Interaction, role: discord.Role | str,
                     member: discord.Member) -> None:
        """
        Handler for the remove commands.
        """

        if type(role) is not discord.Role:
            role = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)
            if len(role) > 1:
                return

            role = role[0]

        await self.checked_role_change(ctx, role, member, "remove")

    @unbox_context
    async def swap(self, ctx_type: ContextTypes, author: discord.User | discord.Member, ctx: commands.Context | discord.Interaction, swap_from: discord.Role | str,
                   swap_to: discord.Role | str) -> None:
        """
        Handler for the swap commands.
        """

        if type(swap_from) is not discord.Role:
            swap_from = await self.find_closest_role(ctx, swap_from, verbosity=Verbosity.ALL)
            if len(swap_from) > 1:
                return
            swap_from = swap_from[0]

        if type(swap_to) is not discord.Role:
            swap_to = await self.find_closest_role(ctx, swap_to, verbosity=Verbosity.ALL)
            if len(swap_to) > 1:
                return
            swap_to = swap_to[0]

        if swap_from == swap_to:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Why would we do that then",
                                                             desc="Try again with 2 different roles!")
            return

        if not len(swap_from.members):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Nothing to do!",
                                                             desc="Nobody has this role!")
            return

        if ctx_type == self.ContextTypes.Context:
            tracker = await ctx.reply(f"Swapped **0/{len(swap_from.members)}**")
        else:
            await ctx.response.send_message(f"Swapped **0/{len(swap_from.members)}**")
            tracker = await ctx.original_message()

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

        if ctx_type == self.ContextTypes.Context:
            await tracker.delete()
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Operation successful",
                                                           desc=f"Successfully swapped **{done}** members from {swap_from.mention} to {swap_to.mention}"
                                                                + ("" if done == len(members) else f" ({len(members) - done} failed)")
                                                                + (
                                                                    "" if no_swap_role == 0 else f" ({no_swap_role} didn't have {swap_from.mention})")
                                                                + (
                                                                    "" if already_got_dest_role == 0 else f" ({already_got_dest_role} already had {swap_to.mention})"))

    @unbox_context
    async def removeall(self, ctx_type: ContextTypes, author: discord.User | discord.Member, ctx: commands.Context | discord.Interaction, role: discord.Role | str) -> None:
        """
        Handler for the removeall commands.
        """

        if type(role) is not discord.Role:
            role = await self.find_closest_role(ctx, role, verbosity=Verbosity.ALL)
            if len(role) > 1:
                return
            role = role[0]

        if len(role.members):
            members = role.members

            if ctx_type == self.ContextTypes.Context:
                tracker = await ctx.reply(f"Removed role from **0/{len(members)}** members")
            else:
                await ctx.response.send_message(f"Removed role from **0/{len(members)}** members")
                tracker = await ctx.original_message()

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

            if ctx_type == self.ContextTypes.Context:
                await tracker.delete()

            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Operation completed!",
                                                               desc=f"Successfully removed {role.mention} from **{done}** members"
                                                                    + ("" if done == len(members) else f" ({len(members) - done} failed)")
                                                                    + (
                                                                        "" if fail == 0 else f" ({fail} already had {role.mention} removed, but not by the bot)"))
            return

        await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Nothing to do!", desc="Nobody has this role!")

    @unbox_context
    async def addall(self, ctx_type: ContextTypes, author: discord.User | discord.Member, ctx: commands.Context | discord.Interaction, ref_role: discord.Role | str,
                     add_role: discord.Role | str) -> None:
        """
        Handler for the addall commands.
        """

        if type(ref_role) is not discord.Role:
            ref_role = await self.find_closest_role(ctx, ref_role, verbosity=Verbosity.ALL)
            if len(ref_role) > 1:
                return
            ref_role = ref_role[0]

        if type(add_role) is not discord.Role:
            add_role = await self.find_closest_role(ctx, add_role, verbosity=Verbosity.ALL)
            if len(add_role) > 1:
                return
            add_role = add_role[0]

        if ref_role == add_role:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Why would we do that then",
                                                             desc="Try again with 2 different roles!")
            return

        if not len(ref_role.members):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Nothing to do!",
                                                             desc="Nobody has this role!")
            return

        members = ref_role.members

        if ctx_type == self.ContextTypes.Context:
            tracker = await ctx.reply(f"Added role to **0/{len(members)}** members")
        else:
            await ctx.response.send_message(f"Added role to **0/{len(members)}** members")
            tracker = await ctx.original_message()

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

        if ctx_type == self.ContextTypes.Context:
            await tracker.delete()
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Operation completed!",
                                                           desc=f"Successfully added {add_role.mention} to **{done}** members with {ref_role.mention} "
                                                                + ("" if done == len(members) else f" ({len(members) - done} failed)")
                                                                + (
                                                                    "" if fail == 0 else f" ({fail} already had {add_role.mention})"))

    async def clear(self, ctx: commands.Context | discord.Interaction, member: discord.Member) -> None:
        """
        Handler for the clear commands.
        """

        if not ctx.guild.me.guild_permissions.manage_roles:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Couldn't remove roles!",
                                                             desc="Please give me **Manage Roles** permissions")
            return

        if len(member.roles) == 1:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "No roles were removed!",
                                                                   desc=f"{member.mention} already has no roles!")
            return

        fail = []

        roles = member.roles[1:]
        for i in range(len(roles)):
            try:
                if await self.manage_roles_check(ctx, "remove", role=roles[i],
                                                 verbosity=Verbosity.SILENT) == 0:  # Then no errors will occur
                    await member.remove_roles(roles[i], reason=f"Requested by {ctx.author}")
                else:
                    fail.append(roles[i].name)
            except errors.NotFound:
                fail.append("Unavailable role")
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Roles removed successfully!",
                                                           desc=f"All roles have been removed from {member.mention}" + (
                                                               f" except for **{(', '.join(fail[:len(fail) - 1]) + f' and {fail[len(fail) - 1]}') if len(fail) > 1 else fail[0]}**, which could not be removed." if fail else ""))
