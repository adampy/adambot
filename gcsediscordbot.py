import discord
from discord.ext.commands import Bot
from discord.ext import commands
from discord.ext.tasks import loop
from discord.utils import get
import asyncio
import time
import os
import psycopg2
from datetime import datetime
from csv import reader

#-----------------------------------------------------------------

# Move logging into a seperate cog for readability

#order trivia leaderboard by score
#add score to trivia

#fix remind command
#create poll command
#helper command w/ cooldown

#-----------------------------------------------------------------

def get_credentials():
    '''Command that checks if a credentials file is available. If it is it puts the vars into environ and returns True, else returns False'''
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

        self.COGS = cogs
        
        self.LOCAL_HOST = local
        self.DB = os.environ.get('DATABASE_URL')
        self.start_up()

    def start_up(self):
        '''Command that starts AdamBot, is run in AdamBot.__init__'''
        self.load_cogs()
        self.loop.create_task(self.execute_todos())
        self.run(os.environ.get('TOKEN'))

    def load_cogs(self):
        '''Loads all the cogs passed into AdamBot'''
        for cog in self.COGS:
            #if cog == "trivia" and self.LOCAL_HOST: # Don't load trivia if running locally
             #   continue
            self.load_extension(f'cogs.{cog}')
            print(f"Loaded: {cog}")

    async def on_ready(self):
        print('Bot Loaded')
        await self.change_presence(activity=discord.Game(name='Type -help for help'))

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)

    async def execute_todos(self):
        '''The loop that continually checks the DB for todos'''
        conn = psycopg2.connect(self.DB, sslmode='require')
        cur = conn.cursor()
        await self.wait_until_ready()
        while True:
            conn = psycopg2.connect(self.DB, sslmode='require')
            cur = conn.cursor()
            cur.execute('SELECT * FROM todo WHERE todo_time <= now()')
            todos = cur.fetchall()
            for todo in todos:
                try:
                    if todo[1] == 1: #unmute
                        member = get(self.get_all_members(), id=todo[3])
                        await member.remove_roles(get(member.guild.roles, name='Muted'), reason='Auto unmuted')
                        cur.execute('DELETE FROM todo WHERE id = %s',(todo[0],))
                        conn.commit()
                    elif todo[1] == 2: #unban
                        user = await self.fetch_user(todo[3])
                        guild = self.get_guild(445194262947037185)
                        await guild.unban(user, reason='Auto unbanned')
                        cur.execute('DELETE FROM todo WHERE id = %s',(todo[0],))
                        conn.commit()
                except Exception as e:
                    print(e)
                    cur.execute('DELETE FROM todo WHERE id = %s',(todo[0],))
                    conn.commit()

            cur.execute('SELECT * FROM remind WHERE reminder_time <= now()')
            reminds = cur.fetchall()
            for remind in reminds:
                try:
                    member = get(self.get_all_members(), id=remind[1])
                    message = f'{member.mention} You told me to remind you about this:\n{remind[3]}'
                    await member.send(message)
                    cur.execute('DELETE FROM remind WHERE id = %s',(remind[0],))
                    conn.commit()
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
            cur.execute('DELETE FROM invites')
            for invite in invites:
                try:
                    data = [invite.inviter.id,
                            invite.code,
                            invite.uses,
                            invite.max_uses,
                            invite.created_at,
                            invite.max_age]

                    cur.execute('INSERT INTO invites (inviter, code, uses, max_uses, created_at, max_age) values (%s, %s, %s, %s, %s, %s)', data)
                except:
                    pass
            conn.commit()
            conn.close()

            await asyncio.sleep(5)

if __name__ == "__main__":
    local_host = get_credentials()

    intents = discord.Intents.default()
    intents.members = True

    cogs = ['member',
        'moderation',
        'questionotd',
        'waitingroom',
        'support',
        'reputation',
        'trivia',
        'private',]

    bot = AdamBot(local_host, cogs, command_prefix='-', intents=intents)
    #bot = commands.Bot(command_prefix=PREFIX, intents=intents)
    #bot.remove_command("help")

