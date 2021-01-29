import discord
from discord import Embed, Colour
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.utils import get
import asyncio
from .utils import separate_args, Permissions, EmbedPages, PageTypes
from datetime import datetime, timedelta
import os
import asyncpg
from math import ceil

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def timer(self, todo, seconds, member_id):
        '''Writes to todo table with the time to perform the given todo (e.g. timer(4, 120) would mean 4 is carried out in 120 seconds)'''
        timestamp = datetime.utcnow()
        new_timestamp = timestamp + timedelta(seconds=seconds)
        async with self.bot.pool.acquire() as connection:
            await connection.execute('INSERT INTO todo (todo_id, todo_time, member_id) values ($1, $2, $3)', todo, new_timestamp, member_id)

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
        for i in range(len(years)-1):
            year = years[i]
            if 'Post-GCSE' in roles:
                if print:
                    await ctx.send('Cannot advance this user: they are Post-GCSE already.')
                return 'postgcse error'
            elif year in roles:
                await member.remove_roles(get(member.guild.roles, name=year))
                await member.add_roles(get(member.guild.roles, name=years[i+1]))
                if print:
                    await ctx.send(':ok_hand: The year has been advanced!')
                return 'success'

    def is_bot_owner(ctx):
        return ctx.message.author.id == 394978551985602571

    def bot_owner_or_permissions(**perms):
        '''Checks if bot owner or has perms'''
        original = commands.has_permissions(**perms).predicate
        async def extended_check(ctx):
            if ctx.guild is None:
                return False
            return 394978551985602571 == ctx.author.id or await original(ctx)
        return commands.check(extended_check)

#-----------------------ADAM-BOT DEV ROLE-----------------------
    
    @commands.command(pass_context=True)
    @commands.check(is_bot_owner)
    async def dev(self, ctx, member: discord.Member, *args):
        '''Toggles Adam-Bot Developer role to the specified user.
Requires bot owner.'''
        role = get(member.guild.roles, name='Adam-Bot Developer')
        if 'Adam-Bot Developer' in [x.name for x in member.roles]:
            await member.remove_roles(role)
            await ctx.send('Removed dev from `{0}`!'.format(member.mention))
        else:
            await member.add_roles(role)
            await ctx.send('Added dev to `{0}`!'.format(member.mention))

#-----------------------PURGE------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MOD)
    async def purge(self, ctx, limit='5', member: discord.Member = None):
        '''Purges the channel.
Moderator role needed.
Usage: `-purge 50`'''
        channel = ctx.channel
        author = ctx.author

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
                    await ctx.send("The amount of messages cannot be more than 100 when deleting a single users messages. Messages older than 14 days also cannot be deleted this way.")

            message = await ctx.send(f"Purged **{len(deleted)}** messages!", delete_after=3)

            embed = Embed(title='Purge', color=Colour.from_rgb(175, 29, 29))
            embed.add_field(name='Count', value=len(deleted))
            embed.add_field(name='Channel', value=channel.mention)
            embed.set_footer(text=(datetime.utcnow()-timedelta(hours=1)).strftime('%x'))
            await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)
        else:
            await ctx.send(f'Please use an integer for the amount of messages to delete, not `{limit}` :ok_hand:')

