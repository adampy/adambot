import discord
from discord.ext import commands
from discord.utils import get
from discord import Embed, Colour, Status
from .utils import time_str, get_spaced_member, DISALLOWED_COOL_WORDS, Permissions, CODE_URL, \
    GCSE_SERVER_ID, SPAMPING_PERMS, send_text_file
import re
from datetime import datetime, timedelta
import time

class Member(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def in_private_server(ctx):
        return (ctx.guild.id == 593788906646929439) or (ctx.author.id in SPAMPING_PERMS)  # in priv server or is adam

    def in_gcse(self, ctx):  # move to utils
        return ctx.guild.id == GCSE_SERVER_ID

# -----------------------MISC------------------------------

    @commands.command(pass_context=True)
    async def host(self, ctx):
        """Check if the bot is currently hosted locally or remotely"""
        await ctx.send(f"Adam-bot is {'**locally**' if self.bot.LOCAL_HOST else '**remotely**'} hosted right now.")

    @commands.command(pass_context=True)
    async def ping(self, ctx):
        """Gets a ping time by measuring time to send & edit a message"""
        start = time.time()
        out = await ctx.message.channel.send("Pong! (N/A)")
        await out.edit(content="Pong! (" + str(round(1000 * (time.time() - start), 1)) + " milliseconds)")

    @commands.command(pass_context=True)
    async def uptime(self, ctx):
        """View how long the bot has been running for"""
        seconds = round(time.time() - self.bot.start_time)   # Rounds to the nearest integer
        time_string = time_str(seconds)
        await ctx.send(f"Current uptime session has lasted **{time_string}**, or **{seconds}** seconds.")


# -----------------------REVISE------------------------------

    async def handle_revise_keyword(self, message):
        """Internal procedure that handles potential key phrase attempts to get into revision mode"""
        conditions = not message.author.bot and not message.content.startswith(
            '-') and not message.author.id == 525083089924259898 and message.guild.id == GCSE_SERVER_ID
        ctx = await self.bot.get_context(message)
        stoprevising_combos = ["stop revising", "end", "stop", "exit", "finished", "finish", "finished revising",
                               "done revising", "leave"]
        msg = message.content.lower()
        if msg == 'need to revise' and conditions:
            await ctx.invoke(self.bot.get_command('revise'))
        elif msg in stoprevising_combos and conditions:
            await ctx.invoke(self.bot.get_command('stoprevising'))

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS) # TODO: Revising is GCSE9-1 specific - fix that
    @commands.guild_only()
    async def revise(self, ctx):
        """Puts you in revising mode."""
        member = ctx.author
        if member.bot:  # Stops bots from putting theirselves into revising mode
            return
        role = get(member.guild.roles, name='Members')
        await member.remove_roles(role)
        role = get(member.guild.roles, name='Revising')
        await member.add_roles(role)
        await self.bot.get_channel(518901847981948938).send(
            f'{member.mention} Welcome to revising mode! Have fun revising and once you\'re done type `stoprevising`, `end`, `stop`, `exit` or `finished revising` in this channel!')

    @commands.command(pass_context=True) # TODO: Remove GCSE9-1 dependency
    @commands.guild_only()
    async def stoprevising(self, ctx):
        """Exits revising mode."""
        member = ctx.author
        if ctx.channel.id == 518901847981948938:
            role = get(member.guild.roles, name='Revising')
            await member.remove_roles(role)
            role = get(member.guild.roles, name='Members')
            await member.add_roles(role)
            await self.bot.get_channel(445199175244709898).send(f'{member.mention} welcome back from revising mode!\n*You may want to refresh Discord to view any messages you missed in revision mode*')
        elif "Revising" in [y.name for y in member.roles]:
            channel = self.bot.get_channel(518901847981948938)  # Revision escape
            await ctx.send(f'Go to {channel.mention} to stop revising')

