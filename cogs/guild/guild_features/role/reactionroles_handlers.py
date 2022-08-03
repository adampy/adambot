import re
from typing import Optional

import discord
from discord.ext import commands

from adambot import AdamBot
from libs.misc.utils import get_user_avatar_url


class ReactionrolesHandlers:
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.ContextTypes = self.bot.ContextTypes

    async def _get_roles(self, payload) -> Optional[list]:
        """
        Returns a list of (discord.Role, bool) pairs for the given `payload`. bool refers to whether the reaction role gives or removes a role on reaction add.
        """

        async with self.bot.pool.acquire() as connection:
            data = await connection.fetch(
                "SELECT role_id, inverse FROM reaction_roles WHERE message_id = $1 AND (emoji_id = $2 OR emoji = $3);",
                payload.message_id, payload.emoji.id, str(payload.emoji))

        guild = self.bot.get_guild(payload.guild_id)
        if not data or not guild:
            return None

        to_return = []
        for i in range(len(data)):
            role = guild.get_role(data[i][0])  # Get the role and add to to_return
            to_return.append([role, data[i][1]])
        return to_return

    async def add(self, ctx: commands.Context | discord.Interaction, emoji: discord.Emoji | str, role: discord.Role,
                  inverse: bool | str = None, message_id: int | str = None) -> None:

        ctx_type = self.bot.get_context_type(ctx)
        if ctx_type is self.ContextTypes.Unknown:
            return

        if not ctx.guild.me.guild_permissions.manage_roles:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "I do not have manage-role permissions!",
                                                             desc="I need these permissions to create the reaction role.")
            return

        if ctx_type == self.ContextTypes.Context and not message_id:
            message_id = ctx.message.reference.message_id

        # Check if custom emoji
        custom_emoji = False
        if type(emoji) is not discord.Emoji:  # todo: check this will actually work
            try:
                emoji = await commands.EmojiConverter().convert(ctx, emoji)
                custom_emoji = True
            except commands.errors.EmojiNotFound:
                # If here, emoji is either a standard emoji, or a custom one from another guild
                match = re.match(r"<(a?):([a-zA-Z\d]{1,32}):(\d{15,20})>$",
                                 emoji)  # True if custom emoji (obtained from https://github.com/Rapptz/discord.py/blob/master/discord/ext/commands/converter.py)
                if match:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                     "You cannot add a reaction of a custom emoji from a different server!")
                    return
                custom_emoji = False

        # Add to DB
        if type(inverse) is str:
            inverse = True if inverse and inverse.lower() in ["yes", "y", "true"] else False
        async with self.bot.pool.acquire() as connection:
            if custom_emoji:
                await connection.execute(
                    "INSERT INTO reaction_roles (message_id, emoji_id, role_id, guild_id, channel_id, inverse) VALUES ($1, $2, $3, $4, $5, $6);",
                    message_id, emoji.id, role.id, ctx.guild.id, ctx.channel.id,
                    inverse)  # If custom emoji, store ID in DB
            else:
                await connection.execute(
                    "INSERT INTO reaction_roles (message_id, emoji, role_id, guild_id, channel_id, inverse) VALUES ($1, $2, $3, $4, $5, $6);",
                    message_id, emoji, role.id, ctx.guild.id, ctx.channel.id,
                    inverse)  # If not custom emoji, store emoji in DB

        # Add reaction

        if type(message_id) is str:
            if message_id.isdigit():
                message_id = int(message_id)

        message = await ctx.channel.fetch_message(message_id) if type(message_id) is int else None
        if message:
            await message.add_reaction(emoji)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"Reaction role added to that message!",
                                                               desc=f"{emoji} {'inversely' if inverse else ''} links to {role.mention}")
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not find the specified message!")

    async def remove(self, ctx: commands.Context | discord.Interaction, emoji: discord.Emoji | str,
                     message_id: int | str = None) -> None:
        ctx_type = self.bot.get_context_type(ctx)
        if ctx_type is self.ContextTypes.Unknown:
            return

        if ctx_type == self.ContextTypes.Context and not message_id:
            message_id = ctx.message.reference.message_id

        # Check if custom emoji
        custom_emoji = False
        if type(emoji) is not discord.Emoji:
            try:
                emoji = await commands.EmojiConverter().convert(ctx, emoji)
                custom_emoji = True
            except commands.errors.EmojiNotFound:
                custom_emoji = False

        async with self.bot.pool.acquire() as connection:
            if custom_emoji:
                await connection.execute("DELETE FROM reaction_roles WHERE message_id = $1 AND emoji_id = $2;",
                                         message_id, emoji.id)
            else:
                await connection.execute("DELETE FROM reaction_roles WHERE message_id = $1 AND emoji = $2;", message_id,
                                         str(emoji))

        if type(message_id) is str:
            if message_id.isdigit():
                message_id = int(message_id)

        message = await ctx.channel.fetch_message(message_id) if type(message_id) is int else None
        if message:
            await message.clear_reaction(emoji)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx,
                                                               f"Reaction role removed from that message!",
                                                               desc=f"{emoji} is no longer a reaction role on that message!")
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not find the specified message!")

    async def delete(self, ctx: commands.Context | discord.Interaction, message_id=None) -> None:
        ctx_type = self.bot.get_context_type(ctx)
        if ctx_type is self.ContextTypes.Unknown:
            return

        if ctx_type == self.ContextTypes.Context and not message_id:
            message_id = ctx.message.reference.message_id

        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM reaction_roles WHERE message_id = $1;", message_id)

        if type(message_id) is str:
            if message_id.isdigit():
                message_id = int(message_id)

        message = await ctx.channel.fetch_message(message_id) if type(message_id) is int else None
        if message:
            await message.clear_reactions()
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx,
                                                               f"The message is no longer a reaction role message!")
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not find the specified message!")

    async def showreactionroles(self, ctx: commands.Context | discord.Interaction) -> None:
        ctx_type = self.bot.get_context_type(ctx)
        if ctx_type is self.ContextTypes.Unknown:
            return

        async with self.bot.pool.acquire() as connection:
            data = await connection.fetch("SELECT * FROM reaction_roles WHERE guild_id = $1;", ctx.guild.id)

        embed = discord.Embed(title=f":information_source: {ctx.guild.name} reaction roles",
                              color=self.bot.INFORMATION_BLUE)
        embed.set_footer(
            text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(
                self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author, mode=1)[0])

        message_reactions = {}  # ID -> str (to put in embed)
        message_channels = {}  # ID -> discord.TextChannel
        for rr in data:
            role = ctx.guild.get_role(rr["role_id"])
            emoji = rr["emoji"] or [x for x in ctx.guild.emojis if x.id == rr["emoji_id"]][0]
            if rr["message_id"] not in message_reactions.keys():
                message_reactions[
                    rr["message_id"]] = f"{emoji} -> {role.mention} {'(inverse)' if rr['inverse'] else ''}"
            else:
                message_reactions[
                    rr["message_id"]] += f"\n{emoji} -> {role.mention} {'(inverse)' if rr['inverse'] else ''}"

            if rr["message_id"] not in message_channels.keys():
                message_channels[rr["message_id"]] = self.bot.get_channel(rr["channel_id"])

        for message_id in message_reactions:
            embed.add_field(name=f"{message_id} (in #{message_channels[message_id]})",
                            value=message_reactions[message_id])

        if ctx_type == self.ContextTypes.Context:
            await ctx.reply(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)
