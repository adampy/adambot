import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from libs.misc.decorators import is_staff, is_staff_slash
from . import starboard_handlers
from .starboard_container import StarboardContainer


class Starboard(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the starboard cog with a provided bot.

        Loads and initialises the StarboardHandlers class
        """

        self.bot = bot
        self.starboards = {}  # Links channel_id -> Starboard
        self.Handlers = starboard_handlers.StarboardHandlers(bot, self)

    # TODO: Some help commands when args are missing would be nice

    # --- Listeners ---

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Listener for reactions being added so the starboards can be managed appropriately.
        """

        await self.Handlers.on_raw_reaction_event(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Listener for reactions being removed so the starboards can be managed appropriately.
        """

        await self.Handlers.on_raw_reaction_event(payload)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel | discord.Thread) -> None:
        """
        Listener for channels being deleted so any starboards tied to them can be automatically cleaned up.
        """

        starboard = await self.Handlers._try_get_starboard(channel.id)
        if starboard:
            await self.Handlers._delete_starboard(channel)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        while not self.bot.online:
            await asyncio.sleep(1)  # Wait else DB won't be available

        async with self.bot.pool.acquire() as connection:
            starboards = await connection.fetch("SELECT * FROM starboard;")
            entries = await connection.fetch("SELECT * FROM starboard_entry;")
            self.starboards = await StarboardContainer.make_starboards(starboards, entries, self.bot)

    # --- Commands ---

    @commands.group()
    async def starboard(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}help starboard```")

    starboard_slash = app_commands.Group(name="starboard", description="View and manage the server starboards")

    @starboard.command(aliases=["list"])
    @commands.guild_only()
    @is_staff()
    async def view(self, ctx: commands.Context) -> None:
        """
        View all of the starboards in the current guild
        """

        await self.Handlers.view(ctx)

    @starboard_slash.command(
        name="view",
        description="View the starboards for this server"
    )
    @is_staff_slash()
    async def view_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command view.
        """

        await self.Handlers.view(interaction)

    @starboard.command()
    @commands.guild_only()
    @is_staff()
    async def create(self, ctx: commands.Context) -> None:
        """
        Start the set up for the creation of a starboard
        """

        await self.Handlers.create(ctx)

    @starboard_slash.command(
        name="create",
        description="Set up a starboard for this server"
    )
    @is_staff_slash()
    async def create_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command create.
        """

        await self.Handlers.create(interaction)

    @starboard.command()
    @commands.guild_only()
    @is_staff()
    async def edit(self, ctx: commands.Context, channel: discord.TextChannel | discord.Thread, option: str,
                   value: str) -> None:
        """
        Edit a starboard setup. `option` can either be "minimum", "emoji", "colour"/"color"/"embed_colour", or "self_star"
        """

        await self.Handlers.edit(ctx, channel, option, value)

    @starboard_slash.command(
        name="edit",
        description="Edit an existing starboard setup on this server"
    )
    @app_commands.describe(
        channel="The channel or thread of the starboard to edit",
        option="The option of the starboard to edit",
        value="The value to set the option to"
    )
    @is_staff_slash()
    async def edit_slash(self, interaction: discord.Interaction,
                         channel: discord.TextChannel | app_commands.AppCommandThread, option: str, value: str) -> None:
        """
        Slash equivalent of the classic command edit.
        """

        await self.Handlers.edit(interaction, channel, option, value)

    @starboard.command()
    @commands.guild_only()
    @is_staff()
    async def delete(self, ctx: commands.Context, channel: discord.TextChannel | discord.Thread) -> None:
        """
        Delete a starboard setup and all its entries from the bot
        """

        await self.Handlers.delete(ctx, channel)

    @starboard_slash.command(
        name="delete",
        description="Delete a starboard from this server"
    )
    @app_commands.describe(
        channel="The channel or thread to delete the starboard setup from"
    )
    @is_staff_slash()
    async def delete_slash(self, interaction: discord.Interaction,
                           channel: discord.TextChannel | app_commands.AppCommandThread) -> None:
        """
        Slash equivalent of the classic command delete.
        """

        await self.Handlers.delete(interaction, channel)

    # --- Error handlers ---
    @edit.error
    async def starboard_edit_error(self, ctx: commands.Context, error) -> None:
        """
        Handles errors that occur in the edit command
        """

        if isinstance(error, commands.errors.ChannelNotFound):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That channel does not exist")
        elif isinstance(error, commands.MissingRequiredArgument):
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Starboard edit help",
                                                                   desc=f"""To edit the starbooard you need to execute the command like this: `{ctx.prefix}starboard edit #starboard_channel option value`
 `option` must be one of 'minimum', 'emoji', 'colour'/'color'/'embed_colour', or 'self_star'\n`value` is the value that you want to change it do""")

    @delete.error
    async def starboard_delete_error(self, ctx: commands.Context, error) -> None:
        """
        Handles errors that occur in the delete command
        """

        if isinstance(error, commands.errors.ChannelNotFound):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That channel does not exist")


async def setup(bot) -> None:
    await bot.add_cog(Starboard(bot))
