from discord.ext import commands
import datetime
from discord import Embed, Colour, Message
from random import choice
from math import inf
from libs.misc.utils import get_user_avatar_url, get_guild_icon_url, DefaultEmbedResponses
from typing import Any, Callable
from inspect import signature  # Used in @qotd_perms decorator
import asyncio


def qotd_perms(func: Callable) -> Callable:
    """
    Decorator that allows the command to only be executed by people with QOTD perms / staff / administrators.
    This needs to be placed underneath the @command.command() decorator, and can only be used for commands in a cog

    Usage:
        @commands.command()
        @qotd_perms
        async def ping(self, ctx):
            await ctx.send("Pong!")
    """

    async def decorator(cog, ctx: commands.Context, *args, **kwargs) -> Any | Message:
        while not cog.bot.online:
            await asyncio.sleep(1)  # Wait else DB won't be available

        qotd_role_id = await cog.bot.get_config_key(ctx, "qotd_role")
        staff_role_id = await cog.bot.get_config_key(ctx, "staff_role")
        role_ids = [y.id for y in ctx.author.roles]
        if qotd_role_id in role_ids or staff_role_id in role_ids or ctx.author.guild_permissions.administrator:
            return await func(cog, ctx, *args, **kwargs)
        else:
            return await DefaultEmbedResponses.invalid_perms(cog.bot, ctx)
    
    decorator.__name__ = func.__name__
    decorator.__signature__ = signature(func)
    return decorator


