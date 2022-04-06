import asyncio
from typing import Optional

import discord
from discord import Embed, Colour

from .support_connection import SupportConnection


class SupportConnectionManager:
    def __init__(self, bot) -> None:
        self.connections: list[SupportConnection] = []
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

    async def create(self, author_id: id, guild_id: id) -> Optional[SupportConnection]:
        """
        Creates a new connection in the database, alerts staff to it, and returns the new connection object.
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute("INSERT INTO support (member_id, staff_id, guild_id) VALUES ($1, $2, $3);",
                                     author_id, 0, guild_id)
            ticket_id = await connection.fetchval("SELECT MAX(id) FROM support")
            new_connection = await SupportConnection.create(self.bot, ticket_id, author_id, 0, None,
                                                            guild_id)  # Set started_at to None

        guild = self.bot.get_guild(guild_id)
        channel_id = await self.bot.get_config_key(guild, "support_log_channel")
        if channel_id is not None:
            staff_id = await self.bot.get_config_key(guild, "staff_role")
            staff = guild.get_role(
                staff_id)  # TODO: HANDLES FOR WHEN EITHER A ROLE OR CHANNEL GET REMOVED AND NOT CHANGED IN THE CONFIG
            channel = self.bot.get_channel(channel_id)
            if channel is None or staff is None:  # If channel or staff removed
                return

            embed = Embed(title="New Ticket", color=Colour.from_rgb(0, 0, 255))
            embed.add_field(name="ID", value=f"{new_connection.id}", inline=True)

            await channel.send(
                f"{staff.mention} Support ticket started by a member, ID: {new_connection.id}. Type `support accept {new_connection.id}` to accept it.",
                embed=embed)
        return new_connection

    async def get(self, id_: int = -1, guild_id: int = -1) -> SupportConnection | list[SupportConnection] | bool:
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

    async def in_connections(self, member: discord.Member) -> SupportConnection | bool:
        """
        Checks if a connection already exists with the user, if it does returns connection data or returns False if not.
        """

        self.connections = await self.get()
        for con in self.connections:
            if con.member_id == member.id or con.staff_id == member.id:
                return con
        return False

    async def remove(self, connection: SupportConnection, staff: discord.User = None) -> None:
        """
        Method that removes the support connection from the database and logs in support-logs. This method assumes
        that the connection DOES exist. If staff is not None then staff closed the ticket, otherwise it was member.
        """

        async with self.bot.pool.acquire() as db_connection:
            await db_connection.execute("DELETE FROM support WHERE id = $1", connection.id)

        channel_id = await self.bot.get_config_key(self.bot.get_guild(connection.guild_id), "support_log_channel")
        if channel_id is not None:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return
            embed = Embed(title="Ticket Ended", color=Colour.from_rgb(255, 0, 0))
            embed.add_field(name="ID", value=connection.id, inline=True)
            if staff is not None:
                embed.add_field(name="Initiator", value=f"Staff: {staff.display_name}", inline=True)
            else:
                embed.add_field(name="Initiator", value="Member", inline=True)

            await channel.send(embed=embed)
