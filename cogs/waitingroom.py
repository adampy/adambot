import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
from .utils import Permissions, CHANNELS
import re
import asyncio
import datetime # For handling lurker_kick

class WaitingRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_message = ""
        self.welcome_channel = None
    
    async def get_parsed_welcome_message(self, welcome_msg, new_user: discord.User, guild: discord.Guild):
        """Method that gets the parsed welcome message, with channel and role mentions."""
        to_send = welcome_msg
        to_send = to_send.replace("<user>", new_user.mention)
        
        while True:
            channel_regex = re.search(r'(?<=C\<).+?(?=\>)', to_send)
            if not channel_regex:
                break
            match = channel_regex.group(0)
            channel = await self.bot.fetch_channel(int(match))
            to_send = to_send.replace(f"C<{match}>", channel.mention)
        
        while True:
            role_regex = re.search(r'(?<=R\<).+?(?=\>)', to_send)
            if not role_regex:
                break
            match = role_regex.group(0)
            role = guild.get_role(int(match))
            to_send = to_send.replace(f"R<{match}>", role.mention)

        return to_send

    @commands.Cog.listener()
    async def on_member_join(self, member):
        #formatting stuffs
        guild = member.guild

        config = self.bot.configs[guild.id]
        raw_msg = config["welcome_msg"]
        channel_id = config["welcome_channel"]
        if raw_msg and channel_id:
            message = await self.get_parsed_welcome_message(raw_msg, member, guild)
            channel = self.bot.get_channel(channel_id)
            await channel.send(message)


    #-----WELCOME MESSAGE TEST-----

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def testwelcome(self, ctx, to_ping: discord.User = None):
        """Command that returns the welcome message, and pretends the command invoker is the new user."""
        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to test the welcome message.")
            return


        msg = self.bot.configs[ctx.guild.id]["welcome_msg"]
        if msg == None:
            await ctx.send("A welcome message has not been set.")
            return
            
        msg = await self.get_parsed_welcome_message(msg, to_ping or ctx.author, ctx.guild) # to_ping or author means the author unless to_ping is provided.
        await ctx.send(msg)

    #-----YEAR COMMANDS-----

    YEARS = {"y9":"Y9", "y10":"Y10", "y11": "Y11", "postgcse":"Post-GCSE", "mature":"Mature Student"} # dict of command aliases:role names, perhaps move to cogs.utils?
    @commands.command(pass_context=True,
                      aliases=[*YEARS],
                      help="Verifies members into the server. Use e.g. -y9 to verify members")
    @commands.has_any_role(*Permissions.STAFF)
    async def verify(self, ctx, member: discord.Member = None):
        """
        When a Year role is specified, the specified user is given that role.
        This is done by looking up the alias used in the YEARS dictionary to get the corresponding role
        Using `verify` shows the specified help message, it's just a dummy to allow the aliases
        """

        if ctx.invoked_with == "verify" or not ctx.invoked_with:
            await ctx.send(f"```{self.verify.help}```")
            return

        if not member:
            if not ctx.message.reference:
                await ctx.send("Specify a user to verify!")
                return
            ref = await ctx.fetch_message(ctx.message.reference.message_id)
            member = ref.author

        year_roles = [get(member.guild.roles, name=self.YEARS[role]) for role in self.YEARS]
        pre_existing_roles = [r for r in year_roles if r in member.roles]
        await member.remove_roles(*year_roles)
        name = self.YEARS[ctx.invoked_with]
        await member.add_roles(*[get(member.guild.roles, name="Members"), get(member.guild.roles, name=name)])
        await ctx.send(f"{member.mention} has been verified!")
        if not pre_existing_roles: # If the user hadn't already been verified
            get_role_channel = self.bot.get_channel(854148889409617920) # Get role channel
            await self.bot.get_channel(CHANNELS["general"]).send(f'Welcome {member.mention} to the server :wave: Take a look in {get_role_channel.mention} for additional roles!') # TODO: GCSE9-1 specific - sort it out!

    @commands.group(aliases=['lurker'])
    @commands.has_any_role(*Permissions.STAFF)
    async def lurkers(self, ctx):
        if ctx.invoked_subcommand is None:
            members = [x for x in ctx.guild.members if len(x.roles) <= 1] # Only the everyone role
            message = ""
            for member in members:
                if len(message) + len(member.mention) + len(' please tell us your year to be verified into the server!') >= 2000:
                    await ctx.send(message + ' please tell us your year to be verified into the server!')
                    message = ""
                else:
                    message += member.mention
            
            if message != "": # There is still members to be mentioned
                await ctx.send(message + ' please tell us your year to be verified into the server!')

            question = await ctx.send("Do you want me to send DMs to all lurkers, to try and get them to join? (Type either 'yes' or 'no')")
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                response = await self.bot.wait_for("message", check = check, timeout = 300)
            except asyncio.TimeoutError:
                await question.delete()
                return
            if response.content.lower() == "yes":
                for i in range(len(members)):
                    member = members[i]

                    await question.edit(content = f"DMs have been sent to {i}/{len(members)} lurkers :ok_hand:")

                    try:
                        await member.send(f"If you are wanting to join the {ctx.guild.name} server then please tell us your year in the waiting room. Thanks!")
                    except discord.Forbidden: # Catches if DMs are closed
                        pass
                    except discord.HTTPException:
                        pass

                await question.edit(content = "DMs have been sent to all lurkers :ok_hand:")
            
            elif response.content.lower() == "no":
                await question.edit(content = "No DMs have been sent to lurkers :ok_hand:")

            else:
                await question.edit(content = "Unknown response, therefore no DMs have been sent to lurkers :ok_hand:")

    @lurkers.command(pass_context = True, name = "kick") # Name parameter defines the name of the command the user will use
    @commands.guild_only()
    async def lurker_kick(self, ctx, days="7"):
        # days is specifically "7" as default and not 7 since if you specify an integer it barfs if you supply a non-int value
        """Command that kicks people without a role, and joined 7 or more days ago."""
        def check(m):
            return m.channel == ctx.channel and m.author == ctx.author
        if not days.isnumeric():
            await ctx.send("Specify a whole, non-zero number of days!")
            return
        days = int(days)
        time_ago = datetime.datetime.now() - datetime.timedelta(days=days)
        ## NOTE THAT x.joined_at will be in the timezone of the system by default, so no messing around needed here
        members = [x for x in ctx.guild.members if len(x.roles) <= 1 and x.joined_at < time_ago] # Members with only the everyone role and more than 7 days ago
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
        embed.set_thumbnail(url=ctx.author.avatar_url)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(WaitingRoom(bot))
