import ast  # using ast for literal_eval, stops code injection
import asyncio
from math import ceil
from typing import Optional

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

from adambot import AdamBot
from libs.misc.decorators import is_staff, is_staff_slash
from . import filter_handlers


class Filter(commands.Cog):
    def __init__(self, bot: AdamBot) -> None:
        """
        Sets up the filter cog with a provided bot.

        Loads and initialises the FilterHandlers class
        """

        self.filters = {}
        self.bot = bot
        self.Handlers = filter_handlers.FilterHandlers(bot, self)

    filter_slash = app_commands.Group(name="filter", description="View the server filter")

    async def check_is_command(self, message: discord.Message) -> bool:
        """
        Checks whether or not `message` is a valid filter command or not
        """

        ctx = await self.bot.get_context(message)
        content = message.content
        prefixes = await self.bot.get_used_prefixes(message)
        prefixes.sort(key=len, reverse=True)
        for prefix in prefixes:
            if content.startswith(prefix):
                content = content.replace(prefix, "")
                break

        is_command = True if (await self.bot.is_staff(ctx) and content.startswith(
            "filter") and content != message.content) else False

        return is_command

    async def load_filters(self, guild: discord.Guild) -> None:
        """
        Method used to load filter data for all guilds into self.filters
        """

        async with self.bot.pool.acquire() as connection:
            prop = await connection.fetchval("SELECT filters FROM filter WHERE guild_id = $1", guild.id)
            if not prop:
                await connection.execute("INSERT INTO filter (guild_id, filters) VALUES ($1, $2)", guild.id,
                                         "{'filtered':[], 'ignored':[]}")
                self.filters[guild.id] = {"filtered": [], "ignored": []}

            else:
                prop = ast.literal_eval(prop)
                if type(prop) is not dict or not ("filtered" in prop and "ignored" in prop):
                    await connection.execute("UPDATE filter SET filters = $1 WHERE guild_id = $2",
                                             "{'filtered':[], 'ignored':[]}", guild.id)
                    self.filters[guild.id] = {"filtered": [], "ignored": []}
                else:
                    self.filters[guild.id] = prop

    async def propagate_new_guild_filter(self, guild: discord.Guild) -> None:
        """
        Method used for pushing filter changes to the DB
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute("UPDATE filter SET filters = $1 WHERE guild_id = $2", str(self.filters[guild.id]),
                                     guild.id)

    # ---LISTENERS---

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Maybe tweak this so the tables are only created on the fly as and when they are needed?
        success = False
        while not success:  # race condition for table to be created otherwise
            try:
                for guild in self.bot.guilds:
                    await self.load_filters(guild)
                    success = True
            except asyncpg.exceptions.UndefinedTableError:
                success = False
                print("filter table doesn't exist yet, waiting 1 second...")
                await asyncio.sleep(1)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Handles messages that are being sent.
        """

        if not self.bot.is_ready() or type(message.channel) not in [discord.TextChannel,
                                                                    discord.Thread]:  # Only filter on TextChannels
            return  # sometimes barfs on startup

        await self.handle_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """
        Handles message edits for people trying to get around the filter.
        """

        if not self.bot.is_ready() or type(before.channel) not in [discord.TextChannel,
                                                                   discord.Thread]:  # Only filter on TextChannels
            return  # sometimes barfs on startup
        await self.handle_message(after)

    async def handle_message(self, message: discord.Message) -> None:
        """
        Checks whether a message should be removed.
        """

        ctx = await self.bot.get_context(message)
        is_command = await self.check_is_command(message)
        if not is_command and message.author.id == self.bot.user.id and message.reference:
            is_command = await self.check_is_command(await ctx.fetch_message(message.reference.message_id))

        try:
            filters = self.filters[message.guild.id]
            msg = message.content.lower()
            for ignore in filters["ignored"]:
                msg = msg.replace(ignore.lower(), "")

            tripped = [phrase.lower() for phrase in filters["filtered"] if phrase.lower() in msg]
            disp_tripped = "||" + (" ,".join([f"'{trip}'" for trip in tripped[:10]])) + (
                f"(+ {len(tripped) - 10} more)" if len(tripped) > 10 else "") + "||"
            if tripped and not is_command:
                # case insensitive is probably the best idea
                await message.delete()

                log_channel = self.bot.get_channel(await self.bot.get_config_key(ctx, "filter_log_channel"))
                log_channel = self.bot.get_channel(
                    await self.bot.get_config_key(ctx, "log_channel")) if not log_channel else log_channel
                if log_channel:
                    embeds = []
                    chunks = ceil(len(message.content) / 1020)

                    for i in range(1, chunks + 1):
                        embed = discord.Embed(title=":x: Message Filtered", color=discord.Colour.from_rgb(255, 7, 58))
                        embed.add_field(name="User",
                                        value=f"{str(message.author)} ({message.author.id})" or "undetected",
                                        inline=True)
                        embed.add_field(name="Filtered phrases", value=disp_tripped)
                        embed.add_field(name="Message ID", value=message.id, inline=True)
                        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                        embed.add_field(name=f"Message {f'part {i}' if i > 1 else ''}",
                                        value=f"||{message.content[1020 * (i - 1):1020 * i]}||" if (hasattr(message,
                                                                                                            "content") and message.content) else "(No detected text content)",
                                        inline=False)
                        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))

                        embeds.append(embed)

                    [await log_channel.send(embed=embed) for embed in embeds]

        except Exception:  # If the bot hasn't loaded the filters yet
            pass

    @commands.group()
    @commands.guild_only()
    async def filter(self, ctx: commands.Context) -> None:
        if not ctx.invoked_subcommand:
            await ctx.reply(f"Type `{ctx.prefix}help filter` to get info!")

    async def clean_up(self, ctx: commands.Context, text: str, key: str, spoiler: bool = True) -> Optional[str]:
        """
        Strictly only cleans up one list. Cross-checks occur specifically within their own scopes.
        This makes sure space isn't wasted by adding random garbage to the filter that will already be in effect anyway
        """

        text = text.lower()  # shouldn't be necessary but removes dependency on other methods to implement case standard
        keys = ["filtered", "ignored"]
        if key not in keys:
            return  # get ignored

        disp_text = f"||{text}||" if spoiler else text
        if True in [phrase in text for phrase in self.filters[ctx.guild.id][key]]:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Redundant phrase wasn't added!",
                                                             desc=f"{disp_text} wasn't added to the {key} list since it contains another phrase that has already been added")
            return

        check = [text in phrase for phrase in self.filters[ctx.guild.id][key]]  # de-duplicate
        removed = []
        while True in check:
            index = check.index(True)
            del check[index]
            removed.append(f"{self.filters[ctx.guild.id][key][index]}")
            del self.filters[ctx.guild.id][key][index]

        message = f"Added *{disp_text}* to the {key} list!"
        the_list = "\n".join([f"•  *{word}*" if key == "ignored" else f"•  ||*{word}*||" for word in removed])
        message = message if not the_list else (
                    message + f"\n\nRemoved some redundant phrases from the {key} list too:\n\n{the_list}")

        return message

    @filter.command()
    @commands.guild_only()
    @is_staff()
    async def add(self, ctx: commands.Context, *, text: str) -> None:
        """
        Allows adding a filtered phrase for the guild. Staff role needed.
        """

        await self.Handlers.add(ctx, text)

    @filter_slash.command(
        name="add",
        description="Add a phrase to the server's filter"
    )
    @app_commands.describe(
        text="The phrase to add to the server's filter"
    )
    @is_staff_slash()
    async def add_slash(self, interaction: discord.Interaction, text: str) -> None:
        """
        Slash equivalent of the classic command add.
        """

        await self.Handlers.add(interaction, text)

    @filter.command()
    @commands.guild_only()
    @is_staff()
    async def add_ignore(self, ctx: commands.Context, *, text: str) -> None:
        """
        Allows adding a phrase that will be ignored by the filter.
        This will only add the phrase if it will have an effect.
        Staff role needed.
        """

        await self.Handlers.add_ignore(ctx, text)

    @filter_slash.command(
        name="add_ignore",
        description="Add a phrase to be ignored when handling filtering on this server"
    )
    @app_commands.describe(
        text="The phrase to be added to the ignore list of the filter"
    )
    @is_staff_slash()
    async def add_ignore_slash(self, interaction: discord.Interaction, text: str) -> None:
        """
        Slash equivalent of the classic command add_ignore.
        """

        await self.Handlers.add_ignore(interaction, text)

    @filter.command()
    @commands.guild_only()
    @is_staff()
    async def remove(self, ctx: commands.Context, *, text: str) -> None:
        """
        Allows removing a filtered phrase. Staff role needed.
        """

        await self.Handlers.remove(ctx, text)

    @filter_slash.command(
        name="remove",
        description="Remove a phrase from the filter for this server"
    )
    @app_commands.describe(
        text="The phrase to be removed from the filter"
    )
    @is_staff_slash()
    async def remove_slash(self, interaction: discord.Interaction, text: str) -> None:
        """
        Slash equivalent of the classic command remove
        """

        await self.Handlers.remove(interaction, text)

    @filter.command()
    @commands.guild_only()
    @is_staff()
    async def remove_ignore(self, ctx: commands.Context, *, text: str) -> None:
        """
        Allows removing a phrase ignored by the filter. Staff role needed.
        """

        await self.Handlers.remove_ignore(ctx, text)

    @filter_slash.command(
        name="remove_ignore",
        description="Remove an ignored filter phrase for this server"
    )
    @app_commands.describe(
        text="The phrase to remove from the ignore list"
    )
    @is_staff_slash()
    async def remove_ignore_slash(self, interaction: discord.Interaction, text: str) -> None:
        """
        Slash equivalent of the classic command remove_ignore.
        """

        await self.Handlers.remove_ignore(interaction, text)

    @filter.command(name="list")
    @commands.guild_only()
    @is_staff()
    async def list_filter(self, ctx: commands.Context) -> None:
        """
        Lists filtered phrases for a guild. Staff role needed.
        """

        await self.Handlers.list_filter(ctx)

    @filter_slash.command(
        name="list",
        description="List all the filtered phrases for this server"
    )
    @is_staff_slash()
    async def list_filter_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command filter.
        """

        await self.Handlers.list_filter(interaction)

    @filter.command()
    @commands.guild_only()
    @is_staff()
    async def list_ignore(self, ctx: commands.Context) -> None:
        """
        Lists ignored phrases for a guild. Staff role needed.
        """

        await self.Handlers.list_filter_ignore(ctx)

    @filter_slash.command(
        name="list_ignore",
        description="List all the ignored phrases for this server"
    )
    @is_staff_slash()
    async def list_ignore_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command list_ignore.
        """

        await self.Handlers.list_filter_ignore(interaction)

    @filter.command(name="clear")
    @commands.guild_only()
    @is_staff()
    async def clear_filter(self, ctx: commands.Context) -> None:
        """
        Allows clearing the list of filtered and ignored phrases for the guild. Staff role needed.
        """

        await self.Handlers.clear_filter(ctx)

    @filter_slash.command(
        name="clear",
        description="Clear the filter for this server"
    )
    @is_staff_slash()
    async def clear_filter_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command clear.
        """

        await self.Handlers.clear_filter(interaction)


async def setup(bot: AdamBot) -> None:
    await bot.add_cog(Filter(bot))
