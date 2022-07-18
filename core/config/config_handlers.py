import copy
from enum import Enum
from typing import Any

import asyncpg
import discord
from discord.ext import commands

from adambot import AdamBot
from libs.misc.utils import get_guild_icon_url, get_user_avatar_url, ContextTypes, get_context_type


class Validation(Enum):
    Channel = 1  # Is a channel that the bot can read/write in
    Role = 2  # Is a valid role
    Integer = 3  # Is a valid integer
    String = 4  # String less than 2000 chars
    Boolean = 5  # Is either a yes/no


def get_validator(value) -> int:
    return getattr(Validation, value)


class ConfigHandlers:
    def __init__(self, bot: AdamBot, cog: commands.Cog) -> None:
        self.bot = bot
        self.cog = cog
        self.Validation = Validation

    async def is_staff(self, ctx: commands.Context | discord.Interaction) -> None | bool:
        """
        Method that checks if a user is staff in their guild or not. `ctx` may be `discord.Message` or `discord.ext.commands.Context`
        """

        ctx_type = get_context_type(ctx)
        if ctx_type is ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            author = ctx.author
        else:
            author = ctx.user

        try:
            staff_role_id = await self.get_config_key(ctx, "staff_role")
            return staff_role_id in [y.id for y in author.roles] or author.guild_permissions.administrator
        except Exception:  # usually ends up being a KeyError. would be neater if all that's relevant can be caught instead
            return False  # prevents daft spam before bot is ready with configs

    def register_config_key(self, name: str, validator_type: str, description: str) -> None:
        if type(validator_type) is str:
            validator_type = getattr(Validation, validator_type, None)

        if [type(a) for a in [name, validator_type, description]] == [str, Validation, str]:
            self.cog.CONFIG[name] = [validator_type, description]

    async def add_all_guild_configs(self) -> None:
        """Adds configs to all guilds - executed on startup"""
        for guild in self.bot.guilds:
            await self.add_config(guild.id)

    async def add_config(self, guild_id: int) -> None:
        """
        Method that gets the configuraton for a guild and puts it into self.bot.configs dictionary (with the guild ID as the key). The data
        is stored in the `config` table. If no configuration is found, a new record is made and a blank configuration dict.
        """

        if guild_id not in self.bot.configs:  # This check (to see if a DB call is needed) is okay because any updates made will be directly made to self.bot.configs (before DB propagation) TODO: Perhaps limit number of items in this
            async with self.bot.pool.acquire() as connection:
                record = await connection.fetchrow("SELECT * FROM config WHERE guild_id = $1;", guild_id)
                if not record:
                    try:
                        await connection.execute("INSERT INTO config (guild_id) VALUES ($1);", guild_id)
                    except asyncpg.exceptions.UniqueViolationError:  # config already exists
                        pass
                    finally:
                        record = await connection.fetchrow("SELECT * FROM config WHERE guild_id = $1;",
                                                           guild_id)  # Fetch configuration record

            keys = list(record.keys())[1:]
            values = list(record.values())[1:]  # Include all keys and values apart from the first one (guild_id)

            i = 0
            while i < len(keys):  # remove phantom keys
                if keys[i] not in self.cog.CONFIG.keys():
                    del keys[i]
                    del values[i]
                    i -= 1
                i += 1

            for key in self.cog.CONFIG:
                if key not in keys:
                    keys.append(key)
                    values.append(None)

            self.bot.configs[guild_id] = dict(
                zip(keys, values))  # Turns the record into a dictionary (column name = key, value = value)

    async def update_config(self, ctx: commands.Context, key: str, value: str) -> None:
        if ctx.guild.id in self.bot.configs:
            self.bot.configs[ctx.guild.id][key] = value
            await self.propagate_config(ctx.guild.id)

    async def get_config_key(self, ctx: commands.Context | discord.Guild | int, key: str) -> Any:
        if isinstance(ctx, discord.Guild):
            ctx_id = ctx.id
        elif hasattr(ctx, "guild"):
            ctx_id = ctx.guild.id
        else:
            ctx_id = ctx
        return self.bot.configs.get(ctx_id, {}).get(key, None)

    async def propagate_config(self, guild_id: int) -> None:
        """
        Method that sends the config data stored in self.bot.configs and propagates them to the DB.
        Should only be called internally ideally.
        """

        async with self.bot.pool.acquire() as connection:
            current_columns = await connection.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'config'")
            current_columns = [column["column_name"] for column in current_columns]

        data = self.bot.configs[guild_id]
        new_data = {}
        for j in data:
            if data.get(j):
                new_data[j] = data[j]

        data = new_data
        length = len(data.keys())

        # Make SQL
        sql_part = ""
        keys = list(data)  # List of the keys (current column names in the database)
        counter = 0
        for i in range(length):
            column_exists = keys[i] in list(current_columns)
            if data.get(keys[i], None):
                if not column_exists:  # create new columns when data needs to be stored
                    async with self.bot.pool.acquire() as connection:
                        validator = self.cog.CONFIG.get(keys[i])[0]
                        if validator in [Validation.Role, Validation.Channel, Validation.Integer]:
                            await connection.execute(f"ALTER TABLE config ADD {keys[i]} BIGINT")
                        elif validator == Validation.Boolean:
                            await connection.execute(f"ALTER TABLE config ADD {keys[i]} BOOLEAN DEFAULT false")
                        else:
                            await connection.execute(f"ALTER TABLE config ADD {keys[i]} VARCHAR(1023)")

            if data.get(keys[i], None) or not data.get(keys[i],
                                                       None) and column_exists:  # need to update table if column exists as there was already data
                sql_part += f"{keys[i]} = (${counter + 1}),"  # For each key, add "{nth key_name} = $n+1"

                counter += 1

        sql = f"UPDATE config SET {sql_part[:-1]} WHERE guild_id = {guild_id};"
        async with self.bot.pool.acquire() as connection:
            await connection.execute(sql, *data.values())

    async def what_prefixes(self, ctx: commands.Context | discord.Interaction) -> None:
        ctx_type = get_context_type(ctx)
        if ctx_type == ContextTypes.Unknown:
            return

        msg = await self.bot.get_used_prefixes(ctx)

        if ctx_type == ContextTypes.Context:
            await ctx.send(str(msg))
        else:
            await ctx.response.send_message(str(msg))

    async def view(self, ctx: commands.Context | discord.Interaction) -> None:
        """
         To get the config options
         1. Copy self.CONFIG into a new variable
         2. Foreach config option, append the option to the list under the specific option's key (this is the embed value)
         3. Pass the dict into EmbedPages for formatting
        """

        if not (ctx.author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        data = copy.deepcopy(self.cog.CONFIG)
        config_dict = self.bot.configs[ctx.guild.id]

        for key in config_dict.keys():
            if key not in data.keys():
                continue  # This clause ensures that variables, e.g. "bruhs", that are in the DB but not in self.CONFIG, do not appear

            if not config_dict[key] or data[key][0] not in [Validation.Channel, Validation.Role]:
                data[key].append(config_dict[key] if config_dict[key] is not None else "*N/A*")

            elif data[key][0] == Validation.Channel:
                channel = ctx.guild.get_channel_or_thread(config_dict[
                                                              key])  # note that this is gonna have to be looked at again if any other types of channels are to be allowed
                data[key].append(f"{channel.mention} ({config_dict[key]})" if channel else "*N/A*")

            elif data[key][0] == Validation.Role:
                role = ctx.guild.get_role(config_dict[key])
                data[key].append(f"{role.mention} ({config_dict[key]})" if role else "*N/A*")

        p = (await self.bot.get_used_prefixes(ctx))[-1]  # guild will be last if set, if not it'll fall back to global
        desc = f"Below are the configurable options for {ctx.guild.name}. To change one, do `{p}config set <key> <value>` where <key> is the option you'd like to change, e.g. `{p}config set qotd_limit 2`"
        embed = self.bot.EmbedPages(
            self.bot.PageTypes.CONFIG,
            data,
            f":tools:  {ctx.guild.name} ({ctx.guild.id}) configuration",
            ctx.author.colour,
            self.bot,
            ctx.author,
            ctx.channel,
            desc=desc,
            thumbnail_url=get_guild_icon_url(ctx.guild),
            icon_url=get_user_avatar_url(ctx.author, mode=1)[0],
            footer=f"Requested by: {ctx.author.display_name} ({ctx.author})\n" + self.bot.correct_time().strftime(
                self.bot.ts_format),
            ctx=ctx
        )
        await embed.set_page(1)  # Default first page
        await embed.send()

    async def set(self, ctx: commands.Context | discord.Interaction, key: str = "", value: str = "") -> None:
        ctx_type = get_context_type(ctx)
        if ctx_type is ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            author = ctx.author
        else:
            author = ctx.user

        if not (author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if not key:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!",
                                                             "You must specify a key to set!")
            return

        if not value:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!",
                                                             "You must specify a value to set the key to!")
            return

        if key == "prefix" and value == self.bot.global_prefix:  # mitigates conflict issue with >1 instances on same DB
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!",
                                                             "This guild-specific prefix is redundant since it's the same as the global prefix!")
            return

        key = key.lower()
        if key not in self.cog.CONFIG.keys():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
            return

        validation_type = self.cog.CONFIG[key][0]
        if validation_type == Validation.Role:
            try:
                role = await commands.RoleConverter().convert(ctx, value)
                value = role
            except commands.errors.RoleNotFound:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That role cannot be found!")
                return

        elif validation_type == Validation.Channel:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, value)
            except commands.errors.ChannelNotFound:
                try:
                    channel = await commands.ThreadConverter().convert(ctx, value)
                except commands.errors.ThreadNotFound:
                    await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That channel cannot be found!")
                    return

            if not channel.permissions_for(ctx.guild.me).send_messages:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx,
                                                                 "I do not have send message permissions in that channel!")
                return
            value = channel

        elif validation_type == Validation.Integer:
            if not value.isdigit():
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!",
                                                                 "Please give me an integer")
                return
            value = int(value)

        elif validation_type == Validation.String:
            if len(value) >= 1000:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!",
                                                                 "The string provided needs to be less than 1000 characters")
                return

        elif validation_type == Validation.Boolean:
            positive = ["yes", "y", "true", "1", "allow"]
            negative = ["no", "n", "0", "disallow", "false"]
            if value.lower() in positive:
                value = True
            elif value.lower() in negative:
                value = False
            else:
                await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "Validation error!",
                                                                 f"The value provided for a boolean must be one of the following: `{'`, `'.join(positive + negative)}`")
                return

        # At this point, the input is valid and can be changed
        if validation_type == Validation.Channel or validation_type == Validation.Role:
            self.bot.configs[ctx.guild.id][key] = value.id
            await self.propagate_config(ctx.guild.id)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!",
                                                               f"It has been changed to '{value.mention}'")  # Value is either a TextChannel, Thread or Role
        else:
            self.bot.configs[ctx.guild.id][key] = value
            await self.propagate_config(ctx.guild.id)
            await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!",
                                                               f"It has been changed to '{value}'")

    async def remove(self, ctx: commands.Context | discord.Interaction, key: str) -> None:

        ctx_type = get_context_type(ctx)
        if ctx_type is ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            author = ctx.author
        else:
            author = ctx.user

        if not (author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        key = key.lower()
        if key not in self.cog.CONFIG.keys():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
            return

        self.bot.configs[ctx.guild.id][key] = None
        await self.propagate_config(ctx.guild.id)
        await self.bot.DefaultEmbedResponses.success_embed(self.bot, ctx, f"{key} has been updated!",
                                                           "It has been changed to ***N/A***")

    async def current(self, ctx: commands.Context | discord.Interaction, key: str) -> None:

        ctx_type = get_context_type(ctx)
        if ctx_type is ContextTypes.Unknown:
            return

        if ctx_type == ContextTypes.Context:
            author = ctx.author
        else:
            author = ctx.user

        if not (author.guild_permissions.administrator or await self.is_staff(ctx)):
            await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        config_dict = self.bot.configs[ctx.guild.id]
        key = key.lower()
        if key not in self.cog.CONFIG.keys():
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, "That is not a valid configuration option!")
            return

        if self.cog.CONFIG[key][0] == Validation.Channel:
            current = ctx.guild.get_channel(config_dict[key])
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",
                                                                   current.mention if current else "***N/A***")
        elif self.cog.CONFIG[key][0] == Validation.Role:
            current = ctx.guild.get_role(config_dict[key])
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",
                                                                   current.mention if current else "***N/A***")
        else:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Current value of {key}",
                                                                   config_dict[key] if config_dict[
                                                                       key] else "***N/A***")

    async def prefix(self, ctx: commands.Context | discord.Interaction, new_prefix: str = "") -> None:
        await self.add_config(ctx.guild.id)

        if new_prefix is None:
            prefix = await self.get_config_key(ctx, "prefix")
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Current value of prefix", prefix)
        else:
            if not (ctx.author.guild_permissions.administrator or await self.is_staff(ctx)):
                await self.bot.DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            else:
                await ctx.invoke(self.bot.get_command("config set"), "prefix", new_prefix)

    async def staffcmd(self, ctx: commands.Context | discord.Interaction) -> None:
        if await self.is_staff(ctx):  # can just use self ref
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "You are staff!",
                                                                   desc="Hello staff member!")
        else:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Disaster has struck!",
                                                                   desc="You are not staff!")
