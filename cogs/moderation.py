import discord
from discord import Embed, Colour
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.utils import get
import asyncio
from .utils import separate_args
from datetime import datetime, timedelta
import os
import psycopg2

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        key = os.environ.get('DATABASE_URL')

        self.conn = psycopg2.connect(key, sslmode='require')
        self.cur = self.conn.cursor()

    def timer(self, todo, seconds, member_id):
        '''Writes to todo table with the time to perform the given todo (e.g. timer(4, 120) would mean 4 is carried out in 120 seconds)'''
        timestamp = datetime.utcnow()
        new_timestamp = timestamp + timedelta(seconds=seconds)
        self.cur.execute('INSERT INTO todo (todo_id, todo_time, member_id) values (%s, %s, %s)', (todo, new_timestamp, member_id))
        self.conn.commit()

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

#-----------------------PURGE------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role('Moderator', 'Abdulministrators')
    async def purge(self, ctx, limit='5', member: discord.Member = None):
        '''Purges the channel.
Moderator role needed.
Usage: `-purge 50`'''
        channel = ctx.channel
        author = ctx.author

        if limit.isdigit():
            await ctx.message.delete()
            deleted = await channel.purge(limit=int(limit))
            message = await ctx.send(f"Purged **{len(deleted)}** messages!")
            
            embed = Embed(title='Purge', color=Colour.from_rgb(175, 29, 29))
            embed.add_field(name='Count', value=len(deleted))
            embed.add_field(name='Channel', value=channel.mention)
            embed.set_footer(text=(datetime.utcnow()-timedelta(hours=1)).strftime('%x'))
            await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)
            await asyncio.sleep(5)
            await message.delete()

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
            if timeperiod:
                self.timer(1, timeperiod, member.id)
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
    @commands.has_any_role('Moderator', 'Abdulministrators')
    async def ban(self, ctx, member: discord.Member, *args):
        '''Bans a given user.
Moderator role needed'''
        if args:
            timeperiod, reason = separate_args(args)
            if not reason:
                reason = f'No reason - banned by {str(ctx.author)}'
            if timeperiod:
                self.timer(1, timeperiod, member.id)
        else:
            reason = None

        await member.ban(reason=reason)
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
    @commands.has_any_role('Moderator', 'Abdulministrators')
    async def unban(self, ctx, user_id, *args):
        '''Unbans a given user with the ID.
Moderator role needed.'''
        if args:
            timeperiod, reason = separate_args(args)
            if not reason:
                reason = f'No reason - unbanned by {ctx.author.name}'
            if timeperiod:
                self.timer(1, timeperiod, member.id)
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
    @commands.has_role('Staff')
    async def mute(self, ctx, member: discord.Member, *args):
        '''Gives a given user the Muted role.
Staff role needed.'''
        if args:
            timeperiod, reason = separate_args(args)
            if timeperiod:
                self.timer(1, timeperiod, member.id)
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
    @commands.has_role('Staff')
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
        if ('Assistant' in [str(y) for y in ctx.author.roles] and 'general' == ctx.channel.name) or 'Moderator' in [str(y) for y in ctx.author.roles] or (ctx.guild.id == 593134700122472450 and 'Abdulministrators' in [y.name for y in ctx.author.roles]):
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
    @has_permissions(manage_roles=True)
    async def jail(self, ctx, member: discord.Member):
        '''Puts a member in #the-court.
Staff role needed.'''
        role = get(member.guild.roles, name='Jail')
        await member.add_roles(role)
        await ctx.send(f':ok_hand: {member.mention} has been jailed.')

    @commands.command(pass_context=True)
    @has_permissions(manage_roles=True)
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
    @has_permissions(manage_roles=True)
    async def banish(self, ctx, member: discord.Member):
        '''Removes all roles from a user, rendering them powerless.
Staff role needed.'''
        await member.edit(roles=[])
        await ctx.send(f':ok_hand: {member.mention} has been banished.')

