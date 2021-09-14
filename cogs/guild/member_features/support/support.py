import discord
from discord import Embed, Colour
from discord.ext import commands
import asyncio

"""
support

id SERIAL PRIMARY KEY,
member_id bigint,
staff_id bigint,
started_at timestamptz,
guild_id bigint
"""


class MessageOrigin:
    MEMBER = 0
    STAFF = 1


class SupportConnection:
    def __init__(self, id_, member_id, staff_id, started_at, guild_id):
        self.id = id_
        self.member_id = member_id
        self.staff_id = staff_id
        self.started_at = started_at
        self.guild_id = guild_id

    @classmethod
    async def create(cls, bot: commands.Bot, id_, member_id, staff_id, started_at, guild_id=0):
        """
        Class method that allows async code to be executed, and therefore the staff and user objects
        to be obtained from the bot.
        """

        self = SupportConnection(id_, member_id, staff_id, started_at, guild_id)
        self.bot = bot
        if member_id != 0:
            self.member = bot.get_user(member_id)
        if staff_id != 0:
            self.staff = bot.get_user(staff_id)
        if guild_id != 0:
            self.guild = bot.get_guild(guild_id)
        return self

    async def log_message(self, msg_type: MessageOrigin, message: discord.Message):
        """
        Method that should be executed when a new message is sent through a support ticket. `message`
        refers to the actual message object sent and `msg_type` should be of the MessageOrigin type.
        """

        channel_id = self.bot.configs[self.guild.id]["support_log_channel"]
        if channel_id is not None:
            channel = self.bot.get_channel(self.bot.configs[self.guild.id]["support_log_channel"])
            if channel is None:
                return

            embed = Embed(title='Message Sent', color=Colour.from_rgb(177, 252, 129))
            embed.add_field(name="ID", value=f"{self.id}", inline=True)
            if msg_type == MessageOrigin.MEMBER:
                embed.add_field(name='Author', value=f'Member', inline=True)
            elif msg_type == MessageOrigin.STAFF:
                embed.add_field(name='Author', value=f'Staff: {message.author.display_name}')

            embed.add_field(name='Content', value=f'{message.content}', inline=False)
            await channel.send(embed=embed)

    async def accept(self, staff: discord.User):
        """
        Method that executes when a staff member has accepted the support ticket that handles the database and objects but nothing else
        """

        async with self.bot.pool.acquire() as connection:  # TODO: Handle when a staff already has a ticket open
            await connection.execute('UPDATE support SET staff_id = $1, started_at = now() WHERE id = $2', staff.id, self.id)
        self.staff_id = staff.id
        self.staff = staff


