import discord
from discord import message
from discord.ext import commands
import asyncpg
from .utils import DefaultEmbedResponses, INFORMATION_BLUE
import re

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _get_role(self, payload):
        async with self.bot.pool.acquire() as connection:
            role_id = await connection.fetchval("SELECT role_id FROM reaction_roles WHERE message_id = $1 AND (emoji_id = $2 OR emoji = $3);", payload.message_id, payload.emoji.id, str(payload.emoji))
        guild = self.bot.get_guild(payload.guild_id)
        if not role_id or not guild:
            return None
        return guild.get_role(role_id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """
        Checks if the reaction was added onto a reaction role message, and if so it is handled
        """
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot:
            return
        role = await self._get_role(payload)
        if role:
            await member.add_roles(role)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """
        Checks if the reaction was removed from a reaction role message, and if so it is handled
        """
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot:
            return
        role = await self._get_role(payload)
        if role:
            await member.remove_roles(role) #TODO: Handle exceptions here

    @commands.group()
    @commands.guild_only()
    async def rr(self, ctx):
        """
        Reaction role command group
        """
        if ctx.invoked_subcommand is None:
            prefixes = await self.bot.get_used_prefixes()
            await ctx.send(f"Use ```{prefixes[2]}rr add``` in a reply to a message to add a reaction role to it.")
            return

    @rr.command()
    @commands.guild_only()
    async def add(self, ctx, emoji, role: discord.Role):
        """
        Adds an emoji and a corresponding role to the replied message
        """
        message_id = ctx.message.reference.message_id

        # Check if custom emoji
        try:
            emoji = await commands.EmojiConverter().convert(ctx, emoji)
            custom_emoji = True
        except commands.errors.EmojiNotFound:
            # If here, emoji is either a standard emoji, or a custom one from another guild
            match = re.match(r'<(a?):([a-zA-Z0-9\_]{1,32}):([0-9]{15,20})>$', emoji) # True if custom emoji (obtained from https://github.com/Rapptz/discord.py/blob/master/discord/ext/commands/converter.py)
            if match:
                await DefaultEmbedResponses.error_embed(self.bot, ctx, "You cannot add a reaction of a custom emoji from a different server!")
                return
            custom_emoji = False

        # Add to DB
        async with self.bot.pool.acquire() as connection:
            if custom_emoji:
                await connection.execute("INSERT INTO reaction_roles (message_id, emoji_id, role_id, guild_id, channel_id) VALUES ($1, $2, $3, $4, $5);", message_id, emoji.id, role.id, ctx.guild.id, ctx.channel.id) # If custom emoji, store ID in DB
            else:
                await connection.execute("INSERT INTO reaction_roles (message_id, emoji, role_id, guild_id, channel_id) VALUES ($1, $2, $3, $4, $5);", message_id, emoji, role.id, ctx.guild.id, ctx.channel.id) # If not custom emoji, store emoji in DB

        # Add reaction
        message = await ctx.channel.fetch_message(message_id)
        await message.add_reaction(emoji)
        await DefaultEmbedResponses.success_embed(self.bot, ctx, f"Reaction role added to that message!", desc=f"{emoji} links to {role.mention}")

    @rr.command()
    @commands.guild_only()
    async def remove(self, ctx, emoji):
        """
        Removes an emoji and a corresponding role from the replied message
        """
        message_id = ctx.message.reference.message_id
        # Check if custom emoji
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
        await DefaultEmbedResponses.success_embed(self.bot, ctx, f"{emoji} is no longer a reaction role on that message!")

    @rr.command()
    @commands.guild_only()
    async def delete(self, ctx):
        """
        Removes the reaction roles from the replied message
        """
        message_id = ctx.message.reference.message_id
        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM reaction_roles WHERE message_id = $1;", message_id)
        
        message = await ctx.channel.fetch_message(message_id)
        await message.clear_reactions()
        await DefaultEmbedResponses.success_embed(self.bot, ctx, f"The message is no longer a reaction role message!")

    @rr.command(name="list")
    @commands.guild_only()
    async def showreactionroles(self, ctx):
        """
        Shows all the current reaction roles in the guild
        """
        async with self.bot.pool.acquire() as connection:
            data = await connection.fetch("SELECT * FROM reaction_roles WHERE guild_id = $1;", ctx.guild.id)

        embed = discord.Embed(title = f':information_source: {ctx.guild.name} reaction roles', color = INFORMATION_BLUE)
        embed.set_footer(text = f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url = ctx.author.avatar_url)
        
        message_reactions = {} # ID -> str (to put in embed)
        message_channels = {} # ID -> discord.TextChannel
        for rr in data:
            role = ctx.guild.get_role(rr["role_id"])
            emoji = rr["emoji"] or [x for x in ctx.guild.emojis if x.id == rr["emoji_id"]][0]
            if rr["message_id"] not in message_reactions.keys():
                message_reactions[rr["message_id"]] = f"{emoji} -> {role.mention}"
            else:
                message_reactions[rr["message_id"]] += f"\n{emoji} -> {role.mention}"

            if rr["message_id"] not in message_channels.keys():
                message_channels[rr["message_id"]] = self.bot.get_channel(rr["channel_id"])

        for message_id in message_reactions:
            embed.add_field(name=f"{message_id} (in #{message_channels[message_id]})", value=message_reactions[message_id])

        await ctx.reply(embed = embed)
        
def setup(bot):
    bot.add_cog(ReactionRoles(bot))
