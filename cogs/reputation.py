import discord
from discord.ext import commands
#from discord.ext.commands import MemberConverter, UserConverter
from discord.utils import get
from discord import Embed, Colour
from .utils import ordinal, Embed, EmbedPages, PageTypes, send_file, get_spaced_member
import matplotlib.pyplot as plt

class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_leaderboard(self, ctx, only_members = False):
        leaderboard = []
        async with self.bot.pool.acquire() as connection:
            leaderboard = await connection.fetch('SELECT * FROM rep WHERE guild_id = $1 ORDER BY reps DESC', ctx.guild.id)

        if len(leaderboard) == 0:
            await ctx.send("There are no rep points in this guild yet :sob:")
            return

        embed = EmbedPages(PageTypes.REP, leaderboard, "Reputation Leaderboard", Colour.from_rgb(177,252,129), self.bot, ctx.author, ctx.channel)
        await embed.set_page(1) # Default first page
        await embed.send()

    async def modify_rep(self, member, change):
        reps = change
        async with self.bot.pool.acquire() as connection:
            reps = await connection.fetchval("SELECT reps FROM rep WHERE member_id = ($1) AND guild_id = $2", member.id, member.guild.id)
            if not reps:
                await connection.execute('INSERT INTO rep (reps, member_id, guild_id) VALUES ($1, $2, $3)', change, member.id, member.guild.id)
            else:
                await self.set_rep(member.id, member.guild.id, reps+change)
                reps = reps + change

        return (reps if reps else change)
    
    async def clear_rep(self, user_id, guild_id):
        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM rep WHERE member_id = ($1) AND guild_id = $2", user_id, guild_id)

    async def set_rep(self, user_id, guild_id, reps):
        async with self.bot.pool.acquire() as connection:
            if reps == 0:
                await self.clear_rep(user_id, guild_id)
                return 0
            else:
                await connection.execute("UPDATE rep SET reps = ($1) WHERE member_id = ($2) AND guild_id = $3", reps, user_id, guild_id)
                new_reps = await connection.fetchval("SELECT reps FROM rep WHERE member_id = ($1) AND guild_id = $2", user_id, guild_id)
                if not new_reps: # User was not already on the rep table, it needs adding
                    await connection.execute("INSERT INTO rep (reps, member_id, guild_id) VALUES ($1, $2, $3)", reps, user_id, guild_id)
                    new_reps = reps
                return new_reps

