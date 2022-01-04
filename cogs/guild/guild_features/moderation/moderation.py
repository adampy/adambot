import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.ext.commands import has_permissions
from discord.utils import get
from datetime import datetime, timedelta
from libs.misc.decorators import is_dev, is_staff
from libs.misc.utils import get_user_avatar_url


class Moderation(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.bot.tasks.register_task_type("unmute", self.handle_unmute)
        await self.bot.tasks.register_task_type("unban", self.handle_unban)

    async def get_member_obj(self, ctx: commands.Context, member: discord.Member) -> list[discord.Member, bool] | list[None, None]:
        """
        Attempts to get user/member object from mention/user ID.
        Independent of whether the user is a member of a shared guild
        Perhaps merge with utils function
        """

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
    async def is_user_banned(ctx: commands.Context, user: discord.User) -> bool:
        try:
            await ctx.guild.fetch_ban(user)
        except discord.NotFound:
            return False
        return True

    # -----------------------CLOSE COMMAND-----------------------

    @commands.command(pass_context=True, name="close", aliases=["die", "yeet"])
    @commands.guild_only()
    @is_dev
    async def botclose(self, ctx: commands.Context) -> None:
        await self.bot.close(ctx)

    # -----------------------PURGE------------------------------

    @commands.command(pass_context=True)
    @commands.has_permissions(
        manage_messages=True)  # TODO: Perhaps make it possible to turn some commands, like purge, off
    async def purge(self, ctx: commands.Context, limit: str = '5', member: discord.Member = None) -> None:
        """
        Purges the channel.
        Usage: `purge 50`
        """

        channel = ctx.channel

        if limit.isdigit():
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

                    await ctx.send("The amount of messages cannot be more than 100 when deleting a single users messages. Messages older than 14 days also cannot be deleted this way.")

            await ctx.send(f"Purged **{len(deleted)}** messages!", delete_after=3)

            channel_id = await self.bot.get_config_key(ctx, "mod_log_channel")
            if channel_id is None:
                return
            channel = self.bot.get_channel(channel_id)

            embed = Embed(title='Purge', color=Colour.from_rgb(175, 29, 29))
            embed.add_field(name='Count', value=f"{len(deleted)}")
            embed.add_field(name='Channel', value=ctx.channel.mention)
            embed.add_field(name='Staff member', value=ctx.author.mention)
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await channel.send(embed=embed)
        else:
            await ctx.send(f'Please use an integer for the amount of messages to delete, not `{limit}` :ok_hand:')

    # -----------------------KICK------------------------------

    @commands.command(pass_context=True)
    @has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, args: str = "") -> None:
        """
        Kicks a given user.
        Kick members perm needed
        """

        if ctx.me.top_role < member.top_role:
            await ctx.send(f"Can't ban {member.mention}, they have a higher role than the bot!")
            return

        reason = None
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"]

        if not reason:
            reason = f'No reason provided'

        try:  # perhaps add some like `attempt_dm` thing in utils instead of this?
            await member.send(f"You have been kicked from {ctx.guild} ({reason})")
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(f"Could not DM {member.display_name} about their kick!")

        await member.kick(reason=reason)
        await ctx.send(f'{member.mention} has been kicked :boot:')

        channel_id = await self.bot.get_config_key(ctx, "mod_log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        embed = Embed(title='Kick', color=Colour.from_rgb(220, 123, 28))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Reason', value=reason + f" (kicked by {ctx.author.name})")
        embed.set_thumbnail(url=get_user_avatar_url(member, mode=1)[0])
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    # -----------------------BAN------------------------------

    @commands.command(pass_context=True, aliases=["hackban", "massban"])
    @has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member | str, *, args: str = "") -> None:
        """
        Bans a given user.
        Merged with previous command hackban
        Single bans work with user mention or user ID
        Mass bans work with user IDs currently, reason flag HAS to be specified if setting
        Ban members perm needed
        """

        if not ctx.me.guild_permissions.ban_members:
            await ctx.send("Can't do that sorry :(")
            return

        invites = await ctx.guild.invites()
        reason = "No reason provided"
        massban = (ctx.invoked_with == "massban")
        timeperiod = tracker = None

        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"],
                                                              blank_as_flag="reason" if not massban else None)
            timeperiod = parsed_args["time"]
            reason = parsed_args["reason"]

        if massban:
            members = ctx.message.content[ctx.message.content.index(" ") + 1:].split(" ")
            members = [member for member in members if len(member) == 18 and str(member).isnumeric()]
            # possibly rearrange at some point to allow checking if the member/user object can be obtained?
            tracker = await ctx.send(f"Processed bans for 0/{len(members)} members")
        else:
            members = [member]
        already_banned = []
        not_found = []
        ban = 0
        for ban, member_ in enumerate(members, start=1):
            if massban:
                await tracker.edit(content=f"Banning {ban}/{len(members)} users" + (
                    f", {len(not_found)} users not found" if len(not_found) > 0 else "") + (
                                               f", {len(already_banned)} users already banned" if len(
                                                   already_banned) > 0 else "")
                                   )

            if type(member_) is not discord.Member:
                member, in_guild = await self.get_member_obj(ctx, member_)
            else:
                member = member_
                in_guild = True

            if in_guild:
                if ctx.me.top_role < member.top_role:
                    await ctx.send(f"Can't ban {member.mention}, they have a higher role than the bot!")
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
                    await ctx.send(f"Couldn't find that user ({member_})!")
                    return
                else:
                    continue
            if await self.is_user_banned(ctx, member):
                already_banned.append(member.mention)
                if not massban:
                    await ctx.send(f"{member.mention} is already banned!")
                    return
                else:
                    continue
            try:
                await member.send(f"You have been banned from {ctx.guild.name} ({reason})")
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(f"Could not DM {member.id} about their ban!")
            await ctx.guild.ban(member, reason=reason, delete_message_days=0)
            if not massban:
                await ctx.send(f'{member.mention} has been banned.')

            channel_id = await self.bot.get_config_key(ctx, "mod_log_channel")
            if channel_id is None:
                return
            channel = self.bot.get_channel(channel_id)

            embed = Embed(title='Ban' if in_guild else 'Hackban', color=Colour.from_rgb(255, 255, 255))
            embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
            embed.add_field(name='Moderator', value=str(ctx.author))
            embed.add_field(name='Reason', value=reason)
            embed.set_thumbnail(url=get_user_avatar_url(member, mode=1)[0])
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))

            await channel.send(embed=embed)
        if massban:
            # chr(10) used for \n since you can't have backslash characters in f string fragments
            await tracker.edit(content=f"Processed bans for {ban}/{len(members)} users" +
                                       (
                                           f"\n__**These users weren't found**__:\n\n - {f'{chr(10)} - '.join(f'{a_not_found}' for a_not_found in not_found)}\n" if len(
                                               not_found) > 0 else ""
                                       ) +
                                       (
                                           f"\n__**These users are already banned**__:\n\n - {f'{chr(10)} - '.join(f'{a_already_banned}' for a_already_banned in already_banned)}" if len(
                                               already_banned) > 0 else ""
                                       )
                               )

    async def handle_unban(self, data: dict, reason: str = "", author: str = "", ctx: commands.Context = None) -> None:
        try:
            user = self.bot.get_user(data["member_id"])
            if not user and ctx:
                user, in_guild = await self.get_member_obj(ctx, data["member_id"])
                if not user:
                    return
            guild = self.bot.get_guild(data["guild_id"])
            await guild.unban(user, reason=reason)
            channel_id = await self.bot.get_config_key(ctx, "mod_log_channel")
            if channel_id is None:
                return
            channel = self.bot.get_channel(channel_id)

            embed = Embed(title='Unban', color=Colour.from_rgb(76, 176, 80))
            embed.add_field(name='User', value=f'{user.mention} ({user.id})')
            embed.add_field(name='Moderator', value=str(self.bot.user if not author else author))
            embed.add_field(name='Reason', value=reason)
            embed.set_thumbnail(url=get_user_avatar_url(user)[0])
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await channel.send(embed=embed)
        except Exception as e:
            print(e)
            pass  # go away!

    @commands.command(pass_context=True)
    @has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, member: discord.User | str, *, args: str = "") -> None:
        """
        Unbans a given user with the ID.
        Ban members perm needed.
        """

        reason = "No reason provided"
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"]

        if type(member) is not discord.User:
            member, in_guild = await self.get_member_obj(ctx, member)

        if member is None:
            await ctx.send("Couldn't find that user!")
            return

        if not await self.is_user_banned(ctx, member):
            await ctx.send(f'{member.mention} is not already banned.')
            return

        await self.handle_unban({"member_id": member.id, "guild_id": ctx.guild.id}, reason=reason, author=ctx.author,
                                ctx=ctx)
        await ctx.send(f'{member.mention} has been unbanned!')

    # -----------------------MUTES------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Method to reinforce mutes in cases where Discord permissions cause problems
        Blameth discordeth foreth thiseth codeth
        """

        if type(message.channel) == discord.DMChannel or type(message.author) == discord.User:
            return

        try:
            muted_role = await self.bot.get_config_key(message, "muted_role")
            if muted_role is not None and muted_role in [role.id for role in message.author.roles]:
                await message.delete()
        except discord.NotFound:
            pass  # Message can't be deleted (nobody cares)
        except KeyError:
            pass  # Bot not fully loaded yet (nobody cares)

    @commands.command(pass_context=True)
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, *, args: str = "") -> None:
        """
        Gives a given user the Muted role.
        Manage roles perm needed.
        """

        role = get(member.guild.roles, id=await self.bot.get_config_key(member, "muted_role"))
        if not role:
            await ctx.send(":x: No muted role has been set!")
            return
        if role in member.roles:
            await ctx.send(f":x: **{member}** is already muted! Unmute them and mute them again to change their mute")
            return
        reason, timeperiod = None, None
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"], blank_as_flag="reason")
            timeperiod = parsed_args["time"]
            reason = parsed_args["reason"]

            if timeperiod:
                await self.bot.tasks.submit_task("unmute", datetime.utcnow() + timedelta(seconds=timeperiod),
                                                 extra_columns={"member_id": member.id, "guild_id": member.guild.id})
        await member.add_roles(role, reason=reason if reason else f'No reason - muted by {ctx.author.name}')
        await ctx.send(f':ok_hand: **{member}** has been muted')
        # 'you are muted ' + timestring
        if not timeperiod:
            timestring = 'indefinitely'
        else:
            time = (self.bot.correct_time() + timedelta(seconds=timeperiod))  # + timedelta(hours = 1)
            timestring = 'until ' + time.strftime('%H:%M on %d/%m/%y')

        if not reason or reason is None:
            reasonstring = 'an unknown reason (the staff member did not give a reason)'
        else:
            reasonstring = reason
        try:
            await member.send(f'You have been muted {timestring} for {reasonstring}.')
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(f"Could not DM {member.display_name} about their mute!")

        channel_id = await self.bot.get_config_key(ctx, "mod_log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        embed = Embed(title='Member Muted', color=Colour.from_rgb(172, 32, 31))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Moderator', value=str(ctx.author))
        embed.add_field(name='Reason', value=reason)
        embed.add_field(name='Expires',
                        value=timestring.replace('until ', '') if timestring != 'indefinitely' else "Never")
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

    @commands.command(pass_context=True)
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, args: str = "") -> None:
        """
        Removes Muted role from a given user.
        Manage roles perm needed.
        """

        reason = ""
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"]
        reason = reason if reason else f'No reason - unmuted by {ctx.author.name}'

        await self.handle_unmute({"member_id": member.id, "guild_id": member.guild.id}, reason=reason)
        await ctx.send(f':ok_hand: **{member}** has been unmuted')

    # -----------------------SLOWMODE------------------------------

    @commands.command(pass_context=True)
    async def slowmode(self, ctx: commands.Context, time: str) -> None:
        """
        Adds slowmode in a specific channel. Time is given in seconds.
        """

        if not ctx.channel.permissions_for(ctx.author).manage_channels:
            await ctx.send("You do not have permissions for that :sob:")
            return

        if time.isdigit():
            if int(time) <= 60:
                await ctx.channel.edit(slowmode_delay=int(time))
                if int(time) == 0:
                    await ctx.send(':ok_hand: slowmode removed from this channel.')
                else:
                    await ctx.send(f':ok_hand: Slowmode of {time} seconds added.')
            else:
                await ctx.send('You cannot add a slowmode greater than 60.')

        else:
            await ctx.send('You must specify a whole number of seconds')

    # -----------------------JAIL & BANISH------------------------------

    @commands.command(pass_context=True)
    @commands.has_permissions(manage_roles=True)
    async def jail(self, ctx: commands.Context, member: discord.Member) -> None:
        """
        Lets a member view whatever channel has been set up with view channel perms for the Jail role.
        Manage roles perm needed.
        """

        role_id = await self.bot.get_config_key(ctx, "jail_role")
        if role_id is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "No jail role has been set")
            return

        role = ctx.guild.get_role(role_id)
        await member.add_roles(role)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{member.display_name} has been jailed.")

    @commands.command(pass_context=True)
    @commands.has_permissions(manage_roles=True)
    async def unjail(self, ctx: commands.Context, member: discord.Member) -> None:
        """
        Removes the Jail role.
        Manage roles perm needed.
        """

        role_id = await self.bot.get_config_key(ctx, "jail_role")
        if role_id is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "No jail role has been set")
            return

        role = get(member.guild.roles, name='Jail')
        await member.remove_roles(role)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{member.display_name} has been unjailed.")

    # -----------------------MISC------------------------------

    @commands.command()
    @is_staff
    async def say(self, ctx: commands.Context, channel: discord.TextChannel, *, text: str) -> None:
        """
        Say a given string in a given channel
        Staff role needed.
        """

        await channel.send(text[5:] if text.startswith("/tts") else text,
                            tts=text.startswith("/tts ") and channel.permissions_for(ctx.author).send_tts_messages)

    @commands.command(pass_context=True)
    @commands.has_permissions(manage_guild=True)
    async def revokeinvite(self, ctx: commands.Context, invite_code: str) -> None:
        """
        Command that revokes an invite from a server
        """

        try:
            await self.bot.delete_invite(invite_code)
            await ctx.send(f"Invite code {invite_code} has been deleted :ok_hand:")
        except discord.Forbidden:
            await ctx.send("Adam-Bot does not have permissions to revoke invites.")
        except discord.NotFound:
            await ctx.send("Invite code was not found - it's either invalid or expired :sob:")
        except Exception as e:
            await ctx.send(f"Invite revoking failed: {e}")


def setup(bot) -> None:
    bot.add_cog(Moderation(bot))
