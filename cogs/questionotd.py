from discord.ext import commands
import psycopg2
import datetime
from discord import Embed, Colour
from discord.utils import get
import datetime
import os
from random import choice
from math import ceil
from .utils import SPAMPING_PERMS

class QuestionOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        key = os.environ.get('DATABASE_URL')

        self.conn = psycopg2.connect(key, sslmode='require')
        self.cur = self.conn.cursor()

    def in_gcse(ctx):
        return ctx.guild.id == 445194262947037185

    def qotd_perms(ctx):
        r = [y.name for y in ctx.author.roles]
        return 'Staff' in r or 'QOTD' in r

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
    @commands.has_role('Members')
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
        self.cur.execute('SELECT * FROM qotd WHERE submitted_by = %s AND submitted_at > %s', (str(member), today_date))
        if len(self.cur.fetchall()) >= 2 and member not in SPAMPING_PERMS and not self.staff(member): #adam bypass
            await ctx.send('You can only submit 2 QOTD per day - this is to stop bot abuse.')
        else:
            self.cur.execute('INSERT INTO qotd (question, submitted_by) VALUES (%s, %s); SELECT MAX(id) FROM qotd', (qotd, member))
            id = self.cur.fetchall()[0][0]
            self.conn.commit()
            await ctx.send(f':thumbsup: Thank you for submitting your QOTD. Your QOTD ID is **{id}**.')
            
            embed = Embed(title='QOTD Submitted', color=Colour.from_rgb(177,252,129))
            embed.add_field(name='ID', value=id)
            embed.add_field(name='Author', value=ctx.author)
            embed.add_field(name='Question', value=qotd, inline=True)
            embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
            await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)

    @qotd.command(pass_context=True)
    @commands.check(qotd_perms)
    async def list(self, ctx, page_num = None):
        self.cur.execute('SELECT * FROM qotd ORDER BY id')
        qotds = self.cur.fetchall()
        aprox = ceil(len(qotds)/5)
        
        if page_num is None:
            await ctx.send(f'Please choose a number from `1` to `{aprox}`!')
            return
        else:
            try:
                page_num = int(page_num)
            except ValueError:
                await ctx.send(f'Please choose a number from `1` to `{aprox}`!')
                return

        pages = []
        while len(qotds) != 0:
            page = Embed(title=f'QOTDs Page {page_num}/{aprox}', color=Colour.from_rgb(177,252,129))
            if len(qotds) > 5:
                n = 5
            else:
                n = len(qotds)

            for i in range(n):
                question_id = qotds[0][0]
                question = qotds[0][1]
                member_id = int(qotds[0][2])
                user = get(self.bot.get_all_members(), id=member_id)
                date = (qotds[0][3]+datetime.timedelta(hours=1)).strftime('%H:%M on %d/%m/%y')
            
                page.add_field(name=f"{question_id}. {question}", value=f"{date} by {user.name if user else '*MEMBER NOT FOUND*'} ({member_id})", inline=False)
                qotds.pop(0)
            pages.append(page)

        try:
            message=await ctx.send(embed=pages[page_num - 1])
        except IndexError:
            await ctx.send(f'{page_num} is not a correct page number, please choose a number from `1` to `{aprox}`!')
        except ValueError:
            await ctx.send(f'{page_num} is not a correct page number, please choose a number from `1` to `{aprox}`!')


    @qotd.command(pass_context=True, aliases=['remove'])
    @commands.check(qotd_perms)
    async def delete(self, ctx, *question_ids):
        deleted = []
        for question_id in question_ids:
            try:
                self.cur.execute('DELETE FROM qotd WHERE id = %s', (question_id,))
                embed = Embed(title='QOTD Deleted', color=Colour.from_rgb(177,252,129))
                embed.add_field(name='ID', value=question_id)
                embed.add_field(name='Staff', value=str(ctx.author))
                embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
                await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)
                
                await ctx.send(f'QOTD ID **{question_id}** has been deleted.')
            except:
                await ctx.send(f'Error whilst deleting question ID {question_id}')
        self.conn.commit()
                        

    @qotd.command(pass_context=True, aliases=['choose'])
    @commands.check(qotd_perms)
    async def pick(self, ctx, question_id):
        if question_id.lower() == 'random':
            self.cur.execute('SELECT * FROM qotd')
        else:
            self.cur.execute('SELECT * FROM qotd WHERE id = %s', (question_id,))
        questions = self.cur.fetchall()
        if not questions:
            await ctx.send(f'Question with ID {question_id} not found. Please try again.')
            return
        else:
            question_data = choice(questions)

        question = question_data[1]
        member = await self.bot.fetch_user(question_data[2])
        message = f"**QOTD**\n{question} - Credit to {member.mention}"

        self.cur.execute('DELETE FROM qotd WHERE id = %s', (question_id,))
        self.conn.commit()

        await ctx.send(':ok_hand:')
        await get(ctx.author.guild.text_channels, name='question-of-the-day').send(message)
        
        embed = Embed(title='QOTD Picked', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='ID', value=question_data[0])
        embed.add_field(name='Author', value=str(member))
        embed.add_field(name='Question', value=question, inline=True)
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=(datetime.datetime.utcnow()-datetime.timedelta(hours=1)).strftime('%x'))
        
        await get(ctx.author.guild.text_channels, name='adambot-logs').send(embed=embed)

def setup(bot):
    bot.add_cog(QuestionOTD(bot))
