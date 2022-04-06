import discord
from discord.ext import commands

from . import utils

from adambot import AdamBot

"""
As the name of the cog suggests, this cog is supposed to be a TEMPORARY part of a solution.
utils will be getting rewritten/restructured as appropriate in the future, but this is a part of an effort to improve upon the general structure of the project.
"""


class Utils(commands.Cog):
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.bot.__dict__.update(utils.__dict__)  # Bring all of utils into the bot - prevents referencing utils in cogs

        self.bot.pages = []
        self.bot.flag_handler = self.bot.flags()
        self.bot.flag_handler.set_flag("time",
                                       {"flag": "t", "post_parse_handler": self.bot.flag_methods.str_time_to_seconds})
        self.bot.flag_handler.set_flag("reason", {"flag": "r"})
        self.bot.last_active = {}  # easiest to put here for now, may move to a cog later

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, member: discord.Member) -> None:
        """
        Subroutine used to control EmbedPages stored within self.pages
        """
        """
        if not member.bot:
            for page in self.bot.pages:
                if reaction.message == page.message and member == page.initiator:
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

                    if reaction.emoji != self.bot.EmojiEnum.CLOSE:  # Fixes errors that occur when deleting the embed above
                        await reaction.message.remove_reaction(reaction.emoji, member)
                    break
        """

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Listener for reactions to EmbedPages messages.

        Switched from on_reaction_add since it wasn't getting fired when reactions were added to interaction response messages for some reason.
        """

        channel = await self.bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        member = await channel.guild.fetch_member(payload.user_id)
        if not payload.user_id == self.bot.user.id:
            for page in self.bot.pages:
                if payload.message_id == page.message.id and payload.user_id == page.initiator.id:
                    if payload.emoji.name == self.bot.EmojiEnum.LEFT_ARROW:
                        await page.previous_page()
                    elif payload.emoji.name == self.bot.EmojiEnum.RIGHT_ARROW:
                        await page.next_page()
                    elif payload.emoji.name == self.bot.EmojiEnum.CLOSE:
                        await message.delete()
                    elif payload.emoji.name == self.bot.EmojiEnum.MIN_BUTTON:
                        await page.first_page()
                    elif payload.emoji.name == self.bot.EmojiEnum.MAX_BUTTON:
                        await page.last_page()

                    if payload.emoji.name != self.bot.EmojiEnum.CLOSE:  # Fixes errors that occur when deleting the embed above
                        await message.remove_reaction(payload.emoji, member)
                    break

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """
        Event that ensures that memory is freed up once a message containing an embed page is deleted.
        """

        for page in self.bot.pages:
            if message == page.message:
                del page
                break

    async def last_active_handle(self, ctx: discord.Message | discord.Interaction) -> None:
        """
        Helper method to maintain the lists of last active members for a given guild.
        """

        user = ctx.author if type(ctx) == discord.Message else ctx.user

        if type(ctx.channel) == discord.DMChannel or user.bot:
            return
        if ctx.guild.id not in self.bot.last_active:
            self.bot.last_active[ctx.guild.id] = []  # create the dict key for that guild if it doesn't exist
        last_active_list = self.bot.last_active[ctx.guild.id]
        if user in last_active_list:
            last_active_list.remove(user)
        last_active_list.insert(0, user)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Event listener that updates the list of last active members for a given guild
        """

        await self.last_active_handle(message)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """
        Same purpose as `on_message` but for interactions, which do not necessarily have triggering messages.
        """

        await self.last_active_handle(interaction)


async def setup(bot: AdamBot) -> None:
    await bot.add_cog(Utils(bot))