# -----------------------LIST------------------------------

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def list(self, ctx, *args):
        """Gives you a list of all the people with a certain role."""
        # if role not entered
        if len(args) <= 0:
            await ctx.send(':x: Please **specify** a **role**')
            return

        # gets the roles that it could be
        role_name = ' '.join(args)
        possible_roles = []
        for role in ctx.message.guild.roles:
            if role_name.lower() == role.name.lower():
                possible_roles.clear()  # Removes bug
                possible_roles.append(role)
                break
            elif role_name.lower() in role.name.lower():
                possible_roles.append(role)

        # narrows it down to 1 role and gets the role id
        if len(possible_roles) == 0:
            await ctx.send(':x: That role does not exist')
        elif len(possible_roles) > 1:
            new_message = 'Multiple roles found. Please try again by entering one of the following roles.\n```'
            new_message = new_message + '\n'.join([role.name for role in possible_roles]) + '```'
            await ctx.send(new_message)
            return
        else:  # when successful
            role = possible_roles[0]
            message = []
            people = []
            # gets all members with that role
            for member in ctx.message.guild.members:
                for search_role in member.roles:
                    if search_role == role:
                        people.append(member)
                        message.append(f'`{member.id}` **{member.name}**')
                        break
            new_message = '\n'.join(message)
            new_message += f"\n------------------------------------\n:white_check_mark: I found **{str(len(message))}** user{'' if len(message) == 0 else 's'} with this role."
            
            if len(new_message) > 2000:
                await send_text_file(new_message, ctx.channel, "roles", "txt")
            else:
                await ctx.send(new_message)
                
# -----------------------MC & CC & WEEABOO------------------------------
    ADDABLE_ROLES = {
        "mc": "Maths Challenge",
        "cc": "CompSci Challenge",
        "ec": "English Challenge",
        "weeaboo": "Weeaboo",
        "announcements": "Announcements",
        "notifications": "Announcements"
    }

    async def manage_role(self, ctx, role_name, member: discord.Member = None):
        """
        Role assign handler. If the member has a role with the specified name, it's removed
        Otherwise it is assigned to the member.
        Returns True if the user was given the role, otherwise False
        """
        if not member:
            member = ctx.author  # of the message context that gets passed
        role = get(member.guild.roles, name=role_name)
        if role_name in [y.name for y in member.roles]:
            await member.remove_roles(role)
        else:
            await member.add_roles(role)
            return True
        return False

    @commands.command(pass_context=True, name=[*ADDABLE_ROLES][0] if ADDABLE_ROLES else None, aliases=[*ADDABLE_ROLES][1:] if ADDABLE_ROLES else [])
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def user_addable_role(self, ctx):
        role_name = self.ADDABLE_ROLES[ctx.invoked_with]
        now_has_role = await self.manage_role(ctx, role_name)
        await ctx.send(f':ok_hand: You have been given `{role_name}` role!' if now_has_role else f':ok_hand: Your `{role_name}` role has vanished!')


# -----------------------QUOTE------------------------------

    @commands.command(pass_context=True)
    async def quote(self, ctx, messageid, channelid=None):
        """Quote a message to remember it."""
        if channelid is not None:
            try:
                channel = self.bot.get_channel(int(channelid))
            except ValueError:
                await ctx.send('Please use a channel id instead of words.')
        else:
            channel = ctx.message.channel

        try:
            msg = await channel.fetch_message(messageid)
        except Exception:

            p = self.bot.configs[ctx.guild.id]["prefix"]
            await ctx.send(f'```{p}quote <message_id> [channel_id]```')
            return

        user = msg.author
        image = None
        repl = re.compile(r"/(\[.+?\])(\(.+?\))/")
        edited = f" (edited at {msg.edited_at.isoformat(' ', 'seconds')})" if msg.edited_at else ''

        content = re.sub(repl, r"\1​\2", msg.content)

        if msg.attachments:
            image = msg.attachments[0]['url']

        embed = Embed(title="Quote link",
                      url=f"https://discordapp.com/channels/{channelid}/{messageid}",
                      color=user.color,
                      timestamp=msg.created_at)

        if image:
            embed.set_image(url=image)
        embed.set_footer(text=f"Sent by {user.name}#{user.discriminator}", icon_url=user.avatar_url)
        embed.description = f"❝ {content} ❞" + edited
        await ctx.send(embed=embed)

        try:
            await ctx.message.delete()
        except Exception as e:
            print(e)

