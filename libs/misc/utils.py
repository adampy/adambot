from datetime import datetime
from enum import Enum
from io import BytesIO, StringIO

import discord
from discord import Embed, Colour, File
from discord.ext import commands


class PageTypes:
    QOTD = 0
    WARN = 1
    REP = 2
    CONFIG = 3
    ROLE_LIST = 4
    STARBOARD_LIST = 5


class EmojiEnum:
    MIN_BUTTON = "\U000023ee"
    MAX_BUTTON = "\U000023ed"
    LEFT_ARROW = "\U000025c0"
    RIGHT_ARROW = "\U000025b6"
    BUTTON = "\U00002b55"
    CLOSE = "\N{CROSS MARK}"
    TRUE = "\U00002705"
    FALSE = "\N{CROSS MARK}"
    RECYCLE = "\U0000267b"
    SPEAKING = "\U0001F5E3"

    ONLINE = "\U0001F7E2"
    IDLE = "\U0001F7E1"
    DND = "\U0001F534"
    OFFLINE = "\U000026AB"


DEVS = [
    394978551985602571,  # Adam C
    420961337448071178,  # Hodor
]

CODE_URL = "https://github.com/adampy/adambot"


async def send_image_file(ctx: commands.Context | discord.Interaction, fig,
                          channel: discord.TextChannel | discord.Thread, filename: str, extension: str = "png") -> None:
    """
    Send data to a channel with filename `filename`
    """

    ctx_type = get_context_type(ctx)
    if ctx_type is ContextTypes.Unknown:
        return

    buf = BytesIO()
    fig.savefig(buf)
    buf.seek(0)
    file = File(buf, filename=f"{filename}.{extension}")

    if ctx_type == ContextTypes.Context:
        await channel.send(file=file)
    else:
        await ctx.response.send_message(file=file)


async def send_text_file(ctx: commands.Context | discord.Interaction, text: str,
                         channel: discord.TextChannel | discord.Thread, filename: str, extension: str = "txt") -> None:
    """
    Send a text data to a channel with filename `filename`
    """

    ctx_type = get_context_type(ctx)
    if ctx_type is ContextTypes.Unknown:
        return

    buf = StringIO()
    buf.write(text)
    buf.seek(0)
    file = File(buf, filename=f"{filename}.{extension}")

    if ctx_type == ContextTypes.Context:
        await channel.send(file=file)
    else:
        await ctx.response.send_message(file=file)


async def get_spaced_member(ctx: commands.Context, bot, *, args: str) -> discord.Member | None:
    """
    Moves hell on Earth to get a guild member object from a given string
    Makes use of last_active, a priority temp list that stores member objects of
    the most recently active members
    """

    possible_mention = args.split(" ")[0]
    user = None
    try:
        user = await commands.MemberConverter().convert(ctx,
                                                        possible_mention)  # try standard approach before anything daft
    except commands.errors.MemberNotFound:
        try:
            user = await commands.MemberConverter().convert(ctx, args)
        except commands.errors.MemberNotFound:
            # for the love of god
            lists = [bot.last_active.get(ctx.guild.id, []), ctx.guild.members]
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
                                # don't need normal checks for this as the converter would have got it already
                                user = member
                                break
                    if user is None:
                        for member in list_:
                            name = getattr(member, attrib)
                            if possible_mention.lower() in name.lower() or args.lower() in name.lower():
                                user = member
                                break

    return user


def make_readable(text: str) -> str:
    """
    Turns stuff like ANIMATED_ICON into Animated Icon
    """

    return " ".join([part[:1].upper() + part[1:] for part in text.lower().replace("_", " ").split()])


def ordinal(n: int) -> str:
    """
    Returns the shortened ordinal for the cardinal number given. E.g. 1 -> "1st", 74 -> "74th"
        - https://stackoverflow.com/questions/9647202/ordinal-numbers-replacement
    """

    suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    return str(n) + suffix


