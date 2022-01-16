# REQUIRES D.PY V2

import discord
from discord.ext import commands
from discord import Embed, Colour
import inspect
import asyncio
import asyncpg
import ast
from libs.misc.decorators import is_staff
from typing import Callable, Any
import copy

"""
Potential TODOs:
    - Allow embed outputs to be used in actions
    - Potentially allow usage of ctx within outputs
    - Conditional outputs? e.g. if user has a particular role already then no output saying they have the role
    - Have a look into whether pre and post invoke hooks need to be manually invoked
    - Tidy up some of the code if possible 
"""


class NoSendContext(commands.Context):
    """
    This class is a factory class for creating Context objects
    Extends discord.ext.commands.Context
    The primary purpose is allow overriding of send and reply methods to empty ones to "silence" commands

    NOTE that one major drawback of this is that commands expecting a Message object to work with *may* break,
    which users are made aware of when attempting to create the action
    """

    async def send(self, *args, **kwargs) -> None:
        return

    async def reply(self, *args, **kwargs) -> None:  # override reply as well since e.g. stuff like DefaultEmbedResponses replies now
        return

    class channel(discord.TextChannel):
        async def send(self, *args, **kwargs) -> None:
            return

        async def reply(self, *args, **kwargs) -> None:
            return


class Checks:  # could also be possible to tidy the wait_for's up if they can be put in a method?
    """
    Class that houses the checks used in "wait_for" calls
    The checks are generated since there are limitations in what the checks expect to pass in the case of each event

    For example: none of the checks receive Context by default, reaction_add checkers do not receive messages etc.
    """

    @staticmethod
    def generate_std_message_check(ctx: commands.Context) -> Callable:
        """
        No, my code doesn't have AIDs

        This method generates a "standard" message check which checks that the context channel and author match an incoming message.
        """

        def check(m: discord.Message) -> bool:
            return m.channel == ctx.channel and m.author == ctx.author
        return check

    @staticmethod
    def generate_emoji_check(ctx: commands.Context, emoji_list: list = None, message: discord.Message = None) -> Callable:
        """
        This methods generates a check function which can be used to check:
            - That a reaction is of an emoji in a given list
            - That the reaction is to the expected message
        """

        if emoji_list is None:
            emoji_list = []  # pycharm likes to complain

        def check2(r: discord.Reaction, a: discord.abc.User) -> bool:
            return a == ctx.message.author and r.emoji in emoji_list if emoji_list else True and r.message == message if message is not None else True

        return check2

    @staticmethod
    def generate_range_check(ctx: commands.Context, lower_: int, upper_: int) -> Callable:
        """
        Method to generate a "range" check.
        Similar to a standard message check except there are extra conditions to be met:
            - That the content can be a "digit"
            - The "digit" is equivalent to or bigger than the lower bound but smaller than or equivalent to the upper bound

        """

        def range_check(lower: int, upper: int) -> Callable:
            def check3(m: discord.Message) -> bool:
                check_ = m.channel == ctx.channel and m.author == ctx.author and m.content.isdigit()
                if check_:
                    check_ = lower <= int(m.content) <= upper
                else:
                    check_ = False
                return check_

            return check3
        return range_check(lower_, upper_)


