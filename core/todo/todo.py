from discord.ext import commands
import asyncio
import asyncpg
import datetime

class Todo:
    pass

class Todos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        while not self.bot.online:
            await asyncio.sleep(1)  # wait else DB won't be available

        await self.execute_todos()


    async def execute_todos(self):
        """The loop that continually checks the DB for todos.
            The todo table looks like:
                id SERIAL PRIMARY KEY,
                todo_id int,
                todo_time timestamptz,
                member_id bigint,
                guild_id bigint
                member_id may not always be a member ID, and can sometimes be a FK to demographic_roles.id"""

        while self.bot.online:
            try:
                async with self.bot.pool.acquire() as connection:
                    todos = await connection.fetch("SELECT * FROM todo WHERE todo_time <= ($1)", datetime.datetime.utcnow())
                    for todo in todos:
                        try:
                            if todo[1] == self.bot.Todo.UNMUTE:
                                member = get(self.bot.get_all_members(), id=todo[3])
                                await member.remove_roles(get(member.guild.roles, name='Muted'),
                                                          reason='Auto unmuted')
                                await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])

                            elif todo[1] == self.bot.Todo.UNBAN:
                                user = await self.bot.fetch_user(todo[3])
                                guild = self.bot.get_guild(todo[4])
                                await guild.unban(user, reason='Auto unbanned')
                                await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])

                            elif todo[1] == self.bot.Todo.DEMOGRAPHIC_SAMPLE or todo[1] == self.bot.Todo.ONE_OFF_DEMOGRAPHIC_SAMPLE:
                                demographic_role_id = todo[3]
                                results = await connection.fetch(
                                    "SELECT role_id, guild_id, sample_rate FROM demographic_roles WHERE id = $1",
                                    demographic_role_id)
                                guild = self.bot.get_guild(results[0][1])
                                role_id = results[0][0]
                                sample_rate = results[0][2]
                                n = len([x for x in guild.members if role_id in [y.id for y in x.roles]])
                                await connection.execute(
                                    "INSERT INTO demographic_samples (n, role_reference) VALUES ($1, $2)", n,
                                    demographic_role_id)
                                await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])

                                if todo[1] == self.bot.Todo.DEMOGRAPHIC_SAMPLE:  # IF NOT A ONE OFF SAMPLE, PERFORM IT AGAIN
                                    await connection.execute(
                                        "INSERT INTO todo (todo_id, todo_time, member_id) VALUES ($1, $2, $3)",
                                        Todo.DEMOGRAPHIC_SAMPLE, datetime.utcnow() + timedelta(days=sample_rate),
                                        demographic_role_id)

                        except Exception as e:
                            print(f'{type(e).__name__}: {e}')
                            await connection.execute('DELETE FROM todo WHERE id = ($1)', todo[0])

                    reminds = await connection.fetch("SELECT * FROM remind WHERE reminder_time <= ($1)", datetime.datetime.utcnow())
                    for remind in reminds:
                        try:
                            member = self.bot.get_user(remind[1])
                            message = f'You told me to remind you about this:\n{remind[3]}'
                            try:
                                await member.send(message)
                            except discord.Forbidden:
                                channel = self.bot.get_channel(remind[5])  # Get the channel it was invoked from
                                await channel.send(member.mention + ", " + message)
                            finally:
                                await connection.execute('DELETE FROM remind WHERE id = ($1)', remind[0])
                        except Exception as e:
                            print(f'REMIND: {type(e).__name__}: {e}')
            except (OSError, asyncpg.exceptions.ConnectionDoesNotExistError):
                await asyncio.sleep(5)  # workaround for task crashing when connection temporarily drops with db

            await asyncio.sleep(5)
def setup(bot):
    bot.add_cog(Todos(bot))