#-----------------------KICK------------------------------

    @commands.command(pass_context=True)
    @has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *args):
        '''Kicks a given user.
Staff role needed'''
        if args:
            timeperiod, reason = separate_args(args)
            if not reason:
                reason = f'No reason - kicked by {str(ctx.author)}'
            #if timeperiod:
            #    await self.timer(1, timeperiod, member.id)
        else:
            reason = None

        await member.kick(reason=reason)
        await ctx.send(f'{member.mention} has been kicked :boot:')

        embed = Embed(title='Kick', color=Colour.from_rgb(220, 123, 28))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Reason', value=reason)
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=(datetime.utcnow()-timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

#-----------------------BAN------------------------------

    @commands.command(pass_context=True)
    @has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *args):
        '''Bans a given user.
Moderator role needed'''
        if args:
            timeperiod, reason = separate_args(args)
            if not reason:
                reason = f'No reason - banned by {str(ctx.author)}'
            if timeperiod:
                await self.timer(2, timeperiod, member.id)
        else:
            reason = None

        await member.ban(reason=reason, delete_message_days=0)
        emoji = get(ctx.message.guild.emojis, name="banned")
        await ctx.send(f'{member.mention} has been banned. {emoji}')

        embed = Embed(title='Ban', color=Colour.from_rgb(255, 255, 255))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Moderator', value=str(ctx.author))
        embed.add_field(name='Reason', value=reason)
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=(datetime.utcnow()-timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @commands.command(pass_context=True)
    @has_permissions(ban_members=True)
    async def hackban(self, ctx, user_id, *args):
        '''Bans a given user.
Moderator role needed'''
        if args:
            timeperiod, reason = separate_args(args)
            if not reason:
                reason = f'No reason - banned by {str(ctx.author)}'
            if timeperiod:
                await self.timer(2, timeperiod, member.id)
        else:
            reason = None

        await member.ban(reason=reason, delete_message_days=0)
        emoji = get(ctx.message.guild.emojis, name="banned")
        await ctx.send(f'{member.mention} has been banned. {emoji}')

        embed = Embed(title='Hackban', color=Colour.from_rgb(255, 255, 255))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Moderator', value=str(ctx.author))
        embed.add_field(name='Reason', value=reason)
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=(datetime.utcnow()-timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @commands.command(pass_context=True)
    @has_permissions(ban_members=True)
    async def unban(self, ctx, user_id, *args):
        '''Unbans a given user with the ID.
Moderator role needed.'''
        if args:
            timeperiod, reason = separate_args(args)
            if not reason:
                reason = f'No reason - unbanned by {ctx.author.name}'
            #if timeperiod:
            #    await self.timer(1, timeperiod, member.id)
        else:
            reason = None

        try:
            user = await self.bot.fetch_user(user_id)
        except discord.errors.NotFound:
            await ctx.send('No user found with that ID.')
            return

        bans = await ctx.guild.bans()
        bans = [be.user for be in bans]
        if user not in bans:
            await ctx.send('That user is not already banned.')
            return

        await ctx.guild.unban(user, reason=reason)
        await ctx.send('The ban has been revoked.')

        embed = Embed(title='Unban', color=Colour.from_rgb(76, 176, 80))
        embed.add_field(name='Member', value=f'{member.mention} ({member.id})')
        embed.add_field(name='Moderator', value=str(ctx.author))
        embed.add_field(name='Reason', value=reason)
        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=(datetime.utcnow()-timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

#-----------------------MUTES------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def mute(self, ctx, member: discord.Member, *args):
        '''Gives a given user the Muted role.
Staff role needed.'''
        if args:
            timeperiod, reason = separate_args(args)
            if timeperiod:
                await self.timer(1, timeperiod, member.id)
        else:
            reason, timeperiod = None, None

        role = get(member.guild.roles, name='Muted')
        await member.add_roles(role, reason=reason if reason else 'No reason - muted by {}'.format(ctx.author.name))
        await ctx.send(':ok_hand:')
        #'you are muted ' + timestring
        if not timeperiod:
            timestring = 'indefinitely'
        else:
            time = (datetime.utcnow() + timedelta(seconds = timeperiod)) + timedelta(hours = 1)
            timestring = 'until ' + time.strftime('%H:%M on %d/%m/%y')

        if not reason or reason is None:
            reasonstring = 'an unknown reason (the staff member did not give a reason)'
        else:
            reasonstring = reason

        await member.send(f'You have been muted {timestring} for {reasonstring}.')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def unmute(self, ctx, member: discord.Member, *args):
        '''Removes Muted role from a given user.
Staff role needed.'''
        if args:
            timeperiod, reason = separate_args(args)
        else:
            reason = None

        role = get(member.guild.roles, name='Muted')
        await member.remove_roles(role, reason=reason if reason else 'No reason - unmuted by {}'.format(ctx.author.name))
        await ctx.send(':ok_hand:')

#-----------------------SLOWMODE------------------------------

    @commands.command(pass_context=True)
    async def slowmode(self, ctx, time, *args):
        '''Adds slowmode in a specific channel. Time is given in seconds.
Moderator role needed.
Assistants have permission in #general only.'''
        if ('Assistant' in [str(y) for y in ctx.author.roles] and 'general' == ctx.channel.name) or 'Moderator' in [str(y) for y in ctx.author.roles] or (ctx.guild.id == 593134700122472450 and 'Administrators' in [y.name for y in ctx.author.roles]):
            try:
                if int(time) <= 60:
                    await ctx.channel.edit(slowmode_delay=int(time))
                    if int(time) == 0:
                        await ctx.send(':ok_hand: slowmode removed from this channel.')
                    else:
                        await ctx.send(f':ok_hand: Slowmode of {time}seconds added.')
                else:
                    await ctx.send('You cannot add a slowmode greater than 60.')
            except Exception as e:
                print(e)


#-----------------------JAIL & BANISH------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def jail(self, ctx, member: discord.Member):
        '''Puts a member in #the-court.
Staff role needed.'''
        role = get(member.guild.roles, name='Jail')
        await member.add_roles(role)
        await ctx.send(f':ok_hand: {member.mention} has been jailed.')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def unjail(self, ctx, member: discord.Member):
        '''Puts a member in #the-court.
Staff role needed.'''
        try:
            role = get(member.guild.roles, name='Jail')
            await member.remove_roles(role)
            await ctx.send(f':ok_hand: {member.mention} has been unjailed.')
        except Exception as e:
            await ctx.send(f'{member.mention} could not be unjailed. Please do it manually.')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def banish(self, ctx, member: discord.Member):
        '''Removes all roles from a user, rendering them powerless.
Staff role needed.'''
        await member.edit(roles=[])
        await ctx.send(f':ok_hand: {member.mention} has been banished.')

#-----------------------ADVANCEMENT------------------------------

    @commands.group(pass_context=True)
    @commands.guild_only()
    async def advance(self, ctx):
        '''Results day command.
Y11 -> Post-GCSE
Y10 -> Y11
Y9 -> Y10'''
        if ctx.invoked_subcommand is None:
            await ctx.send('```-advance member @Member``` or ```-advance all```')

    @advance.command(pass_context=True)
    @commands.has_any_role(*Permissions.MOD)
    async def memberx(self, ctx, member: discord.Member):
        '''Advances one user.
Moderator role needed.'''
        try:
            await self.advance_user(ctx, member)
            await ctx.send(':ok_hand: the year has been advanced.')
        except Exception as e:
            ctx.send('''Unexpected error...
```{}```'''.format(e))

    @advance.command(pass_context=True)
    @commands.has_any_role(*Permissions.ADMIN)
    async def allx(self, ctx):
        '''Advances everybody in the server.
Administrator role needed.'''
        msg = await ctx.send('Doing all, please wait...')
        members = ctx.guild.members #everyone
        errors = []

        n = len(members)
        for i, member in enumerate(members):
            try:
                advance = await self.advance_user(ctx, member)
                if advance != 'success' or advance != 'postgcse error':
                    errors.append([member, advance])
                await msg.edit(content=f"Doing all, please wait... currently on {i+1}/{n}")
            except Exception as e:
                errors.append([member, f'unexpected: {e}'])

        await ctx.send('Advanced everyone\'s year!')
        for error in errors:
            log_channel = get(ctx.guild.text_channels, name='adambot-logs')
            await log_channel.send(f'{error[0].mention} = {error[1]}')

    #@all.error
    #async def all_handler(self, ctx, error):
    #    if isinstance(error, commands.CheckFailure):
    #        await ctx.send('`Administrator` role needed.')

#-----------------------WARNS------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def warn(self, ctx, member: discord.Member, *reason):
        '''Gives a member a warning, a reason is optional but recommended.
Staff role needed.'''
        key = os.environ.get('DATABASE_URL')

        reason = ' '.join(reason)
        reason = reason.replace('-r', '') # Removes -r if a staff member includes it
        if len(reason) > 255:
            await ctx.send('The reason must be below 256 characters. Please shorten it before trying again.')
            return
        
        warns = 0
        async with self.bot.pool.acquire() as connection:
            await connection.execute('INSERT INTO warn (member_id, staff_id, reason) values ($1, $2, $3)', member.id, ctx.author.id, reason)
            warns = await connection.fetchval('SELECT COUNT(*) FROM warn WHERE member_id = ($1)', member.id)

        await ctx.send(f':ok_hand: {member.mention} has been warned. They now have {warns} warns')
        try:
            await member.send(f'You have been warned by a member of the staff team. The reason for your warn is: {reason}. You now have {warns} warns.')
        except Exception as e:
            print(e)

    @commands.group()
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def warnlist(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('```-warnlist member @Member <page_number>``` or ```warnlist all <page_number>```')
            return

    async def warnlist_member(self, ctx, member, page_num = 1):
        '''Handle gettings the warns for a specific member'''
        warns = []
        async with self.bot.pool.acquire() as connection:
            warns = await connection.fetch('SELECT * FROM warn WHERE member_id = ($1) ORDER BY id', member.id)

        if len(warns) > 0:
            embed = EmbedPages(PageTypes.WARN, warns, "Warnings", Colour.from_rgb(177,252,129), self.bot, ctx.author)
            await embed.set_page(int(page_num))
            await embed.send(ctx.channel)
        else:
            await ctx.send("No warnings recorded!")

    @warnlist.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def member(self, ctx, member: discord.Member = None, page_num = 1):
        '''Shows warnings for a given member.
Staff role needed.'''
        if member == None:
            await ctx.send("```-warnlist member @Member <page_number>```")
        else:
            await self.warnlist_member(ctx, member, page_num)

    @warnlist.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def me(self, ctx, page_num = 1):
        '''Shows warnings for yourself.
Member role needed.'''
        await self.warnlist_member(ctx, ctx.author, page_num)

    @warnlist.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def all(self, ctx, page_num = 1):
        '''Shows all the warnings in the server.
Staff role needed.'''
        warns = []
        async with self.bot.pool.acquire() as connection:
            warns = await connection.fetch('SELECT * FROM warn ORDER BY id')

        if len(warns) > 0:
            embed = EmbedPages(PageTypes.WARN, warns, "Warnings", Colour.from_rgb(177,252,129), self.bot, ctx.author)
            await embed.set_page(int(page_num))
            await embed.send(ctx.channel)
        else:
            await ctx.send("No warnings recorded!")

    @commands.command(pass_context=True, aliases=['warndelete'])
    @commands.has_any_role(*Permissions.MOD)
    @commands.guild_only()
    async def warnremove(self, ctx, *warnings):
        '''Remove warnings with this command, can do -warnremove <warnID> or -warnremove <warnID1> <warnID2>.
Moderator role needed'''

        if warnings[0].lower() == 'all':
            async with self.bot.pool.acquire() as connection:
                await connection.execute('DELETE FROM warn')
            await ctx.send("All warnings have been removed.")


        if len(warnings) > 1:
            await ctx.send('One moment...')

        async with self.bot.pool.acquire() as connection:
            for warning in warnings:
                try:
                    warning = int(warning)
                    await connection.execute('DELETE FROM warn WHERE id = ($1)', warning)
                    if len(warnings) == 1:
                        await ctx.send(f'Warning with ID {warning} has been deleted.')
                except ValueError:
                    await ctx.send(f'Error whilst deleting ID {warning}: give me a warning ID, not words!')

        if len(warnings) > 1:
            await ctx.send(f"The warning's have been deleted.")

#-----------------------MISC------------------------------

    @commands.command(aliases=['announce'])
    @commands.has_any_role(*Permissions.STAFF)
    async def say(self, ctx, channel: discord.TextChannel, *text):
        '''Say a given string in a given channel
Staff role needed.'''
        await channel.send(' '.join(text))

    @commands.command()
    @commands.check(is_bot_owner)
    async def reset_invites(self, ctx):
        '''A command for adam only which resets the invites'''
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

                    await connection.execute('INSERT INTO invites (inviter, code, uses, max_uses, created_at, max_age) values ($1, $2, $3, $4, $5, $6)', **data)
                except:
                    pass




def setup(bot):
    bot.add_cog(Moderation(bot))
