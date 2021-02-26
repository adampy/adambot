import discord
from discord.ext import commands
#from discord.ext.commands import MemberConverter, UserConverter
from discord.utils import get
from discord import Embed, Colour
import os
import asyncpg
import datetime
from .utils import Permissions, ordinal, Embed, EmbedPages, PageTypes, send_file, get_spaced_member, GCSE_SERVER_ID
import matplotlib.pyplot as plt
import matplotlib

class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key = os.environ.get('DATABASE_URL')

    async def get_valid_name(self, member: discord.Member):
        return member.name if member.nick is None else member.nick


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
        return ctx.guild.id == GCSE_SERVER_ID

#-----------------------REP COMMANDS------------------------------

    @commands.group()
    @commands.guild_only()
    async def rep(self, ctx, *args):
        """Reputation module"""
        if not args:
            await ctx.send('To award rep to someone, type \n`-rep Member_Name`\nor\n`-rep @Member`\n'
                           'Pro tip: If e.g. fred roberto was recently active you can type `-rep fred`')

        wanted_command = filter(lambda cmd: cmd.name == args[0], self.rep.commands)[0] # Get all commands with the same name as that requested, and retreive first index
        if not wanted_command:
            await ctx.invoke(self.bot.get_command("rep award"), *args)
        else:
            await ctx.invoke(wanted_command, *args)

    @rep.error
    async def rep_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You cannot award rep in this server!")
        else:
            await ctx.send("Oopsies something went wrong with that!")

##    @rep.command()
##    @commands.guild_only()
##    async def help(self, ctx):
##        await ctx.send('```-rep award @Member``` or ```-rep leaderboard```')

    @rep.command(aliases=['give', 'point'])
    @commands.guild_only()
    async def award(self, ctx, *args):
        """Gives the member a reputation point. Aliases are give and point"""
        author_nick = await self.get_valid_name(ctx.author)
        if len(args) == 0:  # check so -rep award doesn't silently fail when no string given
            user = ctx.author
        else:
            user = await get_spaced_member(ctx, args, self.bot)
            if user is None:
                await ctx.send(embed=Embed(title=f':x:  Sorry {author_nick} we could not find that user!', color=Colour.from_rgb(255, 7, 58)))
                return
        nick = await self.get_valid_name(user)

        if ctx.author != user and not user.bot:  # check to not rep yourself and that user is not a bot
            reps = await self.modify_rep(user, 1)

            user_embed = Embed(title=f':white_check_mark:  {nick} received a reputation point!', color=Colour.from_rgb(57,255,20))
            user_embed.add_field(name='_ _', value=f'{user.mention} now has {reps} reputation points!')
            user_embed.set_thumbnail(url=user.avatar_url)
            user_embed.set_footer(text=f"Awarded by: {author_nick} ({ctx.author})\n" + (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).strftime('%A %d/%m/%Y %H:%M:%S'))
            await ctx.send(embed=user_embed)
            
            embed = Embed(title='Reputation Points', color=Colour.from_rgb(177,252,129))
            embed.add_field(name='From', value=f'{str(ctx.author)} ({ctx.author.id})')
            embed.add_field(name='To', value=f'{str(user)} ({user.id})')
            embed.add_field(name='New Rep', value=reps)
            embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%A %d/%m/%Y %H:%M:%S'))
            await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

        else:
            if user.bot:
                fail_text = "The bot overlords do not accept puny humans' rewards"
            else:
                fail_text = "You cannot rep yourself, cheating bugger."
            embed = Embed(title=f':x: Failed to award a reputation point to {nick}!', color=Colour.from_rgb(255,7,58))
            embed.add_field(name='_ _', value=fail_text)
            embed.set_footer(text=(datetime.datetime.utcnow() - datetime.timedelta(hours=1)).strftime('%A %d/%m/%Y %H:%M:%S'))
            embed.set_thumbnail(url=user.avatar_url)
            await ctx.send(embed=embed)

    @rep.command(aliases=['lb'])
    @commands.guild_only()
    async def leaderboard(self, ctx, modifier=''):
        """Displays the leaderboard of reputation points, if [modifier] is 'members' then it only shows current server members"""
        if modifier.lower() in ['members', 'member']:
            await self.get_leaderboard(ctx, only_members=True)
        else:
            await self.get_leaderboard(ctx, only_members=False)

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
        """Resets a single users reps."""
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
        """Resets everyones reps."""
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
    @commands.has_any_role(*Permissions.ASSISTANT)
    async def set(self, ctx, user: discord.User, rep):
        """Sets a specific members reps to a given value."""
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
    @commands.has_any_role(*Permissions.ASSISTANT)
    async def hardset(self, ctx, user_id, rep):
        """Sets a specific member's reps to a given value via their ID."""
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
    async def check(self, ctx, *args):
        """Checks a specific person reps, or your own if user is left blank"""
        if len(args) == 0:
            user = ctx.author
        else:
            user = await get_spaced_member(ctx, args, self.bot)
            if user is None:
                await ctx.send(embed=Embed(title=f':x:  Sorry {ctx.author.display_name} we could not find that user!', color=Colour.from_rgb(255, 7, 58)))
                return
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
        embed = Embed(title=f'Rep info for {user.display_name} ({user})', color=Colour.from_rgb(139, 0, 139))
        # could change to user.colour at some point, I prefer the purple for now though
        embed.add_field(name='Rep points', value=rep)
        embed.add_field(name='Leaderboard position', value=ordinal(lb_pos) if lb_pos else 'Nowhere :(')
        embed.set_footer(text=f"Requested by {ctx.author.display_name} ({ctx.author})\n" + (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).strftime('%A %d/%m/%Y %H:%M:%S'))
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)
        #await ctx.send(f'{user.mention} {f"is **{ordinal(lb_pos)}** on the reputation leaderboard with" if lb_pos else "has"} **{rep}** reputation points. {"They are not yet on the leaderboard because they have no reputation points." if (not lb_pos or rep == 0) else ""}')


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
