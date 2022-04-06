import discord
from discord import Colour
from discord.ext import commands

from libs.misc.utils import get_user_avatar_url, get_guild_icon_url


class WarningHandlers:
    def __init__(self, bot, cog):
        self.bot = bot
        self.cog = cog

    async def _warnlist_member(self, ctx: commands.Context | discord.Interaction, member: discord.Member,
                               page_num: int = 1) -> None:
        """
        Handles getting the warns for a specific member
        """

        is_ctx = type(ctx) is commands.Context
        author = ctx.author if is_ctx else ctx.user

        async with self.bot.pool.acquire() as connection:
            warns = await connection.fetch("SELECT * FROM warn WHERE member_id = ($1) AND guild_id = $2 ORDER BY id;",
                                           member.id, ctx.guild.id)

        if len(warns) > 0:
            embed = self.bot.EmbedPages(
                self.bot.PageTypes.WARN,
                warns,
                f"{member.display_name}'s warnings",
                Colour.from_rgb(177, 252, 129),
                self.bot,
                author,
                ctx.channel,
                thumbnail_url=get_guild_icon_url(ctx.guild),
                icon_url=get_user_avatar_url(author, mode=1)[0],
                footer=f"Requested by: {author.display_name} ({author})\n" + self.bot.correct_time().strftime(
                    self.bot.ts_format),
                ctx=ctx
            )

            await embed.set_page(int(page_num))
            await embed.send()
        else:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Couldn't find any warnings!",
                                                                   desc=f"No warnings recorded for {member.mention}!")

    async def warn(self, ctx: commands.Context | discord.Interaction, member: discord.Member, reason: str = "") -> None:
        """
        Handler for the warn commands.
        """

        is_ctx = type(ctx) is commands.Context
        author = ctx.author if is_ctx else ctx.user

        parsed_args = self.bot.flag_handler.separate_args(reason, fetch=["reason"], blank_as_flag="reason")
        reason = parsed_args["reason"]
        if len(reason) > 255:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Warn reason is too long!",
                                                             desc="The reason must be below 256 characters. Please shorten it before trying again.")
            return

        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO warn (member_id, staff_id, guild_id, reason) values ($1, $2, $3, $4)",
                                     member.id, author.id, ctx.guild.id, reason)
            warns = await connection.fetchval("SELECT COUNT(*) FROM warn WHERE member_id = ($1) AND guild_id = $2",
                                              member.id, ctx.guild.id)

        await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Warned successfully!",
                                                               desc=f":ok_hand: {member.mention} has been warned. They now have {warns} warns")

        try:
            await member.send(
                f"You have been warned by a member of the staff team ({author.mention}). The reason for your warn is: {reason}. You now have {warns} warns.")
        except Exception as e:
            print(e)

    async def warns(self, ctx: commands.Context | discord.Interaction,
                    member: discord.Member | discord.User = None) -> None:
        """
        Handler for the warns commands.
        """

        is_ctx = type(ctx) is commands.Context
        author = ctx.author if is_ctx else ctx.user

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
                        author,
                        ctx.channel,
                        thumbnail_url=get_guild_icon_url(ctx.guild),
                        icon_url=get_user_avatar_url(author, mode=1)[0],
                        footer=f"Requested by: {author.display_name} ({author})\n" + self.bot.correct_time().strftime(
                            self.bot.ts_format),
                        ctx=ctx
                    )

                    await embed.set_page(1)
                    await embed.send()
                else:
                    await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Couldn't find anything!",
                                                                           desc="There are no warnings recorded!")
            else:
                # Show member's warns
                await self._warnlist_member(ctx, member, 1)  # Last parameter is the page number to start on
        else:
            if not member or member.id == author.id:
                # Show author warns
                await self._warnlist_member(ctx, author, 1)
            else:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Couldn't find anything!",
                                                                 desc="You don't have permission to view other people's warns.")

    async def warnremove(self, ctx: commands.Context | discord.Interaction, warnings: str):
        """
        Handler for the warnremove commands.
        """

        warnings = warnings.split(" ") if type(warnings) is str else warnings
        async with self.bot.pool.acquire() as connection:
            for warning in warnings:
                if warning.isdigit():
                    warning = int(warning)
                    existing_warnings = await connection.fetch("SELECT * FROM warn WHERE id = $1 AND guild_id = $2",
                                                               warning, ctx.guild.id)
                    if len(existing_warnings) == 0:
                        await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not remove warning(s)!", desc="You cannot remove warnings originating from another guild, or those that do not exist.")
                        continue  # Try next warning instead

                    await connection.execute("DELETE FROM warn WHERE id = ($1) AND guild_id = $2", warning,
                                             ctx.guild.id)
                    if len(warnings) == 1:
                        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx,
                                                                           "Successfully deleted warning!",
                                                                           desc=f"Warning with ID {warning} has been deleted.")
                else:
                    await ctx.channel.send(f"Error whilst deleting ID {warning}: give me a warning ID, not words!")

        if len(warnings) > 1:
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Successfully deleted warnings!",
                                                               desc=f"The valid warnings were deleted.")
