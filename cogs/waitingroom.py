import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import os
import asyncpg
from .utils import Permissions, CHANNELS
import re
import asyncio

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
        
    async def get_parsed_welcome_message(self, new_user: discord.User):
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
            role = ctx.guild.get_role(int(match))
            to_send = to_send.replace(f"R<{match}>", role.name)

        await ctx.send(to_send)

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
        message = self.get_parsed_welcome_message(member)
        await self.welcome_channel.send(message)

        #invite stuffs
        guild = self.bot.get_guild(445194262947037185)
        old_invites = []
        async with self.bot.pool.acquire() as connection:
            old_invites = await connection.fetch('SELECT * FROM invites')
        invites = await guild.invites()
        invite_data = None
        
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
            await get(guild.text_channels, name='invite-logs').send('No invite data avaliable.' if not day_warning else f'No invite data avaliable. {member.mention}\'s account is **less than 7 days old.**')



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
        msg = self.get_parsed_welcome_message(to_ping or ctx.author) # to_ping or author means the author unless to_ping is provided.
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
            await ctx.send("Unkown response, please try again.")
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
            await ctx.send("Unkown response, please try again.")
        
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

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def y9(self, ctx, member: discord.Member):
        '''Verifies a Y9.
Staff role needed.'''
        role = get(member.guild.roles, name='Y9')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send('<@{}> has been verified!'.format(member.id))
        await self.bot.get_channel(CHANNELS['general']).send(f'Welcome {member.mention} to the server :wave:')


    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def y10(self, ctx, member: discord.Member):
        '''Verifies a Y10.
Staff role needed.'''
        role = get(member.guild.roles, name='Y10')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send('<@{}> has been verified!'.format(member.id))
        await self.bot.get_channel(CHANNELS['general']).send(f'Welcome {member.mention} to the server :wave:')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def y11(self, ctx, member: discord.Member):
        '''Verifies a Y11.
Staff role needed.'''
        role = get(member.guild.roles, name='Y11')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send('<@{}> has been verified!'.format(member.id))
        await self.bot.get_channel(CHANNELS['general']).send(f'Welcome {member.mention} to the server :wave:')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def postgcse(self, ctx, member: discord.Member):
        '''Verifies a Post-GCSE.
Staff role needed.'''
        role = get(member.guild.roles, name='Post-GCSE')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send(f'{member.mention} has been verified!')
        await self.bot.get_channel(CHANNELS['general']).send(f'Welcome {member.mention} to the server :wave:')

    @commands.command(aliases=['lurker'])
    @commands.has_any_role(*Permissions.STAFF)
    async def lurkers(self, ctx):
        members = [x for x in ctx.guild.members if len(x.roles) <= 1] # Only the everyone role
        message = ', '.join([x.mention for x in members]) + ' please tell us your year to be verified into the server!'

        for member in members:
            try:
                await member.send("If you are wanting to join the GCSE 9-1 server then please tell us your year in the waiting room. Thanks!")
            except discord.Forbidden: # Catches if DMs are closed
                pass

        await ctx.send(message)

def setup(bot):
    bot.add_cog(WaitingRoom(bot))
