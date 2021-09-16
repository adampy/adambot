import discord
from discord.ext import commands
from discord import Embed, Colour
import platform
import time


class BotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def botinfo(self, ctx):
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


def setup(bot):
    bot.add_cog(BotCog(bot))
