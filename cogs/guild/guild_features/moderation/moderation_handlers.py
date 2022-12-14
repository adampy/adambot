from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import Embed, Colour, app_commands
from discord.ext import commands
from discord.utils import get

from adambot import AdamBot
from libs.misc.handler import CommandHandler
from libs.misc.utils import ContextTypes, get_user_avatar_url

from re import sub

class ModerationHandlers(CommandHandler):
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.ContextTypes = self.bot.ContextTypes

    async def get_member_obj(self, ctx: commands.Context | discord.Interaction, member: str | discord.Member) -> tuple[Optional[discord.Member], Optional[bool]]:
        """
        Attempts to get user/member object from mention/user ID.
        Independent of whether the user is a member of a shared guild
        Perhaps merge with utils function
        """

        if type(ctx) is discord.Interaction:
            ctx = await self.bot.interaction_context(self.bot, ctx)

        in_guild = True
        try:
            member = await commands.MemberConverter().convert(ctx, member)  # converts mention to member object
        except Exception:
            try:  # assumes id
                member = str(member).replace("<@!", "").replace(">", "")
                # fix for funny issue with mentioning users that aren't guild members
                member = await self.bot.fetch_user(member)
                # gets object from id, seems to work for users not in the server
                in_guild = False
            except Exception:
                return None, None

        return member, in_guild

    @staticmethod
    async def is_user_banned(ctx: commands.Context | discord.Interaction, user: discord.Member | discord.User) -> bool:
        try:
            await ctx.guild.fetch_ban(user)
        except discord.NotFound:
            return False
        return True

    async def botclose(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the shutdown commands.
        """

        await self.bot.shutdown(ctx)

    async def purge(self, ctx: commands.Context | discord.Interaction, limit: str | int = 5,
                    member: discord.Member = None) -> None:
        """
        Handler for the purge commands.
        """

        (ctx_type, author) = self.command_args
        channel = ctx.channel

        if (type(limit) is str and limit.isdigit()) or type(limit) is int:
            if ctx_type == self.ContextTypes.Context:
                await ctx.message.delete()
            if not member:
                deleted = await channel.purge(limit=int(limit))

            else:
                deleted = []
                try:
                    async for message in channel.history():
                        if len(deleted) == int(limit):
                            break
                        if message.author == member:
                            deleted.append(message)
                    await ctx.channel.delete_messages(deleted)
                except discord.ClientException:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                     "Invalid number of messages provided!",
                                                                     desc="The amount of messages cannot be more than 100 when deleting a single users messages. Messages older than 14 days also cannot be deleted this way.",
                                                                     respond_to_interaction=False)

            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Successfully purged messages!",
                                                               desc=f"Purged **{len(deleted)}** messages!")

            channel_id = await self.bot.get_config_key(ctx, "log_channel")
            if channel_id is None:
                return
            channel = self.bot.get_channel(channel_id)

            embed = Embed(title="Purge", color=Colour.from_rgb(175, 29, 29))
            embed.add_field(name="Count", value=f"{len(deleted)}")
            embed.add_field(name="Channel", value=ctx.channel.mention)
            embed.add_field(name="Staff member", value=author.mention)
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await channel.send(embed=embed)
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid number of messages provided!",
                                                             desc=f"Please use an integer for the amount of messages to delete, not `{limit}` :ok_hand:")

    async def kick(self, ctx: commands.Context | discord.Interaction, member: str | discord.Member,
                   reason: str = "No reason provided", args: str = "") -> None:
        """
        Handler for the kick commands.
        """

        (ctx_type, author) = self.command_args
        if ctx.guild.me.top_role < member.top_role:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not kick member!",
                                                             desc=f"Can't kick {member.mention}, they have a higher role than the bot!")
            return

        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"] if parsed_args["reason"] and reason == "No reason provided" else reason

        if reason is None:
            reason = "No reason provided"
    
        try:  # perhaps add some like `attempt_dm` thing in utils instead of this?
            await member.send(f"You have been kicked from {ctx.guild} ({reason})")
        except (discord.Forbidden, discord.HTTPException):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not DM member!",
                                                             desc=f"Could not DM {member.display_name} about their kick!",
                                                             respond_to_interaction=False)

        await member.kick(reason=reason)

        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Successfully kicked member!",
                                                           desc=f"{member.mention} has been kicked :boot:")

        channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        embed = Embed(title="Kick", color=Colour.from_rgb(220, 123, 28))
        embed.add_field(name="Member", value=f"{member.mention} ({member.id})")
        embed.add_field(name="Reason", value=reason + f" (kicked by {author.name})")
        embed.set_thumbnail(url=get_user_avatar_url(member, mode=1)[0])
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    async def ban(self, ctx: commands.Context | discord.Interaction, members: str | discord.Member,
                  reason: str = "No reason provided", timeperiod: str = None) -> None:
        """
        Handler for the ban commands.
        """

        (ctx_type, author) = self.command_args
        if not ctx.guild.me.guild_permissions.ban_members:
            await self.bot.DefaultEmbedResponses(self.bot, ctx, "Could not proceed with the ban!",
                                                 desc="I don't have permissions to ban members in this server!")
            return

        tracker = None
        invites = await ctx.guild.invites()
        if type(members) is str:
            all_members = members.split(" ")
            all_members = [member.replace("<@", "").replace("!", ""). replace(">", "") for member in all_members]
            all_members = [member for member in all_members if len(str(member)) == 18 and str(member).isnumeric()]
        else:
            all_members = [members]

        if ctx_type == self.ContextTypes.Context:
            massban = ctx.invoked_with == "massban"
        else:
            massban = len(all_members) > 1

        if type(members) is str and ctx_type == self.ContextTypes.Context:  # parsing is only needed in the classic command#
            args_without_members = sub("<@!?[0-9]{17,18}>", "", members) # Use REGEX to remove all user mentions from the args for parsing purposes
            parsed_args = self.bot.flag_handler.separate_args(args_without_members, fetch=["time", "reason"],
                                                              blank_as_flag="reason" if not massban else "")
            timeperiod = parsed_args["time"] if not timeperiod else timeperiod
            timeperiod: int = self.bot.time_arg(timeperiod) if timeperiod else None
            reason = parsed_args["reason"] if parsed_args["reason"] and reason == "No reason provided" else reason

        if massban:
            message = f"Processed bans for 0/{len(members)} members"
            if ctx_type == self.ContextTypes.Context:
                tracker = await ctx.send(message)
            else:
                await ctx.response.send_message(message)
                tracker = await ctx.original_message()

        already_banned = []
        not_found = []
        could_not_notify = []
        ban = 0
        for ban, member_ in enumerate(all_members, start=1):
            if massban:
                message = f"Banning {ban}/{len(members)} users" + (
                    f", {len(not_found)} users not found" if len(not_found) > 0 else "") + (
                              f", {len(already_banned)} users already banned" if len(
                                  already_banned) > 0 else "")
                await tracker.edit(content=message)

            member: discord.Member  # analysis gets confused so type clarification
            if type(member_) is not discord.Member:
                member, in_guild = await self.get_member_obj(ctx, member_)
            else:
                member = member_
                in_guild = True

            if in_guild:
                if ctx.guild.me.top_role < member.top_role:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not ban user!",
                                                                     desc=f"Can't ban {member.mention}, they have a higher role than the bot!",
                                                                     respond_to_interaction=False)
                    continue

            for invite in invites:
                if invite.inviter.id == member.id:
                    await ctx.invoke(self.bot.get_command("revokeinvite"), invite_code=invite.code)
            if timeperiod:
                await self.bot.tasks.submit_task("unban", datetime.utcnow() + timedelta(seconds=timeperiod),
                                                 extra_columns={"member_id": member.id, "guild_id": ctx.guild.id})
            if not member:
                not_found.append(member_)
                if not massban:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not ban user",
                                                                     desc=f"Couldn't find that user ({member_})!")
                    return
                else:
                    continue
                    
            if await self.is_user_banned(ctx, member):
                already_banned.append(member.mention)
                if not massban:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not ban user",
                                                                     desc=f"{member.mention} is already banned!")
                    return
                else:
                    continue
            try:
                await member.send(f"You have been banned from {ctx.guild.name} ({reason})")
            except (discord.Forbidden, discord.HTTPException):
                if not massban:
                    await ctx.channel.send(f"Could not DM {member.mention} ({member.id}) about their ban!")
                else:
                    could_not_notify.append(member)

            await ctx.guild.ban(member, reason=reason, delete_message_days=0)
            if not massban:
                await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Successfully banned user!",
                                                                   desc=f"{member.mention} has been banned.")

            channel_id = await self.bot.get_config_key(ctx, "log_channel")
            if channel_id is None:
                return
            channel = self.bot.get_channel(channel_id)

            embed = Embed(title="Ban" if in_guild else "Hackban", color=Colour.from_rgb(255, 255, 255))
            embed.add_field(name="Member", value=f"{member.mention} ({member.id})")
            embed.add_field(name="Moderator", value=str(author))
            embed.add_field(name="Reason", value=reason)
            embed.set_thumbnail(url=get_user_avatar_url(member, mode=1)[0])
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))

            await channel.send(embed=embed)

        if massban:
            # chr(10) used for \n since you can't have backslash characters in f string fragments
            message = (
                    f"Processed bans for {ban}/{len(members)} users" +
                    (
                        f"\n__**These users weren't found**__:\n\n - {f'{chr(10)} - '.join(f'{a_not_found}' for a_not_found in not_found)}\n" if len(
                            not_found) > 0 else ""
                    ) +
                    (
                        f"\n__**These users are already banned**__:\n\n - {f'{chr(10)} - '.join(f'{a_already_banned}' for a_already_banned in already_banned)}" if len(
                            already_banned) > 0 else ""
                    ) +
                    (
                        f"\n__**These users couldn't be DMed about their ban**__:\n\n - {f'{chr(10)} - '.join(f'{a_unnotified}' for a_unnotified in could_not_notify)}" if len(
                            could_not_notify) > 0 else ""
                    )
            )

            await tracker.edit(content=message)

    async def handle_unban(self, data: dict, reason: str = "", author: discord.Member | str = "",
                           ctx: commands.Context | discord.Interaction = None) -> None:
        try:
            user = self.bot.get_user(data["member_id"])
            if not user and ctx:
                user, in_guild = await self.get_member_obj(ctx, data["member_id"])
                if not user:
                    return
            guild = self.bot.get_guild(data["guild_id"])
            await guild.unban(user, reason=reason)
            channel_id = await self.bot.get_config_key(ctx, "log_channel")
            if channel_id is None:
                return
            channel = self.bot.get_channel(channel_id)

            embed = Embed(title="Unban", color=Colour.from_rgb(76, 176, 80))
            embed.add_field(name="User", value=f"{user.mention} ({user.id})")
            embed.add_field(name="Moderator", value=str(self.bot.user if not author else author))
            embed.add_field(name="Reason", value=reason)
            embed.set_thumbnail(url=get_user_avatar_url(user)[0])
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await channel.send(embed=embed)
        except Exception:
            pass  # go away!

    async def unban(self, ctx: commands.Context | discord.Interaction, member: str, args: str = None,
                    reason: str = "No reason provided") -> None:
        """
        Handler for the unban commands.
        """

        (ctx_type, author) = self.command_args
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"] if parsed_args["reason"] and reason == "No reason provided" else reason

        if type(member) is not discord.User:
            member, in_guild = await self.get_member_obj(ctx, member)

        if member is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not unban user!",
                                                             desc="Couldn't find that user!")
            return

        if not await self.is_user_banned(ctx, member):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not unban user!",
                                                             desc=f"{member.mention} is not already banned.")
            return

        await self.handle_unban({"member_id": member.id, "guild_id": ctx.guild.id}, reason=reason, author=author,
                                ctx=ctx)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Unbanned member successfully!",
                                                           desc=f"{member.mention} has been unbanned!")

    async def slowmode(self, ctx_type: ContextTypes, author: discord.User | discord.Member, ctx: commands.Context | discord.Interaction, time: str | int) -> None:
        """
        Handler for the slowmode commands.
        """

        if not ctx.channel.permissions_for(author).manage_channels:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not add a slowmode here!",
                                                             desc="You do not have permissions for that :sob:")
            return

        if (type(time) is str and time.isdigit()) or type(time) is int:
            if int(time) <= 60:
                await ctx.channel.edit(slowmode_delay=int(time))
                if int(time) == 0:
                    await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Slowmode removed successfully!",
                                                                       desc=":ok_hand: slowmode removed from this channel.")
                else:
                    await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Slowmode added successfully!",
                                                                       desc=f":ok_hand: Slowmode of {time} seconds added.")
            else:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not add a slowmode here!",
                                                                 desc="You cannot add a slowmode greater than 60.")

        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not add a slowmode here!",
                                                             desc="You must specify a whole number of seconds!")

    async def say(self, ctx: commands.Context | discord.Interaction,
                  channel: discord.TextChannel | discord.Thread | app_commands.AppCommandThread, text: str):
        """
        Handler for the say commands.
        """

        (ctx_type, author) = self.command_args
        await channel.send(text[5:] if text.startswith("/tts") else text,
                           tts=text.startswith("/tts ") and channel.permissions_for(author).send_tts_messages)

        if type(ctx) is discord.Interaction:
            await ctx.response.send_message(":ok_hand:")  # interactions need a response else they're marked as failed

    async def jail(self, ctx: commands.Context | discord.Interaction, member: discord.Member | discord.User) -> None:
        """
        Handler for the jail commands.
        """

        role_id = await self.bot.get_config_key(ctx, "jail_role")
        if role_id is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "No jail role has been set")
            return

        role = ctx.guild.get_role(role_id)
        await member.add_roles(role)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{member.display_name} has been jailed.")

    async def unjail(self, ctx: commands.Context | discord.Interaction, member: discord.Member | discord.User) -> None:
        """
        Handler for the unjail commands.
        """

        role_id = await self.bot.get_config_key(ctx, "jail_role")
        if role_id is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "No jail role has been set")
            return

        role = get(member.guild.roles, name="Jail")
        await member.remove_roles(role)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{member.display_name} has been unjailed.")

    async def revokeinvite(self, ctx: commands.Context | discord.Interaction, invite_code: str) -> None:
        """
        Handler for the revokeinvite commands.
        """

        try:
            await self.bot.delete_invite(invite_code)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Invite deleted successfully!",
                                                               desc=f"Invite code {invite_code} has been deleted :ok_hand:")
        except discord.Forbidden:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not delete invite!",
                                                             desc="Adam-Bot does not have permissions to revoke invites.")
        except discord.NotFound:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not delete invite!",
                                                             desc="Invite code was not found - it's either invalid or expired :sob:")
        except Exception as e:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not delete invite!",
                                                             desc=f"Invite revoking failed: {e}")

    async def mute(self, ctx: commands.Context | discord.Interaction, member: discord.Member,
                   reason: str = "No reason provided!", timeperiod: int | str = "", args: str = "") -> None:
        """
        Handler for the mute commands.
        """

        (ctx_type, author) = self.command_args
        role = get(member.guild.roles, id=await self.bot.get_config_key(member, "muted_role"))
        if not role:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not mute member!",
                                                             desc=":x: No muted role has been set!")
            return
        if role in member.roles:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not mute member!",
                                                             desc=f":x: **{member}** is already muted! Unmute them and mute them again to change their mute")
            return

        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"], blank_as_flag="reason")
            timeperiod = parsed_args["time"] if not timeperiod else timeperiod
            reason = parsed_args["reason"] if parsed_args["reason"] and reason == "No reason provided!" else reason

        if timeperiod:
            timeperiod = self.bot.time_arg(timeperiod) if type(timeperiod) is str else timeperiod
            await self.bot.tasks.submit_task("unmute", datetime.utcnow() + timedelta(seconds=timeperiod),
                                             extra_columns={"member_id": member.id, "guild_id": member.guild.id})
        await member.add_roles(role, reason=reason if reason else f"No reason - muted by {author.name}")
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Successfully muted member!",
                                                           desc=f":ok_hand: **{member}** has been muted")

        # "you are muted " + timestring
        if not timeperiod:
            timestring = "indefinitely"
        else:
            time = (self.bot.correct_time() + timedelta(seconds=timeperiod))  # + timedelta(hours = 1)
            timestring = "until " + time.strftime("%H:%M on %d/%m/%y")

        if not reason or reason is None:
            reasonstring = "an unknown reason (the staff member did not give a reason)"
        else:
            reasonstring = reason
        try:
            await member.send(f"You have been muted {timestring} for {reasonstring}.")
        except (discord.Forbidden, discord.HTTPException):
            await ctx.channel.send(f"Could not DM {member.display_name} about their mute!")

        channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        embed = Embed(title="Member Muted", color=Colour.from_rgb(172, 32, 31))
        embed.add_field(name="Member", value=f"{member.mention} ({member.id})")
        embed.add_field(name="Moderator", value=author)
        embed.add_field(name="Reason", value=reasonstring)
        embed.add_field(name="Expires",
                        value=timestring.replace("until ", "") if timestring != "indefinitely" else "Never")
        embed.set_thumbnail(url=get_user_avatar_url(member, mode=1)[0])
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    async def handle_unmute(self, data: dict, reason: str = "") -> None:
        try:
            guild = self.bot.get_guild(data["guild_id"])
            member = guild.get_member(data["member_id"])
            role = get(guild.roles, id=await self.bot.get_config_key(guild, "muted_role"))
            await member.remove_roles(role, reason=reason)
        except Exception:
            pass  # whatever

    async def unmute(self, ctx: commands.Context | discord.Interaction, member: discord.Member,
                     reason: str = "No reason provided", args: str = "") -> None:
        """
        Handler for the unmute commands.
        """

        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"] if parsed_args["reason"] and reason == "No reason provided" else reason

        await self.handle_unmute({"member_id": member.id, "guild_id": member.guild.id}, reason=reason)

        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Successfully unmuted member!",
                                                           desc=f":ok_hand: **{member}** has been unmuted")
