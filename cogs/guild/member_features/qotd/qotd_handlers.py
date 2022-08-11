import datetime
from math import inf
from random import choice

import discord
from discord import Embed, Colour
from discord.ext import commands

from adambot import AdamBot
from libs.misc.decorators import unbox_context_args
from libs.misc.utils import ContextTypes, get_user_avatar_url, get_guild_icon_url


class QOTDHandlers:
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.ContextTypes = self.bot.ContextTypes

    @unbox_context_args
    async def submit(self, ctx: commands.Context | discord.Interaction, qotd: str) -> None:
        """
        Handler for the submit commands.
        """

        (ctx_type, author) = self.command_args
        if len(qotd) > 255:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not submit question!",
                                                             desc="Question over **255** characters, please **shorten** before trying the command again.")
            return

        if not qotd and ctx_type == self.ContextTypes.Context:
            await ctx.send(f"```{ctx.prefix}qotd submit <question>```")
            return

        member = author.id
        is_staff = await self.bot.is_staff(ctx)

        today = datetime.datetime.utcnow().date()
        today_date = datetime.datetime(today.year, today.month, today.day)
        async with self.bot.pool.acquire() as connection:
            submitted_today = await connection.fetch(
                "SELECT * FROM qotd WHERE submitted_by = ($1) AND submitted_at > ($2) AND guild_id = $3", member,
                today_date, ctx.guild.id)

            limit = await self.bot.get_config_key(ctx, "qotd_limit")
            if limit is None or limit == 0:  # Account for a limit set to 0 and a non-changed limit
                limit = inf  # math.inf

            if len(submitted_today) >= limit and not is_staff:  # Staff bypass
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not submit question!",
                                                                 desc=f"You can only submit {limit} QOTD per day - this is to prevent spam.")
            else:
                await connection.execute("INSERT INTO qotd (question, submitted_by, guild_id) VALUES ($1, $2, $3)",
                                         qotd, member, ctx.guild.id)
                qotd_id = await connection.fetchval("SELECT MAX(id) FROM qotd WHERE guild_id = $1", ctx.guild.id)

                if ctx_type == self.ContextTypes.Context:
                    await ctx.message.delete()

                await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Successfully submitted QOTD!",
                                                                   desc=f":thumbsup: Thank you for submitting your QOTD. Your QOTD ID is **{qotd_id}**.")

                log_channel_id = await self.bot.get_config_key(ctx, "log_channel")
                if log_channel_id is not None:
                    log = self.bot.get_channel(log_channel_id)
                    embed = Embed(title=":grey_question: QOTD Submitted", color=Colour.from_rgb(177, 252, 129))
                    embed.add_field(name="ID", value=qotd_id)
                    embed.add_field(name="Author", value=author)
                    embed.add_field(name="Question", value=qotd, inline=True)
                    embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                    await log.send(embed=embed)

    @unbox_context_args
    async def qotd_list(self, ctx: commands.Context | discord.Interaction, page_num: int = 1) -> None:
        """
        Handler for the list commands.
        """

        (ctx_type, author) = self.command_args
        async with self.bot.pool.acquire() as connection:
            qotds = await connection.fetch("SELECT * FROM qotd WHERE guild_id = $1 ORDER BY id", ctx.guild.id)

        if len(qotds) > 0:
            embed = self.bot.EmbedPages(
                self.bot.PageTypes.QOTD,
                qotds,
                f"{ctx.guild.name}'s QOTDs",
                Colour.from_rgb(177, 252, 129),
                self.bot,
                author,
                ctx.channel,
                thumbnail_url=get_guild_icon_url(ctx.guild),
                icon_url=get_user_avatar_url(author, mode=1)[0],
                footer=f"Requested by: {author.display_name} ({author})\n" + self.bot.correct_time().strftime(
                    self.bot.ts_format),
                ctx=ctx
            )
            await embed.set_page(int(page_num))
            await embed.send()
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Nothing here!",
                                                             desc="This server does not currently have any QOTDs!")

    @unbox_context_args
    async def delete(self, ctx: commands.Context | discord.Interaction, question_ids: str) -> None:
        """
        Handler for the delete commands.
        """

        (ctx_type, author) = self.command_args
        question_ids = question_ids.split(" ")

        info = ""
        async with self.bot.pool.acquire() as connection:
            for question_id in question_ids:
                try:
                    await connection.execute("DELETE FROM qotd WHERE id = ($1) AND guild_id = $2", int(question_id),
                                             ctx.guild.id)
                    info += f"\nQOTD ID **{question_id}** has been deleted."

                    log_channel_id = await self.bot.get_config_key(ctx, "log_channel")
                    if log_channel_id is not None:
                        log = self.bot.get_channel(log_channel_id)
                        embed = Embed(title=":grey_question: QOTD Deleted", color=Colour.from_rgb(177, 252, 129))
                        embed.add_field(name="ID", value=question_id)
                        embed.add_field(name="Staff", value=author)
                        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                        await log.send(embed=embed)

                except ValueError:
                    info += f"\nQuestion ID ({question_id}) must be an integer!"
                except Exception as e:
                    info += f"\nError whilst deleting question ID {question_id}: {e}"

        await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Finished deleting QOTDs", desc=info)

    @unbox_context_args
    async def pick(self, ctx: commands.Context | discord.Interaction, question_id: str | int) -> None:
        """
        Handler for the pick commands.
        """

        (ctx_type, author) = self.command_args
        qotd_channel_id = await self.bot.get_config_key(ctx, "qotd_channel")
        if qotd_channel_id is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not pick QOTD!",
                                                             desc="You cannot pick a QOTD because a QOTD channel has not been set :sob:")
            return
        qotd_channel = self.bot.get_channel(qotd_channel_id)

        async with self.bot.pool.acquire() as connection:
            if question_id.lower() == "random":
                questions = await connection.fetch("SELECT * FROM qotd WHERE guild_id = $1", ctx.guild.id)
            else:
                questions = await connection.fetch("SELECT * FROM qotd WHERE id = $1 AND guild_id = $2",
                                                   int(question_id), ctx.guild.id)
            if not questions:  # If no questions are returned
                if question_id.lower() == "random":
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not pick QOTD!",
                                                                     desc="This server does not currently have any QOTDs to choose from!")
                else:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not pick QOTD!",
                                                                     desc=f"Question with ID {question_id} not found. Please try again.")
                return

            else:
                question_data = choice(questions)

            question = question_data[1]
            member = await self.bot.fetch_user(question_data[2])
            message = f"**QOTD**\n{question} - Credit to {member.mention}"

            await connection.execute("DELETE FROM qotd WHERE id = ($1) AND guild_id = $2", question_data[0],
                                     ctx.guild.id)

        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "QOTD picked successfully!",
                                                           desc=f"The QOTD should now show up in {qotd_channel.mention}!")
        await qotd_channel.send(message)

        log_channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if log_channel_id is not None:
            log = self.bot.get_channel(log_channel_id)
            embed = Embed(title=":grey_question: QOTD Picked", color=Colour.from_rgb(177, 252, 129))
            embed.add_field(name="ID", value=question_data[0])
            embed.add_field(name="Author", value=str(member))
            embed.add_field(name="Question", value=question, inline=True)
            embed.add_field(name="Picked by", value=author)
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            await log.send(embed=embed)
