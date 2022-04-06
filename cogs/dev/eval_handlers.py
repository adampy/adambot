import inspect
import os

import discord
from discord.ext import commands

from adambot import AdamBot


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

    async def evaluate(self, ctx: commands.Context | discord.Interaction, command: str = "") -> None:
        """
        Handler for the evaluate commands.

        Allows evaluating strings of code (intended for testing).
        If something doesn't output correctly try wrapping in str()
        """

        is_ctx = type(ctx) is commands.Context

        try:
            output = eval(command)
            if inspect.isawaitable(output):
                a_output = await output
                if a_output is None:
                    await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Finished evaluation",
                                                                           desc="No output (command probably executed correctly)")
                else:
                    if len(a_output) > 2000:
                        a_output = self.split_2000(a_output)
                    if type(a_output) is str:
                        await ctx.send(a_output) if is_ctx else await ctx.response.send_message(a_output)
                    else:
                        for i, chunk in enumerate(a_output):
                            await ctx.channel.send(chunk) if is_ctx or i != 0 else await ctx.response.send_message(
                                chunk)
            elif output is None:
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Finished evaluation",
                                                                       desc="No output (command probably executed correctly)")
            else:
                if len(output) > 2000:
                    output = self.split_2000(output)
                if type(output) is str:
                    await ctx.send(output) if is_ctx else await ctx.response.send_message(output)
                else:
                    for i, chunk in enumerate(output):
                        await ctx.channel.send(chunk) if is_ctx or i != 0 else await ctx.response.send_message(chunk)
        except Exception as e:
            e = str(e)
            e.replace(os.getcwd(), ".")
            await ctx.channel.send(e)

    async def execute(self, ctx: commands.Context | discord.Interaction, command: str = "") -> None:
        """
        Handler for the execute commands.
        """
        is_ctx = type(ctx) is commands.Context
        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute(command)
            except Exception as e:
                msg = f"EXCEPTION: {e}"
                await ctx.send(msg) if is_ctx else await ctx.response.send_message(msg)

    async def fetch(self, ctx: commands.Context | discord.Interaction, command: str = "") -> None:
        """
        Handler for the fetch commands.
        """

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

                await ctx.channel.send(f"EXCEPTION: {e}")
