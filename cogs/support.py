import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import os
import asyncio
from .utils import NEWLINE, Permissions, GCSE_SERVER_ID, CHANNELS
from datetime import timedelta, datetime

#support
	    #id SERIAL PRIMARY KEY,
	    #member_id bigint,
	    #staff_id bigint,
	    #started_at timestamptz

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

    async def log_message(self, msg_type, message: discord.Message):
        channel = self.bot.get_guild(GCSE_SERVER_ID).get_channel(CHANNELS["support-logs"])
        embed = Embed(title='Support DMs', color=Colour.from_rgb(177,252,129))
        embed.add_field(name="ID", value=f"{self.id}", inline=True)
        if msg_type == MessageType.USERTOSTAFF:
            embed.add_field(name='Author', value=f'Member', inline=True)
        elif msg_type == MessageType.STAFFTOUSER:
            embed.add_field(name='Author', value=f'Staff: {message.author.display_name}')

        embed.add_field(name='Content', value=f'{message.content}', inline=False)
        await channel.send(embed=embed)

    async def accept(self, staff: discord.User):
        """Method that executes when a staff member has accepted the support ticket."""
        async with self.bot.pool.acquire() as connection:
            await connection.execute('UPDATE support SET staff_id = $1, started_at = now() WHERE id = $2', staff.id, self.id)

class MessageType:
    USERTOSTAFF = 0
    STAFFTOUSER = 1

class SupportConnectionManager:
    def __init__(self, bot: commands.Bot):
        self.connections: SuportConnection = []
        self.bot = bot

    async def refresh_connections(self):
        while self.bot.online:
            try:
                self.connections = await self.get()
                await asyncio.sleep(5)
            except Exception as e:
                print(e)

    async def create(self, user: discord.User):
        new_connection = None
        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO support (member_id, staff_id) VALUES ($1, $2);", user.id, 0)
            id = await connection.fetchval("SELECT MAX(id) FROM support")
            new_connection = await SupportConnection.create(self.bot, id, user.id, 0, None) #  Set started_at to None

        channel = self.bot.get_guild(GCSE_SERVER_ID).get_channel(CHANNELS["support-logs"])
        embed = Embed(title='New Ticket', color=Colour.from_rgb(0,0,255))
        embed.add_field(name='ID', value=f"{new_connection.id}", inline=True)
        await channel.send(embed=embed)
        return new_connection

    async def get(self, id = -1):
            """Returns connections from the database, whether they are open or not, or a support connection via ID"""
            if id == -1: #  Return all connections from the database
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
        """Checks if a connection already exists with the user, if it does returns connection data or returns False if not"""
        self.connections = await self.get()
        for con in self.connections:
            if con.member_id == member.id or con.staff_id == member.id:
                return con
        return False

    async def remove(self, connection: SupportConnection):
        """Method that removes the support connection from the database and logs in support-logs. This method assumes
        that the connection DOES exist"""
        async with self.bot.pool.acquire() as db_connection:
            await db_connection.execute("DELETE FROM support WHERE id = $1", connection.id)
        embed = Embed(title='Ticket Ended', color=Colour.from_rgb(255,0,0))
        embed.add_field(name='ID', value=connection.id, inline=True)
        embed.add_field(name='Initiator', value="Delete", inline=True) # TODO: Change to "Member" or "Staff"
        await self.bot.get_channel(CHANNELS["support-logs"]).send(embed=embed)

class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.support_manager = SupportConnectionManager(self.bot)

    # async def create_connection(self, member: discord.Member):
    #     """Makes a connection by adding it to the DB table support"""
    #     connection_id = 0
    #     async with self.bot.pool.acquire() as connection:
    #         await connection.execute('INSERT INTO support (member_id, staff_id) values ($1, $2)', member.id, 0)
    #         connection.execute('SELECT * FROM support ORDER BY id DESC LIMIT 1;')
    #         connection_id = await connection.fetchval("SELECT MAX(id) FROM support")
    #     print(connection_id)
    #     return connection_id

    

    # async def remove_connection(self, connection_id):
    #     async with self.bot.pool.acquire() as connection:
    #         await connection.execute("DELETE FROM support WHERE id = ($1)", connection_id)

    async def log(self, mode, connection: SupportConnection, message: discord.Message = None):
        """Logs the message in support-logs"""
        pass

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.support_manager.refresh_connections())
        #async with self.bot.pool.acquire() as connection:
        #    await connection.execute("DELETE FROM support")
        #    await connection.execute("INSERT INTO support (member_id, staff_id, started_at) VALUES (686967704116002827, 420961337448071178, now())")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None and not message.author.bot: #valid dm message
            #if support requested
            connection = await self.support_manager.in_connections(message.author) #holds connection data or False if a connection is not open
            
            if message.content.lower().startswith('support start'):
                if not connection:
                    #start connection
                    connection = await self.support_manager.create(message.author)
                    guild = self.bot.get_guild(GCSE_SERVER_ID)
                    await guild.get_channel(CHANNELS["support-logs"]).send(f"Support ticket started by a member, id:{connection.id}. Type `-support accept {connection.id}` to accept it.")
                    #await guild.get_channel(CHANNELS["support-logs"]).send(f"{get(guild.roles, name='Assistant').mention} Support ticket started by a member, id:{connection.id}. Type `-support accept {connection.id}` to accept it.")
                    await message.author.send('Your ticket has been sent. A staff member will be connected to you shortly!')
                else:
                    #in connection, trying to start another
                    await message.author.send('You cannot start another ticket. You must finish this one by typing `support end`.')
            
            elif message.content.lower().startswith('support end') and connection:
                await message.author.send('The ticket has been closed!')
                if connection.member_id == message.author.id: #member sending
                    if connection.staff: # If a staff member has accepted it yet
                        await connection.staff.send('The ticket was closed by the member.')
                elif connection.staff_id == message.author.id: #staff sending
                    await connection.member.send('The ticket was closed by staff.')
                await self.support_manager.remove(connection)
            
            else:
                if not connection and not message.content.startswith('-'):
                    #not in connection and not starts with -support AND not trying to do a command
                    await message.author.send('Hi! You are not in a support chat with a staff member. If you would like to start an anonymous chat with an anonymous staff member then please type `support start` in our DM chat.')
                else:
                    #doesnt start with -support and in a connection
                    if connection.member_id == message.author.id and connection.staff_id != 0: #member sending
                        await connection.staff.send(f'Member: {message.content}')
                        await connection.log_message(MessageType.USERTOSTAFF, message)
                    elif connection.staff_id == message.author.id and connection.member_id != 0: #staff sending
                        await connection.member.send(f'Staff: {message.content}')
                        await connection.log_message(MessageType.STAFFTOUSER, message)

    @commands.group()
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def support(self, ctx):
        """Support module"""
        if ctx.invoked_subcommand is None:
            await ctx.send('```-support accept <ticket_id>```')

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
        current = []
        waiting = []
        tickets = []

        tickets = await self.support_manager.get()

        for ticket in tickets:
            if ticket.staff_id != 0:
                if ticket.started_at:
                    date = (ticket.started_at + timedelta(hours=1)).strftime('%H:%M on %d/%m/%y')
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
