import os
import platform
import subprocess
import time
from datetime import datetime

import discord
import requests
from discord import Embed
from discord.ext import commands

from libs.misc.utils import get_user_avatar_url

from adambot import AdamBot


class BotHandlers:
    def __init__(self, bot: AdamBot) -> None:
        """
        Initialises the class and also tries to determine the commit and branch the bot is running on where applicable
        """

        self.bot = bot

        self.ContextTypes = self.bot.ContextTypes

        self.remote_url = os.environ.get("AB_REMOTE_URL")
        self.given_commit_hash = os.environ.get("AB_COMMIT_HASH")
        self.given_branch = os.environ.get("AB_REMOTE_BRANCH")

        folder_name = ""
        if self.remote_url:  # only clone to depth 1 if no commit hash is specified (ie assume latest), and only a specific branch IF specified else do all
            clone = subprocess.run(
                f"git clone {'--depth 1' if not self.given_commit_hash else ''} {f'--branch {self.given_branch}' if self.given_branch else '--no-single-branch'} {os.environ.get('AB_REMOTE_URL')}.git".split(
                    " "), stdout=subprocess.PIPE).stdout.decode("utf-8").strip()
            if "fatal" not in clone:
                folder_name = f"-C {self.remote_url.split('/')[-1]} "

        self.branch_name = subprocess.run(f"git {folder_name}rev-parse --abbrev-ref HEAD".split(" "),
                                          stdout=subprocess.PIPE).stdout.decode(
            "utf-8").strip() if not self.given_branch else self.given_branch

        if not self.remote_url:
            self.remote_name = subprocess.run(f"git config branch.{self.branch_name}.remote".split(" "),
                                              stdout=subprocess.PIPE).stdout.decode(
                "utf-8").strip() if self.branch_name else ""
            self.remote_url = subprocess.run(f"git config remote.{self.remote_name}.url".split(" "),
                                             stdout=subprocess.PIPE).stdout.decode(
                "utf-8").strip() if self.remote_name else ""
            if self.remote_url.endswith(".git"):
                self.remote_url = self.remote_url[:-4]

        self.commit_hash = subprocess.run(f"git {folder_name}rev-parse HEAD".split(" "),
                                          stdout=subprocess.PIPE).stdout.decode(
            "utf-8").strip() if not self.given_commit_hash else self.given_commit_hash
        self.commit_name = subprocess.run(f"git {folder_name}log -1 {self.commit_hash} --pretty=format:%s".split(" "),
                                          stdout=subprocess.PIPE).stdout.decode("utf-8").strip()
        self.commit_page = requests.get(
            f"{self.remote_url}/commit/{self.commit_hash}") if self.commit_hash and self.remote_url else ""
        self.commit_url = f"{self.remote_url}/commit/{self.commit_hash}" if type(
            self.commit_page) is not str and self.commit_page.status_code == 200 else "" if self.commit_page else ""

    async def botinfo(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the botinfo commands.

        Constructs and sends the botinfo embed.
        """

        ctx_type = self.bot.get_context_type(ctx)

        if ctx_type == self.ContextTypes.Unknown:
            return

        app_info = await self.bot.application_info()
        embed = Embed(title=f"Bot info for ({self.bot.user})",
                      description=app_info.description if app_info.description else "", colour=0x87CEEB)
        embed.add_field(name="Uptime", value=self.bot.time_str(round(time.time() - self.bot.start_time)))
        embed.add_field(name="Discord.py version", value=discord.__version__, inline=False)
        embed.add_field(name="Python version", value=f"{platform.python_version()}", inline=False)
        embed.add_field(name="Commit in use",
                        value=f"{self.commit_name} ({self.commit_hash})" if self.commit_hash else "Unknown",
                        inline=False)

        if self.commit_url:
            embed.add_field(name="Commit link", value=self.commit_url, inline=False)

        if self.branch_name:
            embed.add_field(name="Currently checked out branch", value=self.branch_name, inline=False)

        embed.add_field(name="Host OS", value=f"{platform.system()}", inline=False)
        embed.add_field(name="Bot owner", value=f"{app_info.owner}", inline=False)
        embed.add_field(name="Public bot", value=f"{app_info.bot_public}", inline=False)

        if hasattr(app_info, "icon"):
            embed.set_thumbnail(url=app_info.icon.url)

        if ctx_type == self.ContextTypes.Context:
            author = ctx.author
        else:
            author = ctx.user

        embed.set_footer(text=f"Requested by: {author.display_name} ({author})\n" + (self.bot.correct_time()).strftime(
            self.bot.ts_format), icon_url=get_user_avatar_url(author, mode=1)[0])

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)

    async def host(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the host commands.

        Allows a user to check if the bot is currently hosted locally or remotely.
        """

        ctx_type = self.bot.get_context_type(ctx)

        if ctx_type == self.ContextTypes.Unknown:
            return

        string = f"Adam-bot is {'**locally**' if self.bot.LOCAL_HOST else '**remotely**'} hosted right now."

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(string)
        else:
            await ctx.response.send_message(string)

    async def ping(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the ping commands.

        Allows a user to view the bot's current latency
        """

        ctx_type = self.bot.get_context_type(ctx)

        if ctx_type == self.ContextTypes.Unknown:
            return

        string = f"Pong! ({round(self.bot.latency * 1000)} ms)"

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(string)
        else:
            await ctx.response.send_message(string)

    async def uptime(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the uptime commands.

        Allows a user to view how long the bot has been running for
        """

        ctx_type = self.bot.get_context_type(ctx)

        if ctx_type == self.ContextTypes.Unknown:
            return

        seconds = round(time.time() - self.bot.start_time)  # Rounds to the nearest integer
        time_string = self.bot.time_str(seconds)

        date = datetime.fromtimestamp(self.bot.start_time)  # datetime object from the POSIX time bot started running
        markdown_time = discord.utils.format_dt(date, style='R')  # e.g `5 days ago`

        string = f"Current uptime session has lasted **{time_string}**, or **{seconds}** seconds. ({markdown_time})"

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(string)
        else:
            await ctx.response.send_message(string)
