import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import urllib.request as request
import csv
from random import choice as randchoice
import asyncio
from datetime import datetime
from .utils import Permissions, CHANNELS

class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.settings = {
            'timeout':[20, 0],
            'overrides':['abdul'],
            'timeout_after':5, #after not getting 5 questions right
            'trivias':['cars',
                       'computers',
                       'disney',
                       'elements',
                       'games',
                       'GCSEBio',
                       'GCSEBloodBrothers',
                       'GCSEChemAQAPaper2',
                       'GCSECompSci',
                       'GCSEFrench',
                       'GCSEMaths',
                       'GCSEPhys',
                       'GCSERomeoJuliet',
                       'GCSERS',
                       'GCSESpanish',
                       'general',
                       'harrypotter',
                       'lordt-history',
                       'nato',
                       'SpecIonTests',
                       'usstateabbreviations',
                       'worldcapitals',
                       'worldflags',
                       'WW2'],
            }

        self.responses = {'positive':['Well done {}! **+1** to you!',
                                      'You got it, {}! **+1** for you!',
                                      'Amazing! **+1** for {}',
                                      'Nice work, Mr {}, you get **+1**!'],
                          'negative':['It\'s {} of course. **+1** for me!',
                                      'I know, It\'s {}! **+1** to the bot!',
                                      'You suck, loser. {} is the right answer. I get **+1**']}

        self.trivia_list = self.settings['trivias']
        self.trivias = {}
        self.timeout = 0 #temp var // amount of unanswered questions until bot times out
        
        self.reset()
        self.reload_trivias()

    def reload_trivias(self):
        for trivia in self.trivia_list:
            try:
                url = f'https://raw.githubusercontent.com/adampy/trivia/master/{trivia}.csv'
                r = request.urlopen(url).read().decode('ISO-8859-1').split("\n")
                reader = csv.reader(r)
                questions_dict = {}
                for line in reader:
                    if line:
                        questions_dict[line[0]] = [x for x in line[1:] if x]
                self.trivias[trivia] = questions_dict
            except Exception as e:
                print(f'Error whilst loading {trivia}: {e}')
        return True

    def reset(self):
        self.running = '' #string with name of current category
        self.question = ''
        self.answers = []
        self.question_number = 0
        self.session_questions = {}
        self.score = {}
        self.started_at = 0
        self.timeout = 0

    async def trivia_end_leaderboard(self, member:discord.Member = None, reset=True):
        result = self.reload_trivias()
        if not result:
            await self.trivia_channel.send("Issue when reloading trivias - ping Adam for a fix.")
        if not member:
            color = Colour.from_rgb(177,252,129)
        else:
            color = member.color
            
        embed = Embed(title='Trivia results' if reset else 'Trivia scores', color=color)
        total_score = sum([self.score[indv] for indv in self.score])
        for indv in self.score:
            embed.add_field(name=indv, value=f'{round(self.score[indv]*100/total_score,4)}% ({self.score[indv]})', inline=True)
        if reset:
            embed.set_footer(text=f'This trivia took {(datetime.utcnow()-self.started_at).seconds} seconds to complete.')
            await self.trivia_channel.send('Trivia stopped.')
            self.reset()
        await self.trivia_channel.send(embed=embed)
            

    async def increment_score(self, member):
        try:
            self.score[str(member)] += 1
        except KeyError:
            self.score[str(member)] = 1
        if member == 'Adam-Bot#2418':
            await self.trivia_channel.send(randchoice(self.responses['negative']).format(self.answers[0]))
        else:
            await self.trivia_channel.send(randchoice(self.responses['positive']).format(member.name))

    async def auto_next(self):
        question = self.question
        done = False
        for i in range(self.settings['timeout'][0]):
            await asyncio.sleep(1)
            if question != self.question:
                #got answer correct and question has changed
                done = True
                break
        #typing notif for last 5 seconds
        if not done:
            async with self.trivia_channel.typing():
                for i in range(self.settings['timeout'][1]):
                    await asyncio.sleep(1)
                    if question != self.question:
                        #got answer correct and question has changed
                        done = True
                        break
        if not done:
            self.timeout += 1
            if self.timeout == self.settings['timeout_after']:
                #stop
                await self.increment_score('Adam-Bot#2418')
                await self.trivia_end_leaderboard()
                self.timeout = 0
            else:
                await self.increment_score('Adam-Bot#2418')
                await self.ask_question()
        else:
            self.timeout = 0
                    
                

    async def ask_question(self):
        if not self.session_questions:
            #no more questions
            await self.trivia_end_leaderboard()
            return

        self.question_number += 1
        self.question, self.answers = randchoice(list(self.session_questions.items()))
        self.session_questions.pop(self.question)
        await self.trivia_channel.send(f'''**Question number {self.question_number}**!

{self.question}''')
        #15s timeout
        self.bot.loop.create_task(self.auto_next())

    @commands.Cog.listener()
    async def on_message(self, message):
        #valid answer checking
        if not message.author.bot and self.running and not message.content.startswith('-'):
            if message.channel.id == self.trivia_channel.id:
                #answer checking
                correct = False
                
                roles = [y.name for y in message.author.roles]
                for override in self.settings['overrides']:
                    if (override.lower() in message.content.lower()) and ('Staff' in roles or 'Server Elitist' in roles or message.author.id == 394978551985602571):
                        correct = True
                        break
                
                for answer in self.answers:
                    if answer.lower() == message.content.lower():
                        correct = True
                        break

                if correct:
                    await self.increment_score(message.author)
                    await self.ask_question()
        return

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(1)
        self.trivia_channel = self.bot.get_channel(CHANNELS['trivia'])

    async def trivia_channel_check(ctx):
        return ctx.channel.id == CHANNELS['trivia']

