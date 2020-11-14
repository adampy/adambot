import discord
from discord.ext import commands
#from discord.ext.commands import MemberConverter, UserConverter
from discord.utils import get
from discord import Embed, Colour
import os
import asyncpg
import datetime
from .utils import Permissions, ordinal, EmbedPages, PageTypes, send_file
import matplotlib.pyplot as plt
import matplotlib

class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key = os.environ.get('DATABASE_URL')

    async def get_leaderboard(self, ctx, only_members = False):
        leaderboard = []
        async with self.bot.pool.acquire() as connection:
            leaderboard = await connection.fetch('SELECT * FROM rep ORDER BY reps DESC')

        embed = EmbedPages(PageTypes.REP, leaderboard, "Reputation Leaderboard", Colour.from_rgb(177,252,129), self.bot, ctx.author)
        await embed.set_page(1) # Default first page
        await embed.send(ctx.channel)

    async def modify_rep(self, member, change):
        reps = change
        async with self.bot.pool.acquire() as connection:
            reps = await connection.fetchval("SELECT reps FROM rep WHERE member_id = ($1)", member.id)
            if not reps:
                await connection.execute('INSERT INTO rep (reps, member_id) VALUES ($1, $2)', change, member.id)
            else:
                await self.set_rep(member.id, reps+change)
                reps = reps + change

        return (reps if reps else change)
    
    async def clear_rep(self, user_id):
        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM rep WHERE member_id = ($1)", user_id)

    async def set_rep(self, user_id, reps):
        async with self.bot.pool.acquire() as connection:
            if reps == 0:
                await self.clear_rep(user_id)
                return 0
            else:
                await connection.execute("UPDATE rep SET reps = ($1) WHERE member_id = ($2)", reps, user_id)
                new_reps = await connection.fetchval("SELECT reps FROM rep WHERE member_id = ($1)", user_id)
                if not new_reps: # User was not already on the rep table, it needs adding
                    await connection.execute("INSERT INTO rep (reps, member_id) VALUES ($1, $2)", reps, user_id)
                    new_reps = reps
                return new_reps

    def in_gcse(ctx):
        return ctx.guild.id == 445194262947037185

#-----------------------REP COMMANDS------------------------------

    @commands.group()
    @commands.guild_only()
    async def rep(self, ctx):
        '''Reputation module'''
        if ctx.invoked_subcommand is None:
            await ctx.send('DefaultDan moment')

    @rep.error
    async def rep_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You cannot award rep in this server!")