TIME_UNITS = {
    "w": {"aliases": ("weeks", "week"), "in_seconds": 604800},
    "d": {"aliases": ("days", "day"), "in_seconds": 86400},
    "h": {"aliases": ("hours", "hour", "hr"), "in_seconds": 3600},
    "m": {"aliases": ("minutes", "minute", "mins", "min"), "in_seconds": 60},
    "s": {"aliases": ("seconds", "second", "secs", "sec"), "in_seconds": 1}
}


# WARNING: You are about to observe Area 51 code, proceed with caution


class flag_methods:
    def __init__(self) -> None:
        return

    @staticmethod
    def str_time_to_seconds(string_: str) -> int:

        # when not close to having a brain aneurysm, rewrite this
        # so it can convert up and down to any defined unit, not
        # just seconds

        string = string_.replace(" ", "")
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
    def __init__(self) -> None:
        self.flag_prefix = "-"
        self.implemented_properties = ["flag", "post_parse_handler"]
        self.flags = {"": {"flag": "", "post_parse_handler": None}}
        self.inv_flags = {"": ""}

    def set_flag(self, flag_name: str, flag_def: dict) -> None:
        assert type(flag_def) is dict and "flag" in flag_def
        assert type(flag_def["flag"]) is str
        assert callable(flag_def.get("post_parse_handler")) or flag_def.get("post_parse_handler") is None
        for property_ in self.implemented_properties:
            if property_ not in flag_def:
                flag_def[property_] = None
        self.flags[flag_name] = flag_def
        self.inv_flags[flag_def["flag"]] = flag_name

    def remove_flag(self, flag_name: str) -> None:
        if flag_name in self.flags:
            del self.flags[flag_name]

    def separate_args(self, args, fetch: list[str] = [], has_cmd: bool = False, blank_as_flag: str = "") -> dict:
        # TODO:
        #   - Use getters for the flags at some point (not strictly necessary but OOP)
        #   - Tidy up if at all possible :P
        #   - possible some of the logic could be replaced by regex but who likes regex?

        if not fetch:
            fetch = ["*"]

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
            args = self.flag_prefix + (
                str(self.flags[blank_as_flag]["flag"]) if (blank_as_flag in self.flags) else "") + " " + args
        if args.startswith(self.flag_prefix):
            args = " " + args
        args = args.split(f" {self.flag_prefix}")
        args = [a.split(" ") for a in args]
        if not args[0][0]:
            del args[0]
        for a in range(len(args)):
            if len(args[a]) == 1:
                args[a].insert(0, "" if blank_as_flag not in self.flags else self.flags[blank_as_flag]["flag"])
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


def time_arg(arg: str) -> int:  # rewrite
    """
    Given a time argument gets the time in seconds
    """

    total = 0
    times = arg.split(" ")
    if len(times) == 0:
        return 0
    for item in times:
        if item[-1] == "w":
            total += 7 * 24 * 60 * 60 * int(item[:-1])
        elif item[-1] == "d":
            total += 24 * 60 * 60 * int(item[:-1])
        elif item[-1] == "h":
            total += 60 * 60 * int(item[:-1])
        elif item[-1] == "m":
            total += 60 * int(item[:-1])
        elif item[-1] == "s":
            total += int(item[:-1])
    return total


def time_str(seconds: int) -> str:  # rewrite before code police get dispatched
    """
    Given a number of seconds returns the string version of the time
    Is outputted in a format that can be fed into time_arg
    """

    weeks = seconds // (7 * 24 * 60 * 60)
    seconds -= weeks * 7 * 24 * 60 * 60
    days = seconds // (24 * 60 * 60)
    seconds -= days * 24 * 60 * 60
    hours = seconds // (60 * 60)
    seconds -= hours * 60 * 60
    minutes = seconds // 60
    seconds -= minutes * 60
    seconds = round(seconds, 0 if str(seconds).endswith(
        ".0") else 1)  # don't think the last bit needs to be as complex for all time units but oh well

    output = ""
    if weeks:
        output += f"{(str(weeks) + ' ').replace('.0 ', '').strip()}w "

    if days:
        output += f"{(str(days) + ' ').replace('.0 ', '').strip()}d "

    if hours:
        output += f"{(str(hours) + ' ').replace('.0 ', '').strip()}h "

    if minutes:
        output += f"{(str(minutes) + ' ').replace('.0 ', '').strip()}m "

    if seconds:
        output += f"{(str(seconds) + ' ').replace('.0 ', '').strip()}s"

    return output.strip()


