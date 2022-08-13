import re
from datetime import datetime, timedelta

import discord
from discord import Embed, Colour, Status, app_commands
from discord.ext import commands

from libs.misc.utils import get_user_avatar_url, get_guild_icon_url
from libs.misc.handler import CommandHandler

class MemberHandlers(CommandHandler):
    def __init__(self, bot) -> None:
        super().__init__(self, bot)

    async def quote(self, ctx: commands.Context | discord.Interaction, messageid: int | str,
                    channel: int | discord.TextChannel | discord.Thread | app_commands.AppCommandThread) -> None:
        """
        Handler method for the classic and slash quote commands.
        Fetches and displays a specified message from its ID and a channel ID if it exists.
        """
        (ctx_type, author) = self.command_args # Unpack command args

        if type(channel) is int:
            channelid = channel
        else:
            channelid = channel.id

        try:
            msg = await channel.fetch_message(int(messageid))
        except Exception:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid message ID!",
                                                             desc="Could not find a message with the given ID!")
            return

        image = None
        repl = re.compile(r"/(\[.+?)(\(.+?\))/")
        edited = f" (edited at {msg.edited_at.isoformat(' ', 'seconds')})" if msg.edited_at else ""

        content = re.sub(repl, r"\1​\2", msg.content)

        if msg.attachments:
            image = msg.attachments[0].url

        embed = Embed(title="Quote link",
                      url=f"https://discordapp.com/channels/{channelid}/{messageid}",
                      color=author.color,
                      timestamp=msg.created_at)

        if image:
            embed.set_image(url=image)
        embed.set_footer(text=f"Sent by {author.name}#{author.discriminator}",
                         icon_url=get_user_avatar_url(author, mode=1)[0])
        embed.description = f"❝ {content} ❞" + edited

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(embed=embed)

            try:
                await ctx.message.delete()
            except Exception as e:
                print(e)
        else:
            await ctx.response.send_message(embed=embed)

    async def bruhs(self, guild: discord.Guild) -> str:
        """
        Handler for the commands to see how many "bruhs" a specified guild has had
        """

        async with self.bot.pool.acquire() as connection:
            global_bruhs = await connection.fetchval("SELECT SUM(bruhs) FROM config;")
            guild_bruhs = await connection.fetchval("SELECT bruhs FROM config WHERE guild_id=($1)", guild.id)

        return f"•**Global** bruh moments: **{global_bruhs}**\n•**{guild.name}** bruh moments: **{guild_bruhs}**"

    async def cool(self, text: str) -> str:
        """
        A handler for the "cool" commands.

        Converts the text to cool form LiKe ThIs
        """

        new = ""
        uppercase = True
        for index, letter in enumerate(text):
            ascii_num = ord(letter)
            try:
                if not (65 <= ascii_num <= 90 or 97 <= ascii_num <= 122):
                    new += letter
                    continue

                if uppercase:
                    new += letter.upper()
                else:
                    new += letter.lower()
                uppercase = not uppercase
            except Exception:
                new += letter
        return new

    async def cringe(self, ctx) -> str:
        """
        Handler for the "cringe" commands.

        Returns the link to the cringe video.
        """

        return "https://cdn.discordapp.com/attachments/593965137266868234/829480599542562866/cringe.mp4"

    async def spamping(self, ctx: commands.Context | discord.Interaction, amount: str | int,
                       user: discord.Member | discord.Role, message) -> None:
        """
        Handler for the spamping commands.

        Pings a given user role with a given message a specified number of times.
        """

        (ctx_type, author) = self.command_args # Unpack command args

        try:
            amount = int(amount)
        except Exception:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid amount specified!",
                                                             desc="`amount` given must be an integer less than or equal to 100!")
            return

        if author.guild_permissions.administrator or await self.bot.get_config_key(ctx.guild, "spamping_access"):
            if not (0 < amount < 101):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid amount specified!",
                                                                 desc="`amount` given must be an integer less than or equal to 100!")
                return

            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Started spamping")

            msg = f"{message} {user.mention}"
            for i in range(int(amount)):
                await ctx.channel.send(msg)
        else:
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
    
    async def ghostping(self, ctx: commands.Context | discord.Interaction, user: discord.Member | discord.Role,
                        amount: str | int) -> None:
        """
        Handler for the ghostping commands.

        Ghost-pings a given user role with a given message a specified number of times.
        """

        (ctx_type, author) = self.command_args # Unpack command args

        try:
            amount = int(amount)
        except Exception:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid amount specified!",
                                                             desc="`amount` given must be an integer less than or equal to 100!")
            return

        if author.guild_permissions.administrator or await self.bot.get_config_key(ctx.guild, "spamping_access"):
            if not (0 < amount < 101):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid amount specified!",
                                                                 desc="`amount` given must be an integer less than or equal to 100!")
                return

            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Started ghostping")

            for i in range(int(amount)):
                for channel in [channel for channel in ctx.guild.channels if
                                type(channel) in [discord.TextChannel, discord.Thread, app_commands.AppCommandThread]]:
                    try:
                        msg = await channel.send(user.mention)
                        await msg.delete()
                    except discord.Forbidden:
                        pass
        else:
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)

    async def serverinfo(self, guild: discord.Guild, user: discord.Member) -> Embed:
        """
        Handler for the serverinfo commands.

        Constructs and returns the serverinfo embed.
        """

        time_ = guild.created_at
        time_since = discord.utils.utcnow() - time_

        join = Embed(title=f"**__{str(guild)}__**",
                     description=f"Created at {self.bot.correct_time(time_).strftime(self.bot.ts_format)}. That's {time_since.days} days ago!",
                     color=Colour.from_rgb(21, 125, 224))
        icon_url = get_guild_icon_url(guild)
        if icon_url:
            join.set_thumbnail(url=icon_url)

        join.add_field(name="Users Online",
                       value=f"{len([x for x in guild.members if x.status != Status.offline])}/{len(guild.members)}")
        if guild.rules_channel:  # only community
            join.add_field(name="Rules Channel", value=f"{guild.rules_channel.mention}")
        join.add_field(name="Text Channels", value=f"{len(guild.text_channels)}")
        join.add_field(name="Voice Channels", value=f"{len(guild.voice_channels)}")

        join.add_field(name="Roles", value=f"{len(guild.roles)}")
        join.add_field(name="Owner", value=f"{str(guild.owner)}")
        join.add_field(name="Server ID", value=f"{guild.id}")

        join.add_field(name="Emoji slots filled", value=f"{len(guild.emojis)}/{guild.emoji_limit}")
        join.add_field(name="Sticker slots filled", value=f"{len(guild.stickers)}/{guild.sticker_limit}")
        join.add_field(name="Upload size limit", value=f"{guild.filesize_limit / 1048576} MB")

        join.add_field(name="Boost level",
                       value=f"{guild.premium_tier} ({guild.premium_subscription_count} boosts, {len(guild.premium_subscribers)} boosters)")
        join.add_field(name="Default Notification Level",
                       value=f"{self.bot.make_readable(guild.default_notifications.name)}")
        join.set_footer(text=f"Requested by: {user.display_name} ({user})\n" + (self.bot.correct_time()).strftime(
            self.bot.ts_format), icon_url=get_user_avatar_url(user, mode=1)[0])

        return join

    async def userinfo(self, ctx: commands.Context, args: str) -> Embed:
        """
        Handler for the userinfo commands.

        Constructs and returns the userinfo embed.
        """

        author = ctx.author
        guild = ctx.guild

        if len(args) == 0:
            user = author
        else:
            user = await self.bot.get_spaced_member(ctx, self.bot, args=args)
            args = args.replace("<", "").replace(">", "").replace("@", "").replace("!", "")
            if user is None and args.isdigit():
                user = await self.bot.fetch_user(
                    int(args))  # allows getting some limited info about a user that isn't a member of the guild
            if user is None:
                return Embed(
                    title="Userinfo",
                    description=f":x:  **Sorry {ctx.author.display_name} we could not find that user!**",
                    color=Colour.from_rgb(255, 7, 58)
                )

        is_member = isinstance(user, discord.Member)
        if is_member:
            statuses = ""
            if user.desktop_status != discord.Status.offline:
                statuses += f"{getattr(self.bot.EmojiEnum, str(user.desktop_status).upper())} Desktop "
            if user.web_status != discord.Status.offline:
                statuses += f"{getattr(self.bot.EmojiEnum, str(user.web_status).upper())} Web "
            if user.mobile_status != discord.Status.offline:
                statuses += f"{getattr(self.bot.EmojiEnum, str(user.mobile_status).upper())} Mobile"
            if not statuses:
                statuses = "in offline status"
            else:
                statuses = f"using {statuses}"

            data = Embed(description=f"Chilling {statuses}" if is_member else "", colour=user.colour)
        else:
            data = Embed(colour=user.colour)

        data.add_field(name="User ID", value=f"{user.id}")
        user_created = self.bot.correct_time(user.created_at.replace(tzinfo=None)).strftime(self.bot.ts_format)

        now = datetime.utcnow()
        since_created = (now - user.created_at.replace(tzinfo=None)).days
        created_on = f"{user_created}\n({since_created} days ago)"
        data.add_field(name="Joined Discord on", value=created_on)

        if is_member:

            joined_at = user.joined_at.replace(tzinfo=None)

            if joined_at is not None:
                since_joined = (now - joined_at).days
                user_joined = self.bot.correct_time(joined_at).strftime(self.bot.ts_format)

            else:
                since_joined = "?"
                user_joined = "Unknown"

            voice_state = user.voice

            member_number = (
                    sorted(guild.members, key=lambda m: m.joined_at or now).index(user)
                    + 1
            )

            joined_on = f"{user_joined}\n({since_joined} days ago)"

            data.add_field(name="Joined this server on", value=joined_on)
            data.add_field(name="Position", value=f"#{member_number}/{len(guild.members)}")
            for activity in user.activities:
                if isinstance(activity, discord.Spotify):
                    diff = discord.utils.utcnow() - activity.start  # timedeltas have stupid normalisation of days, seconds, milliseconds because that make sense
                    data.add_field(
                        name="Listening to Spotify",
                        value=f"{activity.title} by {activity.artist} on {activity.album} ({self.bot.time_str(diff.seconds + diff.days * 86400)} elapsed)",
                        inline=False
                    )

                elif isinstance(activity, discord.CustomActivity):
                    data.add_field(name="Custom Status", value=f"{activity.name}", inline=False)

                else:
                    """
                    It's worth noting that all activities normally have details attached, but Game objects do NOT have details
                    Rationale: memory optimisation
                    """

                    if activity.start:
                        diff = discord.utils.utcnow() - activity.start
                        diff = f"({self.bot.time_str(diff.seconds + diff.days * 86400)} elapsed)"
                    else:
                        diff = ""
                    data.add_field(name=f"{type(activity).__name__}",
                                   value=f"{activity.name} {diff}\n{'' if not hasattr(activity, 'details') else activity.details}",
                                   inline=False)

            roles = user.roles[1:]
            if roles:
                disp_roles = ", ".join([role.mention for role in roles[:-11:-1]])
                if len(roles) > 10:
                    disp_roles += f" (+{len(roles) - 10} roles)"
                data.add_field(name="Roles", value=disp_roles, inline=False)

            else:
                data.add_field(name="Roles", value="No roles currently!")

            if voice_state and voice_state.channel:
                data.add_field(
                    name="Current voice channel",
                    value=f"{voice_state.channel.mention} ID: {voice_state.channel.id}",
                    inline=False,
                )

        data.set_footer(
            text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (self.bot.correct_time()).strftime(
                self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author, mode=1)[0])
        flags = user.public_flags.all()  # e.g. hypesquad stuff
        if flags:
            desc = []
            for flag in flags:
                desc.append(self.bot.make_readable(
                    flag.name))  # PyCharm likes to complain about this but it's an enum so... it's perfectly valid
            desc = ", ".join(desc)
            data.add_field(name="Special flags", value=desc, inline=False)

        name = f"{user} ~ {user.display_name}"

        avatar = get_user_avatar_url(user, mode=1)[0]
        data.set_author(name=name, icon_url=avatar)
        data.set_thumbnail(url=avatar)

        return data

    async def remind(self, ctx: commands.Context | discord.Interaction, time: int, reason: str = "") -> None:
        """
        Handler for setting up a reminder.

        Submits a reminder task with a given reason and time.
        """
        
        (ctx_type, author) = self.command_args # Unpack command args

        str_tp = self.bot.time_str(time)  # runs it through a convertor because hodor's OCD cannot take seeing 100000s
        str_reason = "*Reminder:* " + (reason if reason else "(Not specified)")
        reminder = "*When:* " + str_tp + " ago\n" + str_reason

        if len(reminder) >= 256:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Reminder is too long!",
                                                             desc="Please shorten your reminder to under 244 characters")
            return

        await self.bot.tasks.submit_task("reminder", datetime.utcnow() + timedelta(seconds=time),
                                         {"member_id": author.id, "channel_id": ctx.channel.id,
                                          "guild_id": ctx.guild.id, "reason": reminder})

        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Reminder created successfully",
                                                           desc=f":ok_hand: You'll be reminded in {str_tp} via a DM! (or in this channel if your DMs are closed)")

    async def code(self) -> str:
        """
        Handler for the code commands.

        Returns the configured code URL.
        """

        return f"Adam-Bot code can be found here: {self.bot.CODE_URL}"

    async def avatar(self, member: discord.Member | discord.User) -> str:
        """
        Handler for the avatar commands.

        Returns the link(s) to the specified user's avatar(s).
        """

        avatar_urls = get_user_avatar_url(member, mode=2)

        if len(avatar_urls) == 1 or avatar_urls[0] == avatar_urls[1]:
            return avatar_urls[0]
        else:
            return f"**ACCOUNT AVATAR (TOP):**\n{avatar_urls[0]}\n**SERVER AVATAR (BOTTOM):**\n{avatar_urls[1]}"

    async def gcses(self, ctx: commands.Context | discord.Interaction, command: str = "gcses") -> None:
        """
        Handler for the gcses commands.

        Constructs and displays the countdown embed.
        """

        (ctx_type, author) = self.command_args # Unpack command args

        embed = Embed(title="Information on UK exams", color=Colour.from_rgb(148, 0, 211))
        now = self.bot.correct_time()
        time_ = self.bot.correct_time(datetime(year=2022, month=5, day=16, hour=9, minute=0, second=0))
        if now > time_:
            embed.description = "Exams have already started!"
        else:
            time_ = time_ - now
            m, s = divmod(time_.seconds, 60)
            h, m = divmod(m, 60)
            if command != "alevels":
                embed.description = f"{time_.days} days {h} hours {m} minutes {s} seconds remaining until the first GCSE exam (RS Paper 1)"
            else:
                embed.description = f"{time_.days} days {h} hours {m} minutes {s} seconds remaining until the first A-level exam (Economics Paper 1)"

        embed.set_footer(text=f"Requested by: {author.display_name} ({author})\n" + (
            self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)


    async def resultsday(self, ctx: commands.Context | discord.Interaction, hour: int | str = 10, which="GCSE") -> None:
        """
        Handler for the resultsday commands.

        Constructs and displays the countdown embed.
        """

        (ctx_type, author) = self.command_args # Unpack command args

        try:
            hour = int(hour)
        except ValueError:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid hour",
                                                             desc="You must choose an integer between 0 and 23 for the command to work!")
            return

        if not 0 <= hour < 24:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid hour",
                                                             desc="You must choose an integer between 0 and 23 for the command to work!")
            return

        if hour == 12:
            string = "12PM"
        elif hour > 12:
            string = f"{hour - 12}PM"
        else:
            string = f"{hour}AM"
        rn = self.bot.correct_time()
        if which == "GCSE":
            time_ = self.bot.correct_time(datetime(year=2022, month=8, day=25, hour=hour, minute=0, second=0))
        else:
            time_ = self.bot.correct_time(datetime(year=2022, month=8, day=18, hour=hour, minute=0, second=0))
        embed = Embed(
            title=f"Countdown until {which} results day at {string} (on {time_.day}/{time_.month}/{time_.year})",
            color=Colour.from_rgb(148, 0, 211))

        if rn > time_:
            embed.description = "Results have already been released!"
        else:
            time_ = time_ - rn
            m, s = divmod(time_.seconds, 60)
            h, m = divmod(m, 60)
            embed.description = f"{time_.days} days {h} hours {m} minutes {s} seconds remaining"

        embed.set_footer(text=f"Requested by: {author.display_name} ({author})\n" + (
            self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])

        icon_url = get_guild_icon_url(ctx.guild)
        if icon_url:
            embed.set_thumbnail(url=icon_url)

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)
