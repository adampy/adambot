import discord
from discord import Colour
from discord.ext import commands

class Warnings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _warnlist_member(self, ctx, member, page_num = 1):
        """Handle gettings the warns for a specific member"""
        warns = []
        async with self.bot.pool.acquire() as connection:
            warns = await connection.fetch('SELECT * FROM warn WHERE member_id = ($1) AND guild_id = $2 ORDER BY id;', member.id, ctx.guild.id)

        if len(warns) > 0:
            embed = self.bot.EmbedPages(
                self.bot.PageTypes.WARN,
                warns,
                f"{member.display_name}'s warnings",
                Colour.from_rgb(177,252,129),
                self.bot,
                ctx.author,
                ctx.channel,
                thumbnail_url = ctx.guild.icon_url,
                icon_url = ctx.author.avatar_url,
                footer = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format))
            await embed.set_page(int(page_num))
            await embed.send()
        else:
            await ctx.send("No warnings recorded!")

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def warn(self, ctx, member: discord.Member, *, reason):
        """Gives a member a warning, a reason is optional but recommended."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to warn.")
            return

        parsed_args = self.bot.flag_handler.separate_args(reason, fetch=["reason"], blank_as_flag="reason")
        reason = parsed_args["reason"]
        if len(reason) > 255:
            await ctx.send('The reason must be below 256 characters. Please shorten it before trying again.')
            return
        
        warns = 0
        async with self.bot.pool.acquire() as connection:
            await connection.execute('INSERT INTO warn (member_id, staff_id, guild_id, reason) values ($1, $2, $3, $4)', member.id, ctx.author.id, ctx.guild.id, reason)
            warns = await connection.fetchval('SELECT COUNT(*) FROM warn WHERE member_id = ($1) AND guild_id = $2', member.id, ctx.guild.id)

        await ctx.send(f':ok_hand: {member.mention} has been warned. They now have {warns} warns')
        try:
            await member.send(f'You have been warned by a member of the staff team ({ctx.author.mention}). The reason for your warn is: {reason}. You now have {warns} warns.')
        except Exception as e:
            print(e)

    @commands.command(pass_context = True)
    @commands.guild_only()
    async def warns(self, ctx, member: discord.Member = None):
        """Shows a user their warnings, or shows staff members all/a single persons warnings"""
        is_staff = await self.bot.is_staff(ctx)
        if is_staff:
            if not member:
                # Show all warns
                warns = []
                async with self.bot.pool.acquire() as connection:
                    warns = await connection.fetch('SELECT * FROM warn WHERE guild_id = $1 ORDER BY id;', ctx.guild.id)

                if len(warns) > 0:
                    embed = self.bot.EmbedPages(
                        self.bot.PageTypes.WARN,
                        warns,
                        f"{ctx.guild.name if not member else member.display_name}'s warnings",
                        Colour.from_rgb(177,252,129),
                        self.bot,
                        ctx.author,
                        ctx.channel,
                        thumbnail_url = ctx.guild.icon_url,
                        icon_url = ctx.author.avatar_url,
                        footer = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format))
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
    @commands.guild_only()
    async def warnremove(self, ctx, *warnings):
        """Remove warnings with this command, can do `warnremove <warnID>` or `warnremove <warnID1> <warnID2> ... <warnIDn>`."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to remove a warning.")
            return

        # if warnings[0].lower() == 'all':
        #     async with self.bot.pool.acquire() as connection:
        #         await connection.execute('DELETE FROM warn WHERE guild_id = $1', ctx.guild.id)
        #     await ctx.send("All warnings on this guild have been removed.")

        if len(warnings) > 1:
            await ctx.send('One moment...')

        async with self.bot.pool.acquire() as connection:
            for warning in warnings:
                try:
                    warning = int(warning)
                    existing_warnings = await connection.fetch("SELECT * FROM warn WHERE id = $1 AND guild_id = $2", warning, ctx.guild.id)
                    if len(existing_warnings) == 0:
                        await ctx.send("You cannot remove warnings originating from another guild, or those that do not exist.")
                        continue # Try next warning instead

                    await connection.execute('DELETE FROM warn WHERE id = ($1) AND guild_id = $2', warning, ctx.guild.id)
                    if len(warnings) == 1:
                        await ctx.send(f'Warning with ID {warning} has been deleted.')

                except ValueError:
                    await ctx.send(f'Error whilst deleting ID {warning}: give me a warning ID, not words!')

        if len(warnings) > 1:
            await ctx.send(f"The warning's have been deleted.")

def setup(bot):
    bot.add_cog(Warnings(bot))
