# Adapted from Hodor's private bot

import discord
from discord import app_commands
from discord.ext import commands

from . import spotify_handlers


class Spotify(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the spotify cog with a provided bot.

        Loads and initialises the SpotifyHandlers class
        """

        self.bot = bot
        self.Handlers = spotify_handlers.SpotifyHandlers(bot)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        A method which listens for the bot to be ready.

        Syncs the application commands here.
        """

        await self.bot.tree.sync()  # possibly doesn't need to be done on every start

    @commands.command(name="spotify", aliases=["spotifyinfo"])
    async def spotify_info(self, ctx: commands.Context, *, args: discord.Member | discord.User | str = "") -> None:
        """
        View the Spotify info for a given user within the context guild
        """

        await self.Handlers.spotify(ctx, args)

    @app_commands.command(
        name="spotify",
        description="View the spotify status of a user"
    )
    @app_commands.describe(
        user="The member to get the spotify information of"
    )
    async def spotify_info_slash(self, interaction: discord.Interaction, user: discord.Member | discord.User) -> None:
        """
        Slash equivalent of the classic commmand spotify
        """

        await self.Handlers.spotify(interaction, user)


async def setup(bot) -> None:
    await bot.add_cog(Spotify(bot))
