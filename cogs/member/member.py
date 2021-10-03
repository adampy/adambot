import discord
from discord.ext import commands
from discord import Embed, Colour, Status
import re
from datetime import datetime, timedelta
from libs.misc.utils import get_user_avatar_url, get_guild_icon_url


class Member(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.bot.tasks.register_task_type("reminder", self.handle_remind, needs_extra_columns={
            "member_id": "bigint",
            "channel_id": "bigint",
            "guild_id": "bigint",
            "reason": "varchar(255)"})
                
# -----------------------QUOTE------------------------------

    @commands.command(pass_context=True)
    async def quote(self, ctx: commands.Context, messageid: int, channel: discord.TextChannel) -> None:
        """
        Quote a message to remember it.
        """

        try:
            msg = await channel.fetch_message(messageid)
        except Exception:
            await ctx.send(f'```{ctx.prefix}quote <message_id> [channel_id]```')
            return

        user = msg.author
        image = None
        repl = re.compile(r"/(\[.+?)(\(.+?\))/")
        edited = f" (edited at {msg.edited_at.isoformat(' ', 'seconds')})" if msg.edited_at else ''

        content = re.sub(repl, r"\1​\2", msg.content)

        if msg.attachments:
            image = msg.attachments[0]['url']

        embed = Embed(title="Quote link",
                      url=f"https://discordapp.com/channels/{channel.id}/{messageid}",
                      color=user.color,
                      timestamp=msg.created_at)

        if image:
            embed.set_image(url=image)
        embed.set_footer(text=f"Sent by {user.name}#{user.discriminator}", icon_url=get_user_avatar_url(user))
        embed.description = f"❝ {content} ❞" + edited
        await ctx.send(embed=embed)

        try:
            await ctx.message.delete()
        except Exception as e:
            print(e)

# -----------------------FUN------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if type(message.channel) == discord.DMChannel or message.author.bot:
            return

        if 'bruh' in message.content.lower() and not message.author.bot and True not in [message.content.startswith(prefix) for prefix in await self.bot.get_used_prefixes(message)]:  # fix prefix detection
            await self.bot.update_config(message, "bruhs", await self.bot.get_config_key(message, "bruhs") + 1)
        return

    @commands.command(aliases=['bruh'])
    async def bruhs(self, ctx: commands.Context) -> None:
        """See how many bruh moments we've had"""
        async with self.bot.pool.acquire() as connection:
            global_bruhs = await connection.fetchval("SELECT SUM(bruhs) FROM config;")
        
        guild_bruhs = await self.bot.get_config_key(ctx, "bruhs")
        await ctx.send(f'•**Global** bruh moments: **{global_bruhs}**\n•**{ctx.guild.name}** bruh moments: **{guild_bruhs}**')

    @commands.command()
    async def cool(self, ctx: commands.Context, *, text: str) -> None:
        """
        MaKe YoUr MeSsAgE cOoL
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

        await ctx.send(new)
        await ctx.message.delete()

    @commands.command()
    async def cringe(self, ctx: commands.Context) -> None:
        await ctx.message.delete()
        await ctx.send('https://cdn.discordapp.com/attachments/593965137266868234/829480599542562866/cringe.mp4')

    @commands.command()
    async def spamping(self, ctx: commands.Context, amount: str, user: discord.Member, *, message) -> None:
        """
        For annoying certain people
        """

        if not amount.isdigit() or (amount.isdigit() and int(amount) > 100):
            await ctx.send("`amount` given must be an integer less than or equal to 100!")
            return

        if ctx.author.guild_permissions.administrator or await self.bot.get_config_key(ctx, "spamping_access"):  # Only allow command if in private server or admin
            await ctx.message.delete()
            msg = f"{message} {user.mention}"
            for i in range(int(amount)):
                await ctx.send(msg)
        else:
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)

    @commands.command()
    async def ghostping(self, ctx: commands.Context, amount: str, user: discord.Member) -> None:
        """
        For sending a ghostping to annoy certain people
        """
        
        if not amount.isdigit() or (amount.isdigit() and int(amount) > 100):
            await ctx.send("`amount` given must be an integer less than or equal to 100!")
            return

        if ctx.author.guild_permissions.administrator or await self.bot.get_config_key(ctx, "spamping_access"):  # Only allow command if in private server or admin
            await ctx.message.delete()
            for i in range(int(amount)):
                for channel in [channel for channel in ctx.guild.channels if type(channel) == discord.TextChannel]:
                    try:
                        msg = await channel.send(user.mention)
                        await msg.delete()
                    except discord.Forbidden:
                        pass
        else:
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)


# -----------------------USER AND SERVER INFO------------------------------

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        """
        Information about the server.
        """

        guild = ctx.message.guild
        time_ = guild.created_at
        time_since = discord.utils.utcnow() - time_

        join = Embed(title=f'**__{str(guild)}__**',
                     description=f"Created at {self.bot.correct_time(time_).strftime(self.bot.ts_format)}. That's {time_since.days} days ago!",
                     color=Colour.from_rgb(21, 125, 224))
        icon_url = get_guild_icon_url(guild)
        if icon_url:
            join.set_thumbnail(url=icon_url)

        join.add_field(name='Users Online',
                       value=f'{len([x for x in guild.members if x.status != Status.offline])}/{len(guild.members)}')
        if ctx.guild.rules_channel:  # only community
            join.add_field(name='Rules Channel', value=f'{ctx.guild.rules_channel.mention}')
        join.add_field(name='Text Channels', value=f'{len(guild.text_channels)}')
        join.add_field(name='Voice Channels', value=f'{len(guild.voice_channels)}')

        join.add_field(name='Roles', value=f'{len(guild.roles)}')
        join.add_field(name='Owner', value=f'{str(guild.owner)}')
        join.add_field(name='Region', value=str(guild.region))
        join.add_field(name='Server ID', value=f'{guild.id}')

        join.add_field(name='Emoji slots filled', value=f'{len(ctx.guild.emojis)}/{ctx.guild.emoji_limit}')
        join.add_field(name='Sticker slots filled', value=f'{len(ctx.guild.stickers)}/{ctx.guild.sticker_limit}')
        join.add_field(name='Upload size limit', value=f'{guild.filesize_limit/1048576} MB')

        join.add_field(name='Boost level', value=f'{ctx.guild.premium_tier} ({ctx.guild.premium_subscription_count} boosts, {len(ctx.guild.premium_subscribers)} boosters)')
        join.add_field(name='Default Notification Level', value=f'{self.bot.make_readable(guild.default_notifications.name)}')
        join.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (self.bot.correct_time()).strftime(
                self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author))

        await ctx.send(embed=join)

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def userinfo(self, ctx: commands.Context, *, args: str = "") -> None:
        """
        Information about you or a user
        """

        author = ctx.author
        guild = ctx.guild

        if len(args) == 0:
            user = author
        else:
            user = await self.bot.get_spaced_member(ctx, self.bot, args=args)
            args = args.replace("<", "").replace(">", "").replace("@", "").replace("!", "")
            if user is None and args.isdigit():
                user = await self.bot.fetch_user(int(args))  # allows getting some limited info about a user that isn't a member of the guild
            if user is None:
                await ctx.send(embed=Embed(title="Userinfo",
                                           description=f':x:  **Sorry {ctx.author.display_name} we could not find that user!**',
                                           color=Colour.from_rgb(255, 7, 58)))
                return

        is_member = isinstance(user, discord.Member)
        if is_member:
            statuses = ""
            if user.desktop_status.name != "offline":
                statuses += f"{getattr(self.bot.EmojiEnum, user.desktop_status.name.upper())} Desktop "
            if user.web_status.name != "offline":
                statuses += f"{getattr(self.bot.EmojiEnum, user.web_status.name.upper())} Web "
            if user.mobile_status.name != "offline":
                statuses += f"{getattr(self.bot.EmojiEnum, user.mobile_status.name.upper())} Mobile"
            if not statuses:
                statuses = "in offline status"
            else:
                statuses = f"using {statuses}"

            data = Embed(description=f"Chilling {statuses}" if is_member else "", colour=user.colour)
        else:
            data = Embed(colour=user.colour)

        data.add_field(name="User ID", value=f"{user.id}")
        user_created = self.bot.correct_time(user.created_at).strftime(self.bot.ts_format)
        since_created = (ctx.message.created_at - user.created_at).days
        created_on = f"{user_created}\n({since_created} days ago)"
        data.add_field(name="Joined Discord on", value=created_on)

        if is_member:
            roles = user.roles[-1:0:-1]

            joined_at = user.joined_at

            if joined_at is not None:
                since_joined = (ctx.message.created_at - joined_at).days
                user_joined = self.bot.correct_time(joined_at).strftime(self.bot.ts_format)

            else:
                since_joined = "?"
                user_joined = "Unknown"

            voice_state = user.voice

            member_number = (
                    sorted(guild.members, key=lambda m: m.joined_at or ctx.message.created_at).index(user)
                    + 1
            )

            joined_on = f"{user_joined}\n({since_joined} days ago)"

            data.add_field(name="Joined this server on", value=joined_on)
            data.add_field(name="Position", value=f"#{member_number}/{len(guild.members)}")
            for activity in user.activities:
                if isinstance(activity, discord.Spotify):
                    data.add_field(name="Listening to Spotify",
                               value=f"{activity.title} by {activity.artist} on {activity.album} ({self.bot.time_str((discord.utils.utcnow() - activity.start).seconds)} elapsed)", inline=False)
                elif isinstance(activity, discord.CustomActivity):
                    data.add_field(name="Custom Status", value=f"{activity.name}", inline=False)
                else:
                    data.add_field(name=f"{type(activity).__name__}", value=f"{activity.name} ({self.bot.time_str((discord.utils.utcnow() - activity.start).seconds)} elapsed)\n{activity.details}", inline=False)
            if roles:
                disp_roles = ', '.join([role.name for role in roles[:10]])
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

        data.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (self.bot.correct_time()).strftime(
                self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author))
        flags = user.public_flags.all()  # e.g. hypesquad stuff
        if flags:
            desc = []
            for flag in flags:
                desc.append(self.bot.make_readable(flag.name))
            desc = ", ".join(desc)
            data.add_field(name="Special flags", value=desc, inline=False)

        name = f"{user} ~ {user.display_name}"

        avatar = get_user_avatar_url(user)
        data.set_author(name=name, icon_url=avatar)
        data.set_thumbnail(url=avatar)
        
        await ctx.send(embed=data)

# -----------------------REMIND------------------------------
    async def handle_remind(self, data: dict) -> None:
        try:
            member = self.bot.get_user(data["member_id"])
            message = f'You told me to remind you about this:\n{data["reason"]}'
            try:
                await member.send(message)
            except discord.Forbidden:
                channel = self.bot.get_channel(data["channel_id"])
                await channel.send(f"{member.mention}, {message}")
        except Exception as e:
            print(f'REMIND: {type(e).__name__}: {e}')

    @commands.command(pass_context=True, aliases=['rm', 'remindme'])
    @commands.guild_only()
    async def remind(self, ctx: commands.Context, *, args: str) -> None:
        """
        Command that is executed when a user wants to be reminded of something.
        If the members DMs are closed, the reminder is sent in the channel the command
        was invoked in.
        """

        timeperiod = ''
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"], blank_as_flag="reason")
            timeperiod = parsed_args["time"]
            reason = parsed_args["reason"]
        if not args or not timeperiod:
            await ctx.send(f'```{ctx.prefix}remind <sentence...> -t <time>```')
            return

        str_tp = self.bot.time_str(timeperiod)  # runs it through a convertor because hodor's OCD cannot take seeing 100000s
        str_reason = "*Reminder:* " + (reason if reason else "(Not specified)")
        reminder = "*When:* " + str_tp + " ago\n" + str_reason

        if len(reminder) >= 256:
            await ctx.send('Please shorten your reminder to under 256 characters.')
            return

        await self.bot.tasks.submit_task("reminder", datetime.utcnow() + timedelta(seconds=timeperiod),
                                         {"member_id": ctx.author.id, "channel_id": ctx.channel.id,
                                          "guild_id": ctx.guild.id, "reason": reminder})

        await ctx.send(
            f":ok_hand: You'll be reminded in {str_tp} via a DM! (or in this channel if your DMs are closed)")

# -----------------------AVATAR------------------------------

    @commands.command(pass_context=True, aliases=["pfp"])
    async def avatar(self, ctx: commands.Context, member: discord.User = None) -> None:
        if not member:
            member = ctx.author

        await ctx.send(get_user_avatar_url(member))

# -----------------------COUNTDOWNS------------------------------

    @commands.command(pass_context=True, aliases=['results', 'gcseresults', 'alevelresults'])
    async def resultsday(self, ctx: commands.Context, hour: str = "") -> None:
        if ctx.invoked_with in ["resultsday", "gcseresults", "results", None]:
            which = "GCSE"
        else:
            which = "A-Level"
        if not hour:
            hour = 10
        else:
            try:
                hour = int(hour)
            except ValueError:
                await ctx.send('You must choose an integer between 0 and 23 for the command to work!')

        if not 0 <= hour < 24:
            await ctx.send('The hour must be between 0 and 23!')
            return

        if hour == 12:
            string = 'noon'
        elif hour == 0:
            string = '0:00AM'
        elif hour >= 12:
            string = f'{hour - 12}PM'
        else:
            string = f'{hour}AM'
        rn = self.bot.correct_time()
        if which == "GCSE":
            time_ = self.bot.correct_time(datetime(year=2022, month=8, day=18, hour=hour, minute=0, second=0))
        else:
            time_ = self.bot.correct_time(datetime(year=2022, month=8, day=11, hour=hour, minute=0, second=0))
        embed = Embed(title=f"Countdown until {which} results day at {string} (on {time_.day}/{time_.month}/{time_.year})",
                      color=Colour.from_rgb(148, 0, 211))

        if rn > time_:
            embed.description = "Results have already been released!"
        else:
            time_ = time_ - rn
            m, s = divmod(time_.seconds, 60)
            h, m = divmod(m, 60)
            embed.description = f"{time_.days} days {h} hours {m} minutes {s} seconds remaining"
        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author))
        icon_url = get_guild_icon_url(ctx.guild)
        if icon_url:
            embed.set_thumbnail(url=icon_url)
        await ctx.send(embed=embed)

    @commands.command(pass_context=True, aliases=["exams", "alevels"])
    async def gcses(self, ctx: commands.Context) -> None:
        embed = Embed(title="Information on UK exams", color=Colour.from_rgb(148, 0, 211))
        now = self.bot.correct_time()
        time_ = self.bot.correct_time(datetime(year=2022, month=5, day=16, hour=9, minute=0, second=0))
        if now > time_:
            embed.description = "Exams have already started!"
        else:
            time_ = time_ - now
            m, s = divmod(time_.seconds, 60)
            h, m = divmod(m, 60)
            embed.description = f"{time_.days} days {h} hours {m} minutes {s} seconds remaining until the first exam (RS Paper 1)"

        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=get_user_avatar_url(ctx.author))
        await ctx.send(embed=embed)

    @commands.command(pass_context=True)
    async def code(self, ctx: commands.Context) -> None:
        await ctx.send(f"Adam-Bot code can be found here: {self.bot.CODE_URL}")


def setup(bot) -> None:
    bot.add_cog(Member(bot))
