from typing import Callable, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .utils import DEVS

"""
The rationale behind these error classes is to basically abstract the error embed
out of the actual decorators themselves. Having the error embed handled in the 
decorator causes issues with anything that runs checks on the commands without
actually invoking it (e.g. stuff like the help command). So we raise an error
which will get passed over to on_command_error if the command has been invoked.
"""


class MissingStaffError(commands.CheckFailure):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class MissingStaffSlashError(app_commands.CheckFailure):
    def __init__(self, *args) -> None:
        super().__init__(*args)


class MissingDevError(commands.CheckFailure):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class MissingDevSlashError(app_commands.CheckFailure):
    def __init__(self, *args) -> None:
        super().__init__(*args)


async def staff_predicate(ctx: commands.Context | discord.Interaction) -> Optional[bool]:
    is_ctx = type(ctx) is commands.Context
    author = ctx.author if is_ctx else ctx.user

    staff_role_id = await ctx.bot.get_config_key(ctx, "staff_role") if is_ctx else await ctx.client.get_config_key(ctx,
                                                                                                                   "staff_role")
    if staff_role_id in [y.id for y in author.roles] or author.guild_permissions.administrator:
        return True
    else:
        raise MissingStaffError if is_ctx else MissingStaffSlashError


async def dev_predicate(ctx: commands.Context | discord.Interaction) -> Optional[bool]:
    is_ctx = type(ctx) is commands.Context
    author = ctx.author if is_ctx else ctx.user

    if author.id in DEVS:
        return True
    else:
        raise MissingDevError


def is_staff() -> Callable:
    """
    Decorator that allows the command to only be executed by staff role or admin perms.
    This needs to be placed underneath the @command.command() decorator, and can only be used for commands in a cog

    Usage:
        from libs.misc.decorators import is_staff

        @commands.command()
        @is_staff()
        async def ping(self, ctx):
            await ctx.send("Pong!")
    """

    async def predicate(ctx: commands.Context) -> Optional[bool]:
        return await staff_predicate(ctx)

    return commands.check(predicate)


def is_staff_slash() -> Callable:
    async def predicate(interaction: discord.Interaction) -> Optional[bool]:
        return await staff_predicate(interaction)

    return app_commands.check(predicate)


def is_dev() -> Callable:
    """
    Decorator that allows the command to only be executed by developers.
    This needs to be placed underneath the @command.command() decorator, and can only be used for commands in a cog

    Usage:
        from libs.misc.decorators import is_dev

        @commands.command()
        @is_dev()
        async def ping(self, ctx):
            await ctx.send("Pong!")
    """

    async def predicate(ctx: commands.Context) -> bool:
        return await dev_predicate(ctx)

    return commands.check(predicate)


def is_dev_slash() -> Callable:
    async def predicate(interaction: discord.Interaction) -> Optional[bool]:
        return await dev_predicate(interaction)

    return app_commands.check(predicate)
