import discord
from discord.ext import commands
from discord.ext import commands
from . import utils

"""
As the name of the cog suggests, this cog is supposed to be a TEMPORARY part of a solution.
utils will be getting rewritten/restructured as appropriate in the future, but this is a part of an effort to improve upon the general structure of the project.
"""

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.__dict__.update(utils.__dict__)  # Bring all of utils into the bot - prevents referencing utils in cogs

        self.bot.pages = [] #self.pages = []
        self.bot.flag_handler = self.bot.flags()
        self.bot.flag_handler.set_flag("time", {"flag": "t", "post_parse_handler": self.bot.flag_methods.str_time_to_seconds})
        self.bot.flag_handler.set_flag("reason", {"flag": "r"})
        self.bot.last_active = {}  # easiest to put here for now, may move to a cog later


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Subroutine used to control EmbedPages stored within self.pages"""
        if not user.bot:
            for page in self.bot.pages:#self.pages:
                if reaction.message == page.message and user == page.initiator:
                    # Do stuff
                    if reaction.emoji == self.bot.EmojiEnum.LEFT_ARROW:
                        await page.previous_page()
                    elif reaction.emoji == self.bot.EmojiEnum.RIGHT_ARROW:
                        await page.next_page()
                    elif reaction.emoji == self.bot.EmojiEnum.CLOSE:
                        await reaction.message.delete()
                    elif reaction.emoji == self.bot.EmojiEnum.MIN_BUTTON:
                        await page.first_page()
                    elif reaction.emoji == self.bot.EmojiEnum.MAX_BUTTON:
                        await page.last_page()

                    if reaction.emoji != self.bot.EmojiEnum.CLOSE: # Fixes errors that occur when deleting the embed above
                        await reaction.message.remove_reaction(reaction.emoji, user)
                    break

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Event that ensures that memory is freed up once a message containing an embed page is deleted."""
        for page in self.bot.pages:#self.pages:
            if message == page.message:
                del page
                break

    @commands.Cog.listener()
    async def on_message(self, message):
        """Event that has checks that stop bots from executing commands"""
        if type(message.channel) == discord.DMChannel or message.author.bot:
            return
        if message.guild.id not in self.bot.last_active:
            self.bot.last_active[message.guild.id] = []  # create the dict key for that guild if it doesn't exist
        last_active_list = self.bot.last_active[message.guild.id]
        if message.author in last_active_list:
            last_active_list.remove(message.author)
        last_active_list.insert(0, message.author)

def setup(bot):
    bot.add_cog(Utils(bot))