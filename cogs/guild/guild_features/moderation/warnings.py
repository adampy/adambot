import discord
from discord import Colour
from discord.ext import commands
from libs.misc.decorators import is_staff
from libs.misc.utils import get_user_avatar_url, get_guild_icon_url


class Warnings(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _warnlist_member(self, ctx: commands.Context, member: discord.Member, page_num: int = 1) -> None:
        """
        Handles getting the warns for a specific member
        """

        async with self.bot.pool.acquire() as connection:
            warns = await connection.fetch("SELECT * FROM warn WHERE member_id = ($1) AND guild_id = $2 ORDER BY id;", member.id, ctx.guild.id)

        if len(warns) > 0:
            embed = self.bot.EmbedPages(
                self.bot.PageTypes.WARN,
                warns,
                f"{member.display_name}'s warnings",
                Colour.from_rgb(177, 252, 129),
                self.bot,
                ctx.author,
                ctx.channel,
                thumbnail_url=get_guild_icon_url(ctx.guild),
                icon_url=get_user_avatar_url(ctx.author, mode=1)[0],
                footer=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format))

            await embed.set_page(int(page_num))
            await embed.send()
        else:
            await ctx.send("No warnings recorded!")

    @commands.command(pass_context=True)
    @commands.guild_only()
    @is_staff()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "") -> None:
        """
        Gives a member a warning, a reason is optional but recommended.
        """

        parsed_args = self.bot.flag_handler.separate_args(reason, fetch=["reason"], blank_as_flag="reason")
        reason = parsed_args["reason"]
        if len(reason) > 255:
            await ctx.send("The reason must be below 256 characters. Please shorten it before trying again.")
            return

        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO warn (member_id, staff_id, guild_id, reason) values ($1, $2, $3, $4)", member.id, ctx.author.id, ctx.guild.id, reason)
            warns = await connection.fetchval("SELECT COUNT(*) FROM warn WHERE member_id = ($1) AND guild_id = $2", member.id, ctx.guild.id)

        await ctx.send(f":ok_hand: {member.mention} has been warned. They now have {warns} warns")
        try:
            await member.send(f"You have been warned by a member of the staff team ({ctx.author.mention}). The reason for your warn is: {reason}. You now have {warns} warns.")
        except Exception as e:
            print(e)

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def warns(self, ctx: commands.Context, member: discord.Member = None) -> None:
        """
        Shows a user their warnings, or shows staff members all/a single persons warnings
        """

        if await self.bot.is_staff(ctx):
            if not member:
                # Show all warns
                async with self.bot.pool.acquire() as connection:
                    warns = await connection.fetch("SELECT * FROM warn WHERE guild_id = $1 ORDER BY id;", ctx.guild.id)

                if len(warns) > 0:
                    embed = self.bot.EmbedPages(
                        self.bot.PageTypes.WARN,
                        warns,
                        f"{ctx.guild.name if not member else member.display_name}'s warnings",
                        Colour.from_rgb(177, 252, 129),
                        self.bot,
                        ctx.author,
                        ctx.channel,
                        thumbnail_url=get_guild_icon_url(ctx.guild),
                        icon_url=get_user_avatar_url(ctx.author, mode=1)[0],
                        footer=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format))

                    await embed.set_page(1)
                    await embed.send()
                else:
                    await ctx.send("No warnings recorded!")
            else:
                # Show member's warns
                await self._warnlist_member(ctx, member, 1)  # Last parameter is the page number to start on
        else:
            if not member or member.id == ctx.author.id:
                # Show ctx.author warns
                await self._warnlist_member(ctx, ctx.author, 1)
            else:
                await ctx.send("You don't have permission to view other people's warns.")

    @commands.command(pass_context=True, aliases=["warndelete"])
    @commands.guild_only()
    @is_staff()
    async def warnremove(self, ctx: commands.Context, *warnings: str) -> None:
        """
        Remove warnings with this command, can do `warnremove <warnID>` or `warnremove <warnID1> <warnID2> ... <warnIDn>`.
        """

        if len(warnings) > 1:
            await ctx.send("One moment...")

        async with self.bot.pool.acquire() as connection:
            for warning in warnings:
                if warning.isdigit():
                    warning = int(warning)
                    existing_warnings = await connection.fetch("SELECT * FROM warn WHERE id = $1 AND guild_id = $2", warning, ctx.guild.id)
                    if len(existing_warnings) == 0:
                        await ctx.send("You cannot remove warnings originating from another guild, or those that do not exist.")
                        continue  # Try next warning instead

                    await connection.execute("DELETE FROM warn WHERE id = ($1) AND guild_id = $2", warning, ctx.guild.id)
                    if len(warnings) == 1:
                        await ctx.send(f"Warning with ID {warning} has been deleted.")
                else:
                    await ctx.send(f"Error whilst deleting ID {warning}: give me a warning ID, not words!")

        if len(warnings) > 1:
            await ctx.send(f"The warning's have been deleted.")


async def setup(bot) -> None:
    await bot.add_cog(Warnings(bot))
