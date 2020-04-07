import discord
from discord.ext import commands
from discord.utils import get
from discord.errors import NotFound
from discord import Embed, Colour, Status
from .utils import separate_args
import requests
import re
import os
from datetime import datetime, timedelta
import psycopg2
from random import choice as randchoice
import asyncio
from bs4 import BeautifulSoup

class Member(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key = os.environ.get('DATABASE_URL')
        self.pastebin = os.environ.get('PASTEBIN_KEY')

    def is_subject_head(ctx):
        reference = {'Head History Helper':['history'],
                     'Head Biology Helper':['biology'],
                     'Head Chemistry Helper':['chemistry'],
                     'Head Geog Helper':['geography','geog-notes'],
                     'Head Physics Helper':['physics'],
                     'Head CompSci Helper':['computer-science'],
                     'Head English Helper':['english'],
                     'Head Maths Helper':['maths','further-maths'],
                     'Head Business Helper':['business-economics']}

        for key in reference:
            if key in [y.name for y in ctx.author.roles] and ctx.channel.name in reference[key]:
                return True
        else:
            return False

    def in_private_server(ctx):
        return (ctx.guild.id == 593788906646929439) or (ctx.author.id == 394978551985602571) #in priv server or is adam
    
    def get_corona_data(self, country):
        '''DEPRECATED, use get_corona_data_updated()'''
        data = {}
        URL = "https://www.worldometers.info/coronavirus/country/{}/"
        r = requests.get(URL.format(country))
        soup = BeautifulSoup(r.text, features="html.parser")
        numbers = soup.find_all(class_=re.compile("maincounter-number"))
        number_tables = soup.find_all(class_=re.compile("number-table"))

        data['total'] = numbers[0].text.strip()
        data['deaths'] = numbers[1].text.strip()
        data['recovered'] = numbers[2].text.strip()

        active = {}
        active['current'] = number_tables[0].text.strip()
        active['mild'] = number_tables[1].text.strip()
        active['critical'] = number_tables[2].text.strip()
        data['active'] = active

        closed = {}
        closed['outcome'] = number_tables[3].text.strip()
        closed['recovered'] = number_tables[4].text.strip()
        closed['deaths'] = number_tables[5].text.strip()
        data['closed'] = closed

        return data

    def get_corona_data_updated(country):
        '''Get COVID19 tracking data from worldometers HTML, use this instead of get_corona_data()'''
        to_return = {}
        URL = "https://www.worldometers.info/coronavirus/"
        r = requests.get(URL)
        soup = BeautifulSoup(r.text, features="html.parser")

        data = []
        for a in soup.find_all('a', href=True):
            if a['href'] == 'country/{}/'.format(country):

                i = 0
                for x in a.next_elements:
                    if x != "\n" and isinstance(x, str):
                        i += 1
                        data.append(x)
                        if i == 12:
                            break
                break

        to_return['country'] = data[0]
        to_return['total'] = data[1]
        to_return['new_cases'] = data[2]
        to_return['deaths'] = data[3]
        to_return['new_deaths'] = data[4]
        to_return['recovered'] = data[5]
        to_return['active'] = data[6]
        to_return['critical'] = data[7]
        to_return['cases_to_1mil'] = data[8]
        to_return['deaths_to_1mil'] = data[9]
        to_return['tests'] = data[10]
        to_return['tests_to_1mil'] = data[11]
        return to_return

#-----------------------REVISE------------------------------        

    @commands.command(pass_context=True)
    @commands.has_role('Members')
    @commands.guild_only()
    async def revise(self, ctx):
        '''Puts you in revising mode.'''
        member = ctx.author
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
            channel = get(member.guild.text_channels, name='revision-escape')
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

#-----------------------MC & LC & WEEABOO------------------------------

    @commands.command(pass_context=True)
    @commands.has_role('Members')
    @commands.guild_only()
    async def mc(self, ctx):
        '''Gives you the Maths Challenge role.'''
        author = ctx.author
        role = get(author.guild.roles, name='Maths Challenge')
        if 'Maths Challenge' in [y.name for y in author.roles]:
            await author.remove_roles(role)
            await ctx.send(':ok_hand: Your `Maths Challenge` role has vanished!')
        else:
            await author.add_roles(role)
            await ctx.send(':ok_hand: You have been given `Maths Challenge` role!')

    @commands.command(pass_context=True)
    @commands.has_role('Members')
    @commands.guild_only()
    async def lc(self, ctx):
        '''Gives you the Languages Challenge role.'''
        author = ctx.author
        role = get(author.guild.roles, name='Languages Challenge')
        if 'Languages Challenge' in [y.name for y in author.roles]:
            await author.remove_roles(role)
            await ctx.send(':ok_hand: Your `Languages Challenge` role has vanished!')
        else:
            await author.add_roles(role)
            await ctx.send(':ok_hand: You have been given `Languages Challenge` role!')

    @commands.command(pass_context=True)
    @commands.has_role('Members')
    @commands.guild_only()
    async def weeaboo(self, ctx):
        '''Gives you the Weeaboo role.'''
        author = ctx.author
        role = get(author.guild.roles, name='Weeaboo')
        if 'Weeaboo' in [y.name for y in author.roles]:
            await author.remove_roles(role)
            await ctx.send(':ok_hand: Your `Weeaboo` role has vanished!')
        else:
            await author.add_roles(role)
            await ctx.send(':ok_hand: You have been given `Weeaboo` role!')

    @commands.command(pass_context=True, aliases=['announcements', 'notifications'])
    @commands.has_role('Members')
    @commands.guild_only()
    async def announcement(self, ctx):
        '''Gives you the Announcements role.'''
        author = ctx.author
        role = get(author.guild.roles, name='Announcements')
        if 'Announcements' in [y.name for y in author.roles]:
            await author.remove_roles(role)
            await ctx.send(':ok_hand: Your `Announcements` role has vanished!')
        else:
            await author.add_roles(role)
            await ctx.send(':ok_hand: You have been given `Announcements` role!')

#-----------------------PIN------------------------------

    @commands.command(pass_context=True)
    @commands.has_role('Members')
    @commands.check(is_subject_head)
    @commands.guild_only()
    async def pin(self, ctx, message_id):
        '''Lets head subject helpers pin messages in their respective channels.'''
        try:
            message = await ctx.channel.fetch_message(message_id)
        except NotFound:
            await ctx.send('I couldn\'t find that message in this channel!')
            return

        if message.pinned:
            await message.unpin()
            await ctx.send(':ok_hand: Message has been unpinned!')
        else:
            await message.pin()
            await ctx.send(':ok_hand: Message has been pinned!')

#-----------------------QUOTE------------------------------

    @commands.command(pass_context=True)
    @commands.has_role('Members')
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
    @commands.has_role('Members')
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
        if 'bruh' in message.content.lower() and not message.author.bot and not message.content.startswith('-') and not message.author.id == 525083089924259898:
            conn = psycopg2.connect(self.key, sslmode='require')
            cur = conn.cursor()

            cur.execute('UPDATE bruh SET amount = amount + 1')
            conn.commit()
            conn.close() 
        return

    @commands.command()
    async def bruhs(self, ctx):
        '''See how many bruh moments we've had'''
        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()
        cur.execute('SELECT amount FROM bruh')
        bruhs = cur.fetchall()[0][0]
        conn.close()
        await ctx.send(f'Bruh moments: **{bruhs}**')

    @commands.command()
    async def cool(self, ctx, *message):
        '''MaKe YoUr MeSsAgE cOoL'''
        new = ''
        for index, letter in enumerate(' '.join(message)):
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

    @commands.command()
    @commands.check(in_private_server)
    async def spamping(self, ctx, amount, user: discord.Member, *message):
        '''For annoying certain people'''
        await ctx.message.delete()
        
        try:
            iterations = int(amount)
        except Exception as e:
            await ctx.send(f"Please use a number for the amount, not {amount}")
            return
        
        if ctx.guild.id == 593788906646929439:
            msg = ' '.join(message) + " " + user.mention
            for i in range(iterations):
                await ctx.send(msg)
        else:
            await ctx.send("Insufficient permission to use this command in this server.")

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
        def write(self, reminder, seconds, member_id):
            '''Writes to remind table with the time to remind (e.g. remind('...', 120, <member_id>) would mean '...' is reminded out in 120 seconds for <member_id>)'''
            conn = psycopg2.connect(self.key, sslmode='require')
            cur = conn.cursor()
            timestamp = datetime.utcnow()
            new_timestamp = timestamp + timedelta(seconds=seconds)
            cur.execute('INSERT INTO remind (member_id, reminder, reminder_time) values (%s, %s, %s)', (member_id, reminder, new_timestamp))
            conn.commit()
            conn.close()

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
        write(self, reminder, seconds, ctx.author.id)
        await ctx.send(':ok_hand: The reminder has been added!')

#-----------------------AVATAR------------------------------

    @commands.command(pass_context=True)
    async def avatar(self, ctx, member: discord.Member = None):
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
        time = datetime(year=2020, month=8, day=20, hour=hour, minute=0, second=0) - (datetime.utcnow() + timedelta(hours=1))
        m, s = divmod(time.seconds, 60)
        h, m = divmod(m, 60)

        await ctx.send(f'''Until GCSE results day at {string} it is
**{time.days}** days
**{h}** hours
**{m}** minutes
**{s}** seconds''') #**{(time.days*24)+h}** hours

    @commands.command(pass_context=True)
    async def gcses(self, ctx):
        time = datetime(year=2020, month=5, day=11, hour=9, minute=0, second=0) - (datetime.utcnow() + timedelta(hours=1))
        
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
        conn = psycopg2.connect(self.key, sslmode='require')
        cur = conn.cursor()
        #check if already joined
        cur.execute("SELECT * FROM ping WHERE member_id = (%s)", (ctx.author.id,))
        member = cur.fetchall()
        if not member:
            #not on - turn it on
            cur.execute('INSERT INTO ping (member_id) values (%s)', (ctx.author.id, ))
            await ctx.send(":ok_hand: You will recieve notifications for 1738. :tada:")
        else:
            #on - turn it off
            cur.execute('DELETE FROM ping WHERE member_id = (%s)', (ctx.author.id, ))
            await ctx.send(":ok_hand: You will no longer recieve notifications for 1738. :sob:")
        conn.commit()
        conn.close()

#-----------------------COVID19 TRACKING------------------------------

    @commands.check(in_private_server)
    @commands.command(pass_context=True)
    async def corona(self, ctx, country=None):
        if country is None:
            await ctx.send('```-corona <country>```')
            return
        
        async with ctx.typing():
            data = self.get_corona_data_updated(country)
            embed = Embed(title="COVID19 Update", color=ctx.author.color)
            embed.add_field(name="Total Cases", value=data['total'])
            embed.add_field(name="Deaths", value=data['deaths'])
            embed.set_footer(text="Data received from https://www.worldometers.info/coronavirus")
        await ctx.send(embed=embed)
        



def setup(bot):
    bot.add_cog(Member(bot))
