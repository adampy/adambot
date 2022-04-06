import discord


class StarboardContainer:
    class Entry:
        @classmethod
        async def make_entry(cls, record: dict, bot: discord.Client) -> __qualname__:
            super().__init__(cls)
            self = StarboardContainer.Entry()
            self.bot = bot
            self.bot_message_id = record["bot_message_id"]
            self.message_id = record["message_id"]
            self.channel_id = record["starboard_channel_id"]  # Channel ID of bot message
            try:
                self.channel = bot.get_channel(self.channel_id)
                self.bot_message = await self.channel.fetch_message(self.bot_message_id)
            except discord.NotFound:
                self.channel = self.bot_message = None
            return self

        async def update_bot_message(self, new_msg: discord.Message) -> None:
            self.bot_message = new_msg
            self.bot_message_id = new_msg.id
            async with self.bot.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE starboard_entry SET bot_message_id = $1 WHERE starboard_channel_id = $2 AND message_id = $3;",
                    self.bot_message_id, self.channel_id, self.message_id)

    def __init__(self, record: dict, bot: discord.Client) -> None:
        self.bot = bot
        self.channel = self.bot.get_channel(record["channel_id"])
        self.guild = self.channel.guild
        self.emoji = record["emoji"]
        self.emoji_id = record["emoji_id"]
        self.minimum_stars = record["minimum_stars"]
        self.embed_colour = record["embed_colour"]
        self.allow_self_star = record["allow_self_star"]
        self.record = record
        self.entries = []

    @classmethod
    async def make_starboards(cls, records: list, entries: list, bot: discord.Client) -> dict:
        """
        Makes a dict of {channel_id: Starboard} for the given starboards and entries from the DB
        """

        starboards = {}
        for record in records:
            obj = StarboardContainer(record, bot)
            starboards[obj.channel.id] = obj  # Make empty starboard
        for entry in entries:
            obj = await StarboardContainer.Entry.make_entry(entry, bot)
            starboards[entry["starboard_channel_id"]].entries.append(
                obj)  # Add all entries to their respective starboard
        return starboards

    def get_record(self) -> dict:
        """
        Function that returns the record in the database for the starboard
        """
        return self.record

    def get_string_emoji(self) -> str:
        """
        Returns the unicode emoji or a discord formatted custom emoji as a string
        """

        custom_emoji = self.bot.get_emoji(self.emoji_id) if self.emoji_id else None
        emoji = self.emoji if self.emoji else f"<:{custom_emoji.name}:{custom_emoji.id}>"
        return emoji

    async def update(self, new_starboard_data: dict) -> None:
        """
        Update a starboard to its current given state
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute(
                "UPDATE starboard SET emoji = $1, emoji_id = $2, minimum_stars = $3, embed_colour = $4, allow_self_star = $5 WHERE channel_id = $6;",
                new_starboard_data["emoji"], new_starboard_data["emoji_id"], new_starboard_data["minimum_stars"],
                new_starboard_data["embed_colour"], new_starboard_data["allow_self_star"], self.channel.id)
        self.emoji = new_starboard_data["emoji"]
        self.emoji_id = new_starboard_data["emoji_id"]
        self.minimum_stars = new_starboard_data["minimum_stars"]
        self.embed_colour = new_starboard_data["embed_colour"]
        self.allow_self_star = new_starboard_data["allow_self_star"]

    async def try_get_entry(self, message_id: int) -> Entry | None:
        """
        Returns either a starboard entry or None if it doesn't exist
        """

        for entry in self.entries:
            if entry.message_id == message_id:
                return entry
        return None

    async def create_entry(self, message_id: int, bot_message_id: int, starboard_channel_id: int,
                           bot: discord.Client) -> None:
        """
        Creates a starboard entry for an existing starboard (adds to the DB too)
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute(
                "INSERT INTO starboard_entry (message_id, starboard_channel_id, bot_message_id) VALUES ($1, $2, $3);",
                message_id, self.channel.id, bot_message_id)
        self.entries.append(await self.Entry.make_entry({
            "message_id": message_id,
            "bot_message_id": bot_message_id,
            "starboard_channel_id": starboard_channel_id
        }, bot))

    async def delete_entry(self, message_id: int) -> None:
        """
        Deletes a starboard entry from an existing starboard (removes from the DB too)
        """

        async with self.bot.pool.acquire() as connection:
            await connection.execute("DELETE FROM starboard_entry WHERE starboard_channel_id = $1 AND message_id = $2;",
                                     self.channel.id, message_id)
        indx = -1
        for i, e in enumerate(
                self.entries):  # TODO: What happens if found_entry is still None after search i.e. entry not found
            if e.message_id == message_id:
                indx = i
                break
        self.entries.pop(indx)
