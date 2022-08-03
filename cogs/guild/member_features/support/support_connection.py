import discord
from discord import Embed, Colour
from discord.ext import commands


class MessageOrigin:
    MEMBER = 0
    STAFF = 1


class SupportConnection:
    def __init__(self, id_: int, member_id: int, staff_id: int, started_at, guild_id: int) -> None:
        self.id = id_
        self.member_id = member_id
        self.staff_id = staff_id
        self.started_at = started_at
        self.guild_id = guild_id

        self.member = None
        self.bot = None
        self.guild = None

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

    async def log_message(self, msg_type: int, message: discord.Message) -> None:
        """
        Method that should be executed when a new message is sent through a support ticket. `message`
        refers to the actual message object sent and `msg_type` should be of the MessageOrigin type.
        """

        channel_id = await self.bot.get_config_key(self.guild, "support_log_channel")
        if channel_id is not None:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return

            embed = Embed(title="Message Sent", color=Colour.from_rgb(177, 252, 129))
            embed.add_field(name="ID", value=f"{self.id}", inline=True)
            if msg_type == MessageOrigin.MEMBER:
                embed.add_field(name="Author", value=f"Member", inline=True)
            elif msg_type == MessageOrigin.STAFF:
                embed.add_field(name="Author", value=f"Staff: {message.author.display_name}")

            embed.add_field(name="Content", value=f"{message.content}", inline=False)
            await channel.send(embed=embed)

    async def accept(self, staff: discord.User) -> None:
        """
        Method that executes when a staff member has accepted the support ticket that handles the database and objects but nothing else
        """

        async with self.bot.pool.acquire() as connection:  # TODO: Handle when a staff already has a ticket open
            await connection.execute("UPDATE support SET staff_id = $1, started_at = now() WHERE id = $2", staff.id,
                                     self.id)
        self.staff_id = staff.id
        self.staff = staff
