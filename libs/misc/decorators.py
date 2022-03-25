import asyncio
from typing import Callable

from discord.ext import commands
from .utils import DefaultEmbedResponses, DEVS


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

    async def predicate(ctx) -> bool:
        while not ctx.bot.online:
            await asyncio.sleep(1)  # Wait else DB won't be available

        staff_role_id = await ctx.bot.get_config_key(ctx, "staff_role")
        if staff_role_id in [y.id for y in ctx.author.roles] or ctx.author.guild_permissions.administrator:
            return True
        else:
            await DefaultEmbedResponses.invalid_perms(ctx.bot, ctx)
            return False
    return commands.check(predicate)


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

    async def predicate(ctx) -> bool:
        if ctx.author.id in DEVS:
            return True
        else:
            await DefaultEmbedResponses.invalid_perms(ctx.bot, ctx)
            return False
    return commands.check(predicate)

