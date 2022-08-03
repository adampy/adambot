import discord
from discord import app_commands
from discord.ext import commands

from libs.misc.decorators import is_staff, is_staff_slash
from . import reactionroles_handlers


class ReactionRoles(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

        self.Handlers = reactionroles_handlers.ReactionrolesHandlers(bot)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload) -> None:
        """
        Checks if the reaction was added onto a reaction role message, and if so it is handled
        """

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member.bot:
            return

        data = await self.Handlers._get_roles(payload)  # Get roles linked to that message + emoji pair
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

        data = await self.Handlers._get_roles(payload)
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

    rr_slash = app_commands.Group(name="rr", description="Manage the server's reaction roles")

    @rr.command()
    @commands.guild_only()
    @is_staff()
    async def add(self, ctx: commands.Context, emoji: discord.Emoji | str, role: discord.Role,
                  inverse: str = None) -> None:
        """
        Adds an emoji and a corresponding role to the replied message. If the `inverse` argument == "true" the role is removed upon reaction add and vice versa.
        """

        await self.Handlers.add(ctx, emoji, role, inverse=inverse)

    @rr_slash.command(
        name="add",
        description="Add a reaction role tied to a specific message"
    )
    @app_commands.describe(
        message_id="The message ID of the message to add the reaction to",
        role="The role to bind this reaction to",
        emoji="The emoji linked to this role",
        inverse="Add a reaction to remove, remove to add"
    )
    @is_staff_slash()
    async def add_slash(self, interaction: discord.Interaction, message_id: str, role: discord.Role, emoji: str = "",
                        inverse: bool = False):
        await self.Handlers.add(interaction, emoji, role, inverse=str(inverse), message_id=message_id)

    @rr.command()
    @commands.guild_only()
    @is_staff()
    async def remove(self, ctx: commands.Context, emoji: discord.Emoji | str) -> None:
        """
        Removes an emoji and a corresponding role from the replied message
        """

        await self.Handlers.remove(ctx, emoji)

    @rr_slash.command(
        name="remove",
        description="Remove a reaction role tied to a specific message"
    )
    @app_commands.describe(
        message_id="The message ID of the message to remove the reaction role from",
        emoji="The emoji tied to the reaction role to be removed"
    )
    @is_staff_slash()
    async def remove_slash(self, interaction: discord.Interaction, message_id: str, emoji: str = "") -> None:
        await self.Handlers.remove(interaction, emoji, message_id=message_id)

    @rr.command()
    @commands.guild_only()
    @is_staff()
    async def delete(self, ctx: commands.Context) -> None:
        """
        Removes all the reaction roles from the replied message
        """

        await self.Handlers.delete(ctx)

    @rr_slash.command(
        name="delete",
        description="Remove all the reaction roles from a given message"
    )
    @app_commands.describe(
        message_id="The ID of the message to remove all reaction roles from"
    )
    @is_staff_slash()
    async def delete_slash(self, interaction: discord.Interaction, message_id: str) -> None:
        await self.Handlers.delete(interaction, message_id=message_id)

    @rr.command(name="list")
    @commands.guild_only()
    @is_staff()
    async def showreactionroles(self, ctx: commands.Context) -> None:
        """
        Shows all the current reaction roles in the guild
        """

        await self.Handlers.showreactionroles(ctx)

    @rr_slash.command(
        name="list",
        description="View all the current reaction roles in the guild"
    )
    @is_staff_slash()
    async def showreactionroles_slash(self, interaction: discord.Interaction) -> None:
        await self.Handlers.showreactionroles(interaction)


async def setup(bot) -> None:
    await bot.add_cog(ReactionRoles(bot))
