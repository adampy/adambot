import discord
from discord import Embed, Colour, Message, TextChannel, File
from discord.ext import commands
from math import ceil
from datetime import timedelta
from io import BytesIO

class EmbedPages:
    def __init__(self, page_type, data, title, colour: Colour, bot, initiator, *args, **kwargs):
        self.bot = bot
        self.data = data
        self.title = title
        self.page_type = page_type
        self.top_limit = 0
        self.colour = colour
        self.embed = Embed(title=title + ": Page 1", color = colour)
        self.message: Message = None
        self.page_num = 1
        self.initiator = initiator # Here to stop others using the embed

    async def set_page(self, page_num: int):
        '''Changes the embed accordingly'''
        if self.page_type == PageTypes.REP:
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
                member = self.bot.get_guild(GCSE_SERVER_ID).get_member(self.data[i][0])
                if member is None:
                    user = await self.bot.fetch_user(self.data[i][0])
                    member = f"{str(user)} - this person is currently not in the server - ID: {user.id}"
                self.embed.add_field(name=f"{member}", value=f"{self.data[i][1]}", inline=False)

    async def previous_page(self, *args):
        '''Moves the embed to the previous page'''
        if self.page_num != 1: # Cannot go to previous page if already on first page
            await self.set_page(self.page_num - 1)
            await self.edit()
            
    async def next_page(self, *args):
        '''Moves the embed to the next page'''
        if self.page_num != self.top_limit: # Can only move next if not on the limit
            await self.set_page(self.page_num + 1)
            await self.edit()

    async def first_page(self, *args):
        '''Moves the embed to the first page'''
        await self.set_page(1)
        await self.edit()

    async def last_page(self, *args):
        '''Moves the embed to the last page'''
        await self.set_page(self.top_limit)
        await self.edit()

    async def send(self, channel: TextChannel, *args):
        '''Sends the embed message. The message is deleted after 300 seconds (5 minutes).'''
        self.message = await channel.send(embed = self.embed, delete_after = 300)
        await self.message.add_reaction(EmojiEnum.MIN_BUTTON)
        await self.message.add_reaction(EmojiEnum.LEFT_ARROW)
        await self.message.add_reaction(EmojiEnum.RIGHT_ARROW)
        await self.message.add_reaction(EmojiEnum.MAX_BUTTON)
        await self.message.add_reaction(EmojiEnum.CLOSE)
        self.bot.pages.append(self)

    async def edit(self, *args):
        '''Edits the message to the current self.embed and updates self.message'''
        await self.message.edit(embed=self.embed)

class PageTypes:
    QOTD = 0
    WARN = 1
    REP = 2

class EmojiEnum:
    MIN_BUTTON = '\U000023ee'
    MAX_BUTTON = '\U000023ed'
    LEFT_ARROW = '\U000025c0'
    RIGHT_ARROW = '\U000025b6'
    BUTTON = '\U00002b55'
    CLOSE = '\N{CROSS MARK}'

class Permissions:
    ROLE_ID = {"Administrator":445195157151809536,
            "Head Mod":445195341310984203,
            "Moderator":445195365625364490,
            "Assistant":445195413343961092,
            "Trial-Assistant":667872197091786793,
            "Staff":445195535901655041,
            "Adam-Bot Developer":740681121863303279,
            "Member":445196497777197056,}

    ADMIN = [ROLE_ID['Administrator']]
    MOD = ADMIN + [ROLE_ID['Head Mod'], ROLE_ID['Moderator']]
    ASSISTANT = MOD + [ROLE_ID['Assistant']]
    TRIALASSISTANT = ASSISTANT + [ROLE_ID['Trial-Assistant']]
    STAFF = TRIALASSISTANT + [ROLE_ID['Staff']]
    MEMBERS = TRIALASSISTANT + [ROLE_ID['Member']]

TIMES = {'w':7*24*60*60,
         'week':7*24*60*60,
         'weeks':7*24*60*60,
         'd':24*60*60,
         'day':24*60*60,
         'days':24*60*60,
         'h':60*60,
         'hour':60*60,
         'hours':60*60,
         'hr':60*60,
         'h':60*60,
         'm':60,
         'minute':60,
         'minutes':60,
         'min':60,
         'mins':60,
         's':1,
         'second':1,
         'seconds':1,
         'sec':1,
         'secs':1}

