from datetime import timedelta
from math import ceil
from typing import Optional

import discord
from discord import Embed, Colour
from discord.ext import commands

from .utils import PageTypes, EmojiEnum  # TODO: Move this into here


class EmbedPageButton(discord.ui.Button['EmbedPages']):
    def __init__(self, emoji: EmojiEnum, func, label: Optional[str] = None, style: discord.ButtonStyle = discord.ButtonStyle.primary):
        super().__init__(style=style, label=label, emoji=emoji)
        self.func = func

    async def callback(self, interaction: discord.Interaction):
        # Defer interactions from anyone but original initiator
        if interaction.user != self.view.initiator:
            await interaction.response.defer()
            return
        await self.func(interaction)


class EmbedPages(discord.ui.View):
    def __init__(self, page_type: int, data: list, title: str, colour: Colour, bot, initiator: discord.Member, channel: discord.TextChannel | discord.Thread, desc: str = "", thumbnail_url: str = "",
                 footer: str = "", icon_url: str = "", ctx: commands.Context | discord.Interaction = None) -> None:
        super().__init__(timeout=300)  # Initialise view
        self.bot = bot
        self.data = data
        self.title = title
        self.page_type = page_type
        self.top_limit = 0
        self.embed: Optional[Embed] = None  # Embed(title=title + ": Page 1", color=colour, desc=desc)
        self.page_num = 1
        self.initiator = initiator  # Here to stop others using the embed
        self.channel = channel

        # These are for formatting the embed
        self.desc = desc
        self.footer = footer
        self.thumbnail_url = thumbnail_url
        self.icon_url = icon_url
        self.colour = colour

        self.ctx = ctx

        # Add reactions
        self.add_item(EmbedPageButton(EmojiEnum.MIN_BUTTON, self.first_page, label="First page"))
        self.add_item(EmbedPageButton(EmojiEnum.LEFT_ARROW, self.previous_page, label="Previous page"))
        self.add_item(EmbedPageButton(EmojiEnum.RIGHT_ARROW, self.next_page, label="Next page"))
        self.add_item(EmbedPageButton(EmojiEnum.MAX_BUTTON, self.last_page, label="Last page"))
        self.add_item(EmbedPageButton(EmojiEnum.CLOSE, self.close, style=discord.ButtonStyle.danger, label="Close"))

    async def set_page(self, page_num: int) -> None:
        """
        Changes the embed accordingly
        """

        if self.page_type == PageTypes.REP:
            self.data = [x for x in self.data if self.channel.guild.get_member(x[0]) is not None]
            page_length = 10
        elif self.page_type == PageTypes.ROLE_LIST:
            page_length = 10
        else:
            page_length = 5
        self.top_limit = ceil(len(self.data) / page_length)

        # Clear previous data
        self.embed = Embed(title=f"{self.title} (Page {page_num}/{self.top_limit})", color=self.colour,
                           description=self.desc)
        
        if self.footer and self.icon_url:
            self.embed.set_footer(text=self.footer, icon_url=self.icon_url)
        elif self.footer:
            self.embed.set_footer(text=self.footer)  # TODO: Is there a more efficient way to cover the cases where either a footer or icon_url is given but not both?
        elif self.icon_url:
            self.embed.set_footer(icon_url=self.icon_url)
        if self.thumbnail_url:
            self.embed.set_thumbnail(url=self.thumbnail_url)  # NOTE: I WAS CHANGING ALL GUILD ICONS AND AVATARS SO THEY WORK WITH THE DEFAULTS I.E. NO AVATAR OR NO GUILD ICON

        # Gettings the wanted data
        self.page_num = page_num
        page_num -= 1
        for i in range(page_length * page_num, min(page_length * page_num + page_length, len(self.data))):
            # Go through each different type of page and format accordingly
            if self.page_type == PageTypes.QOTD:
                question_id = self.data[i][0]
                question = self.data[i][1]
                member_id = int(self.data[i][2])
                user = await self.bot.fetch_user(member_id)
                date = (self.data[i][3] + timedelta(hours=1)).strftime("%H:%M on %d/%m/%y")

                self.embed.add_field(name=f"{question}",
                                     value=f"ID **{question_id}** submitted on {date} by {user.name if user else '*MEMBER NOT FOUND*'} ({member_id})",
                                     inline=False)

            elif self.page_type == PageTypes.WARN:
                staff = await self.bot.fetch_user(self.data[i][2])
                member = await self.bot.fetch_user(self.data[i][1])

                if member:
                    member_string = f"{str(member)} ({self.data[i][1]}) Reason: {self.data[i][4]}"
                else:
                    member_string = f"DELETED USER ({self.data[i][1]}) Reason: {self.data[i][4]}"

                if staff:
                    staff_string = f"{str(staff)} ({self.data[i][2]})"
                else:
                    staff_string = f"DELETED USER ({self.data[i][2]})"

                self.embed.add_field(name=f"**{self.data[i][0]}** : {member_string}",
                                     value=f"{self.data[i][3].strftime('On %d/%m/%Y at %I:%M %p')} by {staff_string}",
                                     inline=False)

            elif self.page_type == PageTypes.REP:
                member = self.channel.guild.get_member(self.data[i][0])
                self.embed.add_field(name=f"{member.display_name}", value=f"{self.data[i][1]}", inline=False)

            elif self.page_type == PageTypes.CONFIG:
                config_key = list(self.data.keys())[i]  # Change the index into the key
                config_option = self.data[config_key]  # Get the current value list from the key
                name = f"• {str(config_key)} ({config_option[1]})"  # Config name that appears on the embed
                self.embed.add_field(name=name, value=config_option[2], inline=False)

            elif self.page_type == PageTypes.ROLE_LIST:
                self.embed.add_field(name=self.data[i].name, value=self.data[i].mention, inline=False)

            elif self.page_type == PageTypes.STARBOARD_LIST:
                starboard = self.data[i]
                channel = self.bot.get_channel(starboard.channel.id)
                custom_emoji = self.bot.get_emoji(starboard.emoji_id) if starboard.emoji_id else None
                colour = starboard.embed_colour if starboard.embed_colour else "#" + "".join([str(hex(component)).replace("0x", "").upper() for component in self.bot.GOLDEN_YELLOW.to_rgb()])
                
                sub_fields = f"• Minimum stars: {starboard.minimum_stars}\n"  # Add star subfield
                sub_fields += "• Emoji: " + (starboard.emoji if starboard.emoji else f"<:{custom_emoji.name}:{custom_emoji.id}>")  # Add either the standard emoji, or the custom one
                sub_fields += "\n• Colour: " + colour
                sub_fields += "\n• Allow self starring (author can star their own message): " + str(starboard.allow_self_star)
                self.embed.add_field(name=f"#{channel.name}", value=sub_fields, inline=False)

    async def previous_page(self, interaction: discord.Interaction) -> None:
        """
        Moves the embed to the previous page
        """

        if self.page_num != 1:  # Cannot go to previous page if already on first page
            await self.set_page(self.page_num - 1)
            await self.edit(interaction)

    async def next_page(self, interaction: discord.Interaction) -> None:
        """
        Moves the embed to the next page
        """

        if self.page_num != self.top_limit:  # Can only move next if not on the limit
            await self.set_page(self.page_num + 1)
            await self.edit(interaction)

    async def first_page(self, interaction: discord.Interaction) -> None:
        """
        Moves the embed to the first page
        """

        await self.set_page(1)
        await self.edit(interaction)

    async def last_page(self, interaction: discord.Interaction) -> None:
        """
        Moves the embed to the last page
        """

        await self.set_page(self.top_limit)
        await self.edit(interaction)

    async def send(self) -> None:
        """
        Sends the embed message. The interaction times out after 300 seconds (5 minutes).
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        if ctx_type == self.bot.ContextTypes.Context or (ctx_type == self.bot.ContextTypes.Interaction and self.ctx.response.is_done()) or not self.ctx:
            await self.channel.send(embed=self.embed, view=self)
        else:
            await self.ctx.response.send_message(embed=self.embed, view=self)

    async def edit(self, interaction: discord.Interaction) -> None:
        """
        Edits the interaction's original message to represent the current self.embed
        """

        await interaction.response.edit_message(embed=self.embed, view=self)

    async def close(self, interaction: discord.Interaction) -> None:
        """
        Clears all of the buttons from the view
        """

        await interaction.response.defer()
        self.clear_items()
        await interaction.delete_original_message()  # TODO: Check raises


class EmbedPageHook(discord.ext.commands.Cog):
    def __init__(self, bot) -> None:
        bot.__dict__.update(globals())  # Bring the embed pages into the bot


async def setup(bot) -> None:
    await bot.add_cog(EmbedPageHook(bot))
