import os
import inspect
from discord.ext import commands
from libs.misc.decorators import is_dev


class Eval(commands.Cog):

    def __init__(self, bot) -> None:
        self.bot = bot

    @staticmethod
    def split_2000(text: str) -> list[str]:
        chunks = []
        while len(text) > 0:
            chunks.append(text[:2000])
            text = text[2000:]
        return chunks

    @commands.command(name="eval", pass_context=True)
    @is_dev()
    async def evaluate(self, ctx: commands.Context, *, command: str = "") -> None:  # command is kwarg to stop it flooding the console when no input is provided
        """
        Allows evaluating strings of code (intended for testing).
        If something doesn't output correctly try wrapping in str()
        """

        try:
            output = eval(command)
            if inspect.isawaitable(output):
                a_output = await output
                if a_output is None:
                    await ctx.message.channel.send("No output (command probably executed correctly)")
                else:
                    if len(a_output) > 2000:
                        a_output = self.split_2000(a_output)
                    if type(a_output) is str:
                        await ctx.message.channel.send(a_output)
                    else:
                        for chunk in a_output:
                            await ctx.message.channel.send(chunk)
            elif output is None:
                await ctx.message.channel.send("No output (command probably executed correctly)")
            else:
                if len(output) > 2000:
                    output = self.split_2000(output)
                if type(output) is str:
                    await ctx.message.channel.send(output)
                else:
                    for chunk in output:
                        await ctx.message.channel.send(chunk)
        except Exception as e:
            e = str(e)
            e.replace(os.getcwd(), ".")
            await ctx.message.channel.send(e)

    @commands.group()
    @commands.guild_only()
    async def sql(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}help sql```")

    @sql.command(pass_context=True)
    @is_dev()
    async def execute(self, ctx: commands.Context, *, command: str) -> None:
        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute(command)
            except Exception as e:
                await ctx.send(f"EXCEPTION: {e}")

    @sql.command(pass_context=True)
    @is_dev()
    async def fetch(self, ctx: commands.Context, *, command: str) -> None:
        async with self.bot.pool.acquire() as connection:
            try:
                records = await connection.fetch(command)
                final_str = ""
                for i in range(len(records)):
                    final_str += str(records[i])
                    if i != len(records) - 1:
                        final_str += "\n"

                await self.bot.send_text_file(final_str, ctx.channel, "query")
            except Exception as e:
                await ctx.send(f"EXCEPTION: {e}")


async def setup(bot) -> None:
    await bot.add_cog(Eval(bot))
