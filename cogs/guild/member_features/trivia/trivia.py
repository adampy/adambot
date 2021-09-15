import discord
from discord import Embed, Colour
from discord.ext import commands
import urllib.request as request
import csv
import random
import asyncio
from datetime import datetime
from libs.misc.decorators import is_staff

TRIVIAS = [
    'cars',
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
    'WW2'
]

SETTINGS = {
    'question_duration': 20,
    'ignored_questions_before_timeout': 5
}

RESPONSES = {
    'positive': [
        'Well done {}! **+1** to you!',
        'You got it, {}! **+1** for you!',
        'Amazing! **+1** for {}',
        'Nice work, Mr {}, you get **+1**!'
    ],
    'negative': [
        'It\'s {} of course. **+1** for me!',
        'I know, It\'s {}! **+1** to the bot!',
        'You suck, loser. {} is the right answer. I get **+1**'
    ]
}


class TriviaSession:
    def __init__(self, bot, channel, trivia_name):
        self.bot = bot
        self.channel = channel
        self.trivia_name = trivia_name
        self.questions = []  # Stores a list of questions still left to ask, array of [question, [answer1, answer2, ...]]
        self.answers = []  # Stores current answers, allows people to cheat in the `trivia answer` command
        self.question_number = 0
        self.started_at = None  # Stores a datetime of when the trivia was started
        self.scores = {}  # MemberID -> Score
        self.running = False  # Stores the state of the game, this is used when the `trivia stop` command is used mid-game
        self.attempts_at_current_question = 0
        self.ignored_questions = 0  # Number of questions where no single answer was received
        self.load_trivia_data()

    def load_trivia_data(self):
        """
        Load trivia data for the trivia under `self.trivia_name` into `self.questions`
        """

        try:
            url = f'https://raw.githubusercontent.com/adampy/trivia/master/{self.trivia_name}.csv'
            r = request.urlopen(url).read().decode('ISO-8859-1').split("\n")
            reader = csv.reader(r)
            for line in reader:
                if line:
                    self.questions.append([line[0], [x for x in line[1:] if x]])
        except Exception as e:
            print(f'Error whilst loading {self.trivia_name}: {e}')

    async def start_trivia(self):
        """
        Method that begins the trivia session
        """

        self.running = True
        self.question_number = 0
        self.started_at = datetime.utcnow()
        self.bot.loop.create_task(self.ask_next_question())

    async def ask_next_question(self):
        """
        Method that asks the next question
        """

        if not self.questions:  # No more unasked questions left
            await self.trivia_end_leaderboard()
            return

        self.question_number += 1
        current_question_number = self.question_number
        rand_indx = random.randint(0, len(self.questions) - 1)
        self.question, self.answers = self.questions[rand_indx]
        self.questions.pop(rand_indx)
        await self.channel.send(f"**Question number {self.question_number}**!\n\n{self.question}")
        
        def check(m):
            valid_attempt = not m.author.bot and m.channel == self.channel
            if valid_attempt:
                self.attempts_at_current_question += 1
            return (
                valid_attempt
                and True in [answer.lower() in m.content.lower() for answer in self.answers]  # List contains True or False for each answer depending on if its present in the response
                and self.question_number == current_question_number  # Ensures that the question numbers are the same, if they aren't the same the question as been skipped
            )

        try:
            self.attempts_at_current_question = 0
            response = await self.bot.wait_for("message", check=check, timeout=SETTINGS["question_duration"])
            # Correct answer
            if not self.running:
                return
            await self.channel.send(random.choice(RESPONSES["positive"]).format(response.author.display_name))
            self.increment_score(response.author)
        except asyncio.TimeoutError:
            # Incorrect answer
            if self.question_number != current_question_number:
                return  # The question has been skipped, score already incremented and another question asked - do nothing
            if not self.running:
                return  # The trivia has been stopped mid-question - do nothing
            if self.attempts_at_current_question == 0:
                self.ignored_questions += 1  # Add to ignored counter
            await self.channel.send(random.choice(RESPONSES["negative"]).format(self.answers[0].lower()))
            self.increment_score(self.bot.user)
        finally:
            # Move onto next question if not finished
            if self.question_number != current_question_number:
                return  # The question has been skipped, score already incremented and another question asked - do nothing
            if self.ignored_questions >= SETTINGS["ignored_questions_before_timeout"]:
                await self.trivia_end_leaderboard(msg_content="Trivia session timed out :sob:")  # If enough questions have been ignored, end the trivia
            if self.running:
                self.bot.loop.create_task(self.ask_next_question())  # Adding to self.bot.loop prevents stack overflow errors

    def increment_score(self, user: discord.User):
        """
        Method that increments the score of a given `user` into the `self.scores` dict.
        """

        before = self.scores.get(user.id, 0)  # Default 0 if no key found
        self.scores[user.id] = before + 1

    async def trivia_end_leaderboard(self, member: discord.Member = None, reset=True, msg_content=""):
        """
        Method that displays a current, or finishing (if `reset` is True), leaderboard for the current trivia session. This method also sets `self.running` = `not reset`.
        """

        self.running = not reset
        color = member.color if member else Colour.from_rgb(177, 252, 129)
        embed = Embed(title='Trivia results' if reset else 'Trivia scores', color=color)
        total_score = sum([self.scores[indv] for indv in self.scores])

        for member_id in self.scores:
            name = self.channel.guild.get_member(member_id).display_name if self.channel.guild.get_member(member_id) else await self.bot.fetch_user(member_id).display_name
            embed.add_field(name=name, value=f'{round(self.scores[member_id]*100/total_score, 1)}% ({self.scores[member_id]})', inline=True)
        if reset:
            embed.set_footer(text=f'This trivia took {(datetime.utcnow()-self.started_at).seconds} seconds to complete.')
        await self.channel.send(msg_content, embed=embed)

    async def stop(self, invoker: discord.Member):
        """
        Method that stops the current trivia session, with the member who invoked the command being sent as the `invoker` parameter
        """

        await self.trivia_end_leaderboard(member=invoker)


