from discord.ext import commands
import asyncio
import asyncpg
import datetime
import random
import ast


class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.task_types = {}
        self.bot.tasks = self

    @commands.Cog.listener()
    async def on_ready(self):
        while not self.bot.online:
            await asyncio.sleep(1)  # wait else DB won't be available

        await self.execute_tasks()

    async def register_task_type(self, task_name: str, handling_method, delete_task: bool = True, needs_extra_columns=None):  # expose to bot object
        if needs_extra_columns is None:
            needs_extra_columns = {"member_id": "bigint", "guild_id": "bigint"}
        while not self.bot.online:
            await asyncio.sleep(1)  # wait else DB won't be available

        async with self.bot.pool.acquire() as connection:
            try:
                for column in needs_extra_columns:
                    await connection.execute(f"ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {column} {needs_extra_columns[column]}")
            except Exception as e:
                print(e)
                return

        self.task_types[task_name] = {
            "handler": handling_method,
            "delete_post_handle": delete_task,
            "extra_data": needs_extra_columns
        }

    async def submit_task(self, task_name: str, timestamp, extra_columns: dict):
        while not self.bot.online:
            await asyncio.sleep(1)  # wait else DB won't be available

        assert task_name in self.task_types
        assert False not in [column in self.task_types[task_name]["extra_data"] for column in extra_columns]

        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute(f"INSERT INTO tasks (task_name, task_time, {', '.join(extra_columns)}) values ($1, $2, {''.join([f', ${i+3}' for i in range(len(extra_columns))])[2:]})", task_name, timestamp, *extra_columns.values())
            except Exception as e:
                raise e

    async def test_task(self, data):
        await self.bot.get_channel(data["channel_id"]).send(data)

    @commands.command()
    @commands.guild_only()
    async def regtest(self, ctx, name, *, extra_columns):
        extra_columns = ast.literal_eval(extra_columns)
        await self.register_task_type(name, self.test_task, needs_extra_columns=extra_columns)
        await ctx.reply(f"Registered {name} with test_task object")

    @commands.command()
    @commands.guild_only()
    async def subtest(self, ctx, name, *, data):
        data = ast.literal_eval(data)
        t = random.randint(5, 20)
        await self.submit_task(ctx, name, datetime.datetime.utcnow() + datetime.timedelta(seconds=t), data)
        await ctx.reply(f"Submitted new {name}, check DB for results, picked {t} seconds delay")

    async def execute_tasks(self):
        """
        The loop that continually checks the DB for todos.
            The todo table looks like:
                id SERIAL PRIMARY KEY,
                task_name VARCHAR(255),
                task_time timestamptz,
                member_id bigint,
                guild_id bigint
        """

        while self.bot.online:
            try:
                async with self.bot.pool.acquire() as connection:
                    tasks = await connection.fetch("SELECT * FROM tasks WHERE task_time <= ($1)", datetime.datetime.utcnow())
                    for task in tasks:
                        task = dict(task)
                        try:
                            if task["task_name"] not in self.task_types:
                                continue  # task_type hasn't been registered yet, hold task
                            await self.task_types[task["task_name"]]["handler"](task)
                        except Exception as e:
                            print(f'{type(e).__name__}: {e}')
                        if self.task_types[task["task_name"]]["delete_post_handle"]:
                            await connection.execute('DELETE FROM tasks WHERE id = ($1)', task["id"])
            except (OSError, asyncpg.exceptions.ConnectionDoesNotExistError):
                await asyncio.sleep(1)  # workaround for task crashing when connection temporarily drops with db

            await asyncio.sleep(1)


def setup(bot):
    bot.add_cog(Tasks(bot))
