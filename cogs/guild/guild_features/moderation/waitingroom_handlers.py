import asyncio
import datetime

import discord
from discord import Embed, Colour
from discord.ext import commands

from libs.misc.handler import CommandHandler
from libs.misc.utils import get_user_avatar_url


class WaitingroomHandlers(CommandHandler):
    def __init__(self, bot, cog):
        super().__init__(self, bot)
        self.cog = cog

    async def testwelcome(self, ctx: commands.Context | discord.Interaction,
                          to_ping: discord.Member | discord.User = None) -> None:
        """
        Handler for the testwelcome commands.
        """

        (ctx_type, author) = self.command_args
        msg = await self.bot.get_config_key(ctx, "welcome_msg")
        if msg is None:
            message = "A welcome message has not been set."

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)
            return

        message = await self.cog.get_parsed_welcome_message(msg,
                                                            to_ping or author)  # to_ping or author means the author unless to_ping is provided.

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(message)
        else:
            await ctx.response.send_message(message)

    async def lurker(self, ctx: commands.Context | discord.Interaction, phrase: str) -> None:
        """
        Handler for the lurker commands.
        """

        (ctx_type, author) = self.command_args
        if ctx_type == self.ContextTypes.Interaction:
            await ctx.response.send_message(":ok_hand:")

        phrase = phrase.split(" ")
        # Get default phrase if there is one, but the one given in the command overrides the config one
        config_phrase = await self.bot.get_config_key(ctx, "lurker_phrase")
        show_tip = False
        if phrase:  # Handle subcommand
            # If phrase is given and a default hasn't yet been set, show a tip on setting defaults
            show_tip = True if config_phrase is None else False
            if phrase[0] == "kick":
                try:
                    days = phrase[1]
                except IndexError:
                    days = "7"
                await ctx.invoke(self.bot.get_command("lurker kick"), days)
                return

        phrase = " ".join(phrase) if phrase else config_phrase if config_phrase else ""
        if ctx.invoked_subcommand is None:
            members = [x for x in ctx.guild.members if len(x.roles) <= 1]  # Only the everyone role
            message = ""
            for member in members:
                if len(message + member.mention) >= 2000:
                    await ctx.channel.send(message + " " + phrase)
                    message = ""

                message += member.mention

            if message != "":  # There is still members to be mentioned
                await ctx.channel.send(message + " " + phrase)

            question = await ctx.channel.send("Do you want me to send DMs to all lurkers? (Type either 'yes' or 'no')")

            def check(m: discord.Message) -> bool:
                return m.author == author and m.channel == ctx.channel

            try:
                response = await self.bot.wait_for("message", check=check, timeout=300)
            except asyncio.TimeoutError:
                await question.delete()
                return
            if response.content.lower() == "yes":
                for i in range(len(members)):
                    member = members[i]

                    await question.edit(content=f"DMs have been sent to {i}/{len(members)} lurkers :ok_hand:")

                    try:
                        await member.send(f"**{ctx.guild.name}**: {phrase}")
                    except discord.Forbidden:  # Catches if DMs are closed
                        pass
                    except discord.HTTPException:
                        pass

                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx,
                                                                       "DM sent to lurkers successfully!",
                                                                       desc="DMs have been sent to all lurkers :ok_hand:")

            elif response.content.lower() == "no":
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "No DMs sent to lurkers!",
                                                                       desc="No DMs have been sent to lurkers :ok_hand:")

            else:
                await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "No DMs sent to lurkers!",
                                                                       desc="Unknown response, therefore no DMs have been sent to lurkers :ok_hand:")

            if show_tip:
                await ctx.channel.send(f"""{author.mention} To save time, you can provide a default message to be displayed on the lurker command, i.e. you don't need to type out the phrase each time.
        You can set this by doing `{ctx.prefix}config set lurker_phrase {phrase}`""")

    async def lurker_kick(self, ctx: commands.Context | discord.Interaction, days: int | str = 7) -> None:
        """
        Handler for the lurker_kick commands.
        """

        (ctx_type, author) = self.command_args
        def check(m: discord.Message) -> bool:
            return m.channel == ctx.channel and m.author == author

        if not days.isnumeric() and type(days) is not int:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Invalid number of days!",
                                                             desc="Specify a whole, non-zero number of days!")
            return

        days = int(days)
        time_ago = discord.utils.utcnow() - datetime.timedelta(days=days)
        members = [x for x in ctx.guild.members if
                   len(x.roles) <= 1 and x.joined_at < time_ago]  # Members with only the everyone role and more than 7 days ago
        if len(members) == 0:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "No lurker to kick!",
                                                                   desc=f"There are no lurkers to kick that have been here {days} days or longer!")
            return

        question = await ctx.channel.send(
            f"Do you want me to kick all lurkers that have been here {days} days or longer ({len(members)} members)? (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check=check, timeout=300)
        except asyncio.TimeoutError:
            await question.delete()
            return

        if response.content.lower() == "yes":
            for i in range(len(members)):
                member = members[i]

                await question.edit(content=f"Kicked {i}/{len(members)} lurkers :ok_hand:")
                await member.kick(reason="Auto-kicked following lurker kick command.")

            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Kicked the lurkers!",
                                                                   desc=f"All {len(members)} lurkers that have been here more than {days} days have been kicked :ok_hand:")

        elif response.content.lower() == "no":
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Kicked no lurkers!",
                                                                   desc="No lurkers have been kicked :ok_hand:")

        else:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Kicked no lurkers!",
                                                                   desc="Unknown response, therefore no lurkers have been kicked :ok_hand:")

        channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if channel_id is None:
            return

        channel = self.bot.get_channel(channel_id)

        embed = Embed(title="Lurker-kick", color=Colour.from_rgb(220, 123, 28))
        embed.add_field(name="Members", value=str(len(members)))
        embed.add_field(name="Reason", value="Auto-kicked from the -lurkers kick command")
        embed.add_field(name="Initiator", value=author.mention)
        embed.set_thumbnail(url=get_user_avatar_url(author, mode=1)[0])
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)
