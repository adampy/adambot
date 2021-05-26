from discord import Embed, Colour, Message, File
from discord.ext import commands
from math import ceil
from datetime import timedelta
from io import BytesIO, StringIO


class EmbedPages:
    def __init__(self, page_type, data, title, colour: Colour, bot, initiator, channel, *args, **kwargs):
        self.bot = bot
        self.data = data
        self.title = title
        self.page_type = page_type
        self.top_limit = 0
        self.colour = colour
        self.embed = Embed(title=title + ": Page 1", color=colour)
        self.message: Message = None
        self.page_num = 1
        self.initiator = initiator # Here to stop others using the embed
        self.channel = channel

    async def set_page(self, page_num: int):
        """Changes the embed accordingly"""
        if self.page_type == PageTypes.REP:
            self.data = [x for x in self.data if self.channel.guild.get_member(x[0]) is not None]
            page_length = 10
        else:
            page_length = 5
        self.top_limit = ceil(len(self.data)/page_length)

        # Clear previous data
        self.embed = Embed(title=f"{self.title}: Page {page_num}/{self.top_limit}", color = self.colour)

        # Gettings the wanted data
        self.page_num = page_num
        page_num -= 1
        for i in range(page_length*page_num, min(page_length*page_num + page_length, len(self.data))):
            if self.page_type == PageTypes.QOTD:
                question_id = self.data[i][0]
                question = self.data[i][1]
                member_id = int(self.data[i][2])
                user = await self.bot.fetch_user(member_id)
                date = (self.data[i][3]+timedelta(hours=1)).strftime('%H:%M on %d/%m/%y')
            
                self.embed.add_field(name=f"{question_id}. {question}", value=f"{date} by {user.name if user else '*MEMBER NOT FOUND*'} ({member_id})", inline=False)

            elif self.page_type == PageTypes.WARN:
                staff = await self.bot.fetch_user(self.data[i][2])
                member = await self.bot.fetch_user(self.data[i][1])

                if member:
                    member_string = f"{str(member)} ({self.data[i][1]}) Reason: {self.data[i][4]}"
                else:
                    member_string = f"DELETED USER ({self.data[i][1]}) Reason: {self.data[i][4]}"

                if staff:
                    staff_string = f"{str(staff)} ({self.data[i][2]})"
                else:
                    staff_string = f"DELETED USER ({self.data[i][2]})"

                self.embed.add_field(name=f"**{self.data[i][0]}** : {member_string}",
                                     value=f"{self.data[i][3].strftime('On %d/%m/%Y at %I:%M %p')} by {staff_string}",
                                     inline=False)

            elif self.page_type == PageTypes.REP:
                member = self.channel.guild.get_member(self.data[i][0])
                #if member is None:
                #    user = await self.bot.fetch_user(self.data[i][0])
                #    member = f"{str(user)} - this person is currently not in the server - ID: {user.id}"
                #if member is not None:
                self.embed.add_field(name=f"{member.display_name}", value=f"{self.data[i][1]}", inline=False)

    async def previous_page(self, *args):
        """Moves the embed to the previous page"""
        if self.page_num != 1: # Cannot go to previous page if already on first page
            await self.set_page(self.page_num - 1)
            await self.edit()
            
    async def next_page(self, *args):
        """Moves the embed to the next page"""
        if self.page_num != self.top_limit: # Can only move next if not on the limit
            await self.set_page(self.page_num + 1)
            await self.edit()

    async def first_page(self, *args):
        """Moves the embed to the first page"""
        await self.set_page(1)
        await self.edit()

    async def last_page(self, *args):
        """Moves the embed to the last page"""
        await self.set_page(self.top_limit)
        await self.edit()

    async def send(self, *args):
        """Sends the embed message. The message is deleted after 300 seconds (5 minutes)."""
        self.message = await self.channel.send(embed = self.embed, delete_after = 300)
        await self.message.add_reaction(EmojiEnum.MIN_BUTTON)
        await self.message.add_reaction(EmojiEnum.LEFT_ARROW)
        await self.message.add_reaction(EmojiEnum.RIGHT_ARROW)
        await self.message.add_reaction(EmojiEnum.MAX_BUTTON)
        await self.message.add_reaction(EmojiEnum.CLOSE)
        self.bot.pages.append(self)

    async def edit(self, *args):
        """Edits the message to the current self.embed and updates self.message"""
        await self.message.edit(embed=self.embed)


