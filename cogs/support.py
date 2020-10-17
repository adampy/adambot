import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import os
import asyncio
from .utils import NEWLINE, Permissions
from datetime import timedelta, datetime

class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connections = []

    async def get_connections(self):
        '''Returns currently active connections'''
        connections = []
        async with self.bot.pool.acquire() as connection:
            connections = await connection.fetch("SELECT * FROM support")
        return connections

    async def in_connections(self, member: discord.Member):
        '''Checks if a connection already exists with the user, if it does returns connection data or returns False if not'''
        conns = await self.get_connections()
        for con in conns:
            if con[1] == member.id or con[2] == member.id:
                return con
        else:
            return False

    async def create_connection(self, member: discord.Member):
        '''Makes a connection by adding it to the DB table support'''
        connection_id = 0
        async with self.bot.pool.acquire() as connection:
            await connection.execute('INSERT INTO support (member_id, staff_id) values ($1, $2)', member.id, 0)
            connection.execute('SELECT * FROM support ORDER BY id DESC LIMIT 1;')
            connection_id = await connection.fetchval("SELECT MAX(id) FROM support")
        print(connection_id)
        return connection_id

    async def refresh_connections(self):
        while True:
            try:
                self.connections = await self.get_connections()
                await asyncio.sleep(5)
            except Exception as e:
                print(e)

    async def remove_connection(self, connection_id):
        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM support WHERE id = ($1)", connection_id)

    async def log(self, mode, connection_id, message: discord.Message = None):
        '''Logs the message in support-logs'''
        channel = self.bot.get_guild(445194262947037185).get_channel(597068935829127168)
        if mode.startswith('log'):
            log_type = mode.split('-')[1]
            embed = Embed(title='Support DMs', color=Colour.from_rgb(177,252,129))
            embed.add_field(name="ID", value=f"{connection_id}", inline=True)
            embed.add_field(name='Author', value=f'{log_type}', inline=True)
            embed.add_field(name='Content', value=f'{message.content}', inline=False)
            await channel.send(embed=embed)
        elif mode == 'new':
            embed = Embed(title='New Ticket', color=Colour.from_rgb(0,0,255))
            embed.add_field(name='ID', value=f"{connection_id}", inline=True)
            await channel.send(embed=embed)
        elif mode.startswith('delete'):
            log_type = mode.split('-')[1]
            embed = Embed(title='Ticket Ended', color=Colour.from_rgb(255,0,0))
            embed.add_field(name='ID' ,value=f"{connection_id}", inline=True)
            embed.add_field(name='Initiator', value=f'{log_type}', inline=True)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.refresh_connections())

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None and not message.author.bot: #valid dm message
            #if support requested
            connection = await self.in_connections(message.author) #holds connection data or False if a connection is not open
            if message.content.lower().startswith('support start'):
                if not connection:
                    #start connection
                    connection_id = await self.create_connection(message.author)
                    guild = self.bot.get_guild(445194262947037185)
                    await guild.get_channel(597068935829127168).send(f"{get(guild.roles, name='Assistant').mention} Support ticket started by a member, id:{connection_id}. Type `-support accept {connection_id}` to accept it.")
                    await message.author.send('Your ticket has been sent. A staff member will be connected to you shortly!')
                else:
                    #in connection, trying to start another
                    await message.author.send('You cannot start another ticket. You must finish this one by typing `support end`.')
            elif message.content.lower().startswith('support end') and connection:
                if connection[1] == message.author.id: #member sending
                    await self.remove_connection(connection[0])
                    await message.author.send('The ticket has been closed!')
                    await self.bot.get_user(connection[2]).send('The ticket was closed by the member.')
                    await self.log('delete-Member', connection[0])
                elif connection[2] == message.author.id: #staff sending
                    await self.remove_connection(connection[0])
                    await message.author.send('The ticket has been closed!')
                    await self.bot.get_user(connection[1]).send('The ticket was closed by staff.')
                    await self.log(f'delete-Staff: {message.author.name} ', connection[0])
            else:
                if not connection and not message.content.startswith('-'):
                    #not in connection and not starts with -support AND not trying to do a command
                    await message.author.send('Hi! You are not in a support chat with a staff member. If you would like to start an anonymous chat with an anonymous staff member then please type `support start` in our DM chat.')
                else:
                    #doesnt start with -support and in a connection
                    if connection[1] == message.author.id and connection[2] != 0: #member sending
                        staff = self.bot.get_user(connection[2])
                        await staff.send(f'Member: {message.content}')
                        await self.log('log-Member', connection[0], message)
                    elif connection[2] == message.author.id and connection[1] != 0: #staff sending
                        member = self.bot.get_user(connection[1])
                        await member.send(f'Staff: {message.content}')
                        await self.log(f'log-Staff: {message.author.name} ', connection[0], message)

    @commands.group()
    @commands.has_any_role(*Permissions.STAFF)
    @commands.guild_only()
    async def support(self, ctx):
        '''Support module'''
        if ctx.invoked_subcommand is None:
            await ctx.send('```-support accept <ticket_id>```')

    @support.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def accept(self, ctx, ticket):
        '''Accept a support ticket.
Staff role needed.'''
        try:
            ticket = int(ticket)
        except ValueError:
            ctx.send('Ticket must be an integer.')
            return

        async with self.bot.pool.acquire() as db_connection:
            records = await db_connection.fetch("SELECT * FROM support WHERE id = ($1)", ticket)
            connection = records[0]
            print(connection)
            if connection:
                if connection[1] != ctx.author.id:
                    await db_connection.execute('UPDATE support SET (staff_id, started_at) = ($1, now()) WHERE id = ($2)', ctx.author.id, ticket)
                    await ctx.send(f'{ctx.author.mention} is now connected with the member.')
                    await ctx.author.send('You are now connected anonymously with a member. DM me to get started!')
                    member = self.bot.get_user(connection[1])
                    await member.send('You are now connected anonymously with a staff member. DM me to get started!')
                    embed = Embed(color=Colour.from_rgb(0,0,255))
                    embed.add_field(name='New Ticket DM', value=f"ID: {connection[0]}", inline=False)
                    await ctx.author.guild.get_channel(597068935829127168).send(embed=embed)
                else:
                    await ctx.send('You cannot open a support ticket with yourself.')
                    await db_connection.execute('DELETE FROM support WHERE id = ($1)', ticket)

    @support.command(pass_context=True)
    @commands.has_any_role(*Permissions.STAFF)
    async def connections(self, ctx):
        current = []
        waiting = []
        tickets = []

        async with self.bot.pool.acquire() as connection:
            tickets = await connection.fetch("SELECT * FROM support")

        #support
	    #id SERIAL PRIMARY KEY,
	    #member_id bigint,
	    #staff_id bigint,
	    #started_at timestamptz

        for ticket in tickets:
            if ticket[3] != None:
                staff = await self.bot.fetch_user(ticket[2])
                date = (ticket[3] + timedelta(hours=1)).strftime('%H:%M on %d/%m/%y')
                current.append(f"ID: {ticket[0]}{NEWLINE}Member ID: ***REDACTED***{NEWLINE}Staff: {staff}{NEWLINE}Started at: {date}{NEWLINE}")
            else:
                waiting.append(f"ID: {ticket[0]}{NEWLINE}Member ID: ***REDACTED***{NEWLINE}")

        x = '\n'.join(current)
        y = '\n'.join(waiting)
        string = f"__**Current connections**__{NEWLINE}{x}{NEWLINE}__**Waiting connections**__{NEWLINE}{y}"
        await ctx.send(string)

def setup(bot):
    bot.add_cog(Support(bot))
