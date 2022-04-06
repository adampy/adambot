import discord
from discord.ext import commands

from adambot import AdamBot


class FilterHandlers:
    def __init__(self, bot: AdamBot, cog: commands.Cog) -> None:  # same point here as with demographics
        self.bot = bot
        self.cog = cog

    async def add(self, ctx: commands.Context | discord.Interaction, text: str) -> None:
        """
        Handler for the add commands.

        Adds a phrase to the context guild's filter.
        """

        text = text.lower()

        if text not in self.cog.filters[ctx.guild.id]["filtered"]:
            message = await self.cog.clean_up(ctx, text, "filtered")
            if not message:
                return

            self.cog.filters[ctx.guild.id]["filtered"].append(text.lower())
            await self.cog.propagate_new_guild_filter(ctx.guild)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Filter added!", desc=message)
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That's already in the filtered list!")

    async def add_ignore(self, ctx: commands.Context | discord.Interaction, text: str) -> None:
        """
        Handler for the add_ignore commands.

        Adds a phrase to be ignored from the context guild's filter.
        """

        text = text.lower()

        if text not in self.cog.filters[ctx.guild.id]["ignored"]:
            message = await self.cog.clean_up(ctx, text, "ignored", spoiler=False)
            if not message:
                return

            if True not in [phrase in text for phrase in self.cog.filters[ctx.guild.id]["filtered"]]:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                 "Didn't add redundant phrase to ignored list",
                                                                 desc="The phrase wasn't added since it would have no effect, as it has no filtered phrases within it")
                return

            if True in [phrase == text for phrase in self.cog.filters[ctx.guild.id]["filtered"]]:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                 "Couldn't add that phrase to the ignored list",
                                                                 desc="A phrase cannot be both in the filtered list and the ignored list at the same time!")
                return

            self.cog.filters[ctx.guild.id]["ignored"].append(text)
            await self.cog.propagate_new_guild_filter(ctx.guild)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Phrase added to ignored list!",
                                                               desc=message)
        else:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That's already in the ignored list!")

    async def remove(self, ctx: commands.Context | discord.Interaction, text: str) -> None:
        """
        Handler for the remove commands.

        Removes a phrase from the context guild's filter.
        """

        text = text.lower()
        remove = [a for a in self.cog.filters[ctx.guild.id]["ignored"]]
        for phrase in self.cog.filters[ctx.guild.id]["ignored"]:
            for phrasee in self.cog.filters[ctx.guild.id]["filtered"]:
                if phrasee in phrase and phrasee != text:  # not checking for what we're removing
                    del remove[remove.index(phrase)]

        for removal in remove:
            del self.cog.filters[ctx.guild.id]["ignored"][self.cog.filters[ctx.guild.id]["ignored"].index(removal)]

        msg = "\n".join([f"•  *{word}*" for word in remove]) if remove else ""
        await self.generic_remove(ctx, text, "filtered",
                                  desc=f"Removed some redundant phrases from the ignored list too:\n\n{msg}" if msg else "")

    async def remove_ignore(self, ctx: commands.Context | discord.Interaction, text: str) -> None:
        """
        Handler for the remove_ignore commands.

        Removes a phrase from the ignore list for the context guild's filter.
        """

        await self.generic_remove(ctx, text.lower(), "ignored")

    async def generic_remove(self, ctx: commands.Context, text: str, key: str, desc: str = "") -> None:
        """
        Method to allow removal of a phrase from either list. Saves almost-duplicate code.
        """

        text = text.lower()
        if key not in ["filtered", "ignored"]:
            return  # get ignored

        if text not in self.cog.filters[ctx.guild.id][key]:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, f"That phrase is not in the {key} list!",
                                                             desc)

        else:
            del self.cog.filters[ctx.guild.id][key][self.cog.filters[ctx.guild.id][key].index(text)]
            await self.cog.propagate_new_guild_filter(ctx.guild)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Phrase removed",
                                                               desc=f"{text} removed from {key} list!\n{desc}")

    async def list_generic(self, ctx: commands.Context, key: str, spoiler: bool = True) -> None:
        """
        Deduplicate list commands.
        """

        if key not in ["filtered", "ignored"]:
            return  # get ignored

        msg_content = (
            "\n".join([f"• ||{word}||" if spoiler else word for word in self.cog.filters[ctx.guild.id][key]])) if \
            self.cog.filters[ctx.guild.id][key] else "Nothing to show here!"
        await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"{ctx.guild.name} {key} phrases list",
                                                               desc=msg_content)

    async def list_filter(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the list commands.

        Lists the context guild's filtered phrases.

        Named as list_filter rather than list to avoid overriding builtin list in this scope.
        """

        await self.list_generic(ctx, "filtered")

    async def list_filter_ignore(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the list_ignore commands.

        Lists the context guild's ignored filter phrases.
        """

        await self.list_generic(ctx, "ignored", spoiler=False)

    async def clear_filter(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the clear commands.

        Clears the filtered phrases list and the ignored phrases list for the context guild.
        """

        self.cog.filters[ctx.guild.id] = {"filtered": [], "ignored": []}
        await self.cog.propagate_new_guild_filter(ctx.guild)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Filter cleared!",
                                                           desc=f"The filter for **{ctx.guild.name}** has been cleared!")