def starts_with_any(string: str, possible_starts: list[str]) -> bool:
    """
    Given a string and a list of possible_starts, the function returns
    True if string starts with any of the starts in the possible starts.
    Otherwise it returns False.
    """

    for start in possible_starts:
        if string.startswith(start):
            return True
    return False


ERROR_RED = Colour.from_rgb(255, 7, 58)
SUCCESS_GREEN = Colour.from_rgb(57, 255, 20)
INFORMATION_BLUE = Colour.from_rgb(32, 141, 177)
GOLDEN_YELLOW = Colour.from_rgb(252, 172, 66)


# EMBED RESPONSES


class DefaultEmbedResponses:
    @staticmethod
    async def invalid_perms(bot, ctx: commands.Context | discord.Interaction, thumbnail_url: str = "",
                            bare: bool = False, respond_to_interaction=True) -> None | discord.Message:
        """
        Internal procedure that is executed when a user has invalid perms
        """

        ctx_type = get_context_type(ctx)
        if ctx_type == ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            user = ctx.author
        else:
            user = ctx.user

        embed = Embed(title=f":x: You do not have permissions to do that!",
                      description="Only people with permissions (usually staff) can use this command!",
                      color=ERROR_RED)
        if not bare:
            embed.set_footer(text=f"Requested by: {user.display_name} ({user})\n" + bot.correct_time().strftime(
                bot.ts_format), icon_url=get_user_avatar_url(user, mode=1)[0])
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        if ctx_type == ContextTypes.Context:
            return await ctx.reply(embed=embed)
        elif respond_to_interaction and not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed)
        else:
            return await ctx.channel.send(embed=embed)

    @staticmethod
    async def error_embed(bot, ctx: commands.Context | discord.Interaction, title: str, desc: str = "",
                          thumbnail_url: str = "", bare: bool = False, respond_to_interaction=True) -> None | discord.Message:

        ctx_type = get_context_type(ctx)
        if ctx_type == ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            user = ctx.author
        else:
            user = ctx.user

        embed = Embed(title=f":x: {title}", description=desc, color=ERROR_RED)
        if not bare:
            if ctx_type == ContextTypes.Context:
                embed.set_footer(text=f"Requested by: {user.display_name} ({user})\n" + bot.correct_time().strftime(
                    bot.ts_format), icon_url=get_user_avatar_url(user, mode=1)[0])

            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        if ctx_type == ContextTypes.Context:
            return await ctx.reply(embed=embed)
        elif respond_to_interaction and not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed)
        else:
            return await ctx.channel.send(embed=embed)

    @staticmethod
    async def success_embed(bot, ctx: commands.Context | discord.Interaction, title: str, desc: str = "",
                            thumbnail_url: str = "", bare: bool = False, respond_to_interaction=True) -> None | discord.Message:

        ctx_type = get_context_type(ctx)
        if ctx_type == ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            user = ctx.author
        else:
            user = ctx.user

        embed = Embed(title=f":white_check_mark: {title}", description=desc, color=SUCCESS_GREEN)
        if not bare:
            embed.set_footer(text=f"Requested by: {user.display_name} ({user})\n" + bot.correct_time().strftime(
                bot.ts_format), icon_url=get_user_avatar_url(user, mode=1)[0])
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        if ctx_type == ContextTypes.Context:
            return await ctx.reply(embed=embed)
        elif respond_to_interaction and not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed)
        else:
            return await ctx.channel.send(embed=embed)

    @staticmethod
    async def information_embed(bot, ctx: commands.Context | discord.Interaction, title: str, desc: str = "",
                                thumbnail_url: str = "", bare: bool = False, respond_to_interaction=True) -> None | discord.Message:

        ctx_type = get_context_type(ctx)
        if ctx_type == ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            user = ctx.author
        else:
            user = ctx.user

        embed = Embed(title=f":information_source: {title}", description=desc, color=INFORMATION_BLUE)
        if not bare:
            embed.set_footer(text=f"Requested by: {user.display_name} ({user})\n" + bot.correct_time().strftime(
                bot.ts_format), icon_url=get_user_avatar_url(user, mode=1)[0])
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        if ctx_type == ContextTypes.Context:
            return await ctx.reply(embed=embed)
        elif respond_to_interaction and not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed)
        else:
            return await ctx.channel.send(embed=embed)

    @staticmethod
    async def question_embed(bot, ctx: commands.Context | discord.Interaction, title: str, desc: str = "",
                             thumbnail_url: str = "", bare: bool = False,
                             respond_to_interaction=True) -> None | discord.Message:

        ctx_type = get_context_type(ctx)
        if ctx_type == ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            user = ctx.author
        else:
            user = ctx.user

        embed = Embed(title=f":grey_question: {title}", description=desc, color=INFORMATION_BLUE)
        if not bare:
            embed.set_footer(text=f"Requested by: {user.display_name} ({user})\n" + bot.correct_time().strftime(
                bot.ts_format), icon_url=get_user_avatar_url(user, mode=1)[0])
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        if ctx_type == ContextTypes.Context:
            return await ctx.reply(embed=embed)
        elif respond_to_interaction and not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed)
        else:
            return await ctx.channel.send(embed=embed)


