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

LOCAL_HOST = False
try:
    with open('credentials.csv') as f:
        for credential in reader(f):
            os.environ[credential[0]] = credential[1]
    LOCAL_HOST = True
except FileNotFoundError:
    pass

DB = os.environ.get('DATABASE_URL')
TOKEN = os.environ.get('TOKEN')

COGS = ['member',
        'moderation',
        'questionotd',
        'waitingroom',
        'support',
        'reputation',
        'trivia',]
PREFIX = '-'

#purge mental health, purge serious command
#support connections command
#warnlist pages
#qotd member not found error
#purge for specific member
#order trivia leaderboard by score
#add score to trivia leaderboard

#-----------------------------------------------------------------

bot = commands.Bot(command_prefix=PREFIX)
#bot.remove_command("help")

conn = psycopg2.connect(DB, sslmode='require')
cur = conn.cursor()

@bot.event
async def on_ready():
    print('Bot Loaded')
    await bot.change_presence(activity=discord.Game(name='Type -help for help'))

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

@bot.command()
async def host(ctx):
    '''Check if the bot is currently hosted locally or remotely'''
    await ctx.send(f"Adam-bot is {'locally' if LOCAL_HOST else 'remotely'} hosted right now.")

#-----------------------------------------------------------------

for cog in COGS:
    bot.load_extension(f'cogs.{cog}')

async def execute_todos():
    await bot.wait_until_ready()
    while True:
        conn = psycopg2.connect(DB, sslmode='require')
        cur = conn.cursor()
        cur.execute('SELECT * FROM todo WHERE todo_time <= now()')
        todos = cur.fetchall()
        for todo in todos:
            try:
                if todo[1] == 1: #unmute
                    member = get(bot.get_all_members(), id=todo[3])
                    await member.remove_roles(get(member.guild.roles, name='Muted'), reason='Auto unmuted')
                    cur.execute('DELETE FROM todo WHERE id = %s',(todo[0],))
                    conn.commit()
                elif todo[1] == 2: #unban
                    user = await bot.fetch_user(todo[3])
                    guild = bot.get_guild(445194262947037185)
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
                member = get(bot.get_all_members(), id=remind[1])
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
        #   await bot.get_channel(445199175244709898).send(f'**17:38** {members} https://cdn.discordapp.com/attachments/418467941294538772/577594985369829386/1738.compressed.mp4')
        
        #invite stuffs
        guild = bot.get_guild(445194262947037185)
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


bot.loop.create_task(execute_todos())
bot.run(TOKEN)

