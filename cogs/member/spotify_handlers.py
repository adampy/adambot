import discord
from discord import Embed, Colour
from discord.ext import commands

from libs.misc.utils import get_user_avatar_url

from adambot import AdamBot


class SpotifyHandlers:
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.ContextTypes = self.bot.ContextTypes

    async def spotify(self, ctx: commands.Context | discord.Interaction,
                      user: discord.Member | discord.User | str = "") -> None:
        """
        Handler for the spotify commands.

        Constructs and send the spotifyinfo embeds.
        """

        ctx_type = self.bot.get_context_type(ctx)
        if ctx_type == self.ContextTypes.Unknown:
            return

        if ctx_type == self.ContextTypes.Context:
            author = ctx.author
        else:
            author = ctx.user

        if not user or (type(user) is str and len(user) == 0):
            user = author
        elif type(user) is str:
            user = await self.bot.get_spaced_member(ctx, self.bot, args=user)

            if user is None:
                fail_embed = Embed(title="Spotify info",
                                   description=f":x:  **Sorry {author.display_name} we could not find that user!**",
                                   color=Colour.from_rgb(255, 7, 58))
                fail_embed.set_footer(text=f"Requested by: {author.display_name} ({author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format),
                                      icon_url=get_user_avatar_url(author, mode=1)[0])

                if ctx_type == self.ContextTypes.Context:
                    await ctx.send(embed=fail_embed)
                else:
                    await ctx.response.send_message(embed=fail_embed)
                return

        spotify_activity = None
        for i in range(0, len(user.activities)):
            if type(user.activities[i]).__name__ == "Spotify":
                spotify_activity = user.activities[i]
                break

        if spotify_activity is None:
            fail_embed = Embed(title=f"Spotify info for {user}",
                               description="The user isn't currently listening to Spotify\n*(note that this can't be detected unless Spotify is visible on the status)*",
                               colour=user.colour)

            fail_embed.set_footer(text=f"Requested by: {author.display_name} ({author})\n" + (
                self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(embed=fail_embed)
            else:
                await ctx.response.send_message(embed=fail_embed)

            return

        duration = spotify_activity.duration.seconds
        minutes = duration // 60
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
        embed.add_field(name="Song's Spotify Link", value=f"https://open.spotify.com/track/{spotify_activity.track_id}",
                        inline=False)
        embed.set_thumbnail(url=spotify_activity.album_cover_url)
        embed.set_author(name=f"{user}", icon_url=get_user_avatar_url(user, mode=1)[0])
        embed.set_footer(text=f"Requested by: {author.display_name} ({author})\n" + (
            self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)
