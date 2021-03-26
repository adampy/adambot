import discord
from discord import Embed, Colour
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.utils import get
import asyncio
from .utils import separate_args, Permissions, EmbedPages, PageTypes, Todo
import os
import asyncpg

class Warnings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _warnlist_member(self, ctx, member, page_num = 1):
        """Handle gettings the warns for a specific member"""
        warns = []
        async with self.bot.pool.acquire() as connection:
            warns = await connection.fetch('SELECT * FROM warn WHERE member_id = ($1) ORDER BY id', member.id)

        if len(warns) > 0:
            embed = EmbedPages(PageTypes.WARN, warns, "Warnings", Colour.from_rgb(177,252,129), self.bot, ctx.author, ctx.channel)
            await embed.set_page(int(page_num))
            await embed.send()
        else:
            await ctx.send("No warnings recorded!")

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def warn(self, ctx, member: discord.Member, *reason):
        """Gives a member a warning, a reason is optional but recommended.
Staff role needed."""
        reason = ' '.join(reason)
        reason = reason.replace('-r', '') # Removes -r if a staff member includes it
        if len(reason) > 255:
            await ctx.send('The reason must be below 256 characters. Please shorten it before trying again.')
            return
        
        warns = 0
        async with self.bot.pool.acquire() as connection:
            await connection.execute('INSERT INTO warn (member_id, staff_id, reason) values ($1, $2, $3)', member.id, ctx.author.id, reason)
            warns = await connection.fetchval('SELECT COUNT(*) FROM warn WHERE member_id = ($1)', member.id)

        await ctx.send(f':ok_hand: {member.mention} has been warned. They now have {warns} warns')
        try:
            await member.send(f'You have been warned by a member of the staff team ({ctx.author.mention}). The reason for your warn is: {reason}. You now have {warns} warns.')
        except Exception as e:
            print(e)

    @commands.command(pass_context = True)
    @commands.guild_only()
    async def warns(self, ctx, member: discord.Member = None):
        is_staff = False
        for role in ctx.author.roles:
            if role.id in Permissions.STAFF:
                is_staff = True
                break

        if is_staff:
            if not member:
                # Show all warns
                warns = []
                async with self.bot.pool.acquire() as connection:
                    warns = await connection.fetch('SELECT * FROM warn ORDER BY id')

                if len(warns) > 0:
                    embed = EmbedPages(PageTypes.WARN, warns, "Warnings", Colour.from_rgb(177,252,129), self.bot, ctx.author, ctx.channel)
                    await embed.set_page(1)
                    await embed.send()
                else:
                    await ctx.send("No warnings recorded!")
            else:
                # Show member's warns
                await self._warnlist_member(ctx, member, 1) # Last parameter is the page number to start on
        else:
            if not member or member.id == ctx.author.id:
                # Show ctx.author warns
                await self._warnlist_member(ctx, ctx.author, 1)
            else:
                await ctx.send("You don't have permission to view other people's warns.")

    @commands.command(pass_context=True, aliases=['warndelete'])
    @commands.has_any_role(*Permissions.MOD)
    @commands.guild_only()
    async def warnremove(self, ctx, *warnings):
        """Remove warnings with this command, can do -warnremove <warnID> or -warnremove <warnID1> <warnID2>.
Moderator role needed"""

        if warnings[0].lower() == 'all':
            async with self.bot.pool.acquire() as connection:
                await connection.execute('DELETE FROM warn')
            await ctx.send("All warnings have been removed.")

        if len(warnings) > 1:
            await ctx.send('One moment...')

        async with self.bot.pool.acquire() as connection:
            for warning in warnings:
                try:
                    warning = int(warning)
                    await connection.execute('DELETE FROM warn WHERE id = ($1)', warning)
                    if len(warnings) == 1:
                        await ctx.send(f'Warning with ID {warning} has been deleted.')
                except ValueError:
                    await ctx.send(f'Error whilst deleting ID {warning}: give me a warning ID, not words!')

        if len(warnings) > 1:
            await ctx.send(f"The warning's have been deleted.")

def setup(bot):
    bot.add_cog(Warnings(bot))
