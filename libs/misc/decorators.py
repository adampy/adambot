import asyncio
import discord
from discord.ext import commands
from inspect import signature
from .utils import DefaultEmbedResponses, DEVS
from typing import Union, Callable, Any


def is_staff(func: Callable) -> Callable:
    """
    Decorator that allows the command to only be executed by staff role or admin perms.
    This needs to be placed underneath the @command.command() decorator, and can only be used for commands in a cog

    Usage:
        from libs.misc.decorators import is_staff

        @commands.command()
        @is_staff
        async def ping(self, ctx):
            await ctx.send("Pong!")
    """

    async def decorator(cog, ctx: commands.Context, *args, **kwargs) -> Union[Any, discord.Message]:
        while not cog.bot.online:
            await asyncio.sleep(1)  # Wait else DB won't be available

        staff_role_id = await cog.bot.get_config_key(ctx, "staff_role")
        if staff_role_id in [y.id for y in ctx.author.roles] or ctx.author.guild_permissions.administrator:
            return await func(cog, ctx, *args, **kwargs)
        else:
            return await DefaultEmbedResponses.invalid_perms(cog.bot, ctx)
    
    decorator.__name__ = func.__name__
    decorator.__signature__ = signature(func)
    return decorator


def is_dev(func: Callable) -> Callable:
    """
    Decorator that allows the command to only be executed by developers.
    This needs to be placed underneath the @command.command() decorator, and can only be used for commands in a cog

    Usage:
        from libs.misc.decorators import is_dev

        @commands.command()
        @is_dev
        async def ping(self, ctx):
            await ctx.send("Pong!")
    """

    async def decorator(cog, ctx: commands.Context, *args, **kwargs) -> Union[Any, discord.Message]:
        if ctx.author.id in DEVS:
            return await func(cog, ctx, *args, **kwargs)
        else:
            return await DefaultEmbedResponses.invalid_perms(cog.bot, ctx)
    
    decorator.__name__ = func.__name__
    decorator.__signature__ = signature(func)
    return decorator