import discord
from discord import app_commands
from discord.ext import commands

from . import member_handlers


class Member(commands.Cog):
    def __init__(self, bot) -> None:
        """
        Sets up the member cog with a provided bot.

        Loads and initialises the MemberHandlers class
        """

        self.bot = bot
        self.Handlers = member_handlers.MemberHandlers(bot)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        A method which listens for the bot to be ready.
        """

        await self.bot.tasks.register_task_type("reminder",
                                                self.handle_remind,
                                                needs_extra_columns=
                                                {
                                                    "member_id": "bigint",
                                                    "channel_id": "bigint",
                                                    "guild_id": "bigint",
                                                    "reason": "varchar(255)"
                                                }
        )

    # -----------------------QUOTE------------------------------

    @commands.command()
    @commands.guild_only()
    async def quote(self, ctx: commands.Context, messageid: int, channel: int | discord.TextChannel | discord.Thread) -> None:
        """
        Quote a message from its ID.
        Channel can be a standard channel or a thread.
        """

        await self.Handlers.quote(ctx, int(messageid), channel)

    @app_commands.command(
        name="quote",
        description="Quote a message from a specified channel or thread"
    )
    @app_commands.describe(
        messageid="The ID of the message to quote",
        channel="The channel or thread to retrieve this message from"
    )
    async def quote_slash(self, interaction: discord.Interaction, messageid: str,
                          channel: discord.TextChannel | app_commands.AppCommandThread) -> None:  # for some bizarre reason discord.Thread is not the type used in the transformer
        """
        Slash command equivalent of the classic quote command
        """

        await self.Handlers.quote(interaction, messageid, channel)

    # -----------------------FUN------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Listener to update the bruh counter.
        """

        if type(message.channel) == discord.DMChannel or message.author.bot:
            return

        if "bruh" in message.content.lower() and not message.author.bot and True not in [message.content.startswith(prefix) for prefix in await self.bot.get_used_prefixes(message)]:  # fix prefix detection
            async with self.bot.pool.acquire() as connection:
                await connection.execute("UPDATE config SET bruhs=bruhs + 1 WHERE guild_id=($1)", message.guild.id)
        return

    @commands.command(aliases=["bruh"])
    @commands.guild_only()
    async def bruhs(self, ctx: commands.Context) -> None:
        """
        Display the number of "bruhs" recorded for the context guild.
        """

        await ctx.send(await self.Handlers.bruhs(ctx.guild))

    @app_commands.command(
        name="bruhs",
        description="Find out how many bruhs have been recorded in this server"
    )
    async def bruhs_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command equivalent of the classic bruhs command.
        """

        await interaction.response.send_message(await self.Handlers.bruhs(interaction.guild))

    @commands.command()
    @commands.guild_only()
    async def cool(self, ctx: commands.Context, *, text: str) -> None:
        """
        MaKe YoUr MeSsAgE cOoL
        """

        await ctx.send(await self.Handlers.cool(text))
        await ctx.message.delete()

    @app_commands.command(
        name="cool",
        description="MaKe YoUr TeXt CoOl"
    )
    @app_commands.describe(
        text="The text to make cool"
    )
    async def cool_slash(self, interaction: discord.Interaction, text: str) -> None:
        """
        Slash command equivalent of the classic command "cool"
        """

        await interaction.response.send_message(await self.Handlers.cool(text))

    @commands.command()
    @commands.guild_only()
    async def cringe(self, ctx: commands.Context) -> None:
        """
        A classic command that sends the cringe video.
        """

        await ctx.message.delete()
        await ctx.send(await self.Handlers.cringe())

    @app_commands.command(
        name="cringe",
        description="Post the cringe video"
    )
    async def cringe_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command equivalent of the classic command "cringe"
        """

        await interaction.response.send_message(await self.Handlers.cringe())

    @commands.command()
    @commands.guild_only()
    async def spamping(self, ctx: commands.Context, amount: str, user: discord.Member | discord.Role, *,
                       message: str) -> None:
        """
        Repeatedly pings with a specified message.
        Can be used for users or roles.

        Requires administrator permissions or the "spamping_access" key to be configured for the context guild
        """

        await ctx.message.delete()
        await self.Handlers.spamping(ctx, amount, user, message)

    @app_commands.command(
        name="spamping",
        description="Spam ping a user or role"
    )
    @app_commands.describe(
        amount="The amount of pings to perform",
        user="The user or role to spamping",
        message="The message to accompany each ping"
    )
    async def spamping_slash(self, interaction: discord.Interaction, amount: int, user: discord.Member | discord.Role,
                             message: str) -> None:
        await self.Handlers.spamping(interaction, amount, user, message)

    @commands.command()
    @commands.guild_only()
    async def ghostping(self, ctx: commands.Context, amount: str, user: discord.Member | discord.Role) -> None:
        """
        A classic command for ghostpinging a given user or role in all of a specified guild's channels
        """

        await ctx.message.delete()
        await self.Handlers.ghostping(ctx, user, amount)

    @app_commands.command(
        name="ghostping",
        description="Ghost ping a user or role"
    )
    @app_commands.describe(
        amount="The amount of pings to perform",
        member="The member or role to ghostping"
    )
    async def ghostping_slash(self, interaction: discord.Interaction, amount: int,
                              member: discord.Member | discord.Role) -> None:
        """
        Slash command equivalent for the classic command "ghostping"
        """

        await self.Handlers.ghostping(interaction, member, amount)

    # -----------------------USER AND SERVER INFO------------------------------

    @commands.command()
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        """
        A classic command to display information about the context guild
        """

        await ctx.send(embed=await self.Handlers.serverinfo(ctx.guild, ctx.author))

    @app_commands.command(
        name="serverinfo",
        description="Display the server info"
    )
    async def serverinfo_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command equivalent of the classic command "serverinfo"
        """

        await interaction.response.send_message(
            embed=await self.Handlers.serverinfo(interaction.guild, interaction.user))

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def userinfo(self, ctx: commands.Context, *, args: discord.Member | str = "") -> None:
        """
        A classic command to display information about a specified member
        """

        await ctx.send(embed=await self.Handlers.userinfo(ctx, args))

    @app_commands.command(
        name="userinfo",
        description="Display userinfo for a given user"
    )
    @app_commands.describe(
        member="The member to get the userinfo of"
    )
    @app_commands.checks.bot_has_permissions(embed_links=True)
    async def userinfo_slash(self, interaction: discord.Interaction, member: str = "") -> None:
        """
        Slash command equivalent of the classic command "userinfo"
        """

        await interaction.response.send_message(
            embed=await self.Handlers.userinfo(await self.bot.interaction_context(self.bot, interaction), member))

    # -----------------------REMIND------------------------------

    async def handle_remind(self, data: dict) -> None:
        """
        A method to handle the sending of reminders when they are due

        If the members DMs are closed, the reminder is sent in the channel the command
        was invoked in.
        """

        try:
            member = self.bot.get_user(data["member_id"])
            message = f"You told me to remind you about this:\n{data['reason']}"
            try:
                await member.send(message)
            except (discord.Forbidden, discord.HTTPException):
                channel = self.bot.get_channel(data["channel_id"])
                await channel.send(f"{member.mention}, {message}")
        except Exception as e:
            print(f"REMIND: {type(e).__name__}: {e}")

    @commands.command(aliases=["rm", "remindme"])
    @commands.guild_only()
    async def remind(self, ctx: commands.Context, *, args: str) -> None:
        """
        A classic command for user reminders
        """

        timeperiod = ""
        if args:
            parsed_args = self.bot.flag_handler.separate_args(args, fetch=["time", "reason"], blank_as_flag="reason")
            timeperiod = parsed_args["time"]
            reason = parsed_args["reason"]
            await self.Handlers.remind(ctx, timeperiod, reason=reason)
        if not args or not timeperiod:
            await ctx.send(f"```{ctx.prefix}remind <sentence...> -t <time>```")
            return

    @app_commands.command(
        name="remind",
        description="Set up a reminder"
    )
    @app_commands.describe(
        time="The delay for the reminder in a format like 1w2d3h1m2s",
        reason="Reason for the reminder"
    )
    async def remind_slash(self, interaction: discord.Interaction, time: str, reason: str = "") -> None:
        """
        Slash command equivalent of the classic command "remind"
        """

        await self.Handlers.remind(interaction, self.bot.time_arg(time), reason=reason)

    # -----------------------AVATAR------------------------------

    @commands.command(aliases=["pfp"])
    @commands.guild_only()
    async def avatar(self, ctx: commands.Context, member: discord.Member | discord.User = None) -> None:
        """
        A classic command which gets the avatar(s) of a specified member
        """

        await ctx.send(await self.Handlers.avatar(member if member else ctx.author))

    @app_commands.command(
        name="avatar",
        description="Display the avatar for a specified user"
    )
    @app_commands.describe(
        member="The member to get the avatar(s) of"
    )
    async def avatar_slash(self, interaction, member: discord.Member | discord.User = None) -> None:
        """
        Slash command equivalent of the classic command "avatar"
        """

        await interaction.response.send_message(await self.Handlers.avatar(member if member else interaction.user))

    # -----------------------COUNTDOWNS------------------------------

    @commands.command(aliases=["results", "gcseresults", "alevelresults"])
    @commands.guild_only()
    async def resultsday(self, ctx: commands.Context, hour: str = "") -> None:
        """
        A classic command which displays a countdown embed for the specified results day
        """

        which = "GCSE" if ctx.invoked_with in ["resultsday", "gcseresults", "results", None] else "A-Level"
        await self.Handlers.resultsday(ctx, hour, which=which)

    @app_commands.command(
        name="results",
        description="Display the countdown to GCSE results day"
    )
    @app_commands.describe(
        hour="The hour to countdown to on results day"
    )
    async def resultsday_slash(self, interaction: discord.Interaction, hour: int = 10) -> None:
        """
        Slash command equivalent of the classic command "resultday" for GCSE
        """

        await self.Handlers.resultsday(interaction, hour)

    @app_commands.command(
        name="alevelresults",
        description="Display the countdown to A-Level results day"
    )
    @app_commands.describe(
        hour="The hour to countdown to on results day"
    )
    async def aresultsday_slash(self, interaction: discord.Interaction, hour: int = 10) -> None:
        """
        Slash command equivalent of the classic command "resultday" for A-Level
        """

        await self.Handlers.resultsday(interaction, hour, which="A-Level")

    @commands.command(aliases=["exams", "alevels"])
    @commands.guild_only()
    async def gcses(self, ctx: commands.Context) -> None:
        """
        A classic command that shows a countdown embed for the specified type of exams.
        """

        await self.Handlers.gcses(ctx, command=ctx.invoked_with)

    @app_commands.command(
        name="gcses",
        description="Display the countdown to the first GCSE exam"
    )
    async def gcses_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command equivalent of the classic command "gcses" for GCSE
        """

        await self.Handlers.gcses(interaction)

    @app_commands.command(
        name="alevels",
        description="Display the countdown to the first A-Level exam"
    )
    async def alevels_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command equivalent of the classic command "gcses" for A-Level
        """

        await self.Handlers.gcses(interaction, command="alevels")

    @commands.command()
    @commands.guild_only()
    async def code(self, ctx: commands.Context) -> None:
        """
        A classic command to send a link to the code for the project.
        """

        await ctx.send(await self.Handlers.code())

    @app_commands.command(
        name="code",
        description="Get the link to the code for this bot"
    )
    async def code_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command "code"
        """

        await interaction.response.send_message(await self.Handlers.code())


async def setup(bot) -> None:
    await bot.add_cog(Member(bot))
