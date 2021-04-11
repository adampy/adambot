import discord
from discord import Embed, Colour
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.utils import get
import asyncio
from .utils import Permissions, EmbedPages, PageTypes, Todo, CHANNELS
from datetime import datetime, timedelta
import os
import asyncpg
from math import ceil


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_member_obj(self, member):
        """
        Attempts to get user/member object from mention/user ID.
        Independent of whether the user is a member of a shared guild
        Perhaps merge with utils function
        """
        in_guild = True
        try:
            print("Attempted member conversion")
            member = await commands.MemberConverter().convert(member)  # converts mention to member object
        except Exception:
            try:  # assumes id
                member = member.replace("<@!", "").replace(">", "")  # fix for funny issue with mentioning users that aren't guild members
                member = await self.bot.fetch_user(member)  # gets object from id, seems to work for users not in the server
                in_guild = False
            except Exception as e:
                print(e)
                return None, None
        return member, in_guild

    async def is_user_banned(self, ctx, user):
        try:
            await ctx.guild.fetch_ban(user)
        except discord.errors.NotFound:
            return False
        return True

    async def timer(self, todo, seconds, member_id):
        """Writes to todo table with the time to perform the given todo (e.g. timer(4, 120) would mean 4 is carried out in 120 seconds)"""
        timestamp = datetime.utcnow()
        new_timestamp = timestamp + timedelta(seconds=seconds)
        async with self.bot.pool.acquire() as connection:
            await connection.execute('INSERT INTO todo (todo_id, todo_time, member_id) values ($1, $2, $3)', todo,
                                     new_timestamp, member_id)

    async def advance_user(self, ctx: commands.Context, member: discord.Member, print=False):
        roles = [y.name for y in member.roles]
        years = ['Y9', 'Y10', 'Y11', 'Post-GCSE']
        total = 0
        for year in years:
            if year in roles:
                total += 1
        if total > 1:
            if print:
                await ctx.send('Cannot advance this user: they have more that 1 year role.')
            return 'multiple years'
        elif total == 0:
            if print:
                await ctx.send('Cannot advance this user: they have no year role.')
            return 'no year'
        for i in range(len(years) - 1):
            year = years[i]
            if 'Post-GCSE' in roles:
                if print:
                    await ctx.send('Cannot advance this user: they are Post-GCSE already.')
                return 'postgcse error'
            elif year in roles:
                await member.remove_roles(get(member.guild.roles, name=year))
                await member.add_roles(get(member.guild.roles, name=years[i + 1]))
                if print:
                    await ctx.send(':ok_hand: The year has been advanced!')
                return 'success'

    def is_bot_owner(ctx):
        return ctx.message.author.id == 394978551985602571

    def bot_owner_or_permissions(**perms):
        """Checks if bot owner or has perms"""
        original = commands.has_permissions(**perms).predicate

        async def extended_check(ctx):
            if ctx.guild is None:
                return False
            return 394978551985602571 == ctx.author.id or await original(ctx)

        return commands.check(extended_check)

    # -----------------------CLOSE COMMAND-----------------------

    @commands.command(pass_context=True, name="close")
    @commands.guild_only()
    @commands.has_any_role(*Permissions.DEV)
    async def botclose(self, ctx):
        await self.bot.close(ctx)

    # -----------------------ADAM-BOT DEV ROLE-----------------------

    @commands.command(pass_context=True)
    @commands.check(is_bot_owner)
    async def dev(self, ctx, member: discord.Member):
        """Toggles Adam-Bot Developer role to the specified user.
Requires bot owner."""
        role = get(member.guild.roles, name='Adam-Bot Developer')
        if 'Adam-Bot Developer' in [x.name for x in member.roles]:
            await member.remove_roles(role)
            await ctx.send('Removed dev from `{0}`!'.format(member.mention))
        else:
            await member.add_roles(role)
            await ctx.send('Added dev to `{0}`!'.format(member.mention))

    # -----------------------PURGE------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MOD)
    async def purge(self, ctx, limit='5', member: discord.Member = None):
        """Purges the channel.
Moderator role needed.
Usage: `-purge 50`"""
        channel = ctx.channel

        if limit.isdigit():
            await ctx.message.delete()
            if not member:
                deleted = await channel.purge(limit=int(limit))
            else:
                try:
                    deleted = []
                    async for message in channel.history():
                        if len(deleted) == int(limit):
                            break
                        if message.author == member:
                            deleted.append(message)
                    await ctx.channel.delete_messages(deleted)
                except discord.ClientException:
                    await ctx.send(
                        "The amount of messages cannot be more than 100 when deleting a single users messages. Messages older than 14 days also cannot be deleted this way.")

            await ctx.send(f"Purged **{len(deleted)}** messages!", delete_after=3)

            embed = Embed(title='Purge', color=Colour.from_rgb(175, 29, 29))
            embed.add_field(name='Count', value=len(deleted))
            embed.add_field(name='Channel', value=channel.mention)
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)
        else:
            await ctx.send(f'Please use an integer for the amount of messages to delete, not `{limit}` :ok_hand:')

    # -----------------------KICK------------------------------

    @commands.command(pass_context=True)
    @has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, args):
        """Kicks a given user.
Staff role needed"""
        reason = None
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"]
        if not reason:
            reason = f'No reason provided'
        try:  # perhaps add some like `attempt_dm` thing in utils instead of this?
            await member.send(f"You have been kicked from {ctx.guild} ({reason})")
        except discord.Errors.Forbidden:
            print(f"Could not DM {member.display_name} about their kick!")
        await member.kick(reason=reason)
        await ctx.send(f'{member.mention} has been kicked :boot:')

        embed = Embed(title='Kick', color=Colour.from_rgb(220, 123, 28))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Reason', value=reason + f" (kicked by {ctx.author.name})")
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    # -----------------------BAN------------------------------

    @commands.command(pass_context=True, aliases=["hackban"])
    @has_permissions(ban_members=True)
    async def ban(self, ctx, member, *, args):
        """Bans a given user.
        Merged with previous command hackban
        Works with user mention or user ID
        Moderator role needed"""
        member, in_guild = await self.get_member_obj(member)
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"], blank_as_flag="reason")
            timeperiod = parsed_args["time"]
            reason = parsed_args["reason"]

            if not reason:
                reason = f'No reason provided'
            if timeperiod:
                await self.timer(Todo.UNBAN, timeperiod, member.id)
        else:
            reason = None
        print(f"MEMBER IS TYPE {type(member).__name__}")
        if not member:
            await ctx.send("Couldn't find that user!")
            return
        if await self.is_user_banned(ctx, member):
            await ctx.send(f"{member.mention} is already banned!")
            return
        try:
            await member.send(f"You have been banned from {ctx.guild.name} ({reason})")
        except discord.Errors.Forbidden:
            print(f"Could not DM {member.id} about their ban!")
        await ctx.guild.ban(member, reason=reason, delete_message_days=0)
        await ctx.send(f'{member.mention} has been banned.')

        embed = Embed(title='Ban' if in_guild else 'Hackban', color=Colour.from_rgb(255, 255, 255))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Moderator', value=str(ctx.author))
        embed.add_field(name='Reason', value=reason)
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @commands.command(pass_context=True)
    @has_permissions(ban_members=True)
    async def unban(self, ctx, member, *, args):
        """Unbans a given user with the ID.
        Moderator role needed."""
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"]

        if not reason:
            reason = "No reason provided"
        member, in_guild = await self.get_member_obj(member)
        if not member:
            await ctx.send("Couldn't find that user!")
            return

        if not await self.is_user_banned(ctx, member):
            await ctx.send(f'{member.mention} is not already banned.')
            return

        await ctx.guild.unban(member, reason=reason)
        await ctx.send(f'{member.mention} has been unbanned!')

        embed = Embed(title='Unban', color=Colour.from_rgb(76, 176, 80))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Moderator', value=str(ctx.author))
        embed.add_field(name='Reason', value=reason)
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    # -----------------------MUTES------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def mute(self, ctx, member: discord.Member, *, args=""):
        """Gives a given user the Muted role.
Staff role needed."""
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"], blank_as_flag="reason")
            timeperiod = parsed_args["time"]
            reason = parsed_args["reason"]

            if timeperiod:
                await self.timer(Todo.UNMUTE, timeperiod, member.id)
        else:
            reason, timeperiod = None, None

        role = get(member.guild.roles, name='Muted')
        await member.add_roles(role, reason=reason if reason else 'No reason - muted by {ctx.author.name}')
        await ctx.send(':ok_hand:')
        # 'you are muted ' + timestring
        if not timeperiod:
            timestring = 'indefinitely'
        else:
            time = (datetime.utcnow() + timedelta(seconds=timeperiod))  # + timedelta(hours = 1)
            timestring = 'until ' + time.strftime('%H:%M on %d/%m/%y')

        if not reason or reason is None:
            reasonstring = 'an unknown reason (the staff member did not give a reason)'
        else:
            reasonstring = reason
        try:
            await member.send(f'You have been muted {timestring} for {reasonstring}.')
        except discord.Errors.Forbidden:
            print(f"NOTE: Could not DM {member.display_name} about their mute")

        embed = Embed(title='Member Muted', color=Colour.from_rgb(172, 32, 31))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Moderator', value=str(ctx.author))
        embed.add_field(name='Reason', value=reason)
        embed.add_field(name='Expires', value=timestring.replace('until ', '') if timestring != 'indefinitely' else "Never")
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def unmute(self, ctx, member: discord.Member, *, args=""):
        """Removes Muted role from a given user.
Staff role needed."""
        if args:

            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["reason"], blank_as_flag="reason")
            reason = parsed_args["reason"]

        else:
            reason = None

        role = get(member.guild.roles, name='Muted')
        await member.remove_roles(role,
                                  reason=reason if reason else f'No reason - unmuted by {ctx.author.name}')
        await ctx.send(':ok_hand:')

    # -----------------------SLOWMODE------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def slowmode(self, ctx, time):
        """Adds slowmode in a specific channel. Time is given in seconds.
        Staff role needed."""
        try:
            if int(time) <= 60:
                await ctx.channel.edit(slowmode_delay=int(time))
                if int(time) == 0:
                    await ctx.send(':ok_hand: slowmode removed from this channel.')
                else:
                    await ctx.send(f':ok_hand: Slowmode of {time} seconds added.')
            else:
                await ctx.send('You cannot add a slowmode greater than 60.')
        except Exception as e:
            print(e)

    # -----------------------JAIL & BANISH------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def jail(self, ctx, member: discord.Member):
        """Lets a member view whatever channel has been set up with view channel perms for the Jail role.
Staff role needed."""
        role = get(member.guild.roles, name='Jail')
        await member.add_roles(role)
        await ctx.send(f':ok_hand: {member.mention} has been jailed.')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def unjail(self, ctx, member: discord.Member):
        """Puts a member in #the-court.
Staff role needed."""
        try:
            role = get(member.guild.roles, name='Jail')
            await member.remove_roles(role)
            await ctx.send(f':ok_hand: {member.mention} has been unjailed.')
        except Exception:
            await ctx.send(f'{member.mention} could not be unjailed. Please do it manually.')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def banish(self, ctx, member: discord.Member):
        """Removes all roles from a user, rendering them powerless.
Staff role needed."""
        await member.edit(roles=[])
        await ctx.send(f':ok_hand: {member.mention} has been banished.')

    # -----------------------ADVANCEMENT------------------------------

    @commands.group(pass_context=True)
    @commands.guild_only()
    async def advance(self, ctx):
        """Results day command.
Y11 -> Post-GCSE
Y10 -> Y11
Y9 -> Y10"""
        if ctx.invoked_subcommand is None:
            await ctx.send('```-advance member @Member``` or ```-advance all```')

    @advance.command(pass_context=True)
    @commands.has_any_role(*Permissions.MOD)
    async def memberx(self, ctx, member: discord.Member):
        """Advances one user.
Moderator role needed."""
        try:
            await self.advance_user(ctx, member)
            await ctx.send(':ok_hand: the year has been advanced.')
        except Exception as e:
            ctx.send('''Unexpected error...
```{}```'''.format(e))

    @advance.command(pass_context=True)
    @commands.has_any_role(*Permissions.ADMIN)
    async def allx(self, ctx):
        """Advances everybody in the server.
Administrator role needed."""
        msg = await ctx.send('Doing all, please wait...')
        members = ctx.guild.members  # everyone
        errors = []

        n = len(members)
        for i, member in enumerate(members):
            try:
                advance = await self.advance_user(ctx, member)
                if advance != 'success' or advance != 'postgcse error':
                    errors.append([member, advance])
                await msg.edit(content=f"Doing all, please wait... currently on {i + 1}/{n}")
            except Exception as e:
                errors.append([member, f'unexpected: {e}'])

        await ctx.send('Advanced everyone\'s year!')
        for error in errors:
            log_channel = get(ctx.guild.text_channels, name='adambot-logs')
            await log_channel.send(f'{error[0].mention} = {error[1]}')

    # @all.error
    # async def all_handler(self, ctx, error):
    #    if isinstance(error, commands.CheckFailure):
    #        await ctx.send('`Administrator` role needed.')

    # -----------------------MISC------------------------------

    @commands.command()
    @commands.has_any_role(*Permissions.STAFF)
    async def say(self, ctx, channel: discord.TextChannel, *, text):
        """Say a given string in a given channel
Staff role needed."""
        await channel.send(text[5:] if text.startswith("/tts") else text, tts=text.startswith("/tts ") and channel.permissions_for(ctx.author).send_tts_messages)

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*Permissions.STAFF)
    async def announce(self, ctx, *text):
        role = ctx.guild.get_role(Permissions.ROLE_ID['Announcements'])
        msg = role.mention + " " + " ".join(text)
        if len(msg) >= 2000:
            await ctx.send(
                "The message is over 2000 characters, you must shorten it or do the announcement in multiple messages.")

        await role.edit(mentionable=True)
        channel = ctx.guild.get_channel(CHANNELS["announcements"])
        await channel.send(msg)
        await role.edit(mentionable=False)

    @commands.command()
    @commands.check(is_bot_owner)
    async def reset_invites(self, ctx):
        """A command for adam only which resets the invites"""
        invites = await ctx.guild.invites()
        async with self.bot.pool.acquire() as connection:
            await connection.execute('DELETE FROM invites')
            for invite in invites:
                try:
                    data = [invite.inviter.id,
                            invite.code,
                            invite.uses,
                            invite.max_uses,
                            invite.created_at,
                            invite.max_age]

                    await connection.execute(
                        'INSERT INTO invites (inviter, code, uses, max_uses, created_at, max_age) values ($1, $2, $3, $4, $5, $6)',
                        *data)
                except Exception:
                    pass
    
    @commands.command(pass_context = True)
    @commands.has_any_role(*Permissions.MOD)
    async def revokeinvite(self, ctx, invite_code):
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


def setup(bot):
    bot.add_cog(Moderation(bot))