def get_guild_icon_url(guild: discord.Guild) -> str:
    """
    Returns either a `str` which corresponds to `guild`'s icon. If none is present, an empty string is returned
    """

    return guild.icon if hasattr(guild, "icon") else ""


def get_user_avatar_url(member: discord.Member | discord.User, mode: int = 0) -> list[str]:
    """
    Returns a `str` which corresponds to `user`'s current avatar url

    Mode:

    0 - Account avatar
    1 - Guild avatar - will return account avatar if None
    2 - Both
    """

    account_avatar_url = member.avatar
    if not account_avatar_url:
        account_avatar_url = member.default_avatar.url
    else:
        account_avatar_url = account_avatar_url.url

    guild_avatar_url = account_avatar_url if (not hasattr(member, "guild_avatar") or not hasattr(member.guild_avatar,
                                                                                                 "url") or not member.guild_avatar.url) else member.guild_avatar.url

    match mode:  # OMG A SWITCH CASE
        case 0:
            return [account_avatar_url]
        case 1:
            return [guild_avatar_url]
        case 2:
            return [account_avatar_url, guild_avatar_url]
        case _:
            return []


async def interaction_context(bot, interaction: discord.Interaction) -> commands.Context:
    """
    Can't get proper context from interaction and the standard `get_context` requires a message

    However this breaks stuff that e.g. relies on MemberConverters.
    """

    message = discord.Message(channel=bot.get_channel(interaction.channel_id),
                              state=None,
                              data={"id": -1,
                                    "attachments": [],
                                    "embeds": [],
                                    "created_at": datetime.now(),
                                    "edited_timestamp": datetime.utcnow().isoformat(),
                                    "type": discord.MessageType.default,
                                    "pinned": False,
                                    "flags": {},
                                    "mention_everyone": False,
                                    "tts": False,
                                    "content": "",
                                    "nonce": None,
                                    "stickers": [],
                                    "components": []})

    setattr(message, "author", interaction.user)
    setattr(message, "guild", interaction.guild)
    return commands.Context(bot=bot, message=message, view=None)


class ContextTypes(Enum):
    Unknown = 0
    Context = 1
    Interaction = 2


def get_context_type(ctx: commands.Context | discord.Interaction) -> ContextTypes:
    if issubclass(ctx.__class__, commands.Context):
        return ContextTypes.Context
    elif issubclass(ctx.__class__, discord.Interaction):
        return ContextTypes.Interaction
    return ContextTypes.Unknown
