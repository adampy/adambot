import discord
from discord.ext import commands
from discord import Embed, Colour
from discord.utils import get
from libs.misc.utils import get_user_avatar_url


# def getdeepattr(obj: object, dotted_attr: str) -> object:
#     """
#     Custom utility function that provides the same functionality as `getattr()` but it allows dotted attributes, e.g. `getattr(member, "avatar.url")`
#     """
#     for child in dotted_attr.split("."):
#         obj = getattr(obj, child)
#     return obj


# def hasdeepattr(obj: object, dotted_attr: str) -> object:
#     """
#     Custom utility function that provides the same functionality as `hasattr()` but it allows dotted attributes, e.g. `hasattr(member, "avatar.url")`
#     """
#     try:
#         getattr(obj, dotted_attr)
#         return True
#     except AttributeError:
#         return False


class Logging(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.previous_inv_log_embeds = []
        self.guilds = []
        self.invites = {}

    @staticmethod
    async def get_all_invites(guild: discord.Guild) -> list[discord.Invite]:
        return await guild.invites() + ([await guild.vanity_invite()] if "VANITY_URL" in guild.features else [])

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.guilds = self.bot.guilds
        for guild in self.guilds:
            self.invites[guild.id] = await self.get_all_invites(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.invites[guild.id] = await self.get_all_invites(guild)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        ctx = await self.bot.get_context(message)  # needed to fetch ref message

        channel_id = await self.bot.get_config_key(message, "mod_log_channel")
        if channel_id is None or (message.author.id == self.bot.user.id and not message.content): # Don't log in the logs if logs dont exist or bot deleting own embed pages
            return

        channel = self.bot.get_channel(channel_id)
        embed = Embed(title=':information_source: Message Deleted', color=Colour.from_rgb(172, 32, 31))
        embed.add_field(name='User', value=f'{str(message.author)} ({message.author.id})' or "undetected", inline=True)
        embed.add_field(name='Message ID', value=message.id, inline=True)
        embed.add_field(name='Channel', value=message.channel.mention, inline=True)
        embed.add_field(name='Message', value=message.content if (hasattr(message, "content") and message.content) else "(No detected text content)", inline=False)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

        if message.reference:  # intended mainly for replies, can be used in other contexts (see docs)
            ref = await ctx.fetch_message(message.reference.message_id)
            reference = Embed(title=':arrow_upper_left: Reference of deleted message', color=Colour.from_rgb(172, 32, 31))
            reference.add_field(name='Author of reference', value=f'{str(ref.author)} ({ref.author.id})', inline=True)
            reference.add_field(name='Message ID', value=ref.id, inline=True)
            reference.add_field(name='Channel', value=ref.channel.mention, inline=True)
            reference.add_field(name='Jump Link', value=ref.jump_url)

            await channel.send(embed=reference)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
        """
        Logs bulk message deletes, such as those used in `purge` command
        """
        msg_channel = self.bot.get_channel(payload.channel_id)

        channel_id = await self.bot.get_config_key(msg_channel, "mod_log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        embed = Embed(title=':information_source: Bulk Message Deleted', color=Colour.from_rgb(172, 32, 31))
        embed.add_field(name='Count', value=f"{len(payload.message_ids)}", inline=True)
        embed.add_field(name='Channel', value=msg_channel.mention, inline=True)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """
        Could perhaps switch to on_raw_message_edit in the future? bot will only log what it can detect
        based off its own caches
        Same issue with on_message_delete
        """

        if before.content == after.content:  # fixes weird bug where messages get logged as updated e.g. when an image or embed is posted, even though there's no actual change to their content
            return

        channel_id = await self.bot.get_config_key(before, "mod_log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        embed = Embed(title=':information_source: Message Updated', color=Colour.from_rgb(118, 37, 171))
        embed.add_field(name='User', value=f'{str(after.author)} ({after.author.id})', inline=True)
        embed.add_field(name='Message ID', value=after.id, inline=True)
        embed.add_field(name='Channel', value=after.channel.mention, inline=True)
        embed.add_field(name='Old Message', value=before.content if before.content else "(No detected text content)", inline=False)
        embed.add_field(name='New Message', value=after.content if after.content else "(No detected text content)", inline=False)
        embed.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))

        await channel.send(embed=embed)

    @staticmethod
    async def role_comparison(before: discord.Member, after: discord.Member) -> tuple[list[discord.Role], list[discord.Role]]:
        """
        Expects before and after as Member objects
        Returns roles a user has had removed, and those that have been added
        """

        before_roles = [role for role in before.roles]
        after_roles = [role for role in after.roles]
        removed_roles = [role for role in before_roles if role not in after_roles]
        added_roles = [role for role in after_roles if role not in before_roles]

        return removed_roles, added_roles

    async def embed_role_comparison(self, before: discord.Member, after: discord.Member) -> dict:
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

    @staticmethod
    async def avatar_handler(before: discord.Member, after: discord.Member) -> dict:
        """
        Handler that returns the old avatar for thumbnail usage and the new avatar for the embed image
        """

        return {"thumbnail_url": get_user_avatar_url(before), "image": get_user_avatar_url(after), "description": ":arrow_right: Old Avatar\n:arrow_down: New Avatar"}

    @staticmethod
    async def disp_name_handler(before: discord.Member, after: discord.Member) -> dict:
        """
        This handler only exists to deduplicate logging.
        Duplicate logging would occur when a guild member has no nickname and changes their username
        """

        if type(before) is not discord.Member:  # ensures no on_user_update related triggers
            return

        return {"fields": [{"name": "Old Nickname", "value": before.display_name},
                           {"name": "New Nickname", "value": after.display_name}]}

    # todo: see if there's some way of aggregating groups of changes
    # for example, multiple role changes shouldn't spam the log channel
    # perhaps some weird stuff with task loops can do it??

    async def prop_change_handler(self, before: discord.Member, after: discord.Member) -> dict:
        """
        God handler which handles all the default logging embed behaviour
        Works for both member and user objects
        """

        """
        Property definitions
        """

        user_updated_colour = Colour.from_rgb(214, 174, 50)  # Storing as var quicker than initialising each time
        watched_props = [{"name": "display_name",
                          "display_name": "Nickname",
                          "colour": user_updated_colour,
                          "custom_handler": self.disp_name_handler
                          },

                         {"name": "roles",
                          "display_name": "Roles",
                          "colour": user_updated_colour,
                          "custom_handler": self.embed_role_comparison
                          },

                         {"name": "avatar",
                          "display_name": "Avatar",
                          "colour": user_updated_colour,
                          "custom_handler": self.avatar_handler
                          },

                         {"name": "name",
                          "display_name": "Username",
                          "colour": user_updated_colour,
                          "custom_handler": None
                          },

                         {"name": "discriminator",
                          "display_name": "Discriminator",
                          "colour": user_updated_colour,
                          "custom_handler": None
                          }

                         ]

        for prop in watched_props:
            thumbnail_set = False

            if hasattr(before, prop["name"]) and hasattr(after, prop["name"]):  # user objects don't have all the same properties as member objects

                if (getattr(before, prop["name"]) != getattr(after, prop["name"])) or (prop["name"] == "avatar" and get_user_avatar_url(before) != get_user_avatar_url(after)): #TODO: Fix up the edge case with avatars?
                    log = Embed(title=f':information_source: {prop["display_name"]} Updated', color=prop["colour"])
                    log.add_field(name='User', value=f'{after} ({after.id})', inline=True)

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
                                log.set_image(url=f'{result["image"]}')
                            if "thumbnail_url" in result:
                                log.set_thumbnail(url=f'{result["thumbnail_url"]}')
                                thumbnail_set = True
                        else:
                            continue

                    if not thumbnail_set:
                        log.set_thumbnail(url=get_user_avatar_url(after))
                    log.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))

                    # Send `log` embed to all servers the user is part of, unless its a nickname change or role change (which are server specific)
                    if prop["display_name"] in ["Nickname", "Roles"]:
                        channel_id = await self.bot.get_config_key(before, "mod_log_channel")
                        if channel_id:
                            channel = self.bot.get_channel(channel_id)
                            await channel.send(embed=log)

                    else:
                        shared_guilds = [x for x in self.bot.guilds if after in x.members]
                        for guild in shared_guilds:
                            channel_id = await self.bot.get_config_key(guild, "mod_log_channel")

                            if channel_id:
                                channel = self.bot.get_channel(channel_id)
                                await channel.send(embed=log)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        await self.prop_change_handler(before, after)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.Member, after: discord.Member) -> None:
        await self.prop_change_handler(before, after)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        channel_id = await self.bot.get_config_key(member, "mod_log_channel")
        if channel_id is None:
            return

        channel = self.bot.get_channel(channel_id)
        member_left = Embed(title=":information_source: User Left", color=Colour.from_rgb(218, 118, 39))
        member_left.add_field(name="User", value=f"{member} ({member.id})\n {member.mention}")

        joined_at = member.joined_at
        if joined_at is not None:
            rn = discord.utils.utcnow()

            a = self.bot.correct_time(joined_at, timezone_="UTC")

            since_joined = (rn - a)
            since_str = ""
            props = ["weeks", "days", "hours", "minutes", "seconds", "milliseconds", "microseconds"]
            for prop in props:
                if prop in dir(since_joined):  # datetime delta objects have no standard get method :(
                    since_str += f"{since_joined.__getattribute__(prop)} {prop} " if since_joined.__getattribute__(prop) else ""
            user_joined = a.strftime(self.bot.ts_format)
            member_left.add_field(name="Joined", value=f"{user_joined} ({since_str} ago)" if joined_at else "Undetected")

        roles = [f"{role.mention}" for role in member.roles][1:]  # 1: eliminates @@everyone
        roles_str = ""
        for role_ in roles:
            roles_str += f"{role_}, "
        roles_str = roles_str[:len(roles_str) - 2]

        member_left.add_field(name="Roles", value=roles_str if member.roles[1:] else "None", inline=False)
        member_left.set_thumbnail(url=get_user_avatar_url(member))
        member_left.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=member_left)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        guild = member.guild

        ichannel_id = await self.bot.get_config_key(guild, "invite_log_channel")
        if ichannel_id is None:  # If invite channel not set
            return
        ichannel = self.bot.get_channel(ichannel_id)
        old_invites = self.invites[guild.id]
        new_invites = await self.get_all_invites(guild)

        updated_invites = []
        possible_joins_missed = False
        for invite in new_invites:
            found = False
            for old_invite in old_invites:
                if old_invite.code == invite.code:
                    found = True
                    if invite.uses > old_invite.uses:
                        updated_invites.append(invite)
                        if invite.uses - old_invite.uses != 1:
                            possible_joins_missed = True

            if not found and invite.uses != 0:  # else 0-use invites will be logged
                updated_invites.append(invite)  # new invites

        self.invites[guild.id] = new_invites
        if ichannel:  # still check & update invites in case channel is configured later
            invite_log = Embed(title="Invite data", color=Colour.from_rgb(0, 0, 255))
            if len(updated_invites) == 1:
                invite_log.set_author(
                    name=f"{updated_invites[0].inviter} ~ {updated_invites[0].inviter.display_name}" if updated_invites[0].inviter else f"{guild.name} ~ Vanity URL",
                    icon_url=get_user_avatar_url(updated_invites[0].inviter))

                invite_log.description = ":arrow_up: Inviter Avatar\n:arrow_right: Member Avatar"
            else:
                invite_log.description = ":arrow_right: Member Avatar"

            invite_log.add_field(name="Member", value=member.mention)

            for x, invite in enumerate(updated_invites):
                invite_log.add_field(
                    name=f"\nPossible Invite #{x + 1}\n\nInviter" if len(updated_invites) != 1 else "Inviter",
                    value=invite.inviter.mention if invite.inviter else "Server (Vanity)",
                    inline=len(updated_invites) == 1)

                invite_log.add_field(name="Code", value=invite.code)
                invite_log.add_field(name="Channel", value=invite.channel.mention)
                invite_log.add_field(name="Expires", value=self.bot.time_str(invite.max_age) if invite.max_age != 0 else "Never")
                invite_log.add_field(name="Uses", value=str(invite.uses) + (f"/{invite.max_uses}" if invite.max_uses != 0 else ""))
                invite_log.add_field(name="Invite Created", value=self.bot.correct_time(invite.created_at).strftime(self.bot.ts_format), inline=False)

            invite_log.add_field(name="Account created", value=self.bot.correct_time(member.created_at).strftime(self.bot.ts_format), inline=False)

            if not updated_invites:
                invite_log.add_field(name="Invite used", value="Undetected")

            invite_log.set_thumbnail(url=get_user_avatar_url(member))
            if (invite_log.to_dict() not in self.previous_inv_log_embeds) or not updated_invites:  # limits log spam e.g. if connection drops

                if possible_joins_missed or len(updated_invites) != 1:
                    await get(guild.text_channels, name='invite-logs').send("*WARNING: Due to a bot glitch or other reason, the below data may be inaccurate due to potentially missed previous joins.*")

                self.previous_inv_log_embeds.append(invite_log.to_dict())
                await ichannel.send(embed=invite_log)

        channel_id = await self.bot.get_config_key(guild, "mod_log_channel")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)

        member_join = Embed(title=":information_source: User Joined", color=Colour.from_rgb(52, 215, 189))
        member_join.add_field(name="User", value=f"{member} ({member.id})\n | {member.mention}")
        member_join.add_field(name="Created",
                              value=self.bot.correct_time(member.created_at).strftime(self.bot.ts_format))
        member_join.set_thumbnail(url=get_user_avatar_url(member))
        member_join.set_footer(text=self.bot.correct_time().strftime(self.bot.ts_format))
        await channel.send(embed=member_join)


def setup(bot) -> None:
    bot.add_cog(Logging(bot))
