from discord.ext import commands
import asyncpg
import datetime
from discord import Embed, Colour
from discord.utils import get
import datetime
import os
from random import choice
from math import ceil
from .utils import SPAMPING_PERMS, Permissions, EmbedPages, PageTypes, CHANNELS

class QuestionOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def in_gcse(ctx):
        return ctx.guild.id == 445194262947037185

    def qotd_perms(ctx):
        r = [y.name for y in ctx.author.roles]
        return 'Staff' in r or 'QOTD' in r or 'Adam-Bot Developer' in r

    @commands.group()
    @commands.check(in_gcse)
    async def qotd(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('```-qotd submit <question>```')

    @qotd.error
    async def qotd_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("The QOTD module is not avaliable in this server!")

    @qotd.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    async def submit(self, ctx, *args):
        '''Submit a QOTD'''
        qotd = ' '.join(args)
        if len(qotd) > 255:
            await ctx.send('Question over **255** characters, please **shorten** before trying the command again.')
            return
        if not args:
            await ctx.send('```-qotd submit <question>```')
            return
        member = ctx.author.id

        today = datetime.datetime.utcnow().date()
        today_date = datetime.datetime(today.year, today.month, today.day)
        async with self.bot.pool.acquire() as connection:
            submitted_today = await connection.fetch('SELECT * FROM qotd WHERE submitted_by = ($1) AND submitted_at > ($2)', str(member), today_date)
            if len(submitted_today) >= 2 and member not in SPAMPING_PERMS and not self.staff(member): #adam bypass
                await ctx.send('You can only submit 2 QOTD per day - this is to stop bot abuse.')
            else:
                await connection.execute('INSERT INTO qotd (question, submitted_by) VALUES ($1, $2)', qotd, str(member))
                id = await connection.fetchval("SELECT MAX(id) FROM qotd")
                await ctx.send(f':thumbsup: Thank you for submitting your QOTD. Your QOTD ID is **{id}**.')
            
                embed = Embed(title='QOTD Submitted', color=Colour.from_rgb(177,252,129))
                embed.add_field(name='ID', value=id)
                embed.add_field(name='Author', value=ctx.author)
                embed.add_field(name='Question', value=qotd, inline=True)
                embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
                await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @qotd.command(pass_context=True)
    @commands.check(qotd_perms)
    async def list(self, ctx, page_num = 1):
        qotds = []
        async with self.bot.pool.acquire() as connection:
            qotds = await connection.fetch('SELECT * FROM qotd ORDER BY id')
        
        if len(qotds) > 0:
            embed = EmbedPages(PageTypes.QOTD, qotds, "QOTDs", Colour.from_rgb(177,252,129), self.bot, ctx.author)
            await embed.set_page(int(page_num))
            await embed.send(ctx.channel)
        else:
            ctx.send("No warnings recorded!")


    @qotd.command(pass_context=True, aliases=['remove'])
    @commands.check(qotd_perms)
    async def delete(self, ctx, *question_ids):
        deleted = []
        async with self.bot.pool.acquire() as connection:
            for question_id in question_ids:
                try:
                    await connection.execute('DELETE FROM qotd WHERE id = ($1)', int(question_id))
                    embed = Embed(title='QOTD Deleted', color=Colour.from_rgb(177,252,129))
                    embed.add_field(name='ID', value=question_id)
                    embed.add_field(name='Staff', value=str(ctx.author))
                    embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
                    await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)
                
                    await ctx.send(f'QOTD ID **{question_id}** has been deleted.')
                except ValueError:
                    await ctx.send("Question ID must be an integer!")
                except:
                    await ctx.send(f'Error whilst deleting question ID {question_id}')
                        

    @qotd.command(pass_context=True, aliases=['choose'])
    @commands.check(qotd_perms)
    async def pick(self, ctx, question_id):
        async with self.bot.pool.acquire() as connection:
            questions = []
            if question_id.lower() == 'random':
                questions = await connection.fetch('SELECT * FROM qotd')
            else:
                questions = await connection.fetch('SELECT * FROM qotd WHERE id = $1', int(question_id))
            if not questions:
                await ctx.send(f'Question with ID {question_id} not found. Please try again.')
                return
            else:
                question_data = choice(questions)

            question = question_data[1]
            member = await self.bot.fetch_user(question_data[2])
            message = f"**QOTD**\n{question} - Credit to {member.mention}"

            await connection.execute('DELETE FROM qotd WHERE id = ($1)', int(question_id))

        await ctx.send(':ok_hand:')
        await self.bot.get_channel(CHANNELS['qotd']).send(message)
        
        embed = Embed(title='QOTD Picked', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='ID', value=question_data[0])
        embed.add_field(name='Author', value=str(member))
        embed.add_field(name='Question', value=question, inline=True)
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        
        await get(ctx.author.guild.text_channels, name='adambot-logs').send(embed=embed)

def setup(bot):
    bot.add_cog(QuestionOTD(bot))
