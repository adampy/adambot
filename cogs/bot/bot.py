import discord
from discord.ext import commands
from discord import Embed, Colour
import platform
import time


class BotCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def botinfo(self, ctx: commands.Context) -> None:
        app_info = await self.bot.application_info()
        embed = Embed(title=f"Bot info for ({self.bot.user})", description=app_info.description if app_info.description else "", colour=0x87CEEB)
        embed.add_field(name="Uptime", value=self.bot.time_str(round(time.time() - self.bot.start_time)))
        embed.add_field(name="Discord.py version", value=discord.__version__, inline=False)
        embed.add_field(name="Python version", value=f"{platform.python_version()}", inline=False)
        embed.add_field(name="Host OS", value=f"{platform.system()}", inline=False)
        embed.add_field(name="Bot owner", value=f"{app_info.owner}", inline=False)
        embed.add_field(name="Public bot", value=f"{app_info.bot_public}", inline=False)

        embed.set_thumbnail(url=app_info.icon.url)
        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed)

    @commands.command(pass_context=True)
    async def host(self, ctx: commands.Context) -> None:
        """
        Check if the bot is currently hosted locally or remotely
        """

        await ctx.send(f"Adam-bot is {'**locally**' if self.bot.LOCAL_HOST else '**remotely**'} hosted right now.")

    @commands.command(pass_context=True)
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send(f"Pong! ({round(self.bot.latency * 1000)} ms)")

    @commands.command(pass_context=True)
    async def uptime(self, ctx: commands.Context) -> None:
        """View how long the bot has been running for"""
        seconds = round(time.time() - self.bot.start_time)   # Rounds to the nearest integer
        time_string = self.bot.time_str(seconds)
        await ctx.send(f"Current uptime session has lasted **{time_string}**, or **{seconds}** seconds.")


def setup(bot) -> None:
    bot.add_cog(BotCog(bot))
