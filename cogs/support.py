import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import asyncio
from .utils import NEWLINE, Permissions, GCSE_SERVER_ID, CHANNELS
from datetime import datetime

#support
	    #id SERIAL PRIMARY KEY,
	    #member_id bigint,
	    #staff_id bigint,
	    #started_at timestamptz

class MessageOrigin:
    MEMBER = 0
    STAFF = 1

class SupportConnection:
    def __init__(self, id, member_id, staff_id, started_at):
        self.id = id
        self.member_id = member_id
        self.staff_id = staff_id
        self.started_at = started_at

    @classmethod
    async def create(cls, bot: commands.Bot, id, member_id, staff_id, started_at):
        """Classmethod that allows async code to be executed, and therefore the staff and user objects
        to be obtained from the bot."""
        self = SupportConnection(id, member_id, staff_id, started_at)
        self.bot = bot
        if member_id != 0:
            self.member = bot.get_user(member_id)
        if staff_id != 0:
            self.staff = bot.get_user(staff_id)
        return self

    async def log_message(self, msg_type: MessageOrigin, message: discord.Message):
        """Method that should be executed when a new message is sent through a support ticket. `message`
        refers to the actual message object sent and `msg_type` should be of the MessageOrigin type."""
        channel = self.bot.get_guild(GCSE_SERVER_ID).get_channel(CHANNELS["support-logs"])
        embed = Embed(title='Support DMs', color=Colour.from_rgb(177,252,129))
        embed.add_field(name="ID", value=f"{self.id}", inline=True)
        if msg_type == MessageOrigin.MEMBER:
            embed.add_field(name='Author', value=f'Member', inline=True)
        elif msg_type == MessageOrigin.STAFF:
            embed.add_field(name='Author', value=f'Staff: {message.author.display_name}')

        embed.add_field(name='Content', value=f'{message.content}', inline=False)
        await channel.send(embed=embed)

    async def accept(self, staff: discord.User):
        """Method that executes when a staff member has accepted the support ticket."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute('UPDATE support SET staff_id = $1, started_at = now() WHERE id = $2', staff.id, self.id)

class SupportConnectionManager:
    def __init__(self, bot: commands.Bot):
        self.connections: SuportConnection = []
        self.bot = bot

    async def refresh_connections(self):
        """Background task running approx. every 5 seconds to refresh the current list of connections."""
        while self.bot.online:
            try:
                self.connections = await self.get()
                await asyncio.sleep(5)
            except Exception as e:
                print(e)

    async def create(self, user: discord.User):
        """Creates a new connection in the database, and returns the new connection object."""
        new_connection = None
        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO support (member_id, staff_id) VALUES ($1, $2);", user.id, 0)
            id = await connection.fetchval("SELECT MAX(id) FROM support")
            new_connection = await SupportConnection.create(self.bot, id, user.id, 0, None)  # Set started_at to None

        channel = self.bot.get_guild(GCSE_SERVER_ID).get_channel(CHANNELS["support-logs"])
        embed = Embed(title='New Ticket', color=Colour.from_rgb(0,0,255))
        embed.add_field(name='ID', value=f"{new_connection.id}", inline=True)
        await channel.send(embed=embed)
        return new_connection

    async def get(self, id = -1):
        """Returns connections from the database, whether they are open or not, or a support connection via ID."""
        if id == -1:  # Return all connections from the database
            connections = []
            async with self.bot.pool.acquire() as connection:
                connections = await connection.fetch("SELECT * FROM support")
            
            for i in range(len(connections)):
                conn = connections[i]
                new_connection = await SupportConnection.create(self.bot, *conn)
                connections[i] = new_connection
            return connections
        else:
            async with self.bot.pool.acquire() as connection:
                records = await connection.fetch("SELECT * FROM support WHERE id = $1", id)
                args = records[0]
                support_connection = await SupportConnection.create(self.bot, *args)
                return support_connection

    async def in_connections(self, member: discord.Member):
        """Checks if a connection already exists with the user, if it does returns connection data or returns False if not."""
        self.connections = await self.get()
        for con in self.connections:
            if con.member_id == member.id or con.staff_id == member.id:
                return con
        return False

    async def remove(self, connection: SupportConnection, staff: discord.User = None):
        """Method that removes the support connection from the database and logs in support-logs. This method assumes
        that the connection DOES exist. If staff is not None then staff closed the ticket, otherwise it was member."""
        async with self.bot.pool.acquire() as db_connection:
            await db_connection.execute("DELETE FROM support WHERE id = $1", connection.id)
        embed = Embed(title='Ticket Ended', color=Colour.from_rgb(255,0,0))
        embed.add_field(name='ID', value=connection.id, inline=True)
        if staff is not None:
            embed.add_field(name='Initiator', value=f"Staff: {staff.display_name}", inline=True)
        else:
            embed.add_field(name='Initiator', value="Member", inline=True)
        await self.bot.get_channel(CHANNELS["support-logs"]).send(embed=embed)

class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.support_manager = SupportConnectionManager(self.bot)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.support_manager.refresh_connections())

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None and not message.author.bot:  # Valid DM message
            # If support requested
            connection = await self.support_manager.in_connections(message.author)  # Holds connection data or False if a connection is not open
            
            if message.content.lower().startswith('support start'):
                if not connection:
                    # Start connection
                    connection = await self.support_manager.create(message.author)
                    guild = self.bot.get_guild(GCSE_SERVER_ID)
                    await guild.get_channel(CHANNELS["support-logs"]).send(f"{get(guild.roles, name='Assistant').mention} Support ticket started by a member, id:{connection.id}. Type `-support accept {connection.id}` to accept it.")
                    await message.author.send('Your ticket has been sent. A staff member will be connected to you shortly!')
                else:
                    # In connection and trying to start another
                    await message.author.send('You cannot start another ticket. You must finish this one by typing `support end`.')
            
            elif message.content.lower().startswith('support end') and connection:
                await message.author.send('The ticket has been closed!')
                if connection.member_id == message.author.id: # Member sending
                    if connection.staff:  # If a staff member has accepted it yet
                        await connection.staff.send('The ticket was closed by the member.')
                        await self.support_manager.remove(connection)
                elif connection.staff_id == message.author.id:  # Staff sending
                    await connection.member.send('The ticket was closed by staff.')
                    await self.support_manager.remove(connection, message.author)
            
            else:
                if not connection and not message.content.startswith('-'):
                    # Not in connection and not starts with -support AND not trying to do a command
                    await message.author.send('Hi! You are not in a support chat with a staff member. If you would like to start an anonymous chat with an anonymous staff member then please type `support start` in our DM chat.')
                else:
                    # Doesn't start with -support and in a connection
                    if connection.member_id == message.author.id and connection.staff_id != 0:  # Member sending
                        await connection.staff.send(f'Member: {message.content}')
                        await connection.log_message(MessageOrigin.MEMBER, message)
                    elif connection.staff_id == message.author.id and connection.member_id != 0:  # Staff sending
                        await connection.member.send(f'Staff: {message.content}')
                        await connection.log_message(MessageOrigin.STAFF, message)

    @commands.Cog.listener()
    async def on_typing(self, channel, user, when):
        """A handle for typing events between DMs, so that the typing presence can go through the DMs via the bot."""
        if not isinstance(channel, discord.DMChannel):
            return

        connections = await self.support_manager.get()
        for conn in connections:
            if conn.member_id == user.id and conn.staff_id != 0:
                # Member typing and staff connected, send typing to staff
                await conn.staff.trigger_typing()

            elif conn.staff_id == user.id:
                # Staff typing, send typing to member
                await conn.member.trigger_typing()

    @commands.group()
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def support(self, ctx):
        """Support module"""
        if ctx.invoked_subcommand is None:
            await ctx.send('```-help support``` for more commands')

    @support.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def accept(self, ctx, ticket):
        """Accept a support ticket.
