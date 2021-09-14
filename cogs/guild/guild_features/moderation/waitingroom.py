import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import asyncio
import datetime


class WaitingRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_message = ""
        self.welcome_channel = None
    
    async def get_parsed_welcome_message(self, welcome_msg, new_user: discord.User):
        """
        Method that gets the parsed welcome message, with channel and role mentions.
        """

        return welcome_msg.replace("<user>", new_user.mention)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = self.bot.configs[member.guild.id]
        raw_msg = config["welcome_msg"]
        channel_id = config["welcome_channel"]

        if raw_msg and channel_id:
            message = await self.get_parsed_welcome_message(raw_msg, member)
            channel = self.bot.get_channel(channel_id)
            await channel.send(message)

    # -----WELCOME MESSAGE TEST-----

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def testwelcome(self, ctx, to_ping: discord.User = None):
        """
        Command that returns the welcome message, and pretends the command invoker is the new user.
        """

        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to test the welcome message.")
            return

        msg = self.bot.configs[ctx.guild.id]["welcome_msg"]
        if msg is None:
            await ctx.send("A welcome message has not been set.")
            return
            
        msg = await self.get_parsed_welcome_message(msg, to_ping or ctx.author)  # to_ping or author means the author unless to_ping is provided.
        await ctx.send(msg)

    # -----LURKERS-----

    @commands.group(aliases=['lurker'])
    async def lurkers(self, ctx, *phrase):
        """
        Ping all the people without a role so you can grab their attention. Optional, first argument is `message` is the phrase you want to send to lurkers.
        """
        if not await self.bot.is_staff(ctx):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        # Get default phrase if there is one, but the one given in the command overrides the config one
        config_phrase = self.bot.configs[ctx.guild.id]["lurker_phrase"]
        show_tip = False
        if phrase: # Handle subcommand
            # If phrase is given and a default hasn't yet been set, show a tip on setting defaults
            show_tip = True if config_phrase is None else False
            if phrase[0] == "kick":
                try:
                    days = phrase[1]
                except IndexError:
                    days = "7"
                await ctx.invoke(self.bot.get_command("lurker kick"), days)
                return

        phrase = " ".join(phrase) if phrase else config_phrase
        if ctx.invoked_subcommand is None:
            members = [x for x in ctx.guild.members if len(x.roles) <= 1]  # Only the everyone role
            message = ""
            for member in members:
                if len(message + member.mention) >= 2000:
                    await ctx.send(message + " " + phrase)
                    message = ""
                
                message += member.mention
            
            if message != "":  # There is still members to be mentioned
                await ctx.send(message + " " + phrase)

            question = await ctx.send("Do you want me to send DMs to all lurkers? (Type either 'yes' or 'no')")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

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

                await question.edit(content="DMs have been sent to all lurkers :ok_hand:")
            
            elif response.content.lower() == "no":
                await question.edit(content="No DMs have been sent to lurkers :ok_hand:")

            else:
                await question.edit(content="Unknown response, therefore no DMs have been sent to lurkers :ok_hand:")

            if show_tip:
                await ctx.send(f"""To save time, you can provide a default message to be displayed on the lurker command, i.e. you don't need to type out the phrase each time. 
You can set this by doing `{ctx.prefix}config set lurker_phrase {phrase}`""")

    @lurkers.command(pass_context=True, name="kick")  # Name parameter defines the name of the command the user will use
    @commands.guild_only()
    async def lurker_kick(self, ctx, days="7"):
        # days is specifically "7" as default and not 7 since if you specify an integer it barfs if you supply a non-int value
        """
        Command that kicks people without a role, and joined 7 or more days ago.
        """

        if not await self.bot.is_staff(ctx):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return
        
        def check(m):
            return m.channel == ctx.channel and m.author == ctx.author
        if not days.isnumeric():
            await ctx.send("Specify a whole, non-zero number of days!")
            return
        days = int(days)
        time_ago = datetime.datetime.now() - datetime.timedelta(days=days)
        # NOTE THAT x.joined_at will be in the timezone of the system by default, so no messing around needed here
        members = [x for x in ctx.guild.members if len(x.roles) <= 1 and x.joined_at < time_ago]  # Members with only the everyone role and more than 7 days ago
        if len(members) == 0:
            await ctx.send(f"There are no lurkers to kick that have been here {days} days or longer!")
            return
        question = await ctx.send(f"Do you want me to kick all lurkers that have been here {days} days or longer ({len(members)} members)? (Type either 'yes' or 'no')")
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

            await question.edit(content=f"All {len(members)} lurkers that have been here more than {days} days have been kicked :ok_hand:")
        
        elif response.content.lower() == "no":
            await question.edit(content="No lurkers have been kicked :ok_hand:")

        else:
            await question.edit(content="Unknown response, therefore no lurkers have been kicked :ok_hand:")

        channel_id = self.bot.configs[ctx.guild.id]["mod_log_channel"]
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        embed = Embed(title='Lurker-kick', color=Colour.from_rgb(220, 123, 28))
        embed.add_field(name='Members', value=str(len(members)))
        embed.add_field(name='Reason', value='Auto-kicked from the -lurkers kick command')
        embed.add_field(name='Initiator', value=ctx.author.mention)
        embed.set_thumbnail(url=ctx.author.avatar.url)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)


def setup(bot):
    bot.add_cog(WaitingRoom(bot))
