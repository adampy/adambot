import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import os
import asyncpg
from .utils import SPAMPING_PERMS

class Private(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def in_private_server(ctx):
        return (ctx.guild.id == 593788906646929439) or (ctx.author.id in SPAMPING_PERMS)  # in priv server or is adam

    @commands.command()
    @commands.check(in_private_server)
    async def spamping(self, ctx, amount, user: discord.Member, *message):
        """For annoying certain people"""
        await ctx.message.delete()

        try:
            iterations = int(amount)
        except Exception:
            await ctx.send(f"Please use a number for the amount, not {amount}")
            return

        msg = ' '.join(message) + " " + user.mention
        for i in range(iterations):
            await ctx.send(msg)

    @commands.command()
    @commands.check(in_private_server)
    async def ghostping(self, ctx, amount, user: discord.Member):
        """For sending a ghostping to annoy certain people"""
        await ctx.message.delete()
        for channel in [channel for channel in ctx.guild.channels if type(channel) == discord.TextChannel]:
            for i in range(int(amount)):
                msg = await channel.send(user.mention)
                await msg.delete()

def setup(bot):
    bot.add_cog(Private(bot))