class PageTypes:
    QOTD = 0
    WARN = 1
    REP = 2


class Todo:
    UNMUTE = 1
    UNBAN = 2
    DEMOGRAPHIC_SAMPLE = 3
    ONE_OFF_DEMOGRAPHIC_SAMPLE = 4


class EmojiEnum:
    MIN_BUTTON = '\U000023ee'
    MAX_BUTTON = '\U000023ed'
    LEFT_ARROW = '\U000025c0'
    RIGHT_ARROW = '\U000025b6'
    BUTTON = '\U00002b55'
    CLOSE = '\N{CROSS MARK}'


class Permissions:
    ROLE_ID = {
               "Administrator": 445195157151809536,
               "Head Mod": 445195341310984203,
               "Moderator": 445195365625364490,
               "Assistant": 445195413343961092,
               "Trial-Assistant": 667872197091786793,
               "Staff": 445195535901655041,
               "Adam-Bot Developer": 740681121863303279,
               "Member": 445196497777197056,
               "Priv": 593791836209020928,
               "Announcements": 619243003202109470,
    }

    ADMIN = [ROLE_ID['Administrator'], ROLE_ID['Priv']]
    MOD = ADMIN + [ROLE_ID['Head Mod'], ROLE_ID['Moderator']]
    DEV = MOD + [ROLE_ID['Adam-Bot Developer']]  # put here specifically so non-dev assistants can't mess with stuff
    ASSISTANT = MOD + [ROLE_ID['Assistant']]
    TRIALASSISTANT = ASSISTANT + [ROLE_ID['Trial-Assistant']]
    STAFF = TRIALASSISTANT + [ROLE_ID['Staff']]
    MEMBERS = TRIALASSISTANT + [ROLE_ID['Member']]


CHANNELS = {
    "general": 445199175244709898,
    "trivia": 498617494693478402,
}

DISALLOWED_COOL_WORDS = ['need to revise', 'stop revising']
SPAMPING_PERMS = [
    394978551985602571, #Adam C
    374144745829826572, #Bxnana
]

DEVS = [
    394978551985602571, # Adam C
    420961337448071178, # Hodor
    686967704116002827, # Xp
]

def is_dev():
    async def predicate(ctx):
        return ctx.author.id in DEVS
    return commands.check(predicate)

GCSE_SERVER_ID = 445194262947037185
CODE_URL = "https://github.com/adampy/adambot"


async def send_file(fig, channel, filename, extension = "png"): # TODO: Rename this to send_image_file
    """Send data to a channel with filename `filename`"""
    buf = BytesIO()
    fig.savefig(buf)
    buf.seek(0)
    await channel.send(file=File(buf, filename=f'{filename}.{extension}'))

async def send_text_file(text, channel, filename, extension = "txt"):
    """Send a text data to a channel with filename `filename`"""
    buf = StringIO()
    buf.write(text)
    buf.seek(0)
    await channel.send(file=File(buf, filename=f'{filename}.{extension}'))


