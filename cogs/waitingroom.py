import discord
from discord import Embed, Colour
from discord.ext import commands
from discord.utils import get
import os
import psycopg2

class WaitingRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        key = os.environ.get('DATABASE_URL')

        self.conn = psycopg2.connect(key, sslmode='require')
        self.cur = self.conn.cursor()
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        #invite stuffs
        guild = self.bot.get_guild(445194262947037185)
        self.cur.execute('SELECT * FROM invites')
        old_invites = self.cur.fetchall()
        invites = await guild.invites()
        invite_data = None
        
        #for each new invite find the old one - if not avaliable then that invite is the one
        seen_invites = []
        breakloop = False
        for new_invite in invites:
            if breakloop:
                break
            seen_invites.append(new_invite)
            #find old invite
            for old_invite in old_invites:
                if new_invite.code == old_invite[1]: #same codes
                    if new_invite.uses - 1 == old_invite[2]: #uses correlate
                        invite_data = new_invite
                        breakloop = True
                        break

        #staff embed
        date = member.joined_at - member.created_at
        day_warning = False
        if date.days < 7:
            day_warning = True
        
        if invite_data:
            embed = Embed(title='Invite data', color=Colour.from_rgb(76, 176, 80))
            embed.add_field(name='Member', value=member.mention)
            embed.add_field(name='Inviter', value=invite_data.inviter.mention)
            embed.add_field(name='Code', value=invite_data.code)
            embed.add_field(name='Uses', value=invite_data.uses)
            embed.add_field(name='Invite created', value=invite_data.created_at.strftime('%H:%M on %d/%m/%y'))
            embed.add_field(name='Account created', value=member.created_at.strftime('%H:%M on %d/%m/%y'))
            embed.set_thumbnail(url=member.avatar_url)
            await get(guild.text_channels, name='brainlets-being-brainlets').send(f'{member.mention}\'s account is **less than 7 days old.**' if day_warning else '', embed=embed)
        else:
            await get(guild.text_channels, name='brainlets-being-brainlets').send('No invite data avaliable.' if not day_warning else f'No invite data avaliable. {member.mention}\'s account is **less than 7 days old.**')



        #reset invites
        self.cur.execute('DELETE FROM invites')
        for invite in invites:
            try:
                data = [invite.inviter.id,
                        invite.code,
                        invite.uses,
                        invite.max_uses,
                        invite.created_at,
                        invite.max_age]

                self.cur.execute('INSERT INTO invites (inviter, code, uses, max_uses, created_at, max_age) values (%s, %s, %s, %s, %s, %s)', data)
            except:
                pass
        self.conn.commit()


        #formatting stuffs
        message = f'''Welcome to the server, {member.mention}! Before you can access the rest of the server, please read through {get(member.guild.text_channels, name='rules').mention} and {get(member.guild.text_channels, name='faqs').mention} , and state what year you're currently in.

If an {get(member.guild.roles, name='Assistant').mention} does not come to assist you with entering the server, please ping one (if none are present ping a mod).'''
        channel = member.guild.system_channel
        await channel.send(message)

    @commands.command(pass_context=True)
    @commands.has_role('Staff')
    async def y9(self, ctx, member: discord.Member):
        '''Verifies a Y9.
Staff role needed.'''
        role = get(member.guild.roles, name='Y9')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send('<@{}> has been verified!'.format(member.id))
        await get(member.guild.text_channels, name='general').send(f'Welcome {member.mention} to the server :wave:')


    @commands.command(pass_context=True)
    @commands.has_role('Staff')
    async def y10(self, ctx, member: discord.Member):
        '''Verifies a Y10.
Staff role needed.'''
        role = get(member.guild.roles, name='Y10')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send('<@{}> has been verified!'.format(member.id))
        await get(member.guild.text_channels, name='general').send(f'Welcome {member.mention} to the server :wave:')

    @commands.command(pass_context=True)
    @commands.has_role('Staff')
    async def y11(self, ctx, member: discord.Member):
        '''Verifies a Y11.
Staff role needed.'''
        role = get(member.guild.roles, name='Y11')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send('<@{}> has been verified!'.format(member.id))
        await get(member.guild.text_channels, name='general').send(f'Welcome {member.mention} to the server :wave:')

    @commands.command(pass_context=True)
    @commands.has_role('Staff')
    async def postgcse(self, ctx, member: discord.Member):
        '''Verifies a Post-GCSE.
Staff role needed.'''
        role = get(member.guild.roles, name='Post-GCSE')
        await member.add_roles(role)
        role = get(member.guild.roles, name='Members')
        await member.add_roles(role)
        await ctx.send(f'{member.mention} has been verified!')
        await get(member.guild.text_channels, name='general').send(f'Welcome {member.mention} to the server :wave:')

    @commands.command(aliases=['lurker'])
    @commands.has_role('Staff')
    async def lurkers(self, ctx):
        members = [x.mention for x in ctx.guild.members if len(x.roles) <= 1]
        message = ', '.join(members) + ' please tell us your year to be verified into the server!'
        await ctx.send(message)

def setup(bot):
    bot.add_cog(WaitingRoom(bot))
