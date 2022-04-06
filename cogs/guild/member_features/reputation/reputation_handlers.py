import discord
import matplotlib.pyplot as plt
from discord import Embed, Colour
from discord.ext import commands

from libs.misc.utils import get_user_avatar_url, get_guild_icon_url

from adambot import AdamBot

class ReputationHandlers:
    def __init__(self, bot: AdamBot) -> None:
        self.bot = bot

    async def get_leaderboard(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Constructs and sends an embed containing the reputation leaderboard for the context guild.
        """

        is_ctx = type(ctx) is commands.Context
        author = ctx.author if is_ctx else ctx.user
        async with self.bot.pool.acquire() as connection:
            leaderboard = await connection.fetch(
                "SELECT member_id, reps FROM rep WHERE guild_id = $1 ORDER BY reps DESC", ctx.guild.id)

        if len(leaderboard) == 0:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                             f"There aren't any reputation points in {ctx.guild.name} yet! ")
            return

        embed = self.bot.EmbedPages(
            self.bot.PageTypes.REP,
            leaderboard,
            f"{ctx.guild.name}'s Reputation Leaderboard",
            Colour.from_rgb(177, 252, 129),
            self.bot,
            author,
            ctx.channel,
            thumbnail_url=get_guild_icon_url(ctx.guild),
            icon_url=get_user_avatar_url(author, mode=1)[0],
            footer=f"Requested by: {author.display_name} ({author})\n" + self.bot.correct_time().strftime(
                self.bot.ts_format),
            ctx=ctx
        )
        await embed.set_page(1)  # Default first page
        await embed.send()

    async def modify_rep(self, member: discord.Member, change: int) -> int:
        """
        Method to modify the reputation points of a given member.
        """

        async with self.bot.pool.acquire() as connection:
            reps = await connection.fetchval("SELECT reps FROM rep WHERE member_id = ($1) AND guild_id = $2", member.id,
                                             member.guild.id)
            if not reps:
                await connection.execute("INSERT INTO rep (reps, member_id, guild_id) VALUES ($1, $2, $3)", change,
                                         member.id, member.guild.id)
            else:
                await self.set_rep(member.id, member.guild.id, reps + change)
                reps = reps + change

        return reps if reps else change

    async def clear_rep(self, user_id: int, guild_id: int) -> None:
        """
        Method to clear the reputation points of a given user in a given guild.
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM rep WHERE member_id = ($1) AND guild_id = $2", user_id, guild_id)

    async def set_rep(self, user_id: int, guild_id: int, reps: int) -> int:
        """
        Method to set the reputation points of a given user in a given guild.
        """

        async with self.bot.pool.acquire() as connection:
            if reps == 0:
                await self.clear_rep(user_id, guild_id)
                return 0
            else:
                await connection.execute("UPDATE rep SET reps = ($1) WHERE member_id = ($2) AND guild_id = $3", reps,
                                         user_id, guild_id)
                new_reps = await connection.fetchval("SELECT reps FROM rep WHERE member_id = ($1) AND guild_id = $2",
                                                     user_id, guild_id)
                if not new_reps:  # User was not already on the rep table, it needs adding
                    await connection.execute("INSERT INTO rep (reps, member_id, guild_id) VALUES ($1, $2, $3)", reps,
                                             user_id, guild_id)
                    new_reps = reps
                return new_reps

    async def award(self, ctx: commands.Context | discord.Interaction, args: discord.Member | discord.User | str = "",
                    member: discord.Member = "") -> None:
        """
        Handler for the award commands.
        """

        is_ctx = type(ctx) is commands.Context
        author = ctx.author if is_ctx else ctx.user

        if args:
            if type(args) == discord.Member:
                user = args
            elif type(args) == discord.User:
                user = ctx.guild.get_member(args.id)
            else:
                # todo: sort this mess out
                user = await self.bot.get_spaced_member(ctx, self.bot,
                                                        args=args) if args else None  # check so rep award doesn't silently fail when no string given
        else:
            user = member

        if not user:
            failed = Embed(title=f":x:  Sorry we could not find the user!" if args else "Rep Help",
                           color=self.bot.ERROR_RED)
            if args:
                failed.add_field(name="Requested user", value=args)

            if is_ctx:
                failed.add_field(name="Information",
                                 value=f"\nTo award rep to someone, type \n`{ctx.prefix}rep Member_Name`\nor\n`{ctx.prefix}rep @Member`\n"
                                       f"Pro tip: If e.g. fred roberto was recently active you can type `{ctx.prefix}rep fred`\n\nTo see the other available rep commands type `{ctx.prefix}help rep`",
                                 inline=False)
            failed.set_footer(
                text=f"Requested by: {author.display_name} ({author})\n" + (self.bot.correct_time()).strftime(
                    self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])

            await ctx.send(embed=failed) if is_ctx else await ctx.response.send_message(embed=failed)
            return
        nick = user.display_name

        if author != user and not user.bot:  # Check prevents self-rep and that receiver is not a bot
            award_banned_role = ctx.guild.get_role(await self.bot.get_config_key(ctx, "rep_award_banned"))
            receive_banned_role = ctx.guild.get_role(await self.bot.get_config_key(ctx, "rep_receive_banned"))
            award_banned = award_banned_role in author.roles
            receive_banned = receive_banned_role in user.roles
            award = not award_banned and not receive_banned
            title = f"You have been blocked from awarding reputation points" if award_banned else ""
            title += " and " if award_banned and receive_banned else "!" if award_banned and not receive_banned else ""
            title += f"{nick} has been blocked from receiving reputation points!" if receive_banned else ""
            title += f"\n\n{nick} did not receive a reputation point!" if not award else ""

            if award:
                reps = await self.modify_rep(user, 1)
                await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx,
                                                                   f"{nick} received a reputation point!",
                                                                   desc=f"{user.mention} now has {reps} reputation points!",
                                                                   thumbnail_url=get_user_avatar_url(user, mode=1)[0])

                # Log rep
                channel_id = await self.bot.get_config_key(ctx, "log_channel")
                if channel_id is None:
                    return
                channel = self.bot.get_channel(channel_id)
                embed = Embed(title="Reputation Points", color=Colour.from_rgb(177, 252, 129))
                embed.add_field(name="From", value=f"{str(author)} ({author.id})")
                embed.add_field(name="To", value=f"{str(user)} ({user.id})")
                embed.add_field(name="New Rep", value=reps)
                embed.add_field(name="Awarded in", value=ctx.channel.mention)
                embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                await channel.send(embed=embed)

            else:  # Rep cannot be given
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, title,
                                                                 desc="Contact a member of staff if you think you are seeing this by mistake.",
                                                                 thumbnail_url=get_user_avatar_url(user, mode=1)[0])

        else:
            desc = "The bot overlords do not accept puny humans' rewards" if user.bot else "You cannot rep yourself, cheating bugger."
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                             f"Failed to award a reputation point to {nick}", desc=desc,
                                                             thumbnail_url=get_user_avatar_url(user, mode=1)[0])

    async def leaderboard(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the leaderboard commands.
        """

        await self.get_leaderboard(ctx)

    async def all(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the all commands. (No this isn't a typo ;) )
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE from rep WHERE guild_id = $1", ctx.guild.id)

        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, "Reputation reset completed!",
                                                           desc=f"All reputation points in {ctx.guild.name} have been removed")

        channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        embed = Embed(title="Reputation Points Reset", color=Colour.from_rgb(177, 252, 129))
        embed.add_field(name="Member", value="**EVERYONE**")
        embed.add_field(name="Staff", value=str(ctx.author if type(ctx) is commands.Context else ctx.user))
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    async def set(self, ctx: commands.Context | discord.Interaction, user: discord.Member | discord.User,
                  rep: str | int) -> None:
        """
        Handler for the set commands.
        """

        if type(rep) is str and not rep.isdigit():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "The reputation points must be a number!")
            return
        new_reps = await self.set_rep(user.id, ctx.guild.id, int(rep))
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx,
                                                           f"{user.display_name}'s reputation points have been changed!",
                                                           desc=f"{user.display_name} now has {new_reps} reputation points!",
                                                           thumbnail_url=get_user_avatar_url(user)[0])

        channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        embed = Embed(title="Reputation Points Set", color=Colour.from_rgb(177, 252, 129))
        embed.add_field(name="Member", value=str(user))
        embed.add_field(name="Staff", value=str(ctx.author if type(ctx) is commands.Context else ctx.user))
        embed.add_field(name="New Rep", value=new_reps)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    async def hardset(self, ctx: commands.Context | discord.Interaction, user_id: str, rep: int | str) -> None:
        """
        Handler for the hardset commands.
        """

        if not user_id.isdigit():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "The user's ID must be a valid ID!")
            return

        if type(rep) is str and not rep.isdigit():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "The reputation points must be a number!")
            return

        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That user does not exist!")
            return

        new_reps = await self.set_rep(int(user_id), ctx.guild.id, int(rep))
        nick = user.display_name if user else user_id
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx,
                                                           f"{nick}'s reputation points have been changed!",
                                                           desc=f"{nick} now has {new_reps} reputation points!")

        channel_id = await self.bot.get_config_key(ctx, "log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        embed = Embed(title="Reputation Points Set (Hard set)", color=Colour.from_rgb(177, 252, 129))
        embed.add_field(name="Member", value=user_id)
        embed.add_field(name="Staff", value=str(ctx.author if type(ctx) is commands.Context else ctx.user))
        embed.add_field(name="New Rep", value=new_reps)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    async def check(self, ctx: commands.Context | discord.Interaction, args: str = "",
                    member: discord.Member | discord.User = "") -> None:
        """
        Handler for the check commands.
        """

        is_ctx = type(ctx) is commands.Context

        author = ctx.author if is_ctx else ctx.user
        if not args:
            user = author if not member else member
        else:
            user = await self.bot.get_spaced_member(ctx, self.bot, args=args)
            if user is None:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "We could not find that user!")
                return

        rep = None
        lb_pos = None
        async with self.bot.pool.acquire() as connection:
            all_rep = await connection.fetch("SELECT member_id, reps FROM rep WHERE guild_id = $1 ORDER by reps DESC;",
                                             ctx.guild.id)
            all_rep = [x for x in all_rep if ctx.channel.guild.get_member(x[0]) is not None]
            member_record = next((x for x in all_rep if x[0] == user.id), None)
            if member_record:  # If the user actually has reps
                rep = member_record[1]  # Check member ID and then get reps
                prev = 0
                lb_pos = 0
                for record in all_rep:
                    if record[1] != prev:
                        lb_pos += 1
                        prev = record[1]  # Else, increase the rank
                    if record[0] == user.id:
                        break  # End loop if reached the user

        if not rep:
            rep = 0
        embed = Embed(title=f"Rep info for {user.display_name} ({user})", color=Colour.from_rgb(139, 0, 139))
        # could change to user.colour at some point, I prefer the purple for now though
        embed.add_field(name="Rep points", value=rep)
        embed.add_field(name="Leaderboard position", value=self.bot.ordinal(lb_pos) if lb_pos else "Nowhere :(")
        embed.set_footer(text=f"Requested by {author.display_name} ({author})\n" + self.bot.correct_time().strftime(
            self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])
        embed.set_thumbnail(url=get_user_avatar_url(user, mode=1)[0])

        await ctx.send(embed=embed) if is_ctx else await ctx.response.send_message(embed=embed)

    async def data(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the data commands.
        """

        async with self.bot.pool.acquire() as connection:
            vals = await connection.fetch(
                "SELECT DISTINCT reps, COUNT(member_id) FROM rep WHERE reps > 0 AND guild_id = $1 GROUP BY reps ORDER BY reps",
                ctx.guild.id)

        fig, ax = plt.subplots()
        ax.plot([x[0] for x in vals], [x[1] for x in vals], "b-o", linewidth=0.5, markersize=1)
        ax.set(xlabel="Reputation points (rep)", ylabel="Frequency (reps)", title="Rep frequency graph")
        ax.grid()
        ax.set_ylim(bottom=0)

        await self.bot.send_image_file(ctx, fig, ctx.channel, "rep-data")
