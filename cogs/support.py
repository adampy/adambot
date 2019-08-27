import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import os
import psycopg2
import asyncio

class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connections = self.get_connections()

    def get_connections(self):
        '''Returns currently active connections'''
        key = os.environ.get('DATABASE_URL')
        conn = psycopg2.connect(key, sslmode='require')
        cur = conn.cursor()

        cur.execute('SELECT * FROM support')
        connections = cur.fetchall()

        cur.close()
        return connections

    def in_connections(self, member: discord.Member):
        '''Checks if a connection already exists with the user, if it does returns connection data or returns False if not'''
        conns = self.get_connections()
        for con in conns:
            if con[1] == member.id or con[2] == member.id:
                return con
        else:
            return False

    def create_connection(self, member: discord.Member):
        '''Makes a connection by adding it to the DB table support'''
        key = os.environ.get('DATABASE_URL')
        conn = psycopg2.connect(key, sslmode='require')
        cur = conn.cursor()

        cur.execute('INSERT INTO support (member_id, staff_id) values (%s, %s)',(member.id, 0))
        conn.commit()
        cur.execute('SELECT * FROM support ORDER BY id DESC LIMIT 1;')
        connection_id = cur.fetchall()[0][0]

        conn.close()

        return connection_id

    async def refresh_connections(self):
        while True:
            try:
                self.connections = self.get_connections()
                await asyncio.sleep(5)
            except Exception as e:
                print(e)

    def remove_connection(self, connection_id):
        key = os.environ.get('DATABASE_URL')
        conn = psycopg2.connect(key, sslmode='require')
        cur = conn.cursor()
        cur.execute('DELETE FROM support WHERE id = (%s)', (connection_id,))
        conn.commit()
        conn.close()

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
            connection = self.in_connections(message.author) #holds connection data or False if a connection is not open
            if message.content.startswith('support start'):
                if not connection:
                    #start connection
                    connection_id = self.create_connection(message.author)
                    guild = self.bot.get_guild(445194262947037185)
                    await guild.get_channel(597068935829127168).send(f"{get(guild.roles, name='Assistant').mention} Support ticket started by a member, id:{connection_id}. Type `-support accept {connection_id}` to accept it.")
                    await message.author.send('Your ticket has been sent. A staff member will be connected to you shortly!')
                else:
                    #in connection, trying to start another
                    await message.author.send('You cannot start another ticket. You must finish this one by typing `support end`.')
            elif message.content.startswith('support end') and connection:
                if connection[1] == message.author.id: #member sending
                    self.remove_connection(connection[0])
                    await message.author.send('The ticket has been closed!')
                    await self.bot.get_user(connection[2]).send('The ticket was closed by the member.')
                    await self.log('delete-Member', connection[0])
                elif connection[2] == message.author.id: #staff sending
                    self.remove_connection(connection[0])
                    await message.author.send('The ticket has been closed!')
                    await self.bot.get_user(connection[1]).send('The ticket was closed by staff.')
                    await self.log(f'delete-Staff: {message.author.name} ', connection[0])
            else:
                if not connection:
                    #not in connection and not starts with -support
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

def setup(bot):
    bot.add_cog(Support(bot))