##    @rep.command()
##    @commands.guild_only()
##    async def help(self, ctx):
##        await ctx.send('```-rep award @Member``` or ```-rep leaderboard```')

    @rep.command()
    @commands.guild_only()
    async def award(self, ctx, user: discord.Member, change = 1):
        '''Gives the member a rep, mods can do `-rep award @Member <change>` where change is the number of reps to be awarded'''
        if ctx.author != user: #check to not rep yourself
            try:
                change = int(change)
            except ValueError:
                await ctx.send('Please choose a valid number!')
                return
            if 'Moderator' in [y.name for y in ctx.author.roles]:
                reps = await self.modify_rep(user, change)
            else:
                reps = await self.modify_rep(user, 1)
            await ctx.send(f'{user.mention} now has {reps} reputation points!')
            
            embed = Embed(title='Reputation Points', color=Colour.from_rgb(177,252,129))
            embed.add_field(name='From', value=f'{str(ctx.author)} ({ctx.author.id})')
            embed.add_field(name='To', value=f'{str(user)} ({user.id})')
            embed.add_field(name='New Rep', value=reps)
            embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
            await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)
        else:
            await ctx.send('You cannot rep yourself, cheating bugger.')

    @rep.command(aliases=['lb'])
    @commands.guild_only()
    async def leaderboard(self, ctx, modifier=''):
        '''Displays the leaderboard of reputation points, if [modifier] is 'members' then it only shows current server members'''
        if modifier.lower() in ['members', 'member']:
            lb = await self.get_leaderboard(ctx, only_members=True)
        else:
            lb = await self.get_leaderboard(ctx, only_members=False)

        #await ctx.send(embed=lb)

    @rep.group()
    @commands.guild_only()
    @commands.has_any_role(*Permissions.MOD)
    async def reset(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('```-rep reset member @Member``` or ```-rep reset all```')

    @reset.command()
    @commands.has_any_role(*Permissions.MOD)
    @commands.guild_only()
    async def member(self, ctx, user_id):
        '''Resets a single users reps.'''
        user = await self.bot.fetch_user(user_id)
        await self.clear_rep(user.id)
        await ctx.send(f'{user.mention} now has 0 points.')
        embed = Embed(title='Reputation Points Reset', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=str(user))
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @reset.command(pass_context=True)
    @commands.guild_only()
    @commands.has_any_role(*Permissions.MOD)
    async def all(self, ctx):
        '''Resets everyones reps.'''
        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE from rep")

        await ctx.send('Done. Everyone now has 0 points.')
        embed = Embed(title='Reputation Points Reset', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value='**EVERYONE**')
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @rep.command()
    @commands.guild_only()
    @commands.has_any_role(*Permissions.MOD)
    async def set(self, ctx, user: discord.User, rep):
        '''Sets a specific members reps to a given value.'''
        try:
            rep = int(rep)
        except ValueError:
            await ctx.send('The rep must be a number!')
            return

        #user = await self.bot.fetch_user(user_id)

        new_reps = await self.set_rep(user.id, rep)
        await ctx.send(f'{user.mention} now has {new_reps} reputation points.')
        embed = Embed(title='Reputation Points Set', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=str(user))
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.add_field(name='New Rep', value=new_reps)
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @rep.command()
    @commands.guild_only()
    @commands.has_any_role(*Permissions.MOD)
    async def hardset(self, ctx, user_id, rep):
        '''Sets a specific member's reps to a given value via their ID.'''
        try:
            rep = int(rep)
        except ValueError:
            await ctx.send('The rep must be a number!')
            return

        new_reps = await self.set_rep(int(user_id), rep)

        await ctx.send(f'{user_id} now has {new_reps} reputation points.')
        embed = Embed(title='Reputation Points Set (Hard set)', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=user_id)
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.add_field(name='New Rep', value=new_reps)
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @rep.command()
    @commands.guild_only()
    async def check(self, ctx, user: discord.User = None):
        '''Checks a specific person reps, or your own if user is left blank'''
        if user is None:
            user = ctx.author
       
        rep = None
        lb_pos = None
        async with self.bot.pool.acquire() as connection:
            rep = await connection.fetchval("SELECT reps FROM rep WHERE member_id = ($1)", user.id)
            lb_pos = await connection.fetchval("""
WITH rankings as (SELECT member_id, DENSE_RANK() OVER (ORDER BY reps DESC) AS RowNum
FROM rep
ORDER BY reps DESC)

SELECT Rownum FROM rankings WHERE member_id = ($1);""", user.id)

        if not rep:
            rep = 0

        await ctx.send(f'{user.mention} {f"is **{ordinal(lb_pos)}** on the reputation leaderboard with" if lb_pos else "has"} **{rep}** reputation points. {"They are not yet on the leaderboard because they have no reputation points." if (not lb_pos or rep == 0) else ""}')


    @rep.command()
    @commands.guild_only()
    async def data(self, ctx):
        vals = []
        async with self.bot.pool.acquire() as connection:
            vals = await connection.fetch("SELECT DISTINCT reps, COUNT(member_id) FROM rep WHERE reps > 0 GROUP BY reps ORDER BY reps")

        fig, ax = plt.subplots()
        ax.plot([x[0] for x in vals], [x[1] for x in vals], 'b-o', linewidth=0.5, markersize=1)
        ax.set(xlabel='Reputation points (rep)', ylabel='Frequency (reps)', title='Rep frequency graph')
        ax.grid()
        ax.set_ylim(bottom=0)

        await send_file(fig, ctx.channel, "rep-data")



def setup(bot):
    bot.add_cog(Reputation(bot))
