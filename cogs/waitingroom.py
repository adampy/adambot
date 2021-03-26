import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import os
import asyncpg
from .utils import Permissions, CHANNELS, GCSE_SERVER_ID
import re
import asyncio
import datetime # For handling lurker_kick

class WaitingRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_message = ""
        self.welcome_channel = None
    
    async def _get_welcome_message(self):
        """Internal method that retreives the welcome message from the DB."""
        to_return = ""
        async with self.bot.pool.acquire() as connection:
            to_return = await connection.fetchval("SELECT value FROM variables WHERE variable = 'welcome_msg';")
        return to_return

    async def _set_welcome_message(self, new_welcome):
        """Internal method that sets the welcome message in the DB."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute("UPDATE variables SET value = ($1) WHERE variable = 'welcome_msg';", new_welcome)

    async def _get_welcome_channel(self):
        """Internal method that retreives the welcome channel from the DB."""
        channel_id = 0
        async with self.bot.pool.acquire() as connection:
            channel_id = await connection.fetchval("SELECT value FROM variables WHERE variable = 'welcome_channel';")
        return int(channel_id)

    async def _set_welcome_channel(self, channel_id):
        """Internal method that sets the welcome channel in the DB."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute("UPDATE variables SET value = ($1) WHERE variable = 'welcome_channel';", str(channel_id))
        
    async def get_parsed_welcome_message(self, new_user: discord.User, guild: discord.Guild):
        """Method that gets the parsed welcome message, with channel and role mentions."""
        to_send = self.welcome_message
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
    async def on_ready(self):
        await asyncio.sleep(1)

        # Get welcome message and parse it
        self.welcome_message = await self._get_welcome_message()

        # Get channel id and parse it
        channel_id = await self._get_welcome_channel()
        self.welcome_channel = await self.bot.fetch_channel(channel_id)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        #formatting stuffs
        guild = self.bot.get_guild(GCSE_SERVER_ID)
        message = await self.get_parsed_welcome_message(member, guild)
        await self.welcome_channel.send(message)

        #invite stuffs
        old_invites = []
        async with self.bot.pool.acquire() as connection:
            old_invites = await connection.fetch('SELECT * FROM invites')
        invites = await guild.invites()
        invite_data = None # Holds the invite used
        
        #for each new invite find the old one - if not avaliable then that invite is the one
        seen_invites = []
        breakloop = False
        for new_invite in invites:
            if breakloop:
                break
            seen_invites.append(new_invite)
            #find old invite
            for old_invite in old_invites:
                if new_invite.code == old_invite[1]: #same codes
                    if new_invite.uses - 1 == old_invite[2]: #uses correlate
                        invite_data = new_invite
                        breakloop = True
                        break

        #staff embed
        date = member.joined_at - member.created_at
        day_warning = False
        if date.days < 7:
            day_warning = True
        
        if invite_data:
            embed = Embed(title='Invite data', color=Colour.from_rgb(76, 176, 80))
            embed.add_field(name='Member', value=member.mention)
            embed.add_field(name='Inviter', value=invite_data.inviter.mention)
            embed.add_field(name='Code', value=invite_data.code)
            embed.add_field(name='Uses', value=invite_data.uses)
            embed.add_field(name='Invite created', value=invite_data.created_at.strftime('%H:%M on %d/%m/%y'))
            embed.add_field(name='Account created', value=member.created_at.strftime('%H:%M on %d/%m/%y'))
            embed.set_thumbnail(url=member.avatar_url)
            await get(guild.text_channels, name='invite-logs').send(f'{member.mention}\'s account is **less than 7 days old.**' if day_warning else '', embed=embed)
        else:
            new_invite_codes = [inv.code for inv in invites]
            for old_invite in old_invites:
                if old_invite[1] not in new_invite_codes: # If the an old invite code is not in the new invites, then it must have been used
                    invite_data = old_invite
                    break

            if invite_data:
                # Get inviter
                inviter = self.bot.get_user(invite_data[0])
                if not inviter:
                    inviter = await self.bot.fetch_user(invite_data[0])
                
                embed = Embed(title='Invite data', color=Colour.from_rgb(76, 176, 80))
                embed.add_field(name='Member', value=member.mention)
                embed.add_field(name='Inviter', value=inviter.mention)
                embed.add_field(name='Code', value=invite_data[1])
                embed.add_field(name='Uses', value="This was a single-use invite (1/1 uses)")
                embed.add_field(name='Invite created', value=invite_data[4].strftime('%H:%M on %d/%m/%y'))
                embed.add_field(name='Account created', value=member.created_at.strftime('%H:%M on %d/%m/%y'))
                embed.set_thumbnail(url=member.avatar_url)
                await get(guild.text_channels, name='invite-logs').send(f'**Single-use-invite used.**{member.mention}\'s account is **less than 7 days old.**' if day_warning else '**Single-use-invite used.**', embed=embed)
            else:
                await get(guild.text_channels, name='invite-logs').send(f"No invite data available for {member.mention} even after checking the single-use invites.")

        #reset invites
        to_insert = []
        for invite in invites:
            data = [invite.inviter.id,
                    invite.code,
                    invite.uses,
                    invite.max_uses,
                    invite.created_at,
                    invite.max_age]
            to_insert.append(data)

        async with self.bot.pool.acquire() as connection:
            await connection.execute('DELETE FROM invites')
            await connection.executemany('INSERT INTO invites (inviter, code, uses, max_uses, created_at, max_age) values ($1, $2, $3, $4, $5, $6)', to_insert)

    #-----WELCOME MESSAGE-----

    @commands.group()
    @commands.has_any_role(*Permissions.MOD)
    async def editwelcome(self, ctx):
        """Edit the welcome message and/or channel"""
        if ctx.invoked_subcommand is None:
            await ctx.send('```-editwelcome message [message...]``` or ```-editwelcome channel <text_channel>```')
            return

    @editwelcome.command(pass_context=True)
    @commands.has_any_role(*Permissions.MOD)
    async def testmessage(self, ctx, to_ping: discord.User = None):
        """Command that returns the welcome message, and pretends the command invoker is the new user."""
        msg = await self.get_parsed_welcome_message(to_ping or ctx.author, ctx.guild) # to_ping or author means the author unless to_ping is provided.
        await ctx.send(msg)

    @editwelcome.command(pass_context=True)
    @commands.has_any_role(*Permissions.MOD)
    async def message(self, ctx, *message):
        """Changes the welcome message. Moderator+ role needed.
Do <user> to ping the new member.
Do R<role_name> to ping a role.
Do C<channel_name> to mention a channel."""
        author = ctx.author
        channel = ctx.channel
        def check(m):
            return m.channel == channel and m.author == author
        
        if not message:
            await ctx.send(f"The current welcome message is:\n```{self.welcome_message}```\nPlease type you new welcome message. (Type 'no' to cancel)")
        else:
            message = ' '.join(message)
            await ctx.send(f"The current welcome message is:\n```{self.welcome_message}```\n")
            await ctx.send(f"Are you sure you want to change it to:\n```{message}```\n(Type 'yes' to change it, and 'no' to cancel)")

        try:
            response = await self.bot.wait_for('message', check=check, timeout=300)
        except asyncio.TimeoutError:
            await ctx.send("Editing timed-out, please try again.")
            return

        if response.content.lower() == "no":
            await ctx.send("Editing cancelled :ok_hand:")
            return
        if message and response.content.lower() != "yes":
            await ctx.send("Unknown response, please try again.")
            return

        # If the message was provided to begin with, move that to `response`
        if not message:
            message = response.content

        if len(message) > 1000:
            await ctx.send("Your welcome message is bigger than the limit (1000 chars). Please shorten it and try again.")
            return
        
        await self._set_welcome_message(message)
        self.welcome_message = message
        await ctx.send("The welcome message has been updated :ok_hand:")

    @editwelcome.command(pass_context=True)
    @commands.has_any_role(*Permissions.MOD)
    async def channel(self, ctx, channel: discord.TextChannel = None):
        """Changes the welcome channel. Moderator+ role needed."""
        command_channel = ctx.channel
        author = ctx.author
        def check(m):
            return m.channel == command_channel and m.author == author

        if channel:
            await ctx.send(f"The current welcome channel is:\n{self.welcome_channel.mention}\nAre you sure you want to change it to {channel.mention}? (Type 'yes' to change, or 'no' to cancel this change)")
        else:
            await ctx.send(f"The current welcome channel is:\n{self.welcome_channel.mention}\nPlease type the channel ID of the new welcome channel. (Type 'no' to cancel)")

        try:
            response = await self.bot.wait_for('message', check=check, timeout=300)
        except asyncio.TimeoutError:
            await ctx.send("Editing timed-out, please try again.")
            return

        if response.content.lower() == "no":
            await ctx.send("Editing cancelled :ok_hand:")
            return

        # Channel already given, and approved
        if channel and response.content.lower() != "yes":
            await ctx.send("Unknown response, please try again.")
        
        # Channel not given, parse it
        if not channel:
            try:
                channel = await self.bot.fetch_channel(int(response.content))
            except discord.NotFound:
                await ctx.send("No channel with that ID found, please try again.")
                return
            except discord.Forbidden:
                await ctx.send("Adam-Bot does not have permissions to access that channel, please try again.")
                return
            except Exception as e:
                await ctx.send(f"Something went wrong: {e}, please try again.")
                return

        # Check adambot can write here
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send("Adam-Bot does not have permissions to access that channel, please try again.")
            return

        await self._set_welcome_channel(channel.id)
        self.welcome_channel = channel
        await ctx.send(f"The welcome channel has been updated to {channel.mention} :ok_hand:")


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
        Using -verify shows the specified help message, it's just a dummy to allow the aliases
        """
        content = ctx.message.content
        if content[1:].startswith("verify"): # assuming message is invoker. TODO: if external use case arises, tweak this
            await ctx.send(f"```{self.verify.help}```")
            return
        if member is None:
            await ctx.send("Specify a user to verify!")
            return

        year_roles = [get(member.guild.roles, name=self.YEARS[role]) for role in self.YEARS]
        pre_existing_roles = [r for r in year_roles if r in member.roles]
        await member.remove_roles(*year_roles)
        await member.add_roles(*[get(member.guild.roles, name="Members"), get(member.guild.roles, name=self.YEARS[content[:content.index(" ")].replace("-", "")])])
        await ctx.send(f"{member.mention} has been verified!")
        if not pre_existing_roles: # If the user hadn't already been verified
            await self.bot.get_channel(CHANNELS["general"]).send(f'Welcome {member.mention} to the server :wave:')

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
                        await member.send("If you are wanting to join the GCSE 9-1 server then please tell us your year in the waiting room. Thanks!")
                    except discord.Forbidden: # Catches if DMs are closed
                        pass

                await question.edit(content = "DMs have been sent to all lurkers :ok_hand:")
            
            elif response.content.lower() == "no":
                await question.edit(content = "No DMs have been sent to lurkers :ok_hand:")

            else:
                await question.edit(content = "Unknown response, therefore no DMs have been sent to lurkers :ok_hand:")

    @lurkers.command(pass_context = True, name = "kick") # Name parameter defines the name of the command the user will use
    @commands.guild_only()
    async def lurker_kick(self, ctx):
        """Command that kicks people without a role, and joined 7 or more days ago."""
        def check(m):
            return m.channel == ctx.channel and m.author == ctx.author

        week_ago = datetime.datetime.utcnow() - datetime.timedelta(days = 7)
        members = [x for x in ctx.guild.members if len(x.roles) <= 1 and x.joined_at < week_ago] # Members with only the everyone role and more than 7 days ago
        
        question = await ctx.send("Do you want me to kick all lurkers that've been here 7 days or longer? (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check = check, timeout = 300)
        except asyncio.TimeoutError:
            await question.delete()
            return

        if response.content.lower() == "yes":
            for i in range(len(members)):
                member = members[i]

                await question.edit(content = f"Kicked {i}/{len(members)} lurkers :ok_hand:")
                await member.kick(reason = "Auto-kicked following lurker kick command.")

            await question.edit(content = f"All {len(members)} lurkers that've been here more than 7 days have been kicked :ok_hand:")
        
        elif response.content.lower() == "no":
            await question.edit(content = "No lurkers have been kicked :ok_hand:")

        else:
            await question.edit(content = "Unknown response, therefore no lurkers have been kicked :ok_hand:")

        embed = Embed(title='Lurker-kick', color=Colour.from_rgb(220, 123, 28))
        embed.add_field(name='Members', value=str(len(members)))
        embed.add_field(name='Reason', value='Auto-kicked from the -lurkers kick command')
        embed.add_field(name='Initiator', value=ctx.author.mention)
        embed.set_thumbnail(url=ctx.author.avatar_url)
        embed.set_footer(text=datetime.datetime.utcnow().strftime(self.bot.ts_format))
        await get(ctx.guild.text_channels, name='adambot-logs').send(embed=embed)


def setup(bot):
    bot.add_cog(WaitingRoom(bot))
