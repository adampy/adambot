from typing import Callable, Optional
import inspect

import discord
from discord import app_commands
from discord.ext import commands

from .utils import DEVS, unbox_context

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


def get_bot(ctx: commands.Context | discord.Interaction):
    if isinstance(ctx, discord.Interaction):
        return ctx.client
    elif isinstance(ctx, commands.Context):
        return ctx.bot


async def staff_predicate(ctx: commands.Context | discord.Interaction) -> Optional[bool]:
    # Get prereqs
    bot = get_bot(ctx)
    ctx_type, author = unbox_context(ctx)
    if not author:
        return

    # Raise MissingStaff if author doesn't have staff
    staff_role_id = await bot.get_config_key(ctx, "staff_role")

    if staff_role_id in [y.id for y in author.roles] or author.guild_permissions.administrator:
        return True
    elif ctx_type == bot.ContextTypes.Context:
        raise MissingStaffError
    else:
        raise MissingStaffSlashError


async def dev_predicate(ctx: commands.Context | discord.Interaction) -> Optional[bool]:
    # Get prereqs
    bot = get_bot(ctx)
    ctx_type, author = unbox_context(ctx)
    if not author:
        return

    # Raise MissingDev if author doesn't have staff
    if author.id in DEVS:
        return True
    elif ctx_type == bot.ContextTypes.Context:
        raise MissingDevError
    else:
        raise MissingDevSlashError


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

def unbox_context(func) -> Callable:
    """
    Decorator that wraps a function to unbox the context into `ContextType`
    and author. Must be used to wrap functions with a signature `self,
    ContextType, discord.User | discord.Member, commands.Context |
    discord.Interaction, ...` where `self` is the command handler (i.e., the
    first four arguments to the function must be `self, ctx_type, author, ctx)
    """
    async def decorator(self, ctx: commands.Context | discord.Interaction, *args, **kwargs):
        ctx_type, author = unbox_context(ctx)
        if not author:
            return
        
        await func(self, ctx_type, author, ctx, *args, **kwargs)

    decorator.__name__ = func.__name__
    sig = inspect.signature(func)
    new_sig = list(sig.parameters.values())
    new_sig.pop(1)
    new_sig.pop(1) # Pop out the ctx_type and author
    decorator.__signature__ = sig.replace(parameters=tuple(new_sig))
    
    return decorator