# -----------------------FUN------------------------------

    @commands.Cog.listener()
    async def on_message(self, message):
        if type(message.channel) == discord.DMChannel or message.author.bot:
            return
        conditions = not message.author.bot and not message.content.startswith(
            '-') and not message.author.id == 525083089924259898 and message.guild.id == GCSE_SERVER_ID
        msg = message.content.lower()

        if 'bruh' in msg and not message.author.bot and not message.content.startswith('-'):
            self.bot.configs[message.guild.id]["bruhs"] += 1
            await self.bot.propagate_config(message.guild.id)
        if conditions:
            await self.handle_revise_keyword(message)
        return

    @commands.command(aliases=['bruh'])
    async def bruhs(self, ctx):
        """See how many bruh moments we've had"""
        async with self.bot.pool.acquire() as connection:
            global_bruhs = await connection.fetchval("SELECT SUM(bruhs) FROM config;")
        
        guild_bruhs = self.bot.configs[ctx.guild.id]["bruhs"]
        await ctx.send(f'•**Global** bruh moments: **{global_bruhs}**\n•**{ctx.guild.name}** bruh moments: **{guild_bruhs}**')

    @commands.command()
    async def cool(self, ctx, *message):
        """MaKe YoUr MeSsAgE cOoL"""
        text = ' '.join(message)
        if text.lower() in DISALLOWED_COOL_WORDS:
            await ctx.send("You can't make that message cool!")
            return
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
    async def cringe(self, ctx):
        await ctx.message.delete()
        await ctx.send('https://cdn.discordapp.com/attachments/593965137266868234/829480599542562866/cringe.mp4')

    @commands.command()
    @commands.check(in_private_server)
    async def spamping(self, ctx, amount, user: discord.Member, *message):
        """For annoying certain people"""
        await ctx.message.delete()

        try:
            iterations = int(amount)
        except Exception:
            await ctx.send(f"Please use a number for the amount, not {amount}")
            return

        msg = ' '.join(message) + " " + user.mention
        for i in range(iterations):
            await ctx.send(msg)

    @commands.command()
    @commands.check(in_private_server)
    async def ghostping(self, ctx, amount, user: discord.Member):
        """For sending a ghostping to annoy certain people"""
        await ctx.message.delete()
        for channel in [channel for channel in ctx.guild.channels if type(channel) == discord.TextChannel]:
            for i in range(int(amount)):
                msg = await channel.send(user.mention)
                await msg.delete()

# -----------------------USER AND SERVER INFO------------------------------

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def serverinfo(self, ctx):
        """Information about the server."""
        guild = ctx.message.guild
        time = guild.created_at
        time_since = datetime.utcnow() - time

        join = Embed(title=f'**__{str(guild)}__**',
                     description=f"Created at {self.bot.correct_time(time).strftime(self.bot.ts_format)}. That's {time_since.days} days ago!",
                     value='Server Name', color=Colour.from_rgb(21, 125, 224))
        join.set_thumbnail(url=guild.icon_url)

        join.add_field(name='Region', value=str(guild.region))
        join.add_field(name='Users Online',
                       value=f'{len([x for x in guild.members if x.status != Status.offline])}/{len(guild.members)}')
        join.add_field(name='Text Channels', value=f'{len(guild.text_channels)}')
        join.add_field(name='Voice Channels', value=f'{len(guild.voice_channels)}')
        join.add_field(name='Roles', value=f'{len(guild.roles)}')
        join.add_field(name='Owner', value=f'{str(guild.owner)}')
        join.set_footer(text=f'Server ID: {guild.id}')

        await ctx.send(embed=join)

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def userinfo(self, ctx, *args):
        """Information about you or a user"""
        author = ctx.author
        guild = ctx.guild

        if len(args) == 0:
            user = author
        else:
            user = await get_spaced_member(ctx, self.bot, *args)
            if user is None:
                await ctx.send(embed=Embed(title="Userinfo",
                                           description=f':x:  **Sorry {ctx.author.display_name} we could not find that user!**',
                                           color=Colour.from_rgb(255, 7, 58)))
                return

        roles = user.roles[-1:0:-1]

        joined_at = user.joined_at
        since_created = (ctx.message.created_at - user.created_at).days

        if joined_at is not None:
            since_joined = (ctx.message.created_at - joined_at).days
            user_joined = self.bot.correct_time(joined_at).strftime(self.bot.ts_format)
        else:
            since_joined = "?"
            user_joined = "Unknown"
        user_created = self.bot.correct_time(user.created_at).strftime(self.bot.ts_format)
        voice_state = user.voice
        member_number = (
                sorted(guild.members, key=lambda m: m.joined_at or ctx.message.created_at).index(user)
                + 1
        )

        created_on = f"{user_created}\n({since_created} days ago)"
        joined_on = f"{user_joined}\n({since_joined} days ago)"
        activity = f"Chilling in {user.status} status"

        data = Embed(description=activity, colour=user.colour)
        data.add_field(name="Joined Discord on", value=created_on)
        data.add_field(name="Joined this server on", value=joined_on)
        for activity in user.activities:
            if isinstance(activity, discord.Spotify):
                data.add_field(name="Listening to Spotify",
                               value=f"{activity.title} by {activity.artist} on {activity.album}", inline=False)
            elif isinstance(activity, discord.CustomActivity):
                data.add_field(name="Custom Status", value=f"{activity.name}", inline=False)
            else:
                data.add_field(name=f"{type(activity).__name__}", value=f"{activity.name}", inline=False)
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
        data.set_footer(text=f"Member #{member_number} | User ID: {user.id}")

        name = f"{user} ~ {user.display_name}"

        if user.avatar:
            avatar = user.avatar_url_as(static_format="png")
            data.set_author(name=name, icon_url=avatar)
            data.set_thumbnail(url=avatar)
        else:
            data.set_author(name=name)

        await ctx.send(embed=data)

# -----------------------REMIND------------------------------

    @commands.command(pass_context=True, aliases=['rm', 'remindme'])
    @commands.guild_only()
    async def remind(self, ctx, *, args):
        """
        Command that is executed when a user wants to be reminded of something.
        If the members DMs are closed, the reminder is sent in the channel the command
        was invoked in.
        """ 
        async def write(self_write, reminder_write, seconds, ctx):
            """Writes to remind table with the time to remind (e.g. remind('...', 120, <member_id>) would mean '...' is reminded out in 120 seconds for <member_id>)"""
            timestamp = datetime.utcnow()
            new_timestamp = timestamp + timedelta(seconds=seconds)
            async with self_write.bot.pool.acquire() as connection:
                await connection.execute('INSERT INTO remind (member_id, reminder, reminder_time, channel_id) VALUES ($1, $2, $3, $4)',
                                         ctx.author.id, reminder_write, new_timestamp, ctx.channel.id)

        """Given the args tuple (from *args) and returns timeperiod in index position 0 and reason in index position 1"""
        timeperiod = ''
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"], blank_as_flag="reason")
            timeperiod = parsed_args["time"]
            reason = parsed_args["reason"]
        if not args or not timeperiod:
            p = self.bot.configs[ctx.guild.id]["prefix"]
            await ctx.send(f'```{p}remind <sentence...> -t <time>```')
            return

        str_tp = time_str(timeperiod)  # runs it through a convertor because hodor's OCD cannot take seeing 100000s
        str_reason = "*Reminder:* " + (reason if reason else "(Not specified)")
        reminder = "*When:* " + str_tp + " ago\n" + str_reason

        if len(reminder) >= 256:
            await ctx.send('Please shorten your reminder to under 256 characters.')

        await write(self, reminder, timeperiod, ctx)
        await ctx.send(
            f":ok_hand: You'll be reminded in {str_tp} via a DM! (or in this channel if your DMs are closed)")

# -----------------------AVATAR------------------------------

    @commands.command(pass_context=True)
    async def avatar(self, ctx, member: discord.User = None):
        if not member:
            member = ctx.author

        await ctx.send(member.avatar_url)

# -----------------------COUNTDOWNS------------------------------

    @commands.command(pass_context=True, aliases=['results', 'gcseresults', 'alevelresults'])
    async def resultsday(self, ctx, hour=None):
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
            time = datetime(year=2021, month=8, day=12, hour=hour, minute=0, second=0)
        else:
            time = datetime(year=2021, month=8, day=10, hour=hour, minute=0, second=0)
        embed = Embed(title=f"Countdown until {which} results day at {string} (on {time.day}/{time.month}/{time.year})",
                      color=Colour.from_rgb(148, 0, 211))
        time = time.replace(tzinfo=self.bot.display_timezone)
        if rn > time:
            embed.description = "Results have already been released!"
        else:
            time = time - rn
            m, s = divmod(time.seconds, 60)
            h, m = divmod(m, 60)
            embed.description = f"{time.days} days {h} hours {m} minutes {s} seconds remaining"
        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=ctx.guild.icon_url)
        await ctx.send(embed=embed)

    @commands.command(pass_context=True, aliases=["exams", "alevels"])
    async def gcses(self, ctx):
        embed = Embed(title="Information on UK exams",  color=Colour.from_rgb(148, 0, 211),
                      description="UK exams are not going ahead this year and have instead been replaced by teacher assessments!")
        embed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
        #time = datetime(year=2021, month=5, day=10, hour=9, minute=0, second=0) - (
        #        datetime.utcnow() + timedelta(hours=1))  # as above
#
 #       m, s = divmod(time.seconds, 60)
  #      h, m = divmod(m, 60)

        #await ctx.send(f'''Until CS Paper 1 (the first GCSE exam) is
#**{time.days}** days
#**{h}** hours
#**{m}** minutes
#**{s}** seconds''')

    @commands.command(pass_context=True)
    async def code(self, ctx):
        await ctx.send(f"Adam-Bot code can be found here: {CODE_URL}")


def setup(bot):
    bot.add_cog(Member(bot))
