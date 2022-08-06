import asyncio

import discord
from discord.ext import commands
from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter

from adambot import AdamBot


class DemographicsHandlers:
    def __init__(self, bot: AdamBot, cog: commands.Cog) -> None:  # note that this should really be of type Demographics but circular dependency needs to be resolved first
        self.bot = bot
        self.cog = cog
        self.ContextTypes = self.bot.ContextTypes

    async def viewroles(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the viewroles commands.

        Responds with a list of role names for roles that are tracked within the context guild.
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        role_ids = await self.cog._get_roles(ctx.guild)
        roles = [ctx.guild.get_role(x).name for x in role_ids]
        message = "Currently tracked roles are: " + ", ".join(roles)

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(message)
        else:
            await ctx.response.send_message(message)

    async def addrole(self, ctx: commands.Context | discord.Interaction, role: discord.Role, sample_rate: int) -> None:
        """
        Handler for the addrole commands.

        Adds a role to be sampled for the context guild.
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        def check(m: discord.Message) -> bool:
            return m.author == author and m.channel == ctx.channel

        if role.id in await self.cog._get_roles(ctx.guild):
            message = "This role is already being tracked!"

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)

            return

        question = await ctx.channel.send(
            f"Do you want to add {role.name} to {role.guild.name}'s demographics? It'll be sampled every {sample_rate} day(s)? (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check=check, timeout=300)  # 5 minute timeout
        except asyncio.TimeoutError:
            message = "Demographic command timed out. :sob:"

            if ctx_type == self.ContextTypes.Context:
                await question.edit(content=message)
            else:
                await ctx.response.send_message(message)

            return

        if response.content.lower() == "yes":
            # Add to DB
            await self.cog._add_role(role, sample_rate)
            message = f"{role.name} has been added to the demographics, it'll be sampled for the first time at midnight today!"

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)

        elif response.content.lower() == "no":
            message = f"{role.name} has not been added. :sob:"
            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)

        else:
            message = "Unknown response, please try again. :sob:"
            if ctx_type == self.ContextTypes.Context:
                await question.edit(content=message)
            else:
                await ctx.response.send_message(message)

    async def removerole(self, ctx: commands.Context | discord.Interaction, role: discord.Role) -> None:
        """
        Handler for the removerole commands.

        Removes a role from being sampled for the context guild.
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        def check(m: discord.Message) -> bool:
            return m.author == author and m.channel == ctx.channel

        if role.id not in await self.cog._get_roles(ctx.guild):
            message = "This role is not currently being tracked!"

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)

            return

        question = await ctx.channel.send(
            f"Are you sure you want to remove {role.name} from {role.guild.name}'s demographics? All previous samples will be deleted too. (Type either 'yes' or 'no')")
        try:
            response = await self.bot.wait_for("message", check=check, timeout=300)  # 5 minute timeout
        except asyncio.TimeoutError:
            message = "Demographic command timed out. :sob:"

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)

            return

        if response.content.lower() == "yes":
            # Remove from DB
            await self.cog._remove_role(role)
            message = f"{role.name}, and all its previous samples, have been removed from the demographics"

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)
        else:
            message = "No action taken."

            if ctx_type == self.ContextTypes.Context:
                await question.edit(content=message)
            else:
                await ctx.response.send_message(message)

    async def takesample(self, ctx: commands.Context | discord.Interaction, role: discord.Role) -> None:
        """
        Handler for the takesample commands.

        Takes a sample immediately for a given role within a context guild.
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        guild_tracked_roles = await self.cog._get_roles(ctx.guild)
        if not role:
            # Take a sample of all roles
            def check(m: discord.Message) -> bool:
                return m.author == author and m.channel == ctx.channel

            if ctx_type == self.ContextTypes.Interaction:
                await ctx.response.send_message(":thumbsup:")

            question = await ctx.channel.send(
                f"No role given, would you like to take a sample of all this guild's roles? (Type either 'yes' or 'no')")
            try:
                response = await self.bot.wait_for("message", check=check, timeout=300)  # 5 minute timeout
            except asyncio.TimeoutError:
                message = "Demographic command timed out. :sob:"
                await question.edit(content=message)

                return

            if response.content.lower() == "yes":
                for role in guild_tracked_roles:
                    await self.cog._require_sample(ctx.guild.get_role(role))
                message = "All roles sampled! :ok_hand:"

            elif response.content.lower() == "no":
                message = "Operation cancelled."

            else:
                message = "Unknown response - operation cancelled."

            await ctx.channel.send(message)

            return  # return here means return does not need to be placed inside each condition

        if role.id not in guild_tracked_roles:
            message = "This role is not currently being tracked!"

            if ctx_type == self.ContextTypes.Context:
                await ctx.send(message)
            else:
                await ctx.response.send_message(message)

            return

        await self.cog._require_sample(role)
        message = "A sample has been taken, it may take a few seconds to be registered in the database. :ok_hand:"

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(message)
        else:
            await ctx.response.send_message(message)

    async def removeallsamples(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the removeallsamples commands.

        Removes all samples for a context guild.
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        async with self.bot.pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM demographic_samples WHERE role_reference IN (SELECT id FROM demographic_roles WHERE guild_id = $1);",
                ctx.guild.id)  # Removes samples for that guild

        message = "All samples have been deleted. :sob:"

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(message)
        else:
            await ctx.response.send_message(message)

    async def show(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the show commands.

        Shows the numbers of members with each tracked role within a context guild.
        """

        ctx_type, author = self.bot.unbox_context(ctx)
        if not author:
            return

        tracked_roles = [ctx.guild.get_role(r) for r in await self.cog._get_roles(ctx.guild) if
                         ctx.guild.get_role(r) is not None]
        message = f"There are a total of **{ctx.guild.member_count}** users in **{ctx.guild.name}**."

        double_newline = True
        for role in tracked_roles:
            n = len(role.members)
            if double_newline:
                message += "\n"
                double_newline = False  # Adds an extra new line on the first iteration
            message += f"\n•**{n}** {role.name}"

        message += f"\n*Note: do `{ctx.prefix if ctx_type == self.ContextTypes.Context else '/'}demographics chart` to view change in demographics over time!*"

        if ctx_type == self.ContextTypes.Context:
            await ctx.send(message)
        else:
            await ctx.response.send_message(message)

    async def chart(self, ctx: commands.Context | discord.Interaction) -> None:
        """
        Handler for the chart commands.

        Shows the demographics chart for the tracked roles within a context guild.
        """

        fig, ax = plt.subplots()
        async with self.bot.pool.acquire() as connection:
            role_data = await connection.fetch("SELECT role_id, id FROM demographic_roles WHERE guild_id = $1",
                                               ctx.guild.id)

            for role in role_data:
                data = await connection.fetch("SELECT taken_at, n FROM demographic_samples WHERE role_reference = $1",
                                              role[1])
                role = ctx.guild.get_role(role[0])
                rgb_scaled_tuple = tuple(
                    x / 255 for x in role.color.to_rgb())  # Scale 0-255 integers down to 0-1 floats

                ax.plot([x[0] for x in data], [x[1] for x in data], linewidth=1, markersize=2, color=rgb_scaled_tuple,
                        label=role.name)

        ax.set(xlabel="Time", ylabel="Frequency",
               title=f"{ctx.guild.name}'s  demographics ({ctx.guild.member_count} members)")
        ax.grid()
        ax.legend(loc="upper left")
        ax.set_ylim(bottom=0)
        ax.fmt_xdata = DateFormatter("% Y-% m-% d % H:% M:% S")
        fig.autofmt_xdate()

        await self.bot.send_image_file(ctx, fig, ctx.channel, "demographics-data")