class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.trivia_sessions = {}

    @commands.group()
    @commands.guild_only()
    async def trivia(self, ctx):
        """
        Trivia module
        """

        if ctx.invoked_subcommand is None:
            await ctx.send(f'```{ctx.prefix}trivia list```')

    @trivia.command()
    async def list(self, ctx):
        desc = ""
        for trivia in TRIVIAS:
            desc += "• " + trivia + ("" if trivia == TRIVIAS[-1] else "\n")
        await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Available trivias", desc=desc)

    @trivia.command(pass_context=True)
    async def start(self, ctx, trivia=None):
        """
        Command that starts a new trivia game in the currently set trivia channel
        """

        trivia_channel_id = await self.bot.get_config_key(ctx, "trivia_channel")
        session = self.trivia_sessions.get(ctx.guild.id, None)
        if session and session.running:  # TriviaSession.stop() cannot remove from this dict, only change self.running, so we only need to check that
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "Trivia game already happening", desc="Please wait until the current trivia is over before starting a new one")
            return
        if trivia_channel_id is None:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, f"{ctx.guild.name} does not have a trivia channel set!")
            return
        if trivia is None or trivia not in TRIVIAS:
            await self.bot.DefaultEmbedResponses.error_embed(self.bot, ctx, f"You must choose a trivia from `{ctx.prefix}trivia list`", desc="(Trivia names are case-sensitive)")
            return

        trivia_channel = self.bot.get_channel(trivia_channel_id)
        session = TriviaSession(self.bot, trivia_channel, trivia)
        self.trivia_sessions[ctx.guild.id] = session
        await session.start_trivia()

    @trivia.command(aliases=['finish', 'end'])
    async def stop(self, ctx):
        """
        Command that stops a current trivia game
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return
        await session.stop(ctx.author)
        del self.trivia_sessions[ctx.guild.id]  # Delete it from dict, and memory

    @trivia.command(aliases=['answers', 'cheat'])
    @is_staff
    async def answer(self, ctx):
        """
        Command that allows staff to see the correct answer
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return
        
        desc = ""
        for ans in session.answers:
            desc += "• " + ans + ("" if ans == session.answers[-1] else "\n")
        await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, f"Answers to: '{session.question}'", desc=desc)

    @trivia.command()
    async def skip(self, ctx):
        """
        Command that skips a question - a point is given to the bot
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return
        session.increment_score(self.bot.user)
        await session.ask_next_question()

    @trivia.command(aliases=['lb'])
    async def leaderboard(self, ctx):
        """
        Command that shows the leaderboard for the current trivia game
        """

        session = self.trivia_sessions.get(ctx.guild.id, None)
        if not session:
            await self.bot.DefaultEmbedResponses.information_embed(self.bot, ctx, "There is no trivia game in progress")
            return
        await session.trivia_end_leaderboard(reset=False)


def setup(bot):
    bot.add_cog(Trivia(bot))