class QOTD(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.group()
    async def qotd(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}qotd submit <question>```")

    @qotd.command(pass_context=True)
    @commands.guild_only()
    async def submit(self, ctx: commands.Context, *, qotd: str) -> None:
        """
        Submit a QOTD
        """

        if len(qotd) > 255:
            await ctx.send("Question over **255** characters, please **shorten** before trying the command again.")
            return

        if not qotd:
            await ctx.send(f"```{ctx.prefix}qotd submit <question>```")
            return

        member = ctx.author.id
        is_staff = await self.bot.is_staff(ctx)

        today = datetime.datetime.utcnow().date()
        today_date = datetime.datetime(today.year, today.month, today.day)
        async with self.bot.pool.acquire() as connection:
            submitted_today = await connection.fetch("SELECT * FROM qotd WHERE submitted_by = ($1) AND submitted_at > ($2) AND guild_id = $3", member, today_date, ctx.guild.id)

            limit = await self.bot.get_config_key(ctx, "qotd_limit")
            if limit is None or limit == 0:  # Account for a limit set to 0 and a non-changed limit
                limit = inf  # math.inf

            if len(submitted_today) >= limit and not is_staff:  # Staff bypass
                await ctx.send(f"You can only submit {limit} QOTD per day - this is to prevent spam.")
            else:
                await connection.execute("INSERT INTO qotd (question, submitted_by, guild_id) VALUES ($1, $2, $3)", qotd, member, ctx.guild.id)
                qotd_id = await connection.fetchval("SELECT MAX(id) FROM qotd WHERE guild_id = $1", ctx.guild.id)
                await ctx.message.delete()
                await ctx.send(f":thumbsup: Thank you for submitting your QOTD. Your QOTD ID is **{qotd_id}**.", delete_after=20)

                log_channel_id = await self.bot.get_config_key(ctx, "log_channel")
                if log_channel_id is not None:
                    log = self.bot.get_channel(log_channel_id)
                    embed = Embed(title=":grey_question: QOTD Submitted", color=Colour.from_rgb(177, 252, 129))
                    embed.add_field(name="ID", value=qotd_id)
                    embed.add_field(name="Author", value=ctx.author)
                    embed.add_field(name="Question", value=qotd, inline=True)
                    embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                    await log.send(embed=embed)

    @qotd.command(pass_context=True)
    @commands.guild_only()
    @qotd_perms
    async def list(self, ctx: commands.Context, page_num: int = 1) -> None:
        async with self.bot.pool.acquire() as connection:
            qotds = await connection.fetch("SELECT * FROM qotd WHERE guild_id = $1 ORDER BY id", ctx.guild.id)

        if len(qotds) > 0:
            embed = self.bot.EmbedPages(
                self.bot.PageTypes.QOTD,
                qotds,
                f"{ctx.guild.name}'s QOTDs",
                Colour.from_rgb(177, 252, 129),
                self.bot,
                ctx.author,
                ctx.channel,
                thumbnail_url=get_guild_icon_url(ctx.guild),
                icon_url=get_user_avatar_url(ctx.author, mode=1)[0],
                footer=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format)
            )
            await embed.set_page(int(page_num))
            await embed.send()
        else:
            await ctx.send("No QOTD have been submitted in this guild before.")

    @qotd.command(pass_context=True, aliases=["remove"])
    @commands.guild_only()
    @qotd_perms
    async def delete(self, ctx: commands.Context, *question_ids: str) -> None:
        async with self.bot.pool.acquire() as connection:
            for question_id in question_ids:
                try:
                    await connection.execute("DELETE FROM qotd WHERE id = ($1) AND guild_id = $2", int(question_id), ctx.guild.id)
                    await ctx.send(f"QOTD ID **{question_id}** has been deleted.")

                    log_channel_id = await self.bot.get_config_key(ctx, "log_channel")
                    if log_channel_id is not None:
                        log = self.bot.get_channel(log_channel_id)
                        embed = Embed(title=":grey_question: QOTD Deleted", color=Colour.from_rgb(177, 252, 129))
                        embed.add_field(name="ID", value=question_id)
                        embed.add_field(name="Staff", value=str(ctx.author))
                        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                        await log.send(embed=embed)
                        
                except ValueError:
                    await ctx.send("Question ID must be an integer!")
                except Exception as e:
                    await ctx.send(f"Error whilst deleting question ID {question_id}: {e}")

    @qotd.command(pass_context=True, aliases=["choose"])
    @commands.guild_only()
    @qotd_perms
    async def pick(self, ctx: commands.Context, question_id: str) -> None:
        qotd_channel_id = await self.bot.get_config_key(ctx, "qotd_channel")
        if qotd_channel_id is None:
            await ctx.send("You cannot pick a QOTD because a QOTD channel has not been set :sob:")
            return
        qotd_channel = self.bot.get_channel(qotd_channel_id)
            
        async with self.bot.pool.acquire() as connection:
            if question_id.lower() == "random":
                questions = await connection.fetch("SELECT * FROM qotd WHERE guild_id = $1", ctx.guild.id)
            else:
                questions = await connection.fetch("SELECT * FROM qotd WHERE id = $1 AND guild_id = $2", int(question_id), ctx.guild.id)
            if not questions:  # If no questions are returned
                if question_id.lower() == "random":
                    await ctx.send("No QOTD have been submitted in this guild before.")
                else:
                    await ctx.send(f"Question with ID {question_id} not found. Please try again.")
                return
            
            else:
                question_data = choice(questions)

            question = question_data[1]
            member = await self.bot.fetch_user(question_data[2])
            message = f"**QOTD**\n{question} - Credit to {member.mention}"

            await connection.execute("DELETE FROM qotd WHERE id = ($1) AND guild_id = $2", question_data[0], ctx.guild.id)

        await ctx.send(":ok_hand:")
        await qotd_channel.send(message)

        log_channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if log_channel_id is not None:
            log = self.bot.get_channel(log_channel_id)
            embed = Embed(title=":grey_question: QOTD Picked", color=Colour.from_rgb(177, 252, 129))
            embed.add_field(name="ID", value=question_data[0])
            embed.add_field(name="Author", value=str(member))
            embed.add_field(name="Question", value=question, inline=True)
            embed.add_field(name="Picked by", value=str(ctx.author))
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await log.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(QOTD(bot))
