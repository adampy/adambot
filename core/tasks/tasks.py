from discord.ext import commands
import asyncio
import asyncpg
import datetime
from typing import Callable


class Tasks(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.task_types = {}
        self.bot.tasks = self

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        while not self.bot.online:
            await asyncio.sleep(1)  # wait else DB won't be available

        await self.execute_tasks()

    async def register_task_type(self, task_name: str, handling_method: Callable, delete_task: bool = True, needs_extra_columns=None) -> None:  # expose to bot object
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

    async def submit_task(self, task_name: str, timestamp: str | datetime.datetime, extra_columns: dict) -> None:
        while not self.bot.online:
            await asyncio.sleep(1)  # wait else DB won't be available

        assert task_name in self.task_types
        assert False not in [column in self.task_types[task_name]["extra_data"] for column in extra_columns]

        async with self.bot.pool.acquire() as connection:
            try:
                await connection.execute(f"INSERT INTO tasks (task_name, task_time, {', '.join(extra_columns)}) values ($1, $2, {''.join([f', ${i+3}' for i in range(len(extra_columns))])[2:]})", task_name, timestamp, *extra_columns.values())
            except Exception as e:
                raise e

    async def execute_tasks(self) -> None:
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


def setup(bot) -> None:
    bot.add_cog(Tasks(bot))
