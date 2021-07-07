from discord.ext import commands
import datetime
from discord import Embed, Colour
from random import choice
from math import inf
from .utils import EmbedPages, PageTypes


class QuestionOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def has_qotd_perms(self, ctx):
        """
        Method that returns true if the ctx.author has either a staff or QOTD role
        """
        qotd_role_id = self.bot.configs[ctx.guild.id]["qotd_role"]
        staff_role_id = self.bot.configs[ctx.guild.id]["staff_role"]
        for role in ctx.author.roles:
            if role.id == qotd_role_id or role.id == staff_role_id:
                return True
        return False

    @commands.group()
    async def qotd(self, ctx):
        if ctx.invoked_subcommand is None:
            p = self.bot.configs[ctx.guild.id]["prefix"]
            await ctx.send(f'```{p}qotd submit <question>```')

    @qotd.command(pass_context=True)
    @commands.guild_only()
    async def submit(self, ctx, *args):
        """Submit a QOTD"""
        qotd = ' '.join(args)
        if len(qotd) > 255:
            await ctx.send('Question over **255** characters, please **shorten** before trying the command again.')
            return
        if not args:
            p = self.bot.configs[ctx.guild.id]["prefix"]
            await ctx.send(f'```{p}qotd submit <question>```')
            return

        member = ctx.author.id
        is_staff = await self.bot.is_staff(ctx)

        today = datetime.datetime.utcnow().date()
        today_date = datetime.datetime(today.year, today.month, today.day)
        async with self.bot.pool.acquire() as connection:
            submitted_today = await connection.fetch(
                'SELECT * FROM qotd WHERE submitted_by = ($1) AND submitted_at > ($2) AND guild_id = $3', member, today_date, ctx.guild.id)
            
            limit = self.bot.configs[ctx.guild.id]["qotd_limit"]
            if limit is None or limit == 0: # Account for a limit set to 0 and a non-changed limit
                limit = inf # math.inf

            if len(submitted_today) >= limit and not is_staff:  # Staff bypass
                await ctx.send(f'You can only submit {limit} QOTD per day - this is to prevent spam.')
            else:
                await connection.execute('INSERT INTO qotd (question, submitted_by, guild_id) VALUES ($1, $2, $3)', qotd, member, ctx.guild.id)
                qotd_id = await connection.fetchval("SELECT MAX(id) FROM qotd WHERE guild_id = $1", ctx.guild.id)
                await ctx.message.delete()
                await ctx.send(f':thumbsup: Thank you for submitting your QOTD. Your QOTD ID is **{qotd_id}**.', delete_after = 20)

                mod_log_channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
                if mod_log_channel_id != None:
                    mod_log = self.bot.get_channel(mod_log_channel_id)
                    embed = Embed(title=':grey_question: QOTD Submitted', color=Colour.from_rgb(177, 252, 129))
                    embed.add_field(name='ID', value=qotd_id)
                    embed.add_field(name='Author', value=ctx.author)
                    embed.add_field(name='Question', value=qotd, inline=True)
                    embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                    await mod_log.send(embed=embed)

    @qotd.command(pass_context=True)
    @commands.guild_only()
    async def list(self, ctx, page_num=1):
        if not await self.has_qotd_perms(ctx):
            await ctx.send("You do not have permissions to show all QOTDs :sob:")
            return

        async with self.bot.pool.acquire() as connection:
            qotds = await connection.fetch('SELECT * FROM qotd WHERE guild_id = $1 ORDER BY id', ctx.guild.id)

        if len(qotds) > 0:
            embed = EmbedPages(PageTypes.QOTD, qotds, "QOTDs", Colour.from_rgb(177, 252, 129), self.bot, ctx.author, ctx.channel)
            await embed.set_page(int(page_num))
            await embed.send()
        else:
            await ctx.send("No QOTD have been submitted in thie guild before.")

    @qotd.command(pass_context=True, aliases=['remove'])
    @commands.guild_only()
    async def delete(self, ctx, *question_ids):
        if not await self.has_qotd_perms(ctx):
            await ctx.send("You do not have permissions to delete a QOTD :sob:")
            return
            
        async with self.bot.pool.acquire() as connection:
            for question_id in question_ids:
                try:
                    await connection.execute('DELETE FROM qotd WHERE id = ($1) AND guild_id = $2', int(question_id), ctx.guild.id)
                    await ctx.send(f'QOTD ID **{question_id}** has been deleted.')

                    mod_log_channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
                    if mod_log_channel_id != None:
                        mod_log = self.bot.get_channel(mod_log_channel_id)
                        embed = Embed(title=':grey_question: QOTD Deleted', color=Colour.from_rgb(177, 252, 129))
                        embed.add_field(name='ID', value=question_id)
                        embed.add_field(name='Staff', value=str(ctx.author))
                        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                        await mod_log.send(embed=embed)
                        
                except ValueError:
                    await ctx.send("Question ID must be an integer!")
                except Exception as e:
                    await ctx.send(f'Error whilst deleting question ID {question_id}: {e}')

    @qotd.command(pass_context=True, aliases=['choose'])
    @commands.guild_only()
    async def pick(self, ctx, question_id):
        if not await self.has_qotd_perms(ctx):
            await ctx.send("You do not have permissions to pick a QOTD :sob:")
            return

        qotd_channel_id = self.bot.configs[ctx.guild.id]["qotd_channel"]
        if qotd_channel_id is None:
            await ctx.send("You cannot pick a QOTD because a QOTD channel has not been set :sob:")
            return
        qotd_channel = self.bot.get_channel(qotd_channel_id)
            
        async with self.bot.pool.acquire() as connection:
            if question_id.lower() == 'random':
                questions = await connection.fetch('SELECT * FROM qotd WHERE guild_id = $1', ctx.guild.id)
            else:
                questions = await connection.fetch('SELECT * FROM qotd WHERE id = $1 AND guild_id = $2', int(question_id), ctx.guild.id)
            if not questions: # If no questions are returned
                if question_id.lower() == "random":
                    await ctx.send("No QOTD have been submitted in thie guild before.")
                else:
                    await ctx.send(f'Question with ID {question_id} not found. Please try again.')
                return
            
            else:
                question_data = choice(questions)

            question = question_data[1]
            member = await self.bot.fetch_user(question_data[2])
            message = f"**QOTD**\n{question} - Credit to {member.mention}"

            await connection.execute('DELETE FROM qotd WHERE id = ($1) AND guild_id = $2', question_data[0], ctx.guild.id)

        await ctx.send(':ok_hand:')
        await qotd_channel.send(message)

        mod_log_channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
        if mod_log_channel_id != None:
            mod_log = self.bot.get_channel(mod_log_channel_id)
            embed = Embed(title=':grey_question: QOTD Picked', color=Colour.from_rgb(177, 252, 129))
            embed.add_field(name='ID', value=question_data[0])
            embed.add_field(name='Author', value=str(member))
            embed.add_field(name='Question', value=question, inline=True)
            embed.add_field(name='Picked by', value=str(ctx.author))
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await mod_log.send(embed=embed)


def setup(bot):
    bot.add_cog(QuestionOTD(bot))
