import discord
from discord.utils import get
from discord.ext import commands
from discord import Embed, Colour
from .utils import GCSE_SERVER_ID, CHANNELS
import asyncio


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(1)
        self.mod_logs = self.bot.get_channel(CHANNELS['mod-logs'])

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        ctx = await self.bot.get_context(message)  # needed to fetch ref message
        embed = Embed(title=':information_source: Message Deleted', color=Colour.from_rgb(172, 32, 31))
        embed.add_field(name='User', value=f'{str(message.author)} ({message.author.id})' or "undetected", inline=True)
        embed.add_field(name='Message ID', value=message.id, inline=True)
        embed.add_field(name='Channel', value=message.channel.mention, inline=True)
        embed.add_field(name='Message', value=message.content if (
                    hasattr(message, "content") and message.content) else "None (probably a pin)", inline=False)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await self.mod_logs.send(embed=embed)
        if message.reference:  # intended mainly for replies, can be used in other contexts (see docs)
            ref = await ctx.fetch_message(message.reference.message_id)
            reference = Embed(title=':arrow_upper_left: Reference of deleted message',
                              color=Colour.from_rgb(172, 32, 31))
            reference.add_field(name='Author of reference', value=f'{str(ref.author)} ({ref.author.id})', inline=True)
            reference.add_field(name='Message ID', value=ref.id, inline=True)
            reference.add_field(name='Channel', value=ref.channel.mention, inline=True)
            reference.add_field(name='Jump Link', value=ref.jump_url)
            await self.mod_logs.send(embed=reference)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """
        Could perhaps switch to on_raw_message_edit in the future? bot will only log what it can detect
        based off its own caches
        Same issue with on_message_delete
        """
        embed = Embed(title=':information_source: Message Updated', color=Colour.from_rgb(118, 37, 171))
        embed.add_field(name='User', value=f'{str(after.author)} ({after.author.id})', inline=True)
        embed.add_field(name='Message ID', value=after.id, inline=True)
        embed.add_field(name='Channel', value=after.channel.mention, inline=True)
        embed.add_field(name='Old Message', value=before.content if before.content else "None (probably an embed)", inline=False)
        embed.add_field(name='New Message', value=after.content if after.content else "None (probably an embed)", inline=False)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await self.mod_logs.send(embed=embed)

    async def role_comparison(self, before, after):
        """
        Expects before and after as Member objects
        """
        before_roles = [role for role in before.roles]
        after_roles = [role for role in after.roles]
        removed_roles = [role for role in before_roles if role not in after_roles]
        added_roles = [role for role in after_roles if role not in before_roles]

        return removed_roles, added_roles

    async def embed_role_comparison(self, before, after):
        """
        Expects before and after as Member objects
        Worth noting that this and role_comparison will be of more use if role change logging aggregation is ever possible
        """
        removed_roles, added_roles = await self.role_comparison(before, after)
        props = {"fields": []}
        if added_roles:
            value = "".join([f":white_check_mark: {role.mention} ({role.name})\n" for role in added_roles])
            props["fields"].append({"name": "Added Roles", "value": value})
        if removed_roles:
            value = "".join([f":x: {role.mention} ({role.name})\n" for role in removed_roles])
            props["fields"].append({"name": "Removed Roles", "value": value})
        return props

    async def avatar_handler(self, before, after):
        """
        Handler that returns the old avatar for thumbnail usage and the new avatar for the embed image
        """
        return {"thumbnail_url": before.avatar_url, "image": after.avatar_url,
                "description": ":arrow_right: Old Avatar\n:arrow_down: New Avatar"}

    async def disp_name_handler(self, before, after):
        """
        This handler only exists to deduplicate logging.
        Duplicate logging would occur when a guild member has no nickname and changes their username
        """
        if type(before) is not discord.Member:  # ensures no on_user_update related triggers
            return
        return {"fields": [{"name": "Old Display Name", "value": before.display_name}, {"name": "New Display Name", "value": after.display_name}]}

    # todo: see if there's some way of aggregating groups of changes
    # for example, multiple role changes shouldn't spam the log channel
    # perhaps some weird stuff with task loops can do it??

    async def prop_change_handler(self, before, after):
        """
        God handler which handles all the default logging embed behaviour
        Works for both member and user objects
        """

        """
        Property definitions
        """
        watched_props = [{"name": "display_name",
                          "display_name": "User nickname",
                          "colour": Colour.from_rgb(118, 37, 171),  # perhaps change some of these colours lol
                          "custom_handler": self.disp_name_handler
                          },

                         {"name": "roles",
                          "display_name": "Roles",
                          "colour": Colour.from_rgb(118, 37, 171),
                          "custom_handler": self.embed_role_comparison
                         },

                         {"name": "avatar_url",
                          "display_name": "Avatar",
                          "colour": Colour.from_rgb(118, 37, 171),
                          "custom_handler": self.avatar_handler
                         },

                         {"name": "name",
                          "display_name": "Username",
                          "colour": Colour.from_rgb(118, 37, 171),
                          "custom_handler": None
                         },

                         {"name": "discriminator",
                          "display_name": "Discriminator",
                          "colour": Colour.from_rgb(118, 37, 171),
                          "custom_handler": None
                         }

                        ]

        for prop in watched_props:
            thumbnail_set = False
            if hasattr(before, prop["name"]) and hasattr(after, prop["name"]):  # user objects don't have all the same properties as member objects
                if getattr(before, prop["name"]) != getattr(after, prop["name"]):
                    log = Embed(title=f':information_source: {prop["display_name"]} update for {after} ({after.id})',
                            color=prop["colour"])
                    if not prop["custom_handler"]:
                        log.add_field(name=f'Old {prop["display_name"].lower()}', value=getattr(before, prop["name"]))
                        log.add_field(name=f'New {prop["display_name"].lower()}', value=getattr(after, prop["name"]))
                    else:
                        """
                        Calls the custom embed handler as defined
                        Custom embed handlers are expected to return dict type objects to be handled below
                        """
                        result = await prop["custom_handler"](before, after)
                        if result:  # return None for no result
                            if "fields" in result:
                                for field in result["fields"]:
                                    log.add_field(name=field["name"], value=field["value"])
                            if "description" in result:
                                log.description = result["description"]
                            if "image" in result:
                                log.set_image(url=result["image"])
                            if "thumbnail_url" in result:
                                log.set_thumbnail(url=result["thumbnail_url"])
                                thumbnail_set = True
                        else:
                            continue
                    if not thumbnail_set:
                        log.set_thumbnail(url=after.avatar_url)
                    log.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
                    await self.mod_logs.send(embed=log)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        await self.prop_change_handler(before, after)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        await self.prop_change_handler(before, after)

    @commands.Cog.listener()
    async def on_member_remove(self, user):
        user_left = Embed(title=":information_source: Member Left", color=Colour.from_rgb(118, 37, 171))
        user_left.add_field(name="User", value=f"{user} ({user.id})\n {user.mention}")
        user_left.set_thumbnail(url=user.avatar_url)
        user_left.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await self.mod_logs.send(embed=user_left)

    @commands.Cog.listener()
    async def on_member_join(self, user):
        user_join = Embed(title=":information_source: Member Joined", color=Colour.from_rgb(118, 37, 171))
        user_join.add_field(name="User", value=f"{user} ({user.id})\n {user.mention}")
        user_join.set_thumbnail(url=user.avatar_url)
        user_join.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await self.mod_logs.send(embed=user_join)

def setup(bot):
    bot.add_cog(Logging(bot))