#-----------------------ADVANCEMENT------------------------------

    @commands.group()
    async def advance(self, ctx):
        '''Results day command.
Y11 -> Post-GCSE
Y10 -> Y11
Y9 -> Y10'''
        if ctx.invoked_subcommand is None:
            await ctx.send('```-advance member @Member``` or ```-advance all```')

    @advance.command(pass_context=True)
    @commands.has_role('Moderator')
    async def member(self, ctx, member: discord.Member):
        '''Advances one user.
Moderator role needed.'''
        try:
            await self.advance_user(ctx, member)
            await ctx.send(':ok_hand: the year has been advanced.')
        except Exception as e:
            ctx.send('''Unexpected error...
```{}```'''.format(e))

    @advance.command(pass_context=True)
    @commands.has_role('Administrator')
    async def all(self, ctx):
        '''Advances everybody in the server.
Administrator role needed.'''
        await ctx.send('Doing all, please wait...')
        members = ctx.guild.members #everyone
        errors = []
        for member in members:
            try:
                advance = await self.advance_user(ctx, member)
                if advance != 'success' or advance != 'postgcse error':
                    errors.append([member, advance])
            except Exception as e:
                errors.append([member, 'unexpected'])
        
        await ctx.send('Advanced everyone\'s year! Errors are as follows...')
        for error in errors:
            await ctx.send(f'{error[0].mention} = {error[1]}')

    @all.error
    async def all_handler(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send('`Administrator` role needed.')

#-----------------------WARNS------------------------------

    @commands.command(pass_context=True)
    @commands.has_role('Staff')
    @commands.guild_only()
    async def warn(self, ctx, member: discord.Member, *reason):
        key = os.environ.get('DATABASE_URL')

        reason = ' '.join(reason)
        conn = psycopg2.connect(key, sslmode='require')
        cur = conn.cursor()
        if len(reason) > 255:
            await ctx.send('The reason must be below 256 characters. Please shorten it before trying again.')
            return
        cur.execute('INSERT INTO warn (member_id, staff_id, reason) values (%s, %s, %s); SELECT COUNT(*) FROM warn WHERE member_id = (%s)', (member.id, ctx.author.id, reason, member.id))
        conn.commit()
        warns = cur.fetchall()[0][0]
        conn.close()
        
        await member.send(f'You have been warned by a member of the staff team. The reason for your warn is: {reason}. You now have {warns} warns.')
        await ctx.send(f':ok_hand: {member.mention} has been warned. They now have {warns} warns')

    @commands.command(pass_context=True)
    @commands.has_role('Staff')
    @commands.guild_only()
    async def warnlist(self, ctx, member: discord.User = None, *reason: str):
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'), sslmode='require')
        cur = conn.cursor()

        if member is None:
            #show all
            cur.execute('SELECT * FROM warn')
            warns = cur.fetchall()
            if len(warns) > 25: #need multiple embeds
                await ctx.send('More than 25 fields; contact Adam.')
            elif len(warns) == 0:
                await ctx.send('No warnings!')
            else:
                embed = Embed(title='All warnings', color=Colour.from_rgb(133,0,255))
                for warn in warns:
                    staff = self.bot.get_user(warn[2])
                    member = self.bot.get_user(warn[1])
                    embed.add_field(name=f"**{warn[0]}** : {str(member)} ({member.id}) Reason: {warn[4]}",
                                    value=f"On {warn[3].strftime('%B %d at %I:%M %p')} by {str(staff)} ({staff.id})")
            try:
                await ctx.send(embed=embed)
            except Exception as e:
                pass
            conn.close()

        else:
            #specific to one member
            cur.execute('SELECT * FROM warn WHERE member_id = (%s) ORDER BY id', (member.id,))
            warns = cur.fetchall()
            if len(warns) > 25: #need multiple embeds
                for warn in warns:
                    await ctx.send(f'{warn[0]} - {warn[1]} - {warn[4]}')
            elif len(warns) == 0:
                await ctx.send(f'{member.mention} has no warnings!')
            else:
                embed = Embed(title=f"{member.name if member else '*MEMBER NOT FOUND*'}'s warnings", color=Colour.from_rgb(133,0,255))
                for warn in warns:
                    staff = self.bot.get_user(warn[2])
                    member = self.bot.get_user(warn[1])
                    embed.add_field(name=f"**{warn[0]}** : {str(member)} ({member.id}) Reason: {warn[4]}",
                                    value=f"On {warn[3].strftime('%B %d at %I:%M %p')} by {str(staff)} ({staff.id})")
            try:
                await ctx.send(embed=embed)
            except Exception as e:
                pass
            conn.close()

    @commands.command(pass_context=True, aliases=['warndelete'])
    @commands.has_role('Moderator')
    @commands.guild_only()
    async def warnremove(self, ctx, *warnings):
        key = os.environ.get('DATABASE_URL')

        conn = psycopg2.connect(key, sslmode='require')
        cur = conn.cursor()

        if warnings[0].lower() == 'all':
            cur.execute('DELETE FROM warn')
        else:
            if len(warnings) > 1:
                await ctx.send('One moment...')
            for warning in warnings:
                try:
                    warning = int(warning)
                    cur.execute('DELETE FROM warn WHERE id = (%s)', (warning,))
                    if len(warnings) == 1:
                        await ctx.send(f'Warning with ID {warning} has been deleted.')
                except ValueError:
                    await ctx.send(f'Error whilst deleting ID {warning}: give me a warning ID, not words!')
        conn.commit()
        conn.close()
        if len(warnings) > 1:
            await ctx.send(f"The warning's have been deleted.")

    @commands.command(aliases=['announce'])
    @has_permissions(ban_members=True)
    async def say(self, ctx, channel: discord.TextChannel, *text):
        await channel.send(' '.join(text))
        



def setup(bot):
    bot.add_cog(Moderation(bot))