async def get_spaced_member(ctx, bot, *args):
    """Moves hell on Earth to get a guild member object from a given string
    Makes use of last_active, a priority temp list that stores member objects of
    the most recently active members"""
    if type(args) in [tuple, list]:
        possible_mention = args[0]
    else:
        possible_mention = args
    user = None
    try:
        user = await commands.MemberConverter().convert(ctx, possible_mention)  # try standard approach before anything daft
    except commands.errors.MemberNotFound:
        args = " ".join(args)
        try:
            user = await commands.MemberConverter().convert(ctx, args)
        except commands.errors.MemberNotFound:
            # for the love of god
            lists = [bot.last_active[ctx.guild.id], ctx.guild.members]
            attribs = ["display_name", "name"]
            for list_ in lists:
                for attrib in attribs:
                    if user is not None:
                        break
                    for member in list_:
                        name = getattr(member, attrib)
                        if possible_mention in name or args in name:
                            user = member
                            break
                    if user is None:
                        for member in list_:
                            name = getattr(member, attrib)
                            if name.lower() == possible_mention.lower() or name.lower() == args.lower():
                                ## don't need normal checks for this as the converter would have got it already
                                user = member
                                break
                    if user is None:
                        for member in list_:
                            name = getattr(member, attrib)
                            if possible_mention.lower() in name.lower() or args.lower() in name.lower():
                                user = member
                                break

    return user


def ordinal(n: int) -> str:
    """Returns the shortened ordinal for the cardinal number given. E.g. 1 -> "1st", 74 -> "74th" """ #https://stackoverflow.com/questions/9647202/ordinal-numbers-replacement
    suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    return str(n) + suffix


TIME_UNITS = {
    "w": {"aliases": ("weeks", "week"), "in_seconds": 604800},
    "d": {"aliases": ("days", "day"), "in_seconds": 86400},
    "h": {"aliases": ("hours", "hour", "hr"), "in_seconds": 3600},
    "m": {"aliases": ("minutes", "minute", "mins", "min"), "in_seconds": 60},
    "s": {"aliases": ("seconds", "second", "secs", "sec"), "in_seconds": 1}
}

## WARNING: You are about to observe Area 51 code, proceed with caution


class flag_methods:
    def __init__(self):
        return

    def str_time_to_seconds(string):  # when not close to having a brain aneurysm, rewrite this
                                      # so it can convert up and down to any defined unit, not
                                      # just seconds
        string = string.replace(" ", "")
        for unit in TIME_UNITS:
            for alias in TIME_UNITS[unit]["aliases"]:
                string = string.replace(alias, unit)
        while ".." in string:  # grade A pointless feature
            string = string.replace("..", ".")
        string = list(string)
        times = []
        time_string = ""
        for pos in string:
            if pos.isdigit() or (pos == "." and "." not in time_string):
                time_string += pos
            else:
                times.append([time_string, pos])
                time_string = ""
        seconds = 0
        for time_ in times:
            if len(time_) == 2 and time_[0] and time_[1] in TIME_UNITS:  # check to weed out dodgy stuff
                seconds += float(time_[0]) * TIME_UNITS[time_[1]]["in_seconds"]
        return seconds