class Actions(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.actions = {}

    async def load_actions(self) -> None:
        """
        Method for loading actions
        Fetches the actions from the db and uses ast to evaluate them and add them to self.actions
        """

        success = False

        while not success:
            success = True
            try:
                async with self.bot.pool.acquire() as connection:
                    for guild in self.bot.guilds:
                        actions = await connection.fetch("SELECT * FROM actions WHERE guild_id = ($1)", guild.id)
                        self.actions[guild.id] = {}
                        for action in actions:
                            action = dict(action)

                            await self.register_action(guild.id, action["action_name"], ast.literal_eval(action["action"]))

            except asyncpg.exceptions.UndefinedTableError:
                print("Actions table doesn't exist yet, waiting 1 second")
                await asyncio.sleep(1)
                success = False

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        while not self.bot.online:
            await asyncio.sleep(1)

        await self.load_actions()

    @commands.group()
    @commands.guild_only()
    async def action(self, ctx: commands.Context) -> None:
        """
        Do `help action` for more info
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(f"```{ctx.prefix}help action```")

    @action.command(name="delete", aliases=["remove"])
    @commands.guild_only()
    @is_staff
    async def delete_action(self, ctx: commands.Context, name: str = "") -> None:  # Actual deleting is handled by remove_action
        """
        Command to delete an action for a guild

        Staff role required
        """

        if not name:
            await ctx.send(embed=Embed(title="You need to provide an action name to be removed", colour=self.bot.ERROR_RED))  # move this to embed responses once timezone stuff is sorted

        elif name not in self.actions[ctx.guild.id]:
            await ctx.send(embed=Embed(title="Could not delete the requested action", description="No action with the given name exists!", colour=self.bot.ERROR_RED))

        else:
            await self.remove_action(ctx.guild.id, name)
            await ctx.send(embed=Embed(title="Successfully deleted action!", description=f"{name} has been removed!", colour=self.bot.SUCCESS_GREEN))

    @action.command()
    @commands.guild_only()
    @is_staff
    async def deleteall(self, ctx: commands.Context) -> None:
        """
        Command to delete all actions for a guild

        Staff role required
        """

        for action in list(self.actions[ctx.guild.id].keys()):
            await self.remove_action(ctx.guild.id, action)

        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"Successfully deleted all actions for {ctx.guild}")

    @action.command()
    @commands.guild_only()
    @is_staff
    async def raw(self, ctx: commands.Context, name: str) -> None:
        if name not in self.actions[ctx.guild.id]:
            await ctx.send(embed=Embed(title="Could not show data for the requested action", description="No action with the given name exists!", colour=self.bot.ERROR_RED))
        else:
            await ctx.send(f"```{self.actions[ctx.guild.id][name]}```")

    @action.command(name="list", aliases=["show"])
    @commands.guild_only()
    async def list_action(self, ctx: commands.Context) -> None:
        """
        Fetches a list of actions for the context guild
        """

        await ctx.send(embed=Embed(title=f"{ctx.guild.name}'s actions", description="\n".join(self.actions[ctx.guild.id].keys()) if self.actions[ctx.guild.id] else "Nothing to show here!"))

    @staticmethod
    async def try_conversion(ctx: commands.Context, value, annotation, name: str = "value") -> Any:
        """
        Method that makes use of ext.commands.run_converters in v2

        It attempts to convert the provided value to the data type/annotation provided, within the context given
        """

        try:
            result = await commands.run_converters(ctx, annotation, value, inspect.Parameter(name, inspect.Parameter.POSITIONAL_ONLY))
        except Exception:
            return
        return result

    @staticmethod
    async def try_remove_reactions(message: discord.Message) -> None:
        """
        Method that tries to remove reactions from a given message.

        Saves having a bunch of repetitive try-excepts everywhere
        """

        try:
            await message.clear_reactions()
        except discord.HTTPException:
            return

    async def register_action(self, guild_id: int, name: str, action: dict) -> None:
        """
        Method to register a given loaded action
        This method ensures that the action is accessible from all the correct places.
        Registers aliases, to the internal bot dict, and as an alias to the base handler.
        """

        self.bot.all_commands["base_action_handler"].aliases.append(name)
        self.actions[guild_id][name] = action
        self.bot.all_commands[name] = self.base_action_handler

    async def propagate_action(self, ctx: commands.Context, name: str, action: dict) -> None:
        """
        Method to propagate a new action to the database
        """

        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute("INSERT INTO actions (guild_id, action_name, action) values ($1, $2, $3)", ctx.guild.id, str(name), str(action))
            except Exception as e:
                raise e
            await self.register_action(ctx.guild.id, name, action)

    async def remove_action(self, guild_id: int, name: str) -> None:
        """
        Method to remove a specified action

        Removes it from internal tracker, removes aliases and removes it from the internal commands dict
        """

        if not name or name not in self.actions[guild_id]:
            return

        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute("DELETE FROM actions WHERE guild_id = ($1) AND action_name = ($2)", guild_id, name)
            except Exception as e:
                raise e
        del self.actions[guild_id][name]
        del self.bot.all_commands[name]
        del self.base_action_handler.aliases[self.base_action_handler.aliases.index(name)]

    @commands.command(hidden=True)  # Hidden to prevent people accessing
    async def base_action_handler(self, ctx: commands.Context, *args) -> None:
        """
        Method that serves as a "base command" for actions.

        Actions are registered as aliases of this command

        Action handling is then completed based off of ctx.invoked_with

        This method analyses the arguments passed, along with the defaults stored
        Each action will have position indicators for each argument, so this method iterates through the argument list passed
        and will appropriately select and pass the correct arguments to each command in an action

        This method also has handling for other properties actions have
        This includes command outputs, command silencing etc

        clean_params is made use of throughout the method, eliminating the need to check for "self" and "ctx"
        """

        action = self.actions.get(ctx.guild.id, {}).get(ctx.invoked_with, None)
        if not action or not action.get("commands", None):
            return

        if action.get("staff", False) and not await self.bot.is_staff(ctx):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        action = copy.deepcopy(action)
        clean_ctx = await self.bot.get_context(ctx.message, cls=NoSendContext)  # not entirely sure yet how to override ctx.message.channel without making all hell break loose

        arg_index = 0
        for f, command in enumerate(action["commands"]):
            command["command_obj"] = self.bot.get_command(command["command"])
            command["arg_values"] = {}
            command["var_args"] = []
            command["all_arg_values"] = []

            arg_list = list(command["command_obj"].clean_params)

            argspec = inspect.getfullargspec(command["command_obj"].callback)
            argspec = argspec._replace(kwonlydefaults={}) if argspec.kwonlydefaults is None else argspec  # makes things simpler later on
            argsig = str(inspect.signature(command["command_obj"].callback)).replace(" ", "")[1:][:-1].split(",")[2:]
            arg_list_ = argspec.args[2:]

            var_arg = argspec.varargs

            command["var_arg_pos"] = None
            consume_pos = None

            for z, arg in enumerate(command["command_obj"].clean_params):
                command["var_arg_pos"] = z if arg == var_arg else command["var_arg_pos"]
                consume_pos = z if arg in argspec.kwonlyargs and arg not in argspec.kwonlydefaults else consume_pos  # *, args type of argument

                if command["var_arg_pos"] is not None or consume_pos is not None:
                    break

            clean_params = list(command["command_obj"].clean_params)[:command["var_arg_pos"] + 1] if command["var_arg_pos"] is not None else (list(command["command_obj"].clean_params)[:consume_pos + 1] if consume_pos is not None else command["command_obj"].clean_params)

            for x, arg in enumerate(clean_params):
                command["var_arg_pos"] = x if arg == var_arg else None

                if x in command["reply_args"] and ctx.message.reference:
                    ref = await ctx.fetch_message(ctx.message.reference.message_id)

                    if arg != var_arg:
                        command["arg_values"][arg_list[x]] = ref.author

                    elif not command["var_args"] or f == len(action["commmands"]) - 1:
                        command["var_args"].append(ref.author)

                elif str(x) in command["defaults"]:
                    if arg != var_arg:
                        command["arg_values"][arg_list[x]] = command["defaults"][str(x)]

                    elif not command["var_args"] or f == len(action["commands"]) - 1:
                        command["var_args"].append(command["defaults"][str(x)])

                elif str(x) in command["reuse"]:
                    y = command["reuse"][str(x)]
                    command_index = int(y[:y.index(",")])
                    arg_index = int(y[y.index(",") + 1:])

                    if arg_index == action["commands"][command_index]["var_arg_pos"]:
                        needed_arg = action["commands"][command_index]["var_args"]

                    else:
                        arg_indexes = list(action["commands"][command_index]["arg_values"])
                        needed_arg = action["commands"][command_index]["arg_values"][arg_indexes[arg_index]]

                    if arg != var_arg:
                        command["arg_values"][arg_list[x]] = needed_arg

                    elif not command["var_args"] or f == len(action["commands"]) - 1:
                        command["var_args"].append(needed_arg)

                elif arg_index < len(args):
                    if arg in argspec.kwonlyargs and arg not in argspec.kwonlydefaults and f == len(action['commands']) - 1 and arg_index != len(args) - 1:  # i.e. *, args type arg
                        command["arg_values"][arg_list[x]] = " ".join(args[arg_index:])

                    elif arg != var_arg:
                        command["arg_values"][arg_list[x]] = args[arg_index]

                    elif not command["var_args"] or f == len(action["commands"]) - 1:
                        command["var_args"].append(args[arg_index])
                        if f == len(action["commands"]) - 1:
                            [command["var_args"].append(args[w]) for w in range(arg_index + 1, len(args))]

                    arg_index += 1

                else:
                    await ctx.send(embed=Embed(title=":x: Missing argument!", description=f"{command['command']} is missing a value for {arg} ({self.bot.ordinal(f + 1)} command)", colour=self.bot.ERROR_RED))
                    return

                annotation = command["command_obj"].clean_params[list(command["command_obj"].clean_params)[x]].annotation

                if annotation is not inspect._empty:
                    if arg != var_arg and arg in command["arg_values"]:  # is there any point doing converters for *args? probs get passed as a tuple anyway
                        # reply won't necessarily be in arg_values
                        command["arg_values"][arg] = await commands.run_converters(ctx, annotation, str(command["arg_values"][arg]), command["command_obj"].clean_params[list(command["command_obj"].clean_params)[x]])

            sorted_parts = []
            for part in command["var_args"]:
                [sorted_parts.append(part_) for part_ in part.split(" ")]
            command["var_args"] = sorted_parts

            command["all_arg_values"] = list(command["arg_values"].values())
            if command["var_arg_pos"] is not None:
                command["all_arg_values"].insert(command["var_arg_pos"], command["var_args"])

        for command_ in action["commands"]:
            if command_["silent"]:
                await clean_ctx.invoke(command_["command_obj"], *command_["var_args"], **command_["arg_values"])
            else:
                await ctx.invoke(command_["command_obj"], *command_["var_args"], **command_["arg_values"])

            for output in command_.get("outputs", []):
                if output["channel_id"] != 0:
                    try:
                        channel = self.bot.get_channel(output["channel_id"])
                    except Exception as e:
                        await ctx.send(e)
                        continue

                split_content = output["content"].split()

                for part in split_content:  # allows stuff like mentioning a user passed in args
                                            # potential todo: allow ctx? e.g. allow mentioning context author. could get a little messy to handle though
                    if len(part) > 1 and part[::len(part) - 1] == "<>" and "." in part:

                        split_part = part[1:][:-1].split(".")
                        if len(split_part) >= 2 and split_part[0].isdigit() and split_part[1].isdigit():

                            if 0 < int(split_part[0]) <= len(action["commands"]):
                                out_command = action["commands"][int(split_part[0]) - 1]

                                if 0 < int(split_part[1]) <= len(out_command["all_arg_values"]):
                                    command_arg = out_command["all_arg_values"][int(split_part[1]) - 1]

                                    for prop in split_part[2:]:
                                        if hasattr(command_arg, prop):
                                            a = getattr(command_arg, prop, None)
                                            if a:
                                                command_arg = a
                                            else:
                                                command_arg = None
                                                break  # no point continuing if None or non-existent

                                    if command_arg is not None:
                                        split_content[split_content.index(part)] = f"{command_arg}"

                content = " ".join(split_content)
                if output["channel_id"] != 0:
                    await channel.send(content)
                else:
                    await ctx.send(content)

    @action.command(name="create", aliases=["make"])
    @commands.guild_only()
    @is_staff
    async def create_action(self, ctx: commands.Context) -> None:  # split this up?
        """
        A command that attempts to provide a user-friendly way of creating actions

        This command guides users through command by command to create an action

        After the action is created, it is registered and propagated as appropriate

        Staff role required
        """

        action = {
            "commands": [],
            "staff": False
        }  # doesn't strictly need to be a dict by itself at the moment, but this makes expansion easier

        commands_ = []
        command_objs = []

        await ctx.send(embed=Embed(title=":information_source: Action name needed", description="Enter a name for your action", colour=Colour.from_rgb(250, 95, 85)))

        try:
            name_msg = await self.bot.wait_for("message", check=Checks.generate_std_message_check(ctx), timeout=300)
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
            return

        name = name_msg.content.replace(" ", "")
        pot_cmd = self.bot.get_command(name)

        if pot_cmd and (name in self.actions[ctx.guild.id] or pot_cmd.callback.__name__ != "base_action_handler"):
            await ctx.send(embed=Embed(title=":x: Invalid action name!", description="An action name cannot be the same as an existing command or action (including aliases)"))
            return

        result = None

        staff_check = await ctx.send(embed=Embed(title=":information_source: Make this action staff only?"))

        await staff_check.add_reaction(self.bot.EmojiEnum.TRUE)
        await staff_check.add_reaction(self.bot.EmojiEnum.FALSE)

        try:
            response = await self.bot.wait_for("reaction_add", check=Checks.generate_emoji_check(ctx, [self.bot.EmojiEnum.FALSE, self.bot.EmojiEnum.TRUE], staff_check), timeout=300)
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
            return

        await self.try_remove_reactions(staff_check)
        if response[0].emoji == self.bot.EmojiEnum.TRUE:
            action["staff"] = True

            await ctx.send(embed=Embed(title=":information_source: This action has been marked as staff only"))

        else:
            await ctx.send(embed=Embed(title=":information_source: This action won't be marked as staff only"))

        while not isinstance(result, tuple):  # adding a reaction returns a tuple because... that makes sense
            hi = await ctx.send(embed=Embed(title=":information_source: Add a command", description=f"Type the name of the {'first' if not result else 'next'} command you want to add, or click the reaction to finish", colour=Colour.from_rgb(238, 130, 238)))
            await hi.add_reaction(self.bot.EmojiEnum.FALSE)

            try:
                done, pending = await asyncio.wait([
                    self.bot.wait_for('message', check=Checks.generate_std_message_check(ctx), timeout=300),
                    self.bot.wait_for('reaction_add', check=Checks.generate_emoji_check(ctx, [self.bot.EmojiEnum.FALSE], hi), timeout=300)
                ], return_when=asyncio.FIRST_COMPLETED)

                result = done.pop().result()
            except(asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
                return

            for future in done:
                future.exception()

            for future in pending:
                future.cancel()  # don't need the rest any more

            await self.try_remove_reactions(hi)

            if isinstance(result, discord.Message):

                command_props = {
                    "command": None,
                    "defaults": {},
                    "reuse": {},
                    "reply_args": [],
                    "silent": False,
                    "outputs": []
                }

                command = self.bot.get_command(result.content)
                if not command:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Couldn't find command!", desc="That command wasn't found!")

                elif command.name == "base_action_handler":  # circular check
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "You can't add other actions to a new action!", desc="Try adding a command!")

                else:
                    argspec = inspect.getfullargspec(command.callback)
                    argspec = argspec._replace(kwonlydefaults={}) if argspec.kwonlydefaults is None else argspec
                    var_arg = argspec.varargs
                    pos = None

                    """
                    This part basically checks what could actually be passed to a command
                    e.g. nothing after *, args, *args, and afaik **kwargs can't be passed under normal circumstances
                    Get rid of these from processing so it doesn't cause everything to have a meltdown
                    """

                    for v, arg in enumerate(list(command.clean_params)):
                        pos = v if (arg == var_arg or (arg in argspec.kwonlyargs and arg not in argspec.kwonlydefaults)) else pos

                        if pos is not None:  # specifically is not None rather than just if pos since pos=0 means false
                            break

                    requested_args = list(command.clean_params)[:pos + 1] if pos is not None else command.clean_params

                    command_props["command"] = command.qualified_name
                    await ctx.send(embed=Embed(title=":white_check_mark: Added command",
                                               description=f"Added {result.content} successfully!{' You will now be prompted to add values for your command.' if requested_args else ''}",
                                               colour=Colour.from_rgb(57, 255, 20)))

                    if requested_args:
                        await ctx.send_help(command)

                    given_args = {}
                    seen_args = sum([len(command.clean_params) for command in command_objs]) > 0
                    for x, param in enumerate(requested_args, start=1):
                        annotation = command.clean_params[param].annotation  # manipulate wanted as list then just refer back to dict by key for param props
                        if annotation is None or annotation == discord.Member:
                            message = await ctx.send(embed=Embed(title=f":information_source: Managing  command values ({param})",
                                                             description=f"React with {self.bot.EmojiEnum.TRUE} if we should look for a reply author to use for this value first"
                                                                         f"\nNote that you will be next prompted to enter a value to fallback on if no reply is found"))  # should this only be done for annotations that could match it?
                                                                                                                                                                          # for example: only for discord.Member or None type annotations
                        # any potential complications with this? e.g. having A B C where B could be a reply author or not
                        # i.e. you could end up with a reply and passing A C or no reply and passing A B C, which could get confusing
                        # todo: look at making reuse of reply args more clear, it even confused me at first

                            await message.add_reaction(self.bot.EmojiEnum.TRUE)
                            await message.add_reaction(self.bot.EmojiEnum.FALSE)
                            try:
                                response_ = await self.bot.wait_for("reaction_add", check=Checks.generate_emoji_check(ctx, [self.bot.EmojiEnum.FALSE, self.bot.EmojiEnum.TRUE], message), timeout=300)
                            except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
                                return

                            await self.try_remove_reactions(message)

                            if response_[0].emoji == self.bot.EmojiEnum.TRUE:
                                command_props["reply_args"].append(x-1)

                        # handle annotation checking here at some point, method from v2 needed for this


                        useable_value = False

                        while not useable_value:
                            pos = self.bot.ordinal(x)
                            text = f"React with :x: if you don't want to add a default for the {pos} value, or type a default value\n"
                            if seen_args > 0:
                                text += f"React with {self.bot.EmojiEnum.RECYCLE} to reuse a value from a previous command"

                            useable_value = True
                            message = await ctx.send(embed=Embed(title=f":information_source: Managing command values ({param})", description=text, colour=Colour.from_rgb(255, 165, 0)))
                            await message.add_reaction(self.bot.EmojiEnum.FALSE)

                            if seen_args > 0:
                                await message.add_reaction(self.bot.EmojiEnum.RECYCLE)

                            try:
                                done, pending = await asyncio.wait([
                                    self.bot.wait_for('message', check=Checks.generate_std_message_check(ctx), timeout=300),
                                    self.bot.wait_for('reaction_add', check=Checks.generate_emoji_check(ctx, [self.bot.EmojiEnum.FALSE, self.bot.EmojiEnum.RECYCLE], message), timeout=300)
                                ], return_when=asyncio.FIRST_COMPLETED)

                                result_ = done.pop().result()
                            except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
                                return

                            for future in done:
                                future.exception()

                            for future in pending:
                                future.cancel()

                            await self.try_remove_reactions(message)

                            if isinstance(result_, discord.Message):
                                if annotation != inspect._empty:  # conversion will always fail on _empty, although it's pointless anyway
                                    try:
                                        test_conv = await commands.run_converters(ctx, annotation, result_.content, command.clean_params[param])  #, inspect.Parameter(param, inspect.Parameter.POSITIONAL_ONLY, annotation=annotation))
                                    except commands.CommandError as e:
                                        useable_value = False
                                        await ctx.send(embed=Embed(title=f"Error using that value for ({param})",
                                                               description="The value given is not of the type needed\nHINT: Values that need to be a member must be a name, mention or user ID of a member, other types of values are invalid"))
                                if useable_value:
                                    given_args[f"{x-1}"] = result_.content

                            elif result_[0].emoji == self.bot.EmojiEnum.RECYCLE:
                                arg_command_names = []
                                for z, command in enumerate(command_objs):
                                    if len(command.clean_params) > 0:
                                        arg_command_names.append((z, command.qualified_name))

                                text = "\n".join([f"{y[0]}: *{y[1]}*" for y in list(enumerate([q[1] for q in arg_command_names], start=1))])
                                await ctx.send(embed=Embed(title=f"{self.bot.EmojiEnum.RECYCLE} Reusing value for ({param})",
                                                           description=f"Please send the number corresponding to the command that you want to reuse a value from:\n{text}",
                                                           colour=Colour.from_rgb(0, 250, 154)))

                                try:
                                    response = await self.bot.wait_for("message", check=Checks.generate_range_check(ctx, 0, len(arg_command_names)), timeout=300)
                                except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
                                    return

                                response_command = int(response.content)
                                params_ = self.bot.get_command(commands_[arg_command_names[response_command - 1][0]]['command']).clean_params
                                params = len(params_)
                                response_arg = 1

                                if params > 1:
                                    await ctx.send(embed=Embed(title=f"{self.bot.EmojiEnum.RECYCLE} Reusing value for ({param})",
                                                               description=f"There are {params} values for this command. Enter a number from 1-{params} to select which value you want to reuse",
                                                               colour=Colour.from_rgb(0, 250, 154)))  # make this bit a bit nicer?

                                    try:
                                        response_arg = await self.bot.wait_for("message", check=Checks.generate_range_check(ctx, 0, params), timeout=300)
                                    except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                                        await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
                                        return
                                    response_arg = int(response_arg.content)

                                else:
                                    await ctx.send(embed=Embed(title=f"{self.bot.EmojiEnum.RECYCLE} Reusing value for ({param})", description="Only detected one value for this command, using this.", colour=Colour.from_rgb(0, 250, 154)))

                                sel_default = commands_[response_command - 1]["defaults"].get(str(response_arg - 1))
                                if sel_default and annotation != inspect._empty:
                                    try:
                                        await commands.run_converters(ctx, annotation, sel_default, command.clean_params[param])
                                    except commands.CommandError:
                                        useable_value = False
                                        await ctx.send(embed=Embed(title=f"Error using that value for ({param})",
                                                                   description="The value selected for reuse is not of the type needed\nHINT: Values that need to be a member must be a name, mention or user ID of a member, other types of values are invalid"))

                                if useable_value:
                                    command_props["reuse"][str(x-1)] = f"{arg_command_names[response_command - 1][0]},{response_arg - 1}"
                                    await ctx.send(embed=Embed(title=f"{self.bot.EmojiEnum.RECYCLE} Reusing value for ({param})", description=f"We will now reuse this command's {self.bot.ordinal(response_arg)} value for this value.", colour=Colour.from_rgb(0, 250, 154)))

                        await ctx.send(embed=Embed(title="Processed value successfully!", description=f"**{command.name}**'s '({param})' has been successfully added", colour=self.bot.SUCCESS_GREEN))

                    command_props["defaults"] = given_args

                    silence = await ctx.send(embed=Embed(title=f"Silence command?", description=f"React with {self.bot.EmojiEnum.TRUE} to silence this command's output, or {self.bot.EmojiEnum.FALSE} to not.\nThis will remove *most* of a command's standard output\n\n**WARNING: This can break commands that e.g. wait on response, but can be cleaner for commands that output success/error messages**", colour=Colour.from_rgb(221, 160, 221)))
                    await silence.add_reaction(self.bot.EmojiEnum.TRUE)
                    await silence.add_reaction(self.bot.EmojiEnum.FALSE)

                    try:
                        response = await self.bot.wait_for("reaction_add", check=Checks.generate_emoji_check(ctx, [self.bot.EmojiEnum.FALSE, self.bot.EmojiEnum.TRUE], silence), timeout=300)
                    except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                        await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out", desc="Command cancelled due to timeout")
                        return

                    command_props["silent"] = True if response[0].emoji == self.bot.EmojiEnum.TRUE else False

                    await self.try_remove_reactions(silence)

                    await ctx.send(embed=Embed(title=f"Successfully applied option", description=f"The command will now {'not' if not command_props['silent'] else ''} be silenced"))

                    result_ = []
                    while True:

                        output = await ctx.send(embed=Embed(title=f"Add {'more ' if command_props['outputs'] else ''}outputs to this command?", description=f"Type a channel name to start, react with {self.bot.EmojiEnum.SPEAKING} send in the channel the command is used in, or react with :x: to cancel"))
                        await output.add_reaction(self.bot.EmojiEnum.FALSE)
                        await output.add_reaction(self.bot.EmojiEnum.SPEAKING)

                        channel_conv = await self.try_conversion(ctx, getattr(result_, "content", None), discord.TextChannel, "content")
                        thread_conv = await self.try_conversion(ctx, getattr(result_, "content", None), discord.Thread, "content")
                        while not channel_conv and not thread_conv:  # can't have async checks

                            try:
                                done, pending = await asyncio.wait([
                                    self.bot.wait_for('message', check=Checks.generate_std_message_check(ctx), timeout=300),
                                    self.bot.wait_for('reaction_add', check=Checks.generate_emoji_check(ctx, [self.bot.EmojiEnum.FALSE, self.bot.EmojiEnum.SPEAKING], output), timeout=300)
                                ], return_when=asyncio.FIRST_COMPLETED)

                                result_ = done.pop().result()
                            except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out",
                                                                                 desc="Command cancelled due to timeout")
                                return

                            for future in done:
                                future.exception()

                            for future in pending:
                                future.cancel()

                            if not isinstance(result_, discord.Message):
                                break

                        await self.try_remove_reactions(output)

                        if isinstance(result_, discord.Message) or result_[0].emoji == self.bot.EmojiEnum.SPEAKING:
                            if isinstance(result_, discord.Message):
                                if channel_conv:
                                    channel = await commands.run_converters(ctx, discord.TextChannel, result_.content, inspect.Parameter("content", inspect.Parameter.POSITIONAL_ONLY))
                                else:
                                    channel = await commands.run_converters(ctx, discord.Thread, result_.content, inspect.Parameter("content", inspect.Parameter.POSITIONAL_ONLY))
                                channel_id = channel.id
                            else:
                                channel_id = 0

                            await ctx.send(embed=Embed(title=f"Successfully selected channel!", description="Type a message to send to this channel once the command is complete"
                                                                                                            "\nTIP: You can use markers like <1.1.mention> in your message, which will take mention from the 1st value from the 1st command"
                                                                                                            "This is useful for mentioning users or channels after your command is complete"))

                            try:
                                response = await self.bot.wait_for("message", check=Checks.generate_std_message_check(ctx), timeout=300)
                            except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Timed out",
                                                                                 desc="Command cancelled due to timeout")
                                return

                            command_props["outputs"].append(
                                {
                                    "channel_id": channel_id,
                                    "content": response.content
                                }
                            )

                            await ctx.send(embed=Embed(title=f"Successfully added message!", description=""))

                            result_ = None  # for next loop

                        else:
                            break

                if command_props["command"] is not None:
                    command_objs.append(command)
                    commands_.append(command_props)

        if commands_:
            action["commands"] = commands_
            await self.propagate_action(ctx, name, action)
            await ctx.send(embed=Embed(title="Added action successfully!", description=f"{name} has been added as a new action!"))


def setup(bot) -> None:
    bot.add_cog(Actions(bot))