#---------------------------------------------------------------------------------

    @commands.group()
    @commands.guild_only()
    @commands.check(trivia_channel_check)
    async def trivia(self, ctx):
        """Trivia module"""
        if ctx.invoked_subcommand is None:
            await ctx.send('```-trivia list```')

    @trivia.error
    async def trivia_error(self, ctx, error):
        if type(error) == commands.CheckFailure:
            await ctx.send(f'You can only use this command in {self.trivia_channel.mention}')

    @trivia.command()
    @commands.has_any_role(*Permissions.MEMBERS)
    async def list(self, ctx):
        message = ', '.join(self.trivia_list)
        await ctx.send(f'```{message}```')

    @trivia.command(pass_context=True)
    @commands.has_any_role(*Permissions.MEMBERS)
    async def start(self, ctx, trivia = None):
        if trivia is None:
            await ctx.send('You must choose a trivia from `-trivia list`.')
            return
        if trivia not in self.trivia_list:
            await ctx.send('This trivia doesn\'t exist :sob: (the trivia names are case sensitive).')
            return
        if self.running:
            await ctx.send('Trivia already happening, please wait until this one is finshed.')
            return
        #try:
        self.session_questions = self.trivias[trivia]
        #except Exception as e:
        #    ctx.send(f'Internal error <@394978551985602571>: {e}')
        self.running = trivia
        self.started_at = datetime.utcnow()
        await self.ask_question()

    @trivia.command(aliases=['finish', 'end'])
    @commands.has_any_role(*Permissions.MEMBERS)
    async def stop(self, ctx):
        if self.running:
            await self.trivia_end_leaderboard(ctx.author)
        else:
            await ctx.send('No trivia session running!')

    @trivia.command(aliases=['answers','cheat'])
    @commands.has_any_role(*Permissions.STAFF)
    async def answer(self, ctx):
        if self.running:
            await ctx.send(f"The answers are `{'`,`'.join(self.answers)}`")
        else:
            await ctx.send('There are no trivia sessions going on at the moment.')

    @trivia.command()
    @commands.has_any_role(*Permissions.MEMBERS)
    async def skip(self, ctx):
        if self.running:
            await self.increment_score(self.bot)
            await self.ask_question()
        else:
            await ctx.send('No trivia session running!')

    @trivia.command(aliases=['lb'])
    @commands.has_any_role(*Permissions.MEMBERS)
    async def leaderboard(self, ctx):
        if self.running:
            await self.trivia_end_leaderboard(reset=False)
        else:
            await ctx.send('No trivia session running!')

    @trivia.command()
    async def reload(self, ctx):
        if ctx.author.id == 394978551985602571:
            result = self.reload_trivias()
            if result:
                await ctx.send('Done!')
            else:
                await ctx.send('Please reload the bot instead.')
        else:
            await ctx.send("Insufficient permission.")


        

            
    

def setup(bot):
    bot.add_cog(Trivia(bot))
