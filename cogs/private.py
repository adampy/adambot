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
        try:
            self.gdrive_link = os.environ['GDRIVE']
            self.classroom_link = os.environ['CLASSROOM']
        except KeyError as e:
            print(f"KeyError in cogs.private: {e}")

    def in_private_server(self, ctx):
        return (ctx.guild.id == 593788906646929439) or (ctx.author.id in SPAMPING_PERMS)  # in priv server or is adam

    def is_adam(self, ctx):
        return ctx.author.id == 394978551985602571

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
    async def csnotes(self, ctx, section=None):
        embed = Embed(title="**MV16 Computer Science 2019-2021**", description="Class code: 7vhujps",
                      color=Colour.blue())

        async with self.bot.pool.acquire() as connection:
            if section == "all":
                temp = await connection.fetch("SELECT * FROM classroom")
                notes_ids = sorted(temp, key=lambda x: x[0])
                for item in notes_ids:
                    embed.add_field(name=f"**Section {item[0]} ({item[2]}) notes**",
                                    value=f"    [Click here!](https://docs.google.com/document/d/{item[1]})")

            elif section:
                try:
                    notes = await connection.fetch("SELECT * FROM classroom WHERE section = ($1)", int(section))
                    embed.add_field(name=f"**Section {section} ({notes[0][2]}) notes**",
                                    value=f"    [Click here!](https://docs.google.com/document/d/{notes[0][1]})")
                except ValueError:
                    await ctx.send("Section ID must be an integer!")
            await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_adam)
    async def csnotesadd(self, ctx, section=None, id=None, *name):
        if not section or not id or not name:
            await ctx.send("'```-csnotesadd <section_number> <GDriveID> <name>```'")
            return
        async with self.bot.pool.acquire() as connection:
            connection.execute("INSERT INTO classroom (section, gid, name) VALUES ($1, $2, $3)", section, id,
                               ' '.join(name))
        await ctx.send(":ok_hand: Done!")

    @commands.command()
    @commands.check(is_adam)
    async def csnotesdelete(self, ctx, section=None):
        if not section:
            await ctx.send("'```-csnotesdelete <section_number>```'")
            return
        async with self.bot.pool.acquire() as connection:
            connection.execute("DELETE FROM classroom WHERE section = ($1)", section)
        await ctx.send(":ok_hand: Done!")


def setup(bot):
    bot.add_cog(Private(bot))
