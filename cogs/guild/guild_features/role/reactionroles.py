import discord
from discord.ext import commands
import re
from libs.misc.decorators import is_staff
from libs.misc.utils import get_user_avatar_url
from typing import Union

class ReactionRoles(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _get_roles(self, payload) -> list:
        """
        Returns a list of (discord.Role, bool) pairs for the given `payload`. bool refers to whether the reaction role gives or removes a role on reaction add.
        """

        async with self.bot.pool.acquire() as connection:
            data = await connection.fetch("SELECT role_id, inverse FROM reaction_roles WHERE message_id = $1 AND (emoji_id = $2 OR emoji = $3);", payload.message_id, payload.emoji.id, str(payload.emoji))

        guild = self.bot.get_guild(payload.guild_id)
        if not data or not guild:
            return None

        to_return = []
        for i in range(len(data)):
            role = guild.get_role(data[i][0])  # Get the role and add to to_return
            to_return.append([role, data[i][1]])
        return to_return

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload) -> None:
        """
        Checks if the reaction was added onto a reaction role message, and if so it is handled
        """

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot:
            return

        data = await self._get_roles(payload)  # Get roles linked to that message + emoji pair
        if not data:
            return  # If no roles linked to that msg, return
        for role, inverse in data:
            if role and not inverse:
                await member.add_roles(role)
            elif role and inverse:
                await member.remove_roles(role)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload) -> None:
        """
        Checks if the reaction was removed from a reaction role message, and if so it is handled
        """

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot:
            return

        data = await self._get_roles(payload)
        if not data:
            return  # If no roles linked to that msg, return

        for role, inverse in data:
            if role and not inverse:
                await member.remove_roles(role)  # TODO: What's the best way to handle exceptions here?
            elif role and inverse:
                await member.add_roles(role)

    @commands.group()
    @commands.guild_only()
    async def rr(self, ctx: commands.Context) -> None:
        """
        Reaction role command group
        """

        if ctx.invoked_subcommand is None:
            await ctx.send(f"Use ```{ctx.prefix}rr add``` in a reply to a message to add a reaction role to it.")
            return

    @rr.command()
    @commands.guild_only()
    @is_staff
    async def add(self, ctx: commands.Context, emoji: Union[discord.Emoji, str], role: discord.Role, inverse: str = None) -> None:
        """
        Adds an emoji and a corresponding role to the replied message. If the `inverse` argument == "true" the role is removed upon reaction add and vice versa.
        """

        if not ctx.me.guild_permissions.manage_roles:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "I do not have manage-role permissions!", desc="I need these permissions to create the reaction role.")
            return

        message_id = ctx.message.reference.message_id

        # Check if custom emoji
        custom_emoji = False
        if type(emoji) is not discord.Emoji:  # todo: check this will actually work
            try:
                emoji = await commands.EmojiConverter().convert(ctx, emoji)
                custom_emoji = True
            except commands.errors.EmojiNotFound:
                # If here, emoji is either a standard emoji, or a custom one from another guild
                match = re.match(r'<(a?):([a-zA-Z0-9]{1,32}):([0-9]{15,20})>$', emoji)  # True if custom emoji (obtained from https://github.com/Rapptz/discord.py/blob/master/discord/ext/commands/converter.py)
                if match:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "You cannot add a reaction of a custom emoji from a different server!")
                    return
                custom_emoji = False

        # Add to DB
        inverse = True if inverse and inverse.lower() in ["yes", "y", "true"] else False
        async with self.bot.pool.acquire() as connection:
            if custom_emoji:
                await connection.execute("INSERT INTO reaction_roles (message_id, emoji_id, role_id, guild_id, channel_id, inverse) VALUES ($1, $2, $3, $4, $5, $6);", message_id, emoji.id, role.id, ctx.guild.id, ctx.channel.id, inverse)  # If custom emoji, store ID in DB
            else:
                await connection.execute("INSERT INTO reaction_roles (message_id, emoji, role_id, guild_id, channel_id, inverse) VALUES ($1, $2, $3, $4, $5, $6);", message_id, emoji, role.id, ctx.guild.id, ctx.channel.id, inverse)  # If not custom emoji, store emoji in DB

        # Add reaction
        message = await ctx.channel.fetch_message(message_id)
        await message.add_reaction(emoji)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"Reaction role added to that message!", desc=f"{emoji} {'inversely' if inverse else ''} links to {role.mention}")

    @rr.command()
    @commands.guild_only()
    @is_staff
    async def remove(self, ctx: commands.Context, emoji: Union[discord.Emoji, str]) -> None:
        """
        Removes an emoji and a corresponding role from the replied message
        """

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
                await connection.execute("DELETE FROM reaction_roles WHERE message_id = $1 AND emoji_id = $2;", message_id, emoji.id)
            else:
                await connection.execute("DELETE FROM reaction_roles WHERE message_id = $1 AND emoji = $2;", message_id, str(emoji))

        message = await ctx.channel.fetch_message(message_id)
        await message.clear_reaction(emoji)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{emoji} is no longer a reaction role on that message!")

    @rr.command()
    @commands.guild_only()
    @is_staff
    async def delete(self, ctx: commands.Context) -> None:
        """
        Removes all the reaction roles from the replied message
        """

        message_id = ctx.message.reference.message_id
        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM reaction_roles WHERE message_id = $1;", message_id)
        
        message = await ctx.channel.fetch_message(message_id)
        await message.clear_reactions()
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"The message is no longer a reaction role message!")

    @rr.command(name="list")
    @commands.guild_only()
    @is_staff
    async def showreactionroles(self, ctx: commands.Context) -> None:
        """
        Shows all the current reaction roles in the guild
        """

        async with self.bot.pool.acquire() as connection:
            data = await connection.fetch("SELECT * FROM reaction_roles WHERE guild_id = $1;", ctx.guild.id)

        embed = discord.Embed(title=f':information_source: {ctx.guild.name} reaction roles', color=self.bot.INFORMATION_BLUE)
        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author, mode=1)[0])
        
        message_reactions = {}  # ID -> str (to put in embed)
        message_channels = {}  # ID -> discord.TextChannel
        for rr in data:
            role = ctx.guild.get_role(rr["role_id"])
            emoji = rr["emoji"] or [x for x in ctx.guild.emojis if x.id == rr["emoji_id"]][0]
            if rr["message_id"] not in message_reactions.keys():
                message_reactions[rr["message_id"]] = f"{emoji} -> {role.mention} {'(inverse)' if rr['inverse'] else ''}"
            else:
                message_reactions[rr["message_id"]] += f"\n{emoji} -> {role.mention} {'(inverse)' if rr['inverse'] else ''}"

            if rr["message_id"] not in message_channels.keys():
                message_channels[rr["message_id"]] = self.bot.get_channel(rr["channel_id"])

        for message_id in message_reactions:
            embed.add_field(name=f"{message_id} (in #{message_channels[message_id]})", value=message_reactions[message_id])

        await ctx.reply(embed=embed)


def setup(bot) -> None:
    bot.add_cog(ReactionRoles(bot))