CHANNELS = {
    "waiting-room":445198121618767872,
    "general":445199175244709898,
    "trivia":498617494693478402,
    "rules":445194263408672769,
    "faqs":583798388718567444,
    "qotd":496472968298496020
}

DISALLOWED_COOL_WORDS = ['need to revise', 'stop revising']
SPAMPING_PERMS = [
394978551985602571, #Adam C
374144745829826572, #Bxnana
]
GCSE_SERVER_ID = 445194262947037185
NEWLINE = '\n'
CODE_URL = "https://github.com/adampy/gcsediscordbot"

async def send_file(fig, channel, filename):
    '''Send data to a channel with filename `filename`'''
    buf = BytesIO()
    fig.savefig(buf)
    buf.seek(0)
    await channel.send(file=File(buf, filename=f'{filename}.png'))


async def get_spaced_member(ctx, args, bot):
    '''Moves hell on Earth to get a guild member object from a given string
    Makes use of last_active, a priority temp list that stores member objects of
    the most recently active members'''
    user = None
    try:
        user = await commands.MemberConverter().convert(ctx, args[0])  # try standard approach before anything daft
    except commands.errors.MemberNotFound:
        try:
            user = await commands.MemberConverter().convert(ctx, ' '.join(args))
        except commands.errors.MemberNotFound:
            # for the love of god

            lists = [bot.last_active[ctx.guild.id], ctx.guild.members]
            attribs = ["display_name", "name"]
            print(bot.last_active)
            for list_ in lists:
                for attrib in attribs:
                    if user is not None:
                        break
                    for member in list_:
                        name = getattr(member, attrib)
                        if args[0] in name or ' '.join(args) in name:
                            user = member
                            break
                    if user is None:
                        for member in list_:
                            name = getattr(member, attrib)
                            if name.lower() == args[0].lower() or name.lower() == ' '.join(args).lower():
                                ## don't need normal checks for this as the converter would have got it already
                                user = member
                                break
                    if user is None:
                        for member in list_:
                            name = getattr(member, attrib)
                            if args[0].lower() in name.lower() or ' '.join(args).lower() in name.lower():
                                user = member
                                break

    return user


def ordinal(n: int) -> str:
    '''Returns the shortened ordinal for the cardinal number given. E.g. 1 -> "1st", 74 -> "74th"''' #https://stackoverflow.com/questions/9647202/ordinal-numbers-replacement
    suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    return str(n) + suffix

def separate_args(args):
    '''Given the args tuple (from *args) and returns seconds in index position 0 and reason in index position 1'''
    arg_list = [arg for arg in ' '.join(args).split('-') if arg]
    seconds = 0
    reason = ''
    for item in arg_list:
        if item[0] == 't':
            time = item[1:].strip()
            times = []
            #split after the last character before whitespace after int
            temp1 = '' #time
            temp2 = '' #unit
            for i, letter in enumerate(time):
                if letter == ' ' and (temp1 and temp2):
                    times.append([temp1, temp2])
                    temp1, temp2 = '', ''
                    #print('append')
                if letter.isdigit():
                    if not temp2:
                        temp1 += letter
                        #print('add time')
                    else:
                        times.append([temp1, temp2])
                        temp1, temp2 = '', ''
                        temp1 += letter
                        #print('append')
                else:
                    if temp1 and letter != ' ':
                        temp2 += letter
                        #print('add letter')
            times.append([temp1, temp2])

            print(times)
            for sets in times:

                try:
                    time, unit = sets
                    if unit in TIMES.keys():
                        multiplier = TIMES[unit]
                        seconds += int(time)*multiplier
                except ValueError:
                    pass

            print(seconds)

        if item[0] == 'r':
            reason = item[1:].strip()
            print(reason)
    return seconds, reason

def time_arg(arg):
    '''Given a time argument gets the time in seconds'''
    total = 0
    times = arg.split(' ')
    if len(times) == 0:
        return 0
    #else
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
