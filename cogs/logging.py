import discord
from discord.utils import get
from discord.ext import commands
from discord import Embed, Colour
from .utils import GCSE_SERVER_ID, CHANNELS
import asyncio

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(1)
        self.mod_logs = self.bot.get_channel(CHANNELS['mod-logs'])

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        embed = Embed(title=':information_source: Message Deleted', color=Colour.from_rgb(172, 32, 31))
        embed.add_field(name='User', value=f'{str(message.author)} ({message.author.id})', inline=True)
        embed.add_field(name='Message ID', value=message.id, inline=True)
        embed.add_field(name='Channel', value=message.channel.mention, inline=True)
        embed.add_field(name='Message', value=message.content or "", inline=False)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await self.mod_logs.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        embed = Embed(title=':information_source: Message Updated', color=Colour.from_rgb(118, 37, 171))
        embed.add_field(name='User', value=f'{str(after.author)} ({after.author.id})', inline=True)
        embed.add_field(name='Message ID', value=after.id, inline=True)
        embed.add_field(name='Channel', value=after.channel.mention, inline=True)
        embed.add_field(name='Old Message', value=before.content or "", inline=False)
        embed.add_field(name='New Message', value=after.content or "", inline=False)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await self.mod_logs.send(embed=embed)
    

def setup(bot):
    bot.add_cog(Logging(bot))