class SupportConnectionManager:
    def __init__(self, bot: commands.Bot):
        self.connections: SupportConnection = []
        self.bot = bot

    async def refresh_connections(self):
        """
        Background task running approx. every 5 seconds to refresh the current list of connections.
        """

        while self.bot.online:
            try:
                self.connections = await self.get()
                await asyncio.sleep(5)
            except Exception as e:
                print(e)

    async def create(self, author_id, guild_id):
        """
        Creates a new connection in the database, alerts staff to it, and returns the new connection object.
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO support (member_id, staff_id, guild_id) VALUES ($1, $2, $3);", author_id, 0, guild_id)
            ticket_id = await connection.fetchval("SELECT MAX(id) FROM support")
            new_connection = await SupportConnection.create(self.bot, ticket_id, author_id, 0, None, guild_id)  # Set started_at to None

        channel_id = self.bot.configs[guild_id]["support_log_channel"]
        if channel_id is not None:
            guild = self.bot.get_guild(guild_id)
            staff_id = self.bot.configs[guild_id]["staff_role"]
            staff = guild.get_role(staff_id)  # TODO: HANDLES FOR WHEN EITHER A ROLE OR CHANNEL GET REMOVED AND NOT CHANGED IN THE CONFIG
            channel = self.bot.get_channel(channel_id)
            if channel is None or staff is None:  # If channel or staff removed
                return
        
            embed = Embed(title='New Ticket', color=Colour.from_rgb(0, 0, 255))
            embed.add_field(name='ID', value=f"{new_connection.id}", inline=True)

            await channel.send(f"{staff.mention} Support ticket started by a member, ID: {new_connection.id}. Type `support accept {new_connection.id}` to accept it.", embed=embed)
        return new_connection

    async def get(self, id_=-1, guild_id=-1):
        """
        Returns connections from the database, whether they are open or not, or a support connection via ID. This method returns False
        if a support ticket is now found when searching by ID, else it returns a list of SupportConnection
        """

        if id_ != -1:  # Return based on ID
            async with self.bot.pool.acquire() as connection:
                records = await connection.fetch("SELECT * FROM support WHERE id = $1", id_)
                if len(records) == 0:
                    return False
                args = records[0]
                support_connection = await SupportConnection.create(self.bot, *args)
                return support_connection
            
        elif guild_id != -1:  # Return based on guild
            async with self.bot.pool.acquire() as connection:
                records = await connection.fetch("SELECT * FROM support WHERE guild_id = $1", guild_id)
            
            for i in range(len(records)):
                conn = records[i]
                new_connection = await SupportConnection.create(self.bot, *conn)
                records[i] = new_connection
            return records

        else:  # Return all connections from the database
            async with self.bot.pool.acquire() as connection:
                connections = await connection.fetch("SELECT * FROM support")
            
            for i in range(len(connections)):
                conn = connections[i]
                new_connection = await SupportConnection.create(self.bot, *conn)
                connections[i] = new_connection
            return connections

    async def in_connections(self, member: discord.Member):
        """
        Checks if a connection already exists with the user, if it does returns connection data or returns False if not.
        """

        self.connections = await self.get()
        for con in self.connections:
            if con.member_id == member.id or con.staff_id == member.id:
                return con
        return False

    async def remove(self, connection: SupportConnection, staff: discord.User = None):
        """
        Method that removes the support connection from the database and logs in support-logs. This method assumes
        that the connection DOES exist. If staff is not None then staff closed the ticket, otherwise it was member.
        """

        async with self.bot.pool.acquire() as db_connection:
            await db_connection.execute("DELETE FROM support WHERE id = $1", connection.id)

        channel_id = self.bot.configs[connection.guild_id]["support_log_channel"]
        if channel_id is not None:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return
            embed = Embed(title='Ticket Ended', color=Colour.from_rgb(255, 0, 0))
            embed.add_field(name='ID', value=connection.id, inline=True)
            if staff is not None:
                embed.add_field(name='Initiator', value=f"Staff: {staff.display_name}", inline=True)
            else:
                embed.add_field(name='Initiator', value="Member", inline=True)

            await channel.send(embed=embed)


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

            if not connection and self.bot.starts_with_any(message.content.lower(), ['support start', 'support begin']):
                # Start a new connection
                try:  # Try clause gets a valid guild_id
                    guild_id = int(message.content.split(' ')[2])
                    if guild_id not in [g.id for g in self.bot.guilds]:
                        await message.author.send(f"That is not a guild I know of, to get a list of guilds type `support start`")
                        return
                except ValueError:
                    await message.author.send(f"That is not a guild I know of, to get a list of guilds type `support start`")
                    return
                except IndexError:
                    shared_guilds = [g for g in self.bot.guilds if message.author in g.members]
                    output = f"To start a ticket, you must run this command with a guild ID, e.g. `support start 1234567890`. Guild IDs of servers that we share are:\n"
                    for i in range(len(shared_guilds)):
                        guild = shared_guilds[i]
                        output += f"• {guild.name}: **{guild.id}**"
                        if i != len(shared_guilds) - 1:
                            output += "\n"
                    await message.author.send(output)
                    return

                connection = await self.support_manager.in_connections(message.author)  # Holds connection data or False if a connection is not open
                if connection:
                    await message.author.send(f"You already have a support ticket open in **{connection.guild.name}** and you cannot open another one until this one is closed")
                    return

                # Check if guild has support module set up
                log_channel_id = self.bot.configs[guild_id]["support_log_channel"]
                if not log_channel_id:
                    await message.author.send(f"**{self.bot.get_guild(guild_id).name}** has not set up the support module :sob:")  # This prevents any connections being made at all
                    return

                connection = await self.support_manager.create(message.author.id, guild_id)  # This method handles the embed making the staff aware of the ticket
                await message.author.send(f'Your ticket, **ID: {connection.id}**, has been sent. Staff have been alerted to your ticket and will be with you shortly!')
            
            if self.bot.starts_with_any(message.content.lower(), ['support end', 'support close', 'support finish']) and connection:
                if connection.member_id == message.author.id:  # Member sending
                    if connection.staff_id != 0:
                        await connection.staff.send('The ticket was closed by the member.')
                    await self.support_manager.remove(connection)
                    await message.author.send('The ticket has been closed!')

                elif connection.staff_id == message.author.id:  # Staff sending
                    await self.support_manager.remove(connection, message.author)
                    await connection.member.send('The ticket was closed by staff.')
                    await message.author.send('The ticket has been closed!')
            
            else:
                if not connection and not message.content.startswith('-'):
                    # Not in connection and not starts with `support` AND not trying to do a command
                    await message.author.send(f'Hi! You are not in a support chat with a staff member. If you would like to start an anonymous chat with an anonymous staff member type `support start` to get started.')
                else:
                    # Doesn't start with -
                    if connection:
                        if connection.member_id == message.author.id and connection.staff_id != 0:  # Member sending
                            await connection.staff.send(f'Member: {message.content}')
                            await connection.log_message(MessageOrigin.MEMBER, message)
                        elif connection.staff_id == message.author.id and connection.member_id != 0:  # Staff sending
                            await connection.member.send(f'Staff: {message.content}')
                            await connection.log_message(MessageOrigin.STAFF, message)

    @commands.Cog.listener()
    async def on_typing(self, channel, user, when):
        """
        A handle for typing events between DMs, so that the typing presence can go through the DMs via the bot.
        """

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
    async def support(self, ctx):
        """
        Support module
        """

        if ctx.invoked_subcommand is None:
            await ctx.send(f'```{ctx.prefix}help support``` for more commands. If you want to open a ticket type ```{ctx.prefix}support start```')

    @support.command(pass_context=True)
    @commands.guild_only()
    async def accept(self, ctx, ticket):
        """
        Accepts a support ticket
        """

        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to accept a support ticket")
            return

        try:
            ticket = int(ticket)
        except ValueError:
            ctx.send('Ticket must be an integer.')
            return

        in_connection = await self.support_manager.in_connections(ctx.author)
        if in_connection:
            await ctx.author.send(f"You are already part of a support ticket in **{in_connection.guild.name}**. You need to close that one before accepting another")
            return

        connection = await self.support_manager.get(id_=ticket)
        if not connection:
            await ctx.send("This ticket ID does not exist!")
            return
        if connection.guild.id != ctx.guild.id:
            await ctx.send("You cannot accept support tickets from other guilds!")
            return
        if connection.member_id == ctx.author.id:
            await ctx.send('You cannot open a support ticket with yourself.')
            return

        await connection.accept(ctx.author)
        await ctx.author.send('You are now connected anonymously with a member. DM me to get started! (Type `support end` here when you are finished to close the support ticket)')
        await connection.member.send('You are now connected anonymously with a staff member. DM me to get started! (Type `support end` here when you are finished to close the support ticket)')

        channel_id = self.bot.configs[ctx.guild.id]["support_log_channel"]
        if channel_id is not None:
            embed = Embed(color=Colour.from_rgb(0, 0, 255))
            embed.add_field(name='Staff Connected', value=f"ID: {connection.id}", inline=False)

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return
            await channel.send(embed=embed)

    @support.command(pass_context=True)
    @commands.guild_only()
    async def connections(self, ctx):
        """
        Shows all current support connections with member info redacted
        """

        if not await self.bot.is_staff(ctx):
            await ctx.send("You do not have permissions to view support tickets")
            return

        current = []
        waiting = []
        newline = "\n"
        
        tickets = await self.support_manager.get(guild_id=ctx.guild.id)
        for ticket in tickets:
            if ticket.staff_id != 0:
                if ticket.started_at:
                    date = ticket.started_at.strftime('%H:%M on %d/%m/%y')
                else:
                    date = "Not yet accepted."
                current.append(f"ID: {ticket.id}{newline}Member ID: ***REDACTED***{newline}Staff: {ticket.staff}{newline}Started at: {date}{newline}")
            else:
                waiting.append(f"ID: {ticket.id}{newline}Member ID: ***REDACTED***{newline}")

        x = newline.join(current)
        y = newline.join(waiting)
        string = f"__**Current connections**__{newline}{x}{newline}__**Waiting connections**__{newline}{y}"
        await ctx.send(string)


def setup(bot):
    bot.add_cog(Support(bot))
