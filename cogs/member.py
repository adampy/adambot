import discord
from discord.ext import commands
from discord.utils import get
from discord.errors import NotFound
from discord import Embed, Colour, Status
from .utils import separate_args, DISALLOWED_COOL_WORDS, Permissions, CODE_URL
import requests
import re
import os
from datetime import datetime, timedelta
import asyncpg
from random import choice as randchoice
import asyncio

class Member(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

#-----------------------MISC------------------------------

    @commands.command(pass_context=True)
    async def host(self, ctx):
        '''Check if the bot is currently hosted locally or remotely'''
        await ctx.send(f"Adam-bot is {'**locally**' if self.bot.LOCAL_HOST else '**remotely**'} hosted right now.")

#-----------------------REVISE------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def revise(self, ctx):
        '''Puts you in revising mode.'''
        member = ctx.author
        if member.bot: # Stops bots from putting theirselves into revising mode
            return
        role = get(member.guild.roles, name='Members')
        await member.remove_roles(role)
        role = get(member.guild.roles, name='Revising')
        await member.add_roles(role)
        await self.bot.get_channel(518901847981948938).send(f'{member.mention} Welcome to revising mode! Have fun revising and once you\'re done type `-stoprevising` in this channel!')

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def stoprevising(self, ctx):
        '''Exits revising mode.'''
        member = ctx.author
        if ctx.channel.id == 518901847981948938:
            role = get(member.guild.roles, name='Revising')
            await member.remove_roles(role)
            role = get(member.guild.roles, name='Members')
            await member.add_roles(role)
            await self.bot.get_channel(445199175244709898).send(f'{member.mention} welcome back from revising mode!')
        else:
            channel = self.bot.get_channel(518901847981948938) # Revision escape
            await ctx.send(f'Go to {channel.mention} to stop revising')

#-----------------------LIST------------------------------

    @commands.command(pass_context=True)
    @commands.guild_only()
    async def list(self, ctx, *args):
        '''Gives you a list of all the people with a certain role.'''
        #if role not entered
        if len(args) <= 0:
            await ctx.send(':x: Please **specify** a **role**')
            return
        
        #gets the roles that it could be
        role_name = ' '.join(args)
        role_id = ctx.message.guild.roles[0]
        possible_roles = []
        for role in ctx.message.guild.roles:
            if role_name.lower() == role.name.lower():
                possible_roles.clear() # Removes bug
                possible_roles.append(role)
                break
            elif role_name.lower() in role.name.lower():
                possible_roles.append(role)

        #narrows it down to 1 role and gets the role id
        if len(possible_roles) == 0:
            await ctx.send(':x: That role does not exist')
        elif len(possible_roles) > 1:
            new_message = 'Multiple roles found. Please try again by entering one of the following roles.\n```'
            new_message = new_message + '\n'.join([role.name for role in possible_roles]) + '```'
            await ctx.send(new_message)
            return
        else: #when successful
            role = possible_roles[0]
            message = []
            people = []
            #gets all members with that role
            for member in ctx.message.guild.members:
                for search_role in member.roles:
                    if search_role == role:
                        people.append(member)
                        message.append(f'`{member.id}` **{member.name}**')
                        break
            new_message = '\n'.join(message)
            new_message += f"\n------------------------------------\n:white_check_mark: I found **{str(len(message))}** user{'' if len(message) == 0 else 's'} with this role."
            try:
                await ctx.send(new_message)
            except Exception as e: #longer than 2000 letters causes this to be run
                new_message = '\n'.join([f'**{member.nick if member.nick else member.name}**' for member in people])
                new_message += f'\n------------------------------------\n:white_check_mark: I found **{str(len(message))}** users with this role.'
                if len(new_message) >= 2000:
                    params = {'api_dev_key':self.pastebin,
                              'api_option':'paste',
                              'api_paste_code':new_message,
                              'api_paste_private':'1',
                              'api_paste_expire_date':'1D',
                              'api_paste_name':role.name}

                    req = requests.post('https://pastebin.com/api/api_post.php', params)
                    await ctx.send(f'Over 2000 characters. Go to {req.text} to see what I would have said')
                else:
                    await ctx.send('Longer than 2000 characters - member ID\'s have been cut from the message.')
                    await ctx.send(new_message)

#-----------------------MC & CC & WEEABOO------------------------------
    addableRoles =	{
            "mc": "Maths Challenge",
            "cc": "CompSci Challenge",
            "weeaboo": "Weeaboo",
            "announcement": "Announcements"
        }

    async def assignRole(self, ctx, roleID):
        roleName = self.addableRoles[roleID]
        author = ctx.author
        role = get(author.guild.roles, name=roleName)
        if roleName in [y.name for y in author.roles]:
            await author.remove_roles(role)
            await ctx.send(':ok_hand: Your `{0}` role has vanished!'.format(roleName))
        else:
            await author.add_roles(role)
            await ctx.send(':ok_hand: You have been given `{0}` role!'.format(roleName))

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def mc(self, ctx):
        '''Gives you the Maths Challenge role.'''
        await self.assignRole(ctx, "mc")

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def cc(self, ctx):
        '''Gives you the CompSci Challenge role.'''
        await self.assignRole(ctx, "cc")

#    @commands.command(pass_context=True)
#    @commands.has_role('Members')
#    @commands.guild_only()
#    async def lc(self, ctx):
#        '''Gives you the Languages Challenge role.'''
#        author = ctx.author
#       role = get(author.guild.roles, name='Languages Challenge')
#       if 'Languages Challenge' in [y.name for y in author.roles]:
#            await author.remove_roles(role)
#            await ctx.send(':ok_hand: Your `Languages Challenge` role has vanished!')
#        else:
#            await author.add_roles(role)
#            await ctx.send(':ok_hand: You have been given `Languages Challenge` role!')

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def weeaboo(self, ctx):
        '''Gives you the Weeaboo role.'''
        await self.assignRole(ctx, "weeaboo")

    @commands.command(pass_context=True, aliases=['announcements', 'notifications'])
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def announcement(self, ctx):
        '''Gives you the Announcements role.'''
        await self.assignRole(ctx, "announcement")

#-----------------------QUOTE------------------------------

    @commands.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    async def quote(self, ctx, messageid, channelid=None):
        '''Quote a message to remember it.'''
        if channelid is not None:
            try:
                channel = self.bot.get_channel(int(channelid))
            except ValueError:
                await ctx.send('Please use a channel id instead of words.')
        else:
            channel = ctx.message.channel

        try:
            msg = await channel.fetch_message(messageid)
        except Exception as e:
            await ctx.send('```-quote <message_id> [channel-id]```')
            return
        
        user = msg.author
        image = None
        repl = re.compile(r"/(\[.+?\])(\(.+?\))/")
        edited = f" (edited at {msg.edited_timestamp.isoformat(' ', 'seconds')})" if msg.edited_at else ''
        
        content = re.sub(repl, r"\1​\2", msg.content)
        
        if msg.attachments:
            image = msg.attachments[0]['url']
        
        embed = Embed(title="Quote link", 
                              url=f"https://discordapp.com/channels/{channelid}/{messageid}",
                              color=user.color,
                              timestamp=msg.created_at)
        
        if image:
            embed.set_image(url=image)
        embed.set_footer(text=f"Sent by {user.name}#{user.discriminator}", icon_url=user.avatar_url)
        embed.description = f"❝ {content} ❞" + edited
        await ctx.send(embed=embed)
        
        try:
            await ctx.message.delete()
        except Exception as e:
            print(e)

#-----------------------DEMOGRAPHICS------------------------------
    @commands.command()
    @commands.has_any_role(*Permissions.MEMBERS)
    @commands.guild_only()
    async def demographics(self, ctx):
        '''View server demographics.'''
        numbers = []
        numbers.append(len(ctx.guild.members))
        for role in ['Post-GCSE', 'Y11', 'Y10', 'Y9']:
            numbers.append(len([x for x in ctx.guild.members if role in [y.name for y in x.roles]]))
        message = """We have {} members.
        
{} Post-GCSE
{} Year 11s
{} Year 10s
{} Year 9s""".format(*numbers)
        await ctx.send(message)

#-----------------------FUN------------------------------
#    @commands.command()
#    @commands.guild_only()
#    async def zyclos(self, ctx):
#        zyclos = get(ctx.guild.members, id=202861110146236428)
#        await ctx.send(f'{zyclos.mention} https://tenor.com/view/jusreign-punjabi-indian-gif-5441330')


    @commands.command()
    async def test(self, ctx):
        '''Secret Area 51 command.'''
        await ctx.send('Testes')
        
    @commands.Cog.listener()
    async def on_message(self, message):
        conditions = not message.author.bot and not message.content.startswith('-') and not message.author.id == 525083089924259898
        msg = message.content.lower()
        
        if 'bruh' in msg and conditions:
            async with self.bot.pool.acquire() as connection:
                result = await connection.fetchval("SELECT value FROM variables WHERE variable = 'bruh';")
                await connection.execute("UPDATE variables SET value = ($1) WHERE variable = 'bruh';", str(int(result)+1))
        elif ('joe' in msg or 'marj' in msg) and conditions:
            if 'http' in msg:
                await message.channel.send("STOP SENDING JOE MARJ GIF")
            else:
                await message.channel.send("STOP SAYING JOE MARJ")
        ##elif '5 days' in msg and conditions:
        ##    await message.channel.send('Top Shagger :sunglasses:')
        ##elif ('snorting rep' in msg or 'xp3dx' in msg) and conditions:
        ##    await message.channel.send('very attractive man :heart_eyes:')
        ##elif ('sarman' in msg or 'ramen' in msg) and conditions:
        ##    await message.channel.send('Sarman\'s Ramen, come get yo ramen from my store. It\'s amazing and you have a sekc host')
        elif msg == 'need to revise' and conditions:
            await revise(message)
        elif msg == 'stop revising' and conditions:
            await stoprevising(message)
        return
        

    @commands.command(aliases=['bruh'])
    async def bruhs(self, ctx):
        '''See how many bruh moments we've had'''
        async with self.bot.pool.acquire() as connection:
            bruhs = await connection.fetchval("SELECT value FROM variables WHERE variable = 'bruh'")
            await ctx.send(f'Bruh moments: **{bruhs}**')
            return

    @commands.command()
    async def cool(self, ctx, *message):
        '''MaKe YoUr MeSsAgE cOoL'''
        text = ' '.join(message)
        if text.lower() in DISALLOWED_COOL_WORDS:
            await ctx.send("You can't make that message cool!")
            return
        new = ''
        for index, letter in enumerate(text):
            try:
                if letter == ' ':
                    new += letter
                elif index % 2 == 0:
                    new += letter.lower()
                else:
                    new += letter.upper()
            except Exception as e:
                new += letter

        await ctx.send(new)

    @commands.command(aliases=['yikes'])
    async def yike(self, ctx):
        await ctx.send('https://cdn.discordapp.com/attachments/445199175244709898/616755258890387486/29e02f54-4741-40e5-b77d-788bf78b33ba.png')

#-----------------------USER AND SERVER INFO------------------------------

    @commands.command(pass_context = True)
    @commands.guild_only()
    async def serverinfo(self, ctx):
        '''Information about the server.'''
        guild = ctx.message.guild
        time = guild.created_at
        time_since = datetime.utcnow() - time

        join = Embed(title=f'**__{str(guild)}__**', description=f"Since {time.strftime('%d %b %Y %H:%M')}. That's over {time_since.days} days ago!", value='Server Name', color=Colour.from_rgb(21,125,224))
        join.set_thumbnail(url=guild.icon_url)

        join.add_field(name='Region', value=str(guild.region))
        join.add_field(name='Users', value=f'{len([x for x in guild.members if x.status != Status.offline])}/{len(guild.members)}')
        join.add_field(name='Text Channels', value=f'{len(guild.text_channels)}')
        join.add_field(name='Voice Channels', value=f'{len(guild.voice_channels)}')
        join.add_field(name='Roles', value=f'{len(guild.roles)}')
        join.add_field(name='Owner', value=f'{str(guild.owner)}')
        join.set_footer(text=f'Server ID: {guild.id}')

        await ctx.send(embed=join)
            
    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def userinfo(self, ctx, *, user: discord.Member = None):
        '''Information about you or a user'''
        author = ctx.author
        guild = ctx.guild

        if not user:
            user = author

        roles = user.roles[-1:0:-1]

        joined_at = user.joined_at
        since_created = (ctx.message.created_at - user.created_at).days
        
        if joined_at is not None:
            since_joined = (ctx.message.created_at - joined_at).days
            user_joined = joined_at.strftime("%d %b %Y %H:%M")
        else:
            since_joined = "?"
            user_joined = "Unknown"
        user_created = user.created_at.strftime("%d %b %Y %H:%M")
        voice_state = user.voice
        member_number = (
            sorted(guild.members, key=lambda m: m.joined_at or ctx.message.created_at).index(user)
            + 1
        )

        created_on = "{}\n({} days ago)".format(user_created, since_created)
        joined_on = "{}\n({} days ago)".format(user_joined, since_joined)

        activity = "Chilling in {} status".format(user.status)
        if user.activity is None:  # Default status
            pass
        elif user.activity.type == discord.ActivityType.playing:
            activity = "Playing {}".format(user.activity.name)
        elif user.activity.type == discord.ActivityType.streaming:
            activity = "Streaming [{}]({})".format(user.activity.name, user.activity.url)
        elif user.activity.type == discord.ActivityType.listening:
            activity = "Listening to {}".format(user.activity.name)
        elif user.activity.type == discord.ActivityType.watching:
            activity = "Watching {}".format(user.activity.name)

        if roles:
            roles = ", ".join([str(x) for x in roles])
        else:
            roles = None

        data = Embed(description=activity, colour=user.colour)
        data.add_field(name="Joined Discord on", value=created_on)
        data.add_field(name="Joined this server on", value=joined_on)
        if roles is not None:
            data.add_field(name="Roles", value=roles, inline=False)
        if voice_state and voice_state.channel:
            data.add_field(
                name="Current voice channel",
                value="{0.mention} ID: {0.id}".format(voice_state.channel),
                inline=False,
            )
        data.set_footer(text="Member #{} | User ID: {}".format(member_number, user.id))

        name = str(user)
        name = " ~ ".join((name, user.nick)) if user.nick else name

        if user.avatar:
            avatar = user.avatar_url_as(static_format="png")
            data.set_author(name=name, url=avatar)
            data.set_thumbnail(url=avatar)
        else:
            data.set_author(name=name)

        await ctx.send(embed=data)

#-----------------------REMIND------------------------------
    
    @commands.command(pass_context=True)
    @commands.guild_only()
    async def remind(self, ctx, *args):
        async def write(self, reminder, seconds, member_id):
            '''Writes to remind table with the time to remind (e.g. remind('...', 120, <member_id>) would mean '...' is reminded out in 120 seconds for <member_id>)'''
            timestamp = datetime.utcnow()
            new_timestamp = timestamp + timedelta(seconds=seconds)
            async with self.bot.pool.acquire() as connection:
                await connection.execute('INSERT INTO remind (member_id, reminder, reminder_time) values ($1, $2, $3)', member_id, reminder, new_timestamp)

        '''Given the args tuple (from *args) and returns timeperiod in index position 0 and reason in index position 1'''
        timeperiod =''
        index = 0
        if args:
            timeperiod, reason = separate_args(args)
        if not args or not timeperiod:
            await ctx.send('```-remind <sentence...> -t <time>```')
            return

        reminder = ' '.join(args[:index])
        if len(reminder) >= 256:
            await ctx.send('Please shorten your reminder to under 256 characters.')
        #seconds = time_arg(timeperiod)
        seconds = separate_args(timeperiod)[0]
        await write(self, reminder, seconds, ctx.author.id)
        await ctx.send(':ok_hand: The reminder has been added!')

#-----------------------AVATAR------------------------------

    @commands.command(pass_context=True)
    async def avatar(self, ctx, member: discord.User = None):
        if not member:
            member = ctx.author

        await ctx.send(member.avatar_url)

#-----------------------COUNTDOWNS------------------------------

    @commands.command(pass_context=True, aliases=['results'])
    async def resultsday(self, ctx, hour = None):
        if hour is None:
            hour = 10
        else:
            try:
                hour = int(hour)
            except ValueError:
                await ctx.send('You must choose an integer between 0 and 23 for the command to work!')

        if not 0 <= hour < 24:
            await ctx.send('The hour must be between 0 and 23!')
            return

        string = ''
        if hour == 12:
            string = 'noon'
        elif hour == 0:
            string = '0:00AM'
        elif hour >= 12:
            string = f'{hour-12}PM'
        else:
            string = f'{hour}AM'
        time = datetime(year=2021, month=8, day=26, hour=hour, minute=0, second=0) - (datetime.utcnow() + timedelta(hours=1))
        m, s = divmod(time.seconds, 60)
        h, m = divmod(m, 60)

        await ctx.send(f'''Until GCSE results day at {string} it is
**{time.days}** days
**{h}** hours
**{m}** minutes
**{s}** seconds''') #**{(time.days*24)+h}** hours

    @commands.command(pass_context=True)
    async def gcses(self, ctx):
        time = datetime(year=2021, month=5, day=10, hour=9, minute=0, second=0) - (datetime.utcnow() + timedelta(hours=1))
        
        m, s = divmod(time.seconds, 60)
        h, m = divmod(m, 60)

        await ctx.send(f'''Until CS Paper 1 (the first GCSE exam) is
**{time.days}** days
**{h}** hours
**{m}** minutes
**{s}** seconds''')


#-----------------------1738------------------------------

    @commands.command(pass_context=True)
    async def toggle1738(self, ctx):
        #db connections
        async with self.bot.pool.acquire() as connection:
            #check if already joined
            member = await connection.fetch("SELECT * FROM ping WHERE member_id = ($1)", ctx.author.id)
            if not member:
                #not on - turn it on
                await connection.execute('INSERT INTO ping (member_id) values ($1)', ctx.author.id)
                await ctx.send(":ok_hand: You will recieve notifications for 1738. :tada:")
            else:
                #on - turn it off
                await connection.execute('DELETE FROM ping WHERE member_id = ($1)', ctx.author.id)
                await ctx.send(":ok_hand: You will no longer recieve notifications for 1738. :sob:")

    @commands.command(pass_context=True)
    async def code(self, ctx):
        await ctx.send(f"Adam-Bot code can be found here: {CODE_URL}")

def setup(bot):
    bot.add_cog(Member(bot))
