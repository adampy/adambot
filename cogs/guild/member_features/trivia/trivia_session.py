import asyncio
import csv
import random
import urllib.request as request
from datetime import datetime
from typing import Optional

import discord
from discord import Embed, Colour

TRIVIAS = [
    "cars",
    "computers",
    "disney",
    "elements",
    "games",
    "GCSEBio",
    "GCSEBloodBrothers",
    "GCSEChemAQAPaper2",
    "GCSECompSci",
    "GCSEFrench",
    "GCSEMaths",
    "GCSEPhys",
    "GCSERomeoJuliet",
    "GCSERS",
    "GCSESpanish",
    "general",
    "harrypotter",
    "lordt-history",
    "nato",
    "SpecIonTests",
    "usstateabbreviations",
    "worldcapitals",
    "worldflags",
    "WW2"
]

SETTINGS = {
    "question_duration": 20,
    "ignored_questions_before_timeout": 5
}

RESPONSES = {
    "positive": [
        "Well done {}! **+1** to you!",
        "You got it, {}! **+1** for you!",
        "Amazing! **+1** for {}",
        "Nice work, Mr {}, you get **+1**!"
    ],
    "negative": [
        "It's {} of course. **+1** for me!",
        "I know, It's {}! **+1** to the bot!",
        "You suck, loser. {} is the right answer. I get **+1**"
    ]
}


class TriviaSession:
    def __init__(self, bot, channel: discord.TextChannel | discord.Thread, trivia_name: str) -> None:
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

    def load_trivia_data(self) -> None:
        """
        Load trivia data for the trivia under `self.trivia_name` into `self.questions`
        """

        try:
            url = f"https://raw.githubusercontent.com/adampy/trivia/master/{self.trivia_name}.csv"
            r = request.urlopen(url).read().decode("ISO-8859-1").split("\n")
            reader = csv.reader(r)
            for line in reader:
                if line:
                    self.questions.append([line[0], [x for x in line[1:] if x]])
        except Exception as e:
            print(f"Error whilst loading {self.trivia_name}: {e}")

    async def start_trivia(self) -> None:
        """
        Method that begins the trivia session
        """

        self.running = True
        self.question_number = 0
        self.started_at = datetime.utcnow()
        self.bot.loop.create_task(self.ask_next_question())

    async def ask_next_question(self) -> Optional[bool]:
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

        def check(m: discord.Message) -> bool:
            valid_attempt = not m.author.bot and m.channel == self.channel
            if valid_attempt:
                self.attempts_at_current_question += 1
            return (
                    valid_attempt
                    and True in [answer.lower() in m.content.lower() for answer in
                                 self.answers]  # List contains True or False for each answer depending on if its present in the response
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
                await self.trivia_end_leaderboard(
                    msg_content="Trivia session timed out :sob:")  # If enough questions have been ignored, end the trivia
            if self.running:
                self.bot.loop.create_task(
                    self.ask_next_question())  # Adding to self.bot.loop prevents stack overflow errors

    def increment_score(self, user: discord.Member | discord.User) -> None:
        """
        Method that increments the score of a given `user` into the `self.scores` dict.
        """

        before = self.scores.get(user.id, 0)  # Default 0 if no key found
        self.scores[user.id] = before + 1

    async def trivia_end_leaderboard(self, member: discord.Member = None, reset: bool = True,
                                     msg_content: str = "") -> None:
        """
        Method that displays a current, or finishing (if `reset` is True), leaderboard for the current trivia session. This method also sets `self.running` = `not reset`.
        """

        self.running = not reset
        color = member.color if member else Colour.from_rgb(177, 252, 129)
        embed = Embed(title="Trivia results" if reset else "Trivia scores", color=color)
        total_score = sum([self.scores[indv] for indv in self.scores])

        for member_id in self.scores:
            name = self.channel.guild.get_member(member_id).display_name if self.channel.guild.get_member(
                member_id) else await self.bot.fetch_user(member_id).display_name
            embed.add_field(name=name,
                            value=f"{round(self.scores[member_id] * 100 / total_score, 1)}% ({self.scores[member_id]})",
                            inline=True)
        if reset:
            embed.set_footer(
                text=f"This trivia took {(datetime.utcnow() - self.started_at).seconds} seconds to complete.")
        await self.channel.send(msg_content, embed=embed)

    async def stop(self, invoker: discord.Member) -> None:
        """
        Method that stops the current trivia session, with the member who invoked the command being sent as the `invoker` parameter
        """

        await self.trivia_end_leaderboard(member=invoker)
