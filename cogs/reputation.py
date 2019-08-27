import discord
from discord.ext import commands
from discord.utils import get
from discord import Embed, Colour
import os
import psycopg2
import datetime

class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key = os.environ.get('DATABASE_URL')

    def get_leaderboard(self, ctx):
        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()
        cur.execute('SELECT * FROM rep ORDER BY reps DESC LIMIT 10')
        leaderboard = cur.fetchall()
        conn.close()
        embed = Embed(title='**__Reputation Leaderboard__**', color=Colour.from_rgb(177,252,129))
        for item in leaderboard:
            embed.add_field(name=f"{ctx.guild.get_member(item[0])}", value=f"{item[1]}", inline=False)

        return embed

    def modify_rep(self, member, change):
        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()

        cur.execute('SELECT reps FROM rep WHERE member_id = (%s)', (member.id, ))
        reps = cur.fetchall()
        if not reps:
            cur.execute('INSERT INTO rep (reps, member_id) VALUES (%s, %s)', (change, member.id))
            reps = change
        else:
            cur.execute('UPDATE rep SET reps = (%s) WHERE member_id = (%s);SELECT reps FROM rep WHERE member_id = (%s)', (reps[0][0]+change, member.id, member.id))
            reps = cur.fetchall()[0][0]

        conn.commit()
        conn.close()
        return reps
    
    def clear_rep(self, member):
        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()
        cur.execute('UPDATE rep SET reps = 0 WHERE member_id = (%s)', (member.id,))
        conn.commit()
        conn.close()

    def in_gcse(ctx):
        return ctx.guild.id == 445194262947037185

#-----------------------REP COMMANDS------------------------------

    @commands.group()
    @commands.guild_only()
    async def rep(self, ctx):
        '''Reputation module'''
        if ctx.invoked_subcommand is None:
            await ctx.send('```-rep award @Member``` or ```-rep leaderboard```')

    @rep.error
    async def rep_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You cannot award rep in this server ***yet***!")

    @rep.command()
    @commands.guild_only()
    async def award(self, ctx, member: discord.Member, change = 1):
        if ctx.author != member: #check to not rep yourself
            try:
                change = int(change)
            except ValueError:
                await ctx.send('Please choose a valid number!')
                return
            if 'Moderator' in [y.name for y in ctx.author.roles]:
                reps = self.modify_rep(member, change)
            else:
                reps = self.modify_rep(member, 1)
            await ctx.send(f'{member.mention} now has {reps} reputation points!')
            
            embed = Embed(title='Reputation Points', color=Colour.from_rgb(177,252,129))
            embed.add_field(name='From', value=f'{str(ctx.author)} ({ctx.author.id})')
            embed.add_field(name='To', value=f'{str(member)} ({member.id})')
            embed.add_field(name='New Rep', value=reps)
            embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
            await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)
        else:
            await ctx.send('You cannot rep yourself, cheating bugger.')

    @rep.command(aliases=['lb'])
    @commands.guild_only()
    async def leaderboard(self, ctx):
        await ctx.send(embed=self.get_leaderboard(ctx))

    @rep.group()
    @commands.guild_only()
    @commands.has_role('Moderator')
    async def reset(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('```-rep reset member @Member``` or ```-rep reset all```')

    @reset.command()
    @commands.has_role('Moderator')
    @commands.guild_only()
    async def member(self, ctx, member: discord.Member):
        self.clear_rep(member)
        await ctx.send(f'{member.mention} now has 0 points.')
        embed = Embed(title='Reputation Points Reset', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=str(member))
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @reset.command(pass_context=True)
    @commands.guild_only()
    @commands.has_role('Moderator')
    async def all(self, ctx):
        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()
        cur.execute('DELETE FROM rep')
        conn.commit()
        conn.close()
        await ctx.send('Done. Everyone now has 0 points.')
        embed = Embed(title='Reputation Points Reset', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value='**EVERYONE**')
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @rep.command()
    @commands.guild_only()
    @commands.has_role('Moderator')
    async def set(self, ctx, member: discord.Member, rep):
        try:
            rep = int(rep)
        except ValueError:
            await ctx.send('The rep must be a number!')
            return

        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()
        cur.execute('UPDATE rep SET reps = (%s) WHERE member_id = (%s); SELECT reps FROM rep WHERE member_id = (%s)', (rep, member.id, member.id))
        reps = cur.fetchall()[0][0]
        conn.commit()
        conn.close()
        await ctx.send(f'{member.mention} now has {rep} reputation points.')
        embed = Embed(title='Reputation Points Set', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=str(member))
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.add_field(name='New Rep', value=reps)
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @rep.command()
    @commands.guild_only()
    async def check(self, ctx, member: discord.Member):
        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()
        cur.execute('SELECT reps FROM rep WHERE member_id = (%s)', (member.id,))
        rep = cur.fetchall()
        if not rep:
            rep = 0
        else:
            rep = rep[0][0]

        conn.close()
        await ctx.send(f'{member.mention} has {rep} reputation points.')

            



def setup(bot):
    bot.add_cog(Reputation(bot))
