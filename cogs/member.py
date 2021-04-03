import discord
from discord.ext import commands
from discord.utils import get
from discord.errors import NotFound
from discord import Embed, Colour, Status
from .utils import separate_args, time_str, get_spaced_member, DISALLOWED_COOL_WORDS, Permissions, CODE_URL, \
    GCSE_SERVER_ID
import requests
import re
import os
from datetime import datetime, timedelta
import asyncpg
from random import choice as randchoice
import asyncio
import time


class JoeMarjTypeTemplate:
    """Enumeration that tells us what type of message needs to be given."""

    def __init__(self):
        self.NONE = 0
        self.GIF = 1
        self.MSG = 2


JoeMarjType = JoeMarjTypeTemplate()


class Member(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.paper_warn_cooldown = {}

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
        seconds = round(time.time() - self.bot.start_time)   # Rounds to the nearest integer
        time_string = time_str(seconds)
        await ctx.send(f"Current uptime session has lasted **{time_string}**, or **{seconds}** seconds.")

# -----------------------JOE MARJ--------------------------

    async def _joe_marj_check(self, message):
        """Internal method that checks a discord.Message for potential 'Joe Marj' infiltration. Returns a JoeMarjType enum."""
        conditions = not message.author.bot and not message.content.startswith(
            '-') and not message.author.id == 525083089924259898 and message.guild.id == GCSE_SERVER_ID
        joe_marj_gifs = ["tenor.com/bwd9c", "tenor.com/bfk5w", "tenor.com/bwhez", "tenor.com/bwl5l", "tenor.com/bwlhw",
                         "we_floss.gif"]
        disallowed_chars = ["~", "*", "|"]
        msg = message.content.lower()
        for y in disallowed_chars:
            msg = msg.replace(y, "")
        if not conditions:  # Increase in performance to break early
            return JoeMarjType.NONE
        if max([x in msg.lower() for x in joe_marj_gifs]):  # Joe marj gif
            return JoeMarjType.GIF
        elif 'joe' in msg or 'marj' in msg:
            return JoeMarjType.MSG

    async def handle_joe_marj(self, message: discord.Message, delete_after=10):
        """Method that receives a message, and replies to it if a 'Joe Marj' infiltration has been detected. Can receive a `delete_after` integer, which deletes the replies after that many seconds"""
        result = await self._joe_marj_check(message)
        if result == JoeMarjType.GIF:
            await message.channel.send("STOP SENDING JOE MARJ GIF", delete_after=delete_after)
        elif result == JoeMarjType.MSG:
            await message.channel.send("STOP SAYING JOE MARJ", delete_after=delete_after)

# -----------------------PAST PAPERS--------------------------

    async def handle_paper_check(self, message: discord.Message):
        paper_kw = [["2019", "paper"], ["2020", "paper"], ["2021", "paper"], ["mini exam"], ["past", "paper"],
                    ["mini assessment"]]  # singular form of all as the singular is in the plural anyway
        ctx = await self.bot.get_context(message)
        if not self.in_gcse(ctx):  # to ignore priv server
            return
        first_warn = False
        if True in [False not in [x in message.content.lower().replace("-", " ") for x in y] for y in paper_kw]:
            # if a check has multiple conditions, False must not be in it
            # but if any one of the checks comes back True, then the warning message should be sent
            # todo: if this gets too spammy then add some kind of cooldown
            # e.g. once per minute per guild, or per user etc
            if ctx.guild.id not in self.paper_warn_cooldown.keys():
                self.paper_warn_cooldown[ctx.guild.id] = {}
            if message.author.id not in self.paper_warn_cooldown[ctx.guild.id].keys():
                first_warn = True
                self.paper_warn_cooldown[ctx.guild.id][message.author.id] = time.time()
            if (time.time() - self.paper_warn_cooldown[ctx.guild.id][message.author.id]) > 60 or first_warn:
                self.paper_warn_cooldown[ctx.guild.id][message.author.id] = time.time()
                await message.channel.send(
                    f"{message.author.mention} REMINDER: This server **does not** distribute unreleased papers such as the 2019, 2020 or 2021 papers."
                    f"  **This includes 'mini-exams'**."
                    f"\n__**Anyone found distributing these to members through the server or through DMs WILL be banned**__", delete_after=20)
            #else:
            #    await ctx.send(f"TEST: {time.time() - self.paper_warn_cooldown[ctx.guild.id][message.author.id]} into cooldown")

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
    @commands.has_any_role(*Permissions.MEMBERS)
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
            f'{member.mention} Welcome to revising mode! Have fun revising and once you\'re done type `-stoprevising`, `end`, `stop`, `exit` or `finished revising` in this channel!')

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def stoprevising(self, ctx):
        """Exits revising mode."""
        member = ctx.author
        if ctx.channel.id == 518901847981948938:
            role = get(member.guild.roles, name='Revising')
            await member.remove_roles(role)
            role = get(member.guild.roles, name='Members')
            await member.add_roles(role)
            await self.bot.get_channel(445199175244709898).send(f'{member.mention} welcome back from revising mode!')
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
            try:
                await ctx.send(new_message)
            except Exception:  # longer than 2000 letters causes this to be run
                new_message = '\n'.join([f'**{member.display_name}**' for member in people])
                new_message += f'\n------------------------------------\n:white_check_mark: I found **{str(len(message))}** users with this role.'
                if len(new_message) >= 2000:
                    params = {'api_dev_key': os.environ.get("PASTEBIN_KEY"),
                              'api_option': 'paste',
                              'api_paste_code': new_message,
                              'api_paste_private': '1',
                              'api_paste_expire_date': '1D',
                              'api_paste_name': role.name}

                    req = requests.post('https://pastebin.com/api/api_post.php', params)
                    await ctx.send(f'Over 2000 characters. Go to {req.text} to see what I would have said')
                else:
                    await ctx.send('Longer than 2000 characters - member ID\'s have been cut from the message.')
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
        content = ctx.message.content + " " if " " not in ctx.message.content else ""
        role_name = self.ADDABLE_ROLES[content[:content.index(" ")].replace(self.bot.prefix, "")]
        now_has_role = await self.manage_role(ctx, role_name)
        await ctx.send(f':ok_hand: You have been given `{role_name}` role!' if now_has_role else f':ok_hand: Your `{role_name}` role has vanished!')


