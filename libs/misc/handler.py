import inspect
from functools import wraps

from discord.ext.commands import Context
from discord import Interaction

from .utils import ContextTypes, unbox_context
from adambot import AdamBot

def unbox_context_wrapper(handler, func):
    @wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        if isinstance(ctx, Context) or isinstance(ctx, Interaction):
            ctx_type, author = unbox_context(ctx)
            if not author:
                return
            # Pass the correct arguments for the provided booleans
            handler.command_args = ctx_type, author

        wrapper.__name__ = func.__name__
        wrapper.__signature__ = inspect.signature(func)

        return await func(ctx, *args, **kwargs)
    return wrapper

class CommandHandler:
    """
    Base command handler class that is used to register command functionality
    with. This class should be used as a superclass only and not instantiated
    by itself. For a function of `CommandHandler` to have automatic contetxt
    unboxing it must be awaitable and also have `"ctx"` as the first argument
    (after self) with type `discord.Interaction` or `commands.Context` and
    will output the ctx_type and author as a tuple in the handler's
    `self.command_args`.
    """
    def __init__(self, sub_class, bot: AdamBot):
        """
        Sets `self.sub_class`, `self.bot` and `self.ContextTypes` as well
        as decorating all functions with `unbox_context`.
        """
        self.sub_class = sub_class
        self.bot = bot
        self.ContextTypes = ContextTypes
        self._decorate_functions()

    def _decorate_functions(self):
        for attr_name in type(self.sub_class).__dict__:
            attr = getattr(self.sub_class, attr_name)
            # Only assign decorator to the function if it has first arg with name "ctx"
            should_decorate = False
            try:
                should_decorate = inspect.signature(attr).parameters["ctx"]
            except:
                pass

            if should_decorate and inspect.iscoroutinefunction(attr):
                setattr(self.sub_class, attr_name, unbox_context_wrapper(self.sub_class, getattr(self.sub_class, attr_name)))