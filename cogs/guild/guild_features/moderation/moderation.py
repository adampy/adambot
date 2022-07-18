from discord.ext.commands import has_permissions

from adambot import AdamBot
from libs.misc.decorators import *
from . import moderation_handlers


class Moderation(commands.Cog):
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot
        self.Handlers = moderation_handlers.ModerationHandlers(bot)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.bot.tasks.register_task_type("unmute", self.Handlers.handle_unmute)
        await self.bot.tasks.register_task_type("unban", self.Handlers.handle_unban)

    # -----------------------CLOSE COMMAND-----------------------

    @commands.command(name="close", aliases=["die", "yeet", "shutdown"])
    @commands.guild_only()
    @is_dev()
    async def botclose(self, ctx: commands.Context) -> None:
        """
        Command to shut the bot down.

        Dev required.
        """

        await self.Handlers.botclose(ctx)

    @app_commands.command(
        name="shutdown",
        description="Shut the bot down"
    )
    @is_dev_slash()
    async def botclose_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash equivalent of the classic command close.
        """

        await self.Handlers.botclose(interaction)

    # -----------------------PURGE------------------------------

    @commands.command()
    @commands.has_permissions(manage_messages=True)  # TODO: Perhaps make it possible to turn some commands, like purge, off
    async def purge(self, ctx: commands.Context, limit: str = "5", member: discord.Member = None) -> None:
        """
        Purges the channel.
        Usage: `purge 50`
        """

        await self.Handlers.purge(ctx, limit=limit, member=member)

    @app_commands.command(
        name="purge",
        description="Purges a given number of messages from the specified channel."
    )
    @app_commands.describe(
        limit="The number of messages to purge",
        member="A member to target the message purge at"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, limit: int = 5, member: discord.Member = None) -> None:
        """
        Slash equivalent of the classic command purge.
        """

        await self.Handlers.purge(interaction, limit=limit, member=member)

    # -----------------------KICK------------------------------

    @commands.command()
    @has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, args: str = "") -> None:
        """
        Kicks a given user.
        Kick members perm needed
        """

        await self.Handlers.kick(ctx, member, args=args)

    @app_commands.command(
        name="kick",
        description="Kick a member from the server"
    )
    @app_commands.describe(
        member="The member to kick",
        reason="Reason for kick"
    )
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = None) -> None:
        """
        Slash equivalent of the classic command kick.
        """

        await self.Handlers.kick(interaction, member, reason=reason)

    # -----------------------BAN------------------------------

    @commands.command(aliases=["hackban", "massban"])
    @has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, *, args: str = "") -> None:
        """
        Bans a given user.
        Merged with previous command hackban
        Single bans work with user mention or user ID
        Mass bans work with user IDs currently, reason flag HAS to be specified if setting
        Ban members perm needed
        """

        await self.Handlers.ban(ctx, args)

    @app_commands.command(
        name="ban",
        description="Ban one or more users"
    )
    @app_commands.describe(
        members="The member(s) to ban",
        reason="Reason for ban(s)",
        timeperiod="The time that the ban will last in a format like 1w2d3h1m2s"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_slash(self, interaction: discord.Interaction, members: str, reason: str = None, timeperiod: str = None) -> None:
        """
        Slash equivalent of the classic command ban.
        """

        await self.Handlers.ban(interaction, members, reason=reason, timeperiod=timeperiod)

    @commands.command()
    @has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, member: discord.User | str, *, args: str = "") -> None:
        """
        Unbans a given user with the ID.
        Ban members perm needed.
        """

        await self.Handlers.unban(ctx, member, args=args)

    @app_commands.command(
        name="unban",
        description="Unban a user from this server"
    )
    @app_commands.describe(
        member="The user to unban",
        reason="Reason for unban"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_slash(self, interaction: discord.Interaction, member: str, reason: str = "") -> None:
        """
        Slash equivalent of the classic command unban.
        """

        await self.Handlers.unban(interaction, member, reason=reason)

    # -----------------------MUTES------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Method to reinforce mutes in cases where Discord permissions cause problems
        Blameth discordeth foreth thiseth codeth
        """

        if type(message.channel) == discord.DMChannel or type(message.author) == discord.User:
            return

        try:
            muted_role = await self.bot.get_config_key(message, "muted_role")
            if muted_role is not None and muted_role in [role.id for role in message.author.roles]:
                await message.delete()
        except discord.NotFound:
            pass  # Message can't be deleted (nobody cares)
        except KeyError:
            pass  # Bot not fully loaded yet (nobody cares)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, *, args: str = "") -> None:
        """
        Gives a given user the Muted role.
        Manage roles perm needed.
        """

        await self.Handlers.mute(ctx, member, args)

    @app_commands.command(
        name="mute",
        description="Give a member the muted role"
    )
    @app_commands.describe(
        member="Member to mute",
        reason="Reason for mute",
        timeperiod="The time that the mute will last in a format like 1w2d3h1m2s"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "", timeperiod: str = "") -> None:
        """
        Slash equivalent of the classic command mute.
        """

        await self.Handlers.mute(interaction, member, reason=reason, timeperiod=timeperiod)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, args: str = "") -> None:
        """
        Removes Muted role from a given user.
        Manage roles perm needed.
        """

        await self.Handlers.unmute(ctx, member, args=args)

    @app_commands.command(
        name="unmute",
        description="Remove the muted role from a member"
    )
    @app_commands.describe(
        member="Member to unmute",
        reason="Reason for unmute"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "") -> None:
        """
        Slash equivalent of the classic command unmute.
        """

        await self.Handlers.unmute(interaction, member, reason=reason)

    # -----------------------SLOWMODE------------------------------

    @commands.command()
    async def slowmode(self, ctx: commands.Context, time: str) -> None:
        """
        Adds slowmode in a specific channel. Time is given in seconds.
        """

        await self.Handlers.slowmode(ctx, time)

    @app_commands.command(
        name="slowmode",
        description="Add a slowmode in this channel"
    )
    @app_commands.describe(
        time="The number of seconds the slowmode should be set to"
    )
    async def slowmode_slash(self, interaction: discord.Interaction, time: int) -> None:
        """
        Slash equivalent of the classic command slowmode.
        """

        await self.Handlers.slowmode(interaction, time)

    # -----------------------JAIL & BANISH------------------------------

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def jail(self, ctx: commands.Context, member: discord.Member) -> None:
        """
        Lets a member view whatever channel has been set up with view channel perms for the Jail role.
        Manage roles perm needed.
        """

        await self.Handlers.jail(ctx, member)

    @app_commands.command(
        name="jail",
        description="Remove all of their roles and send them to the designated jail channel"
    )
    @app_commands.describe(
        member="The member to jail"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def jail_slash(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """
        Slash equivalent of the classic command jail.
        """

        await self.Handlers.jail(interaction, member)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unjail(self, ctx: commands.Context, member: discord.Member) -> None:
        """
        Removes the Jail role.
        Manage roles perm needed.
        """

        await self.Handlers.unjail(ctx, member)

    @app_commands.command(
        name="unjail",
        description="Unjail a member"
    )
    @app_commands.describe(
        member="The member to unjail"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def unjail_slash(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """
        Slash equivalent of the classic command unjail.
        """

        await self.Handlers.unjail(interaction, member)

    # -----------------------MISC------------------------------

    @commands.command()
    @is_staff()
    async def say(self, ctx: commands.Context, channel: discord.TextChannel | discord.Thread, *, text: str) -> None:
        """
        Say a given string in a given channel
        Staff role needed.
        """

        await self.Handlers.say(ctx, channel, text)

    @app_commands.command(
        name="say",
        description="Make the bot send a given piece of text in a given channel"
    )
    @app_commands.describe(
        channel="The channel or thread to send the message in",
        text="The text to send"
    )
    @is_staff_slash()
    async def say_slash(self, interaction: discord.Interaction, channel: discord.TextChannel | app_commands.AppCommandThread, text: str) -> None:
        """
        Slash equivalent of the classic command say.
        """

        await self.Handlers.say(interaction, channel, text)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def revokeinvite(self, ctx: commands.Context, invite_code: str) -> None:
        """
        Command that revokes an invite from a server
        """

        await self.Handlers.revokeinvite(ctx, invite_code)

    @app_commands.command(
        name="revokeinvite",
        description="Revoke an invite on this server"
    )
    @app_commands.describe(
        invite_code="The invite code to revoke"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def revokeinvite_slash(self, interaction: discord.Interaction, invite_code: str) -> None:
        """
        Slash equivalent of the classic command revokeinvite.
        """

        await self.Handlers.revokeinvite(interaction, invite_code)


async def setup(bot: AdamBot) -> None:
    await bot.add_cog(Moderation(bot))