# -----------------------QUOTE------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
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
            await ctx.send('```-quote <message_id> [channel-id]```')
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
    #    @commands.command()
    #    @commands.guild_only()
    #    async def zyclos(self, ctx):
    #        zyclos = get(ctx.guild.members, id=202861110146236428)
    #        await ctx.send(f'{zyclos.mention} https://tenor.com/view/jusreign-punjabi-indian-gif-5441330')

    @commands.command()
    async def test(self, ctx):
        """Secret Area 51 command."""
        await ctx.send('Testes')

    @commands.Cog.listener()
    async def on_message(self, message):
        if type(message.channel) == discord.DMChannel or message.author.bot:
            return
        conditions = not message.author.bot and not message.content.startswith(
            '-') and not message.author.id == 525083089924259898 and message.guild.id == GCSE_SERVER_ID
        msg = message.content.lower()

        if 'bruh' in msg and conditions:
            async with self.bot.pool.acquire() as connection:
                result = await connection.fetchval("SELECT value FROM variables WHERE variable = 'bruh';")
                await connection.execute("UPDATE variables SET value = ($1) WHERE variable = 'bruh';",
                                         str(int(result) + 1))

        await self.handle_paper_check(message)
        # await self.handle_joe_marj(message)
        await self.handle_revise_keyword(message)
        return

    @commands.Cog.listener()
    async def on_message_edit(self, prev, curr):
        already_warned = await self._joe_marj_check(prev)
        if not already_warned:
            await self.handle_joe_marj(curr)

    @commands.command(aliases=['bruh'])
    async def bruhs(self, ctx):
        """See how many bruh moments we've had"""
        async with self.bot.pool.acquire() as connection:
            bruhs = await connection.fetchval("SELECT value FROM variables WHERE variable = 'bruh'")
            await ctx.send(f'Bruh moments: **{bruhs}**')
            return

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

    @commands.command(aliases=['yikes'])
    async def yike(self, ctx):
        await ctx.send(
            'https://cdn.discordapp.com/attachments/445199175244709898/616755258890387486/29e02f54-4741-40e5-b77d-788bf78b33ba.png')

