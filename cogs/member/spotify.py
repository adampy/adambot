# Adapted from Hodor's private bot

import discord
from discord.ext import commands
from discord import Embed, Colour
from typing import Union
from libs.misc.utils import get_user_avatar_url


class Spotify(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command(name="spotify", aliases=["spotifyinfo"], pass_context=True)
    async def spotify_info(self, ctx: commands.Context, *, args: Union[discord.Member, str] = "") -> None:
        if len(args) == 0:
            user = ctx.message.author
        else:
            if type(args) is not discord.Member:
                user = await self.bot.get_spaced_member(ctx, self.bot, args=args)
            else:
                user = args
            if user is None:
                fail_embed = Embed(title="Spotify info", description=f':x:  **Sorry {ctx.author.display_name} we could not find that user!**', color=Colour.from_rgb(255, 7, 58))
                fail_embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                        self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author))
                await ctx.send(embed=fail_embed)
                return

        spotify_activity = None
        for i in range(0, len(user.activities)):
            if type(user.activities[i]).__name__ == "Spotify":
                spotify_activity = user.activities[i]
                break
        if spotify_activity is None:
            fail_embed = Embed(title=f"Spotify info for {user}", description="The user isn't currently listening to Spotify\n*(note that this can't be detected unless Spotify is visible on the status)*", colour=user.colour)
            fail_embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author))
            await ctx.message.channel.send(embed=fail_embed)
            return
        duration = spotify_activity.duration.seconds
        minutes = duration//60
        seconds = duration % 60
        if seconds < 10:
            seconds = "0" + str(seconds)
        song_start = self.bot.correct_time(spotify_activity.start).strftime("%H:%M:%S")
        song_end = self.bot.correct_time(spotify_activity.end).strftime("%H:%M:%S")
        embed = Embed(title=f"Spotify info", colour=user.colour)
        embed.add_field(name="Track", value=f"{spotify_activity.title}")
        embed.add_field(name="Artist(s)", value=f"{spotify_activity.artist}")
        embed.add_field(name="Album", value=f"{spotify_activity.album}")
        embed.add_field(name="Track Length", value=f"{minutes}:{seconds}")
        embed.add_field(name="Time This Song Started", value=f"{song_start}")
        embed.add_field(name="Time This Song Will End", value=f"{song_end}")
        embed.add_field(name="Party ID (Premium Only)", value=f"{spotify_activity.party_id}")
        embed.add_field(name="Song's Spotify Link", value=f"https://open.spotify.com/track/{spotify_activity.track_id}", inline=False)
        embed.set_thumbnail(url=spotify_activity.album_cover_url)
        embed.set_author(name=f"{user}", icon_url=get_user_avatar_url(user))
        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author))
        await ctx.message.channel.send(embed=embed)


def setup(bot) -> None:
    bot.add_cog(Spotify(bot))
