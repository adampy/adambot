import discord
from discord import Embed, Colour
from discord.ext import commands

from .support_connection import MessageOrigin


class SupportHandlers:
    def __init__(self, bot, cog) -> None:
        self.bot = bot
        self.cog = cog

    async def accept(self, ctx: commands.Context | discord.Interaction, ticket: str | int) -> None:
        """
        Handler for the accept commands.
        """

        is_ctx = type(ctx) is commands.Context
        author = ctx.author if is_ctx else ctx.user

        try:
            ticket = int(ticket)
        except ValueError:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not find that ticket!",
                                                             desc="Ticket must be an integer.")
            return

        in_connection = await self.cog.support_manager.in_connections(author)
        if in_connection:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not accept ticket!",
                                                             desc=f"You are already part of a support ticket in **{in_connection.guild.name}** with ID {in_connection.id}. You need to close that one before accepting another")
            return

        connection = await self.cog.support_manager.get(id_=ticket)
        if not connection:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not find that ticket!",
                                                             desc="This ticket ID does not exist!")
            return

        if connection.guild.id != ctx.guild.id:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not accept that ticket!",
                                                             desc="You cannot accept support tickets from other guilds!")
            return

        if connection.member_id == author.id:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Could not accept that ticket!",
                                                             desc="You cannot open a support ticket with yourself.")
            return

        await connection.accept(author)
        await author.send(
            f"You are now connected anonymously with a member in **{connection.guild.name}** with the ticket ID {connection.id}. DM me to get started! (Type `support end` here when you are finished to close the support ticket)")
        await connection.member.send(
            "You are now connected anonymously with a staff member in **{connection.guild.name}**. DM me to get started! (Type `support end` here when you are finished to close the support ticket)")

        channel_id = await self.bot.get_config_key(ctx, "support_log_channel")
        if channel_id is not None:
            embed = Embed(color=Colour.from_rgb(0, 0, 255))
            embed.add_field(name="Staff Connected", value=f"ID: {connection.id}", inline=False)

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return
            await channel.send(embed=embed)

    async def connections(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the connections commands.
        """

        current = []
        waiting = []
        newline = "\n"

        tickets = await self.cog.support_manager.get(guild_id=ctx.guild.id)
        for ticket in tickets:
            if ticket.staff_id != 0:
                if ticket.started_at:
                    date = ticket.started_at.strftime("%H:%M on %d/%m/%y")
                else:
                    date = "Not yet accepted."
                current.append(
                    f"ID: {ticket.id}{newline}Member ID: ***REDACTED***{newline}Staff: {ticket.staff}{newline}Started at: {date}{newline}")
            else:
                waiting.append(f"ID: {ticket.id}{newline}Member ID: ***REDACTED***{newline}")

        x = newline.join(current)
        y = newline.join(waiting)
        string = f"__**Current connections**__{newline}{x}{newline}__**Waiting connections**__{newline}{y}"
        await ctx.send(string) if type(ctx) is commands.Context else await ctx.response.send_message(string)

    async def on_message(self, message: discord.Message) -> None:
        """
        Handler for the on_message listener.
        """

        if message.guild is None and not message.author.bot:  # Valid DM message
            # If support requested
            connection = await self.cog.support_manager.in_connections(
                message.author)  # Holds connection data or False if a connection is not open

            if not connection and self.bot.starts_with_any(message.content.lower(), ["support start", "support begin"]):
                # Start a new connection
                try:  # Try clause gets a valid guild_id
                    guild_id = int(message.content.split(" ")[2])
                    if guild_id not in [g.id for g in self.bot.guilds]:
                        await message.author.send(
                            f"That is not a guild I know of, to get a list of guilds type `support start`")
                        return
                except ValueError:
                    await message.author.send(
                        f"That is not a guild I know of, to get a list of guilds type `support start`")
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

                guild = self.bot.get_guild(guild_id)
                if not guild.get_member(
                        message.author.id):  # users should not be able to open support tickets for guild they are not a member of
                    await message.author.send(
                        f"That is not a guild I know of, to get a list of guilds type `support start`")  # shouldn't tell them they don't share the guild since they don't need to know the guild has the bot
                    return

                connection = await self.cog.support_manager.in_connections(
                    message.author)  # Holds connection data or False if a connection is not open
                if connection:
                    await message.author.send(
                        f"You already have a support ticket open in **{connection.guild.name}** and you cannot open another one until this one is closed")
                    return

                # Check if guild has support module set up
                log_channel_id = await self.bot.get_config_key(self.bot.get_guild(guild_id), "support_log_channel")
                if not log_channel_id:
                    await message.author.send(
                        f"**{guild.name}** has not set up the support module :sob:")  # This prevents any connections being made at all
                    return

                connection = await self.cog.support_manager.create(message.author.id,
                                                                   guild_id)  # This method handles the embed making the staff aware of the ticket
                await message.author.send(
                    f"Your ticket, **ID: {connection.id}**, has been sent. Staff have been alerted to your ticket and will be with you shortly!")

            if self.bot.starts_with_any(message.content.lower(),
                                        ["support end", "support close", "support finish"]) and connection:
                if connection.member_id == message.author.id:  # Member sending
                    if connection.staff_id != 0:
                        await connection.staff.send("The ticket was closed by the member.")
                    await self.cog.support_manager.remove(connection)
                    await message.author.send("The ticket has been closed!")

                elif connection.staff_id == message.author.id:  # Staff sending
                    await self.cog.support_manager.remove(connection, message.author)
                    await connection.member.send("The ticket was closed by staff.")
                    await message.author.send("The ticket has been closed!")

            else:
                if not connection and not message.content.startswith("-"):
                    # Not in connection and not starts with `support` AND not trying to do a command
                    await message.author.send(
                        f"Hi! You are not in a support chat with a staff member. If you would like to start an anonymous chat with an anonymous staff member type `support start` to get started.")
                else:
                    # Doesn't start with -
                    if connection:
                        if connection.member_id == message.author.id and connection.staff_id != 0:  # Member sending
                            await connection.staff.send(f"Member: {message.content}")
                            await connection.log_message(MessageOrigin.MEMBER, message)
                        elif connection.staff_id == message.author.id and connection.member_id != 0:  # Staff sending
                            await connection.member.send(f"Staff: {message.content}")
                            await connection.log_message(MessageOrigin.STAFF, message)

    async def on_typing(self, channel: discord.DMChannel | discord.TextChannel | discord.Thread,
                        user: discord.User) -> None:
        """
        Handler for the on_typing handler.
        """

        if not isinstance(channel, discord.DMChannel):
            return

        connections = await self.cog.support_manager.get()
        for conn in connections:
            if conn.member_id == user.id and conn.staff_id != 0:
                # Member typing and staff connected, send typing to staff
                await conn.staff.trigger_typing()

            elif conn.staff_id == user.id:
                # Staff typing, send typing to member
                await conn.member.trigger_typing()