Staff role needed."""
        try:
            ticket = int(ticket)
        except ValueError:
            ctx.send('Ticket must be an integer.')
            return

        connection = await self.support_manager.get(id = ticket)
        if connection.staff_id != ctx.author.id:
            await connection.accept(ctx.author)
            await ctx.send(f'{ctx.author.mention} is now connected with the member.')
            await ctx.author.send('You are now connected anonymously with a member. DM me to get started!')
            await connection.member.send('You are now connected anonymously with a staff member. DM me to get started!')
            embed = Embed(color=Colour.from_rgb(0,0,255))
            embed.add_field(name='New Ticket DM', value=f"ID: {connection.id}", inline=False)
            await ctx.author.guild.get_channel(CHANNELS["support-logs"]).send(embed=embed)
        else:
            await ctx.send('You cannot open a support ticket with yourself.')
            #await db_connection.execute('DELETE FROM support WHERE id = ($1)', ticket)

    @support.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def connections(self, ctx):
        """Shows all current support connections with member info redacted.
Staff role needed."""
        current = []
        waiting = []
        
        tickets = await self.support_manager.get()
        for ticket in tickets:
            if ticket.staff_id != 0:
                if ticket.started_at:
                    date = ticket.started_at.strftime('%H:%M on %d/%m/%y')
                else:
                    date = "Not yet accepted."
                current.append(f"ID: {ticket.id}{NEWLINE}Member ID: ***REDACTED***{NEWLINE}Staff: {ticket.staff}{NEWLINE}Started at: {date}{NEWLINE}")
            else:
                waiting.append(f"ID: {ticket.id}{NEWLINE}Member ID: ***REDACTED***{NEWLINE}")

        x = '\n'.join(current)
        y = '\n'.join(waiting)
        string = f"__**Current connections**__{NEWLINE}{x}{NEWLINE}__**Waiting connections**__{NEWLINE}{y}"
        await ctx.send(string)

def setup(bot):
    bot.add_cog(Support(bot))