class flags:
    def __init__(self):
        self.flag_prefix = "-"
        self.implemented_properties = ["flag", "post_parse_handler"]
        self.flags = {"": {"flag": "", "post_parse_handler": None}}
        self.inv_flags = {"": ""}

    def set_flag(self, flag_name, flag_def):
        assert type(flag_def) is dict and "flag" in flag_def
        assert type(flag_def["flag"]) is str
        assert callable(flag_def.get("post_parse_handler")) or flag_def.get("post_parse_handler") is None
        for property in self.implemented_properties:
            if property not in flag_def:
                flag_def[property] = None
        self.flags[flag_name] = flag_def
        self.inv_flags[flag_def["flag"]] = flag_name

    def remove_flag(self, flag_name):
        if flag_name in self.flags:
            del self.flags[flag_name]

    def separate_args(self, args, fetch=["*"], has_cmd=False, blank_as_flag=None):
        # TODO:
        #   - Use getters for the flags at some point (not strictly necessary but OOP)
        #   - Tidy up if at all possible :P
        #   - possible some of the logic could be replaced by regex but who likes regex?

        args = args.strip()
        if has_cmd:
            args = " " + " ".join(args.split(" ")[1:])
        flag_dict = {}
        startswithflag = False
        for flag in self.inv_flags:
            if args.startswith(f"{self.flag_prefix}{flag}") and flag:
                startswithflag = True
                break
        if not startswithflag:  # then it's blank
            args = self.flag_prefix + (str(self.flags[blank_as_flag]["flag"]) if (blank_as_flag in self.flags) else '') + ' ' + args
        if args.startswith(self.flag_prefix):
            args = " " + args
        args = args.split(f" {self.flag_prefix}")
        args = [a.split(" ") for a in args]
        if not args[0][0]:
            del args[0]
        for a in range(len(args)):
            if len(args[a]) == 1:
                args[a].insert(0, '' if blank_as_flag not in self.flags else self.flags[blank_as_flag]["flag"])
            args[a] = [args[a][0], " ".join(args[a][1:])]
            if (args[a][0] in self.inv_flags) and (self.inv_flags[args[a][0]] in fetch or fetch == ["*"]):
                if self.inv_flags[args[a][0]] in flag_dict:
                    flag_dict[self.inv_flags[args[a][0]]] += " " + args[a][1]
                else:
                    flag_dict[self.inv_flags[args[a][0]]] = args[a][1]
        flags_found = flag_dict.keys()
        for flag in flags_found:
            post_handler = self.flags[flag]["post_parse_handler"]
            if post_handler:
                updated_flag = post_handler(flag_dict[flag])
                flag_dict[flag] = updated_flag

        for fetcher in fetch:
            if fetcher != "*" and fetcher not in flag_dict:
                flag_dict[fetcher] = None  # saves a bunch of boilerplate code elsewhere

        return flag_dict  # YES IT HAS FINISHED! FINALLY!




def time_arg(arg):  # rewrite
    """Given a time argument gets the time in seconds"""
    total = 0
    times = arg.split(' ')
    if len(times) == 0:
        return 0
    for item in times:
        if item[-1] == 'w':
            total += 7*24*60*60*int(item[:-1])
        elif item[-1] == 'd':
            total += 24*60*60*int(item[:-1])
        elif item[-1] == 'h':
            total += 60*60*int(item[:-1])
        elif item[-1] == 'm':
            total += 60*int(item[:-1])
        elif item[-1] == 's':
            total += int(item[:-1])
    return total


def time_str(seconds):  # rewrite before code police get dispatched
    """Given a number of seconds returns the string version of the time
    Is outputted in a format that can be fed into time_arg"""
    weeks = seconds // (7 * 24 * 60 * 60)
    seconds -= weeks * 7 * 24 * 60 * 60
    days = seconds // (24 * 60 * 60)
    seconds -= days * 24 * 60 * 60
    hours = seconds // (60 * 60)
    seconds -= hours * 60 * 60
    minutes = seconds // 60
    seconds -= minutes * 60
    seconds = round(seconds, 0 if str(seconds).endswith(".0") else 1)  # don't think the last bit needs to be as complex for all time units but oh well

    output = ""
    if weeks: output += f"{(str(weeks) + ' ').replace('.0 ', '').strip()}w "
    if days: output += f"{(str(days) + ' ').replace('.0 ', '').strip()}d "
    if hours: output += f"{(str(hours) + ' ').replace('.0 ', '').strip()}h "
    if minutes: output += f"{(str(minutes) + ' ').replace('.0 ', '').strip()}m "
    if seconds: output += f"{(str(seconds) + ' ').replace('.0 ', '').strip()}s"
    return output.strip()


def starts_with_any(string, possible_starts):
    """Given a string and a list of possible_starts, the function returns
    True if string starts with any of the starts in the possible starts.
    Otherwise it returns False."""
    for start in possible_starts:
        if string.startswith(start):
            return True
    return False