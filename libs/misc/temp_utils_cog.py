import discord
from discord.ext import commands
from . import utils

"""
As the name of the cog suggests, this cog is supposed to be a TEMPORARY part of a solution.
utils will be getting rewritten/restructured as appropriate in the future, but this is a part of an effort to improve upon the general structure of the project.
"""

class Utils(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.bot.__dict__.update(utils.__dict__)  # Bring all of utils into the bot - prevents referencing utils in cogs

        self.bot.flag_handler = self.bot.flags()
        self.bot.flag_handler.set_flag("time", {"flag": "t", "post_parse_handler": self.bot.flag_methods.str_time_to_seconds})
        self.bot.flag_handler.set_flag("reason", {"flag": "r"})
        self.bot.last_active = {}  # easiest to put here for now, may move to a cog later

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Event that has checks that stop bots from executing commands
        """

        if type(message.channel) == discord.DMChannel or message.author.bot:
            return
        if message.guild.id not in self.bot.last_active:
            self.bot.last_active[message.guild.id] = []  # create the dict key for that guild if it doesn't exist
        last_active_list = self.bot.last_active[message.guild.id]
        if message.author in last_active_list:
            last_active_list.remove(message.author)
        last_active_list.insert(0, message.author)


async def setup(bot) -> None:
    await bot.add_cog(Utils(bot))
