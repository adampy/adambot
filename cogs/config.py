import discord
from discord import Embed, Colour
from discord.ext import commands
import asyncio

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_staff(self, ctx):
        """
        Method that checks if a user is staff in their guild or not
        """
        await self.bot.add_config(ctx.guild.id)
        staff_role_id = self.bot.configs[ctx.guild.id]["staff_role"]
        return staff_role_id in [y.id for y in ctx.author.roles]

    @commands.command(pass_context = True)
    @commands.has_permissions(administrator = True)
    async def staff(self, ctx, role):
        """
        Command that sets up the staff role for the server the command is executed in
        """
        if not role.isdigit():
            await ctx.send("You need to provide a role *ID* to do this")
            return

        await self.bot.add_config(ctx.guild.id)
        self.bot.configs[ctx.guild.id]["staff_role"] = int(role)
        await self.bot.propagate_config(ctx.guild.id)
        await ctx.send(f"The staff role has been changed to '{ctx.guild.get_role(int(role)).name}' :ok_hand:")
        
    @staff.error
    async def staff_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need to be an administrator to do this :sob:")
            return

    @commands.command(pass_context = True)
    async def staffcmd(self, ctx):
        if await self.is_staff(ctx):
            await ctx.send("Hello staff member!")
        else:
            await ctx.send("You are not staff!")

def setup(bot):
    bot.add_cog(Config(bot))
