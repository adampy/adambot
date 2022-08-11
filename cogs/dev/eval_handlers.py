import inspect
import os

import discord
from discord.ext import commands

from adambot import AdamBot
from libs.misc.decorators import unbox_context_args
from libs.misc.utils import ContextTypes


class EvalHandlers:
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot

    @staticmethod
    def split_2000(text: str) -> list[str]:
        chunks = []
        while len(text) > 0:
            chunks.append(text[:2000])
            text = text[2000:]
        return chunks

    @unbox_context_args
    async def evaluate(self, ctx: commands.Context | discord.Interaction, command: str = "") -> None:
        """
        Handler for the evaluate commands.

        Allows evaluating strings of code (intended for testing).
        If something doesn't output correctly try wrapping in str()
        """

        (ctx_type, author) = self.command_args

        try:
            output = eval(command)
            if inspect.isawaitable(output):
                a_output = await output
            else:
                a_output = output

            if a_output is None:
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Finished evaluation",
                                                                       desc="No output (command probably executed correctly)")
            else:
                if type(a_output) is not str:
                    a_output = "\n".join(str(x) for x in a_output)

                if len(a_output) > 2000:
                    await self.bot.send_text_file(ctx, a_output, ctx.channel, "eval")

                elif ctx_type == self.bot.ContextTypes.Context:
                    await ctx.send(a_output)
                else:
                    await ctx.response.send_message(a_output)

        except Exception as e:
            e = str(e)
            e.replace(os.getcwd(), ".")
            await ctx.channel.send(e)

    @unbox_context_args
    async def execute(self, ctx: commands.Context | discord.Interaction, command: str = "") -> None:
        """
        Handler for the execute commands.
        """

        (ctx_type, author) = self.command_args
        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute(command)
            except Exception as e:
                msg = f"EXCEPTION: {e}"

                if ctx_type == self.bot.ContextTypes.Context:
                    await ctx.send(msg)
                else:
                    await ctx.response.send_message(msg)

    @unbox_context_args
    async def fetch(self, ctx: commands.Context | discord.Interaction, command: str = "") -> None:
        """
        Handler for the fetch commands.
        """

        (ctx_type, author) = self.command_args
        async with self.bot.pool.acquire() as connection:
            try:
                records = await connection.fetch(command)
                final_str = ""
                for i in range(len(records)):
                    final_str += str(records[i])
                    if i != len(records) - 1:
                        final_str += "\n"

                await self.bot.send_text_file(ctx, final_str, ctx.channel, "query")
            except Exception as e:
                if ctx_type == self.bot.ContextTypes.Context:
                    await ctx.channel.send(f"EXCEPTION: {e}")
                else:
                    await ctx.response.send_message(f"EXCEPTION: {e}")