# -----------------------USER AND SERVER INFO------------------------------

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def serverinfo(self, ctx):
        """Information about the server."""
        guild = ctx.message.guild
        time = guild.created_at
        time_since = datetime.utcnow() - time

        join = Embed(title=f'**__{str(guild)}__**',
                     description=f"Since {time.strftime(self.bot.ts_format)}. That's over {time_since.days} days ago!",
                     value='Server Name', color=Colour.from_rgb(21, 125, 224))
        join.set_thumbnail(url=guild.icon_url)

        join.add_field(name='Region', value=str(guild.region))
        join.add_field(name='Users',
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
            user = await get_spaced_member(ctx, args, self.bot)
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
            user_joined = joined_at.strftime("%d %b %Y %H:%M")
        else:
            since_joined = "?"
            user_joined = "Unknown"
        user_created = user.created_at.strftime("%d %b %Y %H:%M")
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
            data.set_author(name=name, url=avatar)
            data.set_thumbnail(url=avatar)
        else:
            data.set_author(name=name)

        await ctx.send(embed=data)

# -----------------------REMIND------------------------------

    @commands.command(pass_context=True, aliases=['rm', 'remindme'])
    @commands.guild_only()
    async def remind(self, ctx, *args):
        async def write(self_write, reminder_write, seconds, member_id):
            """Writes to remind table with the time to remind (e.g. remind('...', 120, <member_id>) would mean '...' is reminded out in 120 seconds for <member_id>)"""
            timestamp = datetime.utcnow()
            new_timestamp = timestamp + timedelta(seconds=seconds)
            async with self_write.bot.pool.acquire() as connection:
                await connection.execute('INSERT INTO remind (member_id, reminder, reminder_time) values ($1, $2, $3)',
                                         member_id, reminder_write, new_timestamp)

        """Given the args tuple (from *args) and returns timeperiod in index position 0 and reason in index position 1"""
        timeperiod = ''
        if args:
            timeperiod, reason = separate_args(args)
            # print(f"timeperiod is {timeperiod}")
            # print(f"reason is {reason}")
        if not args or not timeperiod:
            await ctx.send('```-remind <sentence...> -t <time>```')
            return

        str_ = ' '.join(args)
        str_tp = time_str(timeperiod)  # runs it through a convertor because hodor's OCD cannot take seeing 100000s
        str_reason = "*Reminder:* " + str_[:str_.index("-t")].replace("-r", "")  # string manipulation go brrrr
        reminder = "*When:* " + str_tp + " ago\n" + str_reason
        # reminder = ' '.join(args).replace("-t ","") + " ago"
        if reminder.startswith(" -r"):
            reminder = reminder[2:]

        if len(reminder) >= 256:
            await ctx.send('Please shorten your reminder to under 256 characters.')
        # seconds = time_arg(timeperiod)
        # seconds = separate_args(timeperiod)[0] # why is this here/needed

        await write(self, reminder, timeperiod, ctx.author.id)
        await ctx.send(
            f":ok_hand: You'll be reminded in {str_tp} via a DM!")  # todo: either/or/and when setting and displaying the reminder, check if member's DMs are open
        # if their DMs aren't open, remind on guild in context

# -----------------------AVATAR------------------------------

    @commands.command(pass_context=True)
    async def avatar(self, ctx, member: discord.User = None):
        if not member:
            member = ctx.author

        await ctx.send(member.avatar_url)

# -----------------------COUNTDOWNS------------------------------

    @commands.command(pass_context=True, aliases=['results'])
    async def resultsday(self, ctx, hour=None):
        if hour is None:
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
        time = datetime(year=2021, month=8, day=12, hour=hour, minute=0, second=0) - (
                datetime.utcnow() + timedelta(hours=1))  # timezone edge case. also date needs updating
        m, s = divmod(time.seconds, 60)
        h, m = divmod(m, 60)

        await ctx.send(f'''Until GCSE results day at {string} it is
**{time.days}** days
**{h}** hours
**{m}** minutes
**{s}** seconds''')  # **{(time.days*24)+h}** hours

    @commands.command(pass_context=True)
    async def gcses(self, ctx):
        time = datetime(year=2021, month=5, day=10, hour=9, minute=0, second=0) - (
                datetime.utcnow() + timedelta(hours=1))  # as above

        m, s = divmod(time.seconds, 60)
        h, m = divmod(m, 60)

        await ctx.send(f'''Until CS Paper 1 (the first GCSE exam) is
**{time.days}** days
**{h}** hours
**{m}** minutes
**{s}** seconds''')


# -----------------------1738------------------------------

    @commands.command(pass_context=True)
    async def toggle1738(self, ctx):
        # db connections
        async with self.bot.pool.acquire() as connection:
            # check if already joined
            member = await connection.fetch("SELECT * FROM ping WHERE member_id = ($1)", ctx.author.id)
            if not member:
                # not on - turn it on
                await connection.execute('INSERT INTO ping (member_id) values ($1)', ctx.author.id)
                await ctx.send(":ok_hand: You will receive notifications for 1738. :tada:")
            else:
                # on - turn it off
                await connection.execute('DELETE FROM ping WHERE member_id = ($1)', ctx.author.id)
                await ctx.send(":ok_hand: You will no longer receive notifications for 1738. :sob:")

    @commands.command(pass_context=True)
    async def code(self, ctx):
        await ctx.send(f"Adam-Bot code can be found here: {CODE_URL}")


def setup(bot):
    bot.add_cog(Member(bot))
