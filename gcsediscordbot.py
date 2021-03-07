import discord
from discord.ext.commands import Bot
from discord.ext import commands
from discord.ext.tasks import loop
from discord.utils import get
import asyncio
import time
import os
from datetime import datetime, timedelta
from csv import reader
import asyncpg
from cogs.utils import EmojiEnum, Todo

#-----------------------------------------------------------------

# Move logging into a seperate cog for readability
#create poll command
#helper command w/ cooldown

#-----------------------------------------------------------------

def get_credentials():
    """Command that checks if a credentials file is available. If it is it puts the vars into environ and returns True, else returns False"""
    try:
        with open('credentials.csv') as f:
            for credential in reader(f):
                os.environ[credential[0]] = credential[1]
        return True
    except FileNotFoundError:
        return False

class AdamBot(Bot):
    def __init__(self, local, cogs, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.online = True
        self.COGS = cogs
        self.LOCAL_HOST = local
        self.DB = os.environ.get('DATABASE_URL')
        self.pages = [] # List of active pages that can be used
        self.prefix = kwargs.get("command_prefix", "-") # Defaults to "-" TODO: Can this be a required parameter instead of being in **kwargs?

        self.start_up()
        
    async def close(self, ctx = None): # ctx = None because this is also called upon CTRL+C in command line
        """Procedure that closes down AdamBot, using the standard client.close() command, as well as some database hadling methods."""
        self.online = False # This is set to false to prevent DB things going on in the background once bot closed
        if ctx: await ctx.send(f"Beginning process of shutting {self.user.mention} down. DB pool shutting down...")
        self.pool.terminate() # TODO: Make this more graceful
        if ctx: await ctx.send("Closing connection to Discord...")
        await self.change_presence(status = discord.Status.offline)
        await super().close()
        self.loop.stop()
        print("Bot closed.")

    def start_up(self):
        """Command that starts AdamBot, is run in AdamBot.__init__"""
        self.load_cogs()
        self.loop.create_task(self.execute_todos())
        self.pool : asyncpg.pool.Pool = self.loop.run_until_complete(asyncpg.create_pool(self.DB + "?sslmode=require", max_size=20))
        self.last_active = {} # easiest to put here for now, may move to a cog later
        self.run(os.environ.get('TOKEN'))

    def load_cogs(self):
        """Loads all the cogs passed into AdamBot"""
        for cog in self.COGS:
            if cog == "trivia" and self.LOCAL_HOST: # Don't load trivia if running locally
                continue
            self.load_extension(f'cogs.{cog}')
            print(f"Loaded: {cog}")

    async def on_ready(self):
        print('Bot Loaded')
        await self.change_presence(activity=discord.Game(name = f'Type {self.prefix}help for help'), status=discord.Status.online)

    async def on_message(self, message):
        """Event that has checks that stop bots from executing commands"""
        if message.author.bot:
            return
        if message.guild.id not in self.last_active:
            self.last_active[message.guild.id] = [] # create the dict key for that guild if it doesn't exist
        last_active_list = self.last_active[message.guild.id]
        if message.author in last_active_list:
            last_active_list.remove(message.author)
        last_active_list.insert(0, message.author)
        await self.process_commands(message)

    async def on_reaction_add(self, reaction, user):
        """Subroutine used to control EmbedPages stored within self.pages"""
        if not user.bot:
            for page in self.pages:
                if reaction.message == page.message and user == page.initiator:
                    # Do stuff
                    if reaction.emoji == EmojiEnum.LEFT_ARROW:
                        await page.previous_page()
                    elif reaction.emoji == EmojiEnum.RIGHT_ARROW:
                        await page.next_page()
                    elif reaction.emoji == EmojiEnum.CLOSE:
                        await reaction.message.delete()
                    elif reaction.emoji == EmojiEnum.MIN_BUTTON:
                        await page.first_page()
                    elif reaction.emoji == EmojiEnum.MAX_BUTTON:
                        await page.last_page()

                    await reaction.message.remove_reaction(reaction.emoji, user)
                    break

    async def on_message_delete(self, message):
        """Event that ensures that memory is freed up once a message containing an embed page is deleted."""
        for page in self.pages:
            if message == page.message:
                del page
                break

    async def execute_todos(self):
        """The loop that continually checks the DB for todos.
The todo table looks like:
	id SERIAL PRIMARY KEY,
	todo_id int,
	todo_time timestamptz,
	member_id bigint
member_id may not always be a member ID, and can sometimes be a FK to demographic_roles.id"""
        await self.wait_until_ready()
        while self.online:
            async with self.pool.acquire() as connection:
                todos = await connection.fetch('SELECT * FROM todo WHERE todo_time <= now()')
                for todo in todos:
                    try:
                        if todo[1] == Todo.UNMUTE:
                            member = get(self.get_all_members(), id=todo[3])
                            await member.remove_roles(get(member.guild.roles, name='Muted'), reason='Auto unmuted')
                            await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])
                        
                        elif todo[1] == Todo.UNBAN:
                            user = await self.fetch_user(todo[3])
                            guild = self.get_guild(445194262947037185)
                            await guild.unban(user, reason='Auto unbanned')
                            await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])

                        elif todo[1] == Todo.DEMOGRAPHIC_SAMPLE or todo[1] == Todo.ONE_OFF_DEMOGRAPHIC_SAMPLE:
                            demographic_role_id = todo[3]
                            results = await connection.fetch("SELECT role_id, guild_id, sample_rate FROM demographic_roles WHERE id = $1", demographic_role_id)
                            guild = self.get_guild(results[0][1])
                            role_id = results[0][0]
                            sample_rate = results[0][2]
                            n = len([x for x in guild.members if role_id in [y.id for y in x.roles]])
                            await connection.execute("INSERT INTO demographic_samples (n, role_reference) VALUES ($1, $2)", n, demographic_role_id)
                            await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])

                            if todo[1] == Todo.DEMOGRAPHIC_SAMPLE: # IF NOT A ONE OFF SAMPLE, PERFORM IT AGAIN
                                await connection.execute("INSERT INTO todo (todo_id, todo_time, member_id) VALUES ($1, $2, $3)", Todo.DEMOGRAPHIC_SAMPLE, datetime.utcnow() + timedelta(days = sample_rate), demographic_role_id)

                    except Exception as e:
                        print(e)
                        await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])

                reminds = await connection.fetch('SELECT * FROM remind WHERE reminder_time <= now()')
                for remind in reminds:
                    try:
                        member = get(self.get_all_members(), id=remind[1])
                        message = f'You told me to remind you about this:\n{remind[3]}'
                        await member.send(message)
                        await connection.execute('DELETE FROM remind WHERE id = ($1)', remind[0])
                    except Exception as e:
                        print(e)

                #1738 stuffs
                #now = datetime.utcnow()
                #if now.hour+1 == 17 and now.minute == 38 and now.second < 5:
                #   cur.execute("SELECT * FROM ping")
                #   members = ' '.join([f'<@{x[0]}>' for x in cur.fetchall()])
                #   await self.get_channel(445199175244709898).send(f'**17:38** {members} https://cdn.discordapp.com/attachments/418467941294538772/577594985369829386/1738.compressed.mp4')

                #Results day countdown stuffs
                #now = datetime.utcnow()
                #msg = await self.get_channel(743235561015476236).fetch_message(744611462244466689)
                #if now >= RESULTS_DAY:
                #    #after results day
                #    await msg.edit(content="RESULTS DAY IS HERE! GOOD LUCK! Please put your grades here!")
                #elif now < RESULTS_DAY:
                #    time_left = RESULTS_DAY - datetime.utcnow()
                #
                #    m, s = divmod(time_left.seconds, 60)
                #    h, m = divmod(m, 60)
                #
                #    await msg.edit(content=f'''**LIVE** GCSE Results day countdown!
        #**{time_left.days}** days
        #**{h}** hours
        #**{m}** minutes
        #**{s}** seconds
        #left until 8AM on results day. GOOD LUCK!!! :ok_hand:''')

                #invite stuffs
                guild = self.get_guild(445194262947037185)
                invites = await guild.invites()
                await connection.execute('DELETE FROM invites')
                new_invites = []
                for invite in invites:
                    data = [invite.inviter.id,
                            invite.code,
                            invite.uses,
                            invite.max_uses,
                            invite.created_at,
                            invite.max_age]
                    new_invites.append(data)
                await connection.executemany('INSERT INTO invites (inviter, code, uses, max_uses, created_at, max_age) values ($1, $2, $3, $4, $5, $6)', new_invites)
                

            await asyncio.sleep(5)

if __name__ == "__main__":
    local_host = get_credentials()

    intents = discord.Intents.default()
    intents.members = True
    intents.presences = True
    intents.reactions = True

    cog_names = ['member',
        'moderation',
        'questionotd',
        'waitingroom',
        'support',
        'reputation',
        'trivia',
        'private',
        'demographics',
        'spotify',
        'warnings',]

    bot = AdamBot(local_host, cog_names, command_prefix='-', intents=intents)
    #bot.remove_command("help")