#-----------------------REP COMMANDS------------------------------

    @commands.group()
    @commands.guild_only()
    async def rep(self, ctx):
        """Reputation module"""
        subcommands = []
        award_commands = ["award"] + [alias for alias in self.rep.get_command("award").aliases]
        for command in self.rep.walk_commands():
            subcommands.append(command.name)
            for alias in command.aliases:
                subcommands.append(alias)

        await self.bot.add_config(ctx.guild.id)
        p = self.bot.configs[ctx.guild.id]["prefix"]
        if ctx.subcommand_passed not in subcommands:
            args = ctx.message.content.replace(f"{p}rep", "").strip()
            await ctx.invoke(self.rep.get_command("award"), args)
        if ctx.subcommand_passed in award_commands:
            await ctx.send(f"*You can now use {p}rep user rather than needing {p}rep award!*")
            
    @rep.error
    async def rep_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You cannot award rep in this server!")
        else:
            await ctx.send(error)#"Oopsies something went wrong with that!")

    @rep.command(aliases=['give', 'point'])
    @commands.guild_only()
    async def award(self, ctx, *args):
        """Gives the member a reputation point. Aliases are give and point"""
        args_ = " ".join(args)
        author_nick = ctx.author.display_name
        if args_:  # check so rep award doesn't silently fail when no string given
            user = await get_spaced_member(ctx, self.bot, *args)
        else:
            user = None
        if not user:
            failed = Embed(title=f':x:  Sorry we could not find the user!' if args_ else 'Rep Help', color=Colour.from_rgb(255, 7, 58))
            if args_:
                failed.add_field(name="Requested user", value=args_)

            await self.bot.add_config(ctx.guild.id)
            p = self.bot.configs[ctx.guild.id]["prefix"]
            failed.add_field(name="Information", value=f'\nTo award rep to someone, type \n`{p}rep Member_Name`\nor\n`{p}rep @Member`\n'
                             f'Pro tip: If e.g. fred roberto was recently active you can type `{p}rep fred`\n\nTo see the other available rep commands type `{p}help rep`', inline=False)
            failed.set_footer(text=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + (
                    self.bot.correct_time()).strftime(self.bot.ts_format), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=failed)
            return
        nick = user.display_name

        if ctx.author != user and not user.bot:  # check to not rep yourself and that user is not a bot
            title = ":x: "
            color = Colour.from_rgb(57, 255, 20)
            award = True
            if "Rep Award Banned" in [str(role) for role in ctx.author.roles]:
                color = Colour.from_rgb(172, 32, 31)
                title += f'You have been blocked from awarding reputation!\n{nick} did not receive a reputation point!'
                award = False

            if "Rep Receive Banned" in [str(role) for role in user.roles]:
                color = Colour.from_rgb(172, 32, 31)
                title += ('\n:x: ' if title != ':x: ' else '') + f'{nick} has been blocked from receiving reputation points!'
                award = False

            if award:
                title = f':white_check_mark:  {nick} received a reputation point!'

            user_embed = Embed(title=title, color=color)

            if award:
                reps = await self.modify_rep(user, 1)
                user_embed.add_field(name='_ _', value=f'{user.mention} now has {reps} reputation points!')
            else:
                user_embed.add_field(name='_ _', value='Contact a member of staff if you think you are seeing this by mistake.')
            user_embed.set_thumbnail(url=user.avatar_url)
            user_embed.set_footer(text=("Awarded" if award else "Requested") + f" by: {author_nick} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=user_embed)
            if award:
                await self.bot.add_config(ctx.guild.id)
                channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
                if channel_id is None:
                    return
                channel = self.bot.get_channel(channel_id)

                embed = Embed(title='Reputation Points', color=Colour.from_rgb(177, 252, 129))
                embed.add_field(name='From', value=f'{str(ctx.author)} ({ctx.author.id})')
                embed.add_field(name='To', value=f'{str(user)} ({user.id})')
                embed.add_field(name='New Rep', value=reps)
                embed.add_field(name='Awarded in', value=ctx.channel.mention)
                embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                await channel.send(embed=embed)

        else:
            if user.bot:
                fail_text = "The bot overlords do not accept puny humans' rewards"
            else:
                fail_text = "You cannot rep yourself, cheating bugger."
            embed = Embed(title=f':x: Failed to award a reputation point to {nick}!', color=Colour.from_rgb(255,7,58))
            embed.add_field(name='_ _', value=fail_text)
            embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
            embed.set_thumbnail(url=user.avatar_url)
            await ctx.send(embed=embed)

    @rep.command(aliases=['lb'])
    @commands.guild_only()
    async def leaderboard(self, ctx, modifier=''):
        """Displays the leaderboard of reputation points, if [modifier] is 'members' then it only shows current server members"""
        if modifier.lower() in ['members', 'member']:
            await self.get_leaderboard(ctx, only_members=True)
        else:
            await self.get_leaderboard(ctx, only_members=False)

        #await ctx.send(embed=lb)

    @rep.group()
    @commands.guild_only()
    async def reset(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.bot.add_config(ctx.guild.id)
            p = self.bot.configs[ctx.guild.id]["prefix"]
            await ctx.send(f'```{p}rep reset member @Member``` or ```{p}rep reset all```')

    @reset.command()
    @commands.guild_only()
    async def member(self, ctx, user_id):
        """Resets a single users reps."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to reset a member's rep points :sob:")
            return

        user = await self.bot.fetch_user(user_id)
        await self.clear_rep(user.id, ctx.guild.id)
        await ctx.send(f'{user.mention} now has 0 points.')

        await self.bot.add_config(ctx.guild.id)
        channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        embed = Embed(title='Reputation Points Reset', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=str(user))
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    @reset.command(pass_context=True)
    @commands.guild_only()
    async def all(self, ctx):
        """Resets everyones reps."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to reset everyone's rep points :sob:")
            return

        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE from rep WHERE guild_id = $1", ctx.guild.id)

        await ctx.send('Done. Everyone now has 0 points.')

        await self.bot.add_config(ctx.guild.id)
        channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        embed = Embed(title='Reputation Points Reset', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value='**EVERYONE**')
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    @rep.command()
    @commands.guild_only()
    async def set(self, ctx, user: discord.User, rep):
        """Sets a specific members reps to a given value."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to set a member's rep points :sob:")
            return

        try:
            rep = int(rep)
        except ValueError:
            await ctx.send('The rep must be a number!')
            return

        #user = await self.bot.fetch_user(user_id)

        new_reps = await self.set_rep(user.id, ctx.guild.id, rep)
        await ctx.send(f'{user.mention} now has {new_reps} reputation points.')

        await self.bot.add_config(ctx.guild.id)
        channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        embed = Embed(title='Reputation Points Set', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=str(user))
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.add_field(name='New Rep', value=new_reps)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    @rep.command()
    @commands.guild_only()
    async def hardset(self, ctx, user_id, rep):
        """Sets a specific member's reps to a given value via their ID."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to hardset a member's rep points :sob:")
            return

        try:
            rep = int(rep)
        except ValueError:
            await ctx.send('The rep must be a number!')
            return

        new_reps = await self.set_rep(int(user_id), ctx.guild_id, rep)
        await ctx.send(f'{user_id} now has {new_reps} reputation points.')

        await self.bot.add_config(ctx.guild.id)
        channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        embed = Embed(title='Reputation Points Set (Hard set)', color=Colour.from_rgb(177,252,129))
        embed.add_field(name='Member', value=user_id)
        embed.add_field(name='Staff', value=str(ctx.author))
        embed.add_field(name='New Rep', value=new_reps)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    @rep.command()
    @commands.guild_only()
    async def check(self, ctx, *args):
        """Checks a specific person reps, or your own if user is left blank"""
        if len(args) == 0:
            user = ctx.author
        else:
            user = await get_spaced_member(ctx, self.bot, *args)
            if user is None:
                await ctx.send(embed=Embed(title=f':x:  Sorry {ctx.author.display_name} we could not find that user!', color=Colour.from_rgb(255, 7, 58)))
                return

        rep = None
        lb_pos = None
        async with self.bot.pool.acquire() as connection:
            all_rep = await connection.fetch("SELECT * FROM rep WHERE guild_id = $1 ORDER by reps DESC;", ctx.guild.id)
            all_rep = [x for x in all_rep if ctx.channel.guild.get_member(x[0]) is not None]
            member_record = next((x for x in all_rep if x[0] == user.id), None)
            if member_record: # If the user actually has reps
                rep = member_record[1] # Check member ID and then get reps
                prev = 0
                lb_pos = 0
                for record in all_rep:
                    if record[1] != prev:
                        lb_pos += 1
                        prev = record[1] # Else, increase the rank
                    if record[0] == user.id:
                        break # End loop if reached the user

        if not rep:
            rep = 0
        embed = Embed(title=f'Rep info for {user.display_name} ({user})', color=Colour.from_rgb(139, 0, 139))
        # could change to user.colour at some point, I prefer the purple for now though
        embed.add_field(name='Rep points', value=rep)
        embed.add_field(name='Leaderboard position', value=ordinal(lb_pos) if lb_pos else 'Nowhere :(')
        embed.set_footer(text=f"Requested by {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(self.bot.ts_format), icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)
        #await ctx.send(f'{user.mention} {f"is **{ordinal(lb_pos)}** on the reputation leaderboard with" if lb_pos else "has"} **{rep}** reputation points. {"They are not yet on the leaderboard because they have no reputation points." if (not lb_pos or rep == 0) else ""}')


    @rep.command()
    @commands.guild_only()
    async def data(self, ctx):
        vals = []
        async with self.bot.pool.acquire() as connection:
            vals = await connection.fetch("SELECT DISTINCT reps, COUNT(member_id) FROM rep WHERE reps > 0 AND guild_id = $1 GROUP BY reps ORDER BY reps", ctx.guild.id)

        fig, ax = plt.subplots()
        ax.plot([x[0] for x in vals], [x[1] for x in vals], 'b-o', linewidth=0.5, markersize=1)
        ax.set(xlabel='Reputation points (rep)', ylabel='Frequency (reps)', title='Rep frequency graph')
        ax.grid()
        ax.set_ylim(bottom=0)

        await send_file(fig, ctx.channel, "rep-data")

def setup(bot):
    bot.add_cog(Reputation(bot))
