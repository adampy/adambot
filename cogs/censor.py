import discord
from discord.ext import commands
from discord.utils import get
import asyncio
import ast  # using ast for literal_eval, stops code injection
import asyncpg
from .utils import DefaultEmbedResponses

class Censor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_is_command(self, message):
        """
        Checks whether or not `message` is a valid censor command or not
        """
        ctx = await self.bot.get_context(message)
        content = message.content
        prefixes = await self.bot.get_used_prefixes(message)
        prefixes.sort(key=len, reverse=True)
        for prefix in prefixes:
            if content.startswith(prefix):
                content = content.replace(prefix, "")
                break
        is_command = True if (await self.bot.is_staff(ctx) and content.startswith(
            "censor") and content != message.content) else False
        return is_command

    async def load_censors(self, guild):
        """
        Method used to load censor data for all guilds into self.censors
        """
        async with self.bot.pool.acquire() as connection:
            prop = await connection.fetchval('SELECT censors FROM censor WHERE guild_id = $1', guild.id)
            if not prop:
                await connection.execute('INSERT INTO censor (guild_id, censors) VALUES ($1, $2)', guild.id, "[]")
                self.censors[guild.id] = []
            else:
                prop = ast.literal_eval(prop)
                if type(prop) is not list:
                    await connection.execute('UPDATE censor SET censors = $1 WHERE guild_id = $2', "[]", guild.id)
                    self.censors[guild.id] = []
                else:
                    self.censors[guild.id] = prop

    async def propagate_new_guild_censor(self, guild):
        """
        Method used for pushing censor changes to the DB
        """
        async with self.bot.pool.acquire() as connection:
            await connection.execute('UPDATE censor SET censors = $1 WHERE guild_id = $2', str(self.censors[guild.id]), guild.id)

    # ---LISTENERS---

    @commands.Cog.listener()
    async def on_ready(self):
        # Maybe tweak this so the tables are only created on the fly as and when they are needed?
        self.censors = {}
        success = False
        while not success:  # race condition for table to be created otherwise
            try:
                for guild in self.bot.guilds:
                    await self.load_censors(guild)
                    success = True
            except asyncpg.exceptions.UndefinedTableError:
                success = False
                print("Censor table doesn't exist yet, waiting 1 second...")
                await asyncio.sleep(1)

    @commands.Cog.listener()
    async def on_message(self, message):
        ctx = await self.bot.get_context(message)
        is_command = await self.check_is_command(message)
        if not is_command and message.author.id == self.bot.user.id and message.reference:
            is_command = await self.check_is_command(await ctx.fetch_message(message.reference.message_id))

        if True in [phrase.lower() in message.content.lower() for phrase in self.censors[message.guild.id]] and not is_command:
            # case insensitive is probably the best idea
            await message.delete()

    @commands.group()
    @commands.guild_only()
    async def censor(self, ctx):
        if not ctx.invoked_subcommand:
            prefixes = await self.bot.get_used_prefixes(ctx.message) # TODO: Is there a nicer way to get the prefix, if not change all previous occasions of getting the prefix to this
            await ctx.reply(f"Type `{prefixes[2]}help censor` to get info!")

    @censor.command()
    @commands.guild_only()
    async def add(self, ctx, *, text):
        """
        Allows adding a filtered phrase for the guild. Staff role needed.
        """
        if not await self.bot.is_staff(ctx.message):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if text not in self.censors[ctx.guild.id]:
            if True in [phrase in text for phrase in self.censors[ctx.guild.id]]:
                """
                If A is in the censor there's no point adding AB to the censor
                """
                await ctx.message.reply(f"||{text}|| wasn't added to the censor since another censored phrase is contained within it, meaning messages containing it will be removed")
                return
            message = f"Added ||{text}|| to the censor!"
            check = [text in phrase for phrase in self.censors[ctx.guild.id]]  # de-duplicate
            removed = []
            while True in check:
                index = check.index(True)
                del check[index]
                removed.append(f"||{self.censors[ctx.guild.id][index]}||")
                del self.censors[ctx.guild.id][index]
            message = message if not removed else (message + "\n\nRemoved some redundant phrases from the censor:\n " + "\n ".join(removed))
            self.censors[ctx.guild.id].append(text)
            await self.propagate_new_guild_censor(ctx.guild)
            await DefaultEmbedResponses.success_embed(self.bot, ctx, "Censor added!", desc = message)
        else:
            await DefaultEmbedResponses.error_embed(self.bot, ctx, "That's already in the censor!")

    @censor.command()
    @commands.guild_only()
    async def remove(self, ctx, *, text):
        """
        Allows removing a filtered phrase for the guild. Staff role needed.
        """
        if not await self.bot.is_staff(ctx.message):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        if text not in self.censors[ctx.guild.id]:
            await DefaultEmbedResponses.error_embed(self.bot, ctx, "No such thing is being censored!")
        else:
            del self.censors[ctx.guild.id][self.censors[ctx.guild.id].index(text)]
            await self.propagate_new_guild_censor(ctx.guild)
            await DefaultEmbedResponses.success_embed(self.bot, ctx, "Censor removed!")

    @censor.command(name="list")
    @commands.guild_only()
    async def list_censor(self, ctx):
        """
        Allows viewing the list of filtered phrases for the guild. Staff role needed.
        """
        if not await self.bot.is_staff(ctx.message):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        msg_content = ("\n".join([f"• ||{word}||" for word in self.censors[ctx.guild.id]])) if self.censors[ctx.guild.id] else "Nothing to show here!"
        await DefaultEmbedResponses.information_embed(self.bot, ctx, f"{ctx.guild.name} censors", desc = msg_content)

    @censor.command(name="clear")
    @commands.guild_only()
    async def clear_censor(self, ctx):
        """
        Allows clearing the list of filtered phrases for the guild. Staff role needed.
        """
        if not await self.bot.is_staff(ctx.message):
            await DefaultEmbedResponses.invalid_perms(self.bot, ctx)
            return

        self.censors[ctx.guild.id] = []
        await self.propagate_new_guild_censor(ctx.guild)
        await DefaultEmbedResponses.success_embed(self.bot, ctx, "Censors cleared!", desc = f"All censors in **{ctx.guild.name}** have been cleared")

def setup(bot):
    bot.add_cog(Censor(bot))
