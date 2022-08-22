import logging
import random
import asyncio

from operator import itemgetter
from string import ascii_letters, digits

import discord

from redbot.core.bot import Red
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS


_ = Translator('AdvArt', __file__)
log = logging.getLogger("red.cogs.advart")


def is_allowed_user():
    async def predicate(ctx: commands.Context):
        cog: commands.Cog = ctx.cog
        if not cog:
            raise commands.CheckFailure

        if not ctx.guild:
            raise commands.CheckFailure

        allowed_users = await cog.config.guild(ctx.guild).allowed_users()

        return ctx.author.id in allowed_users

    return commands.check(predicate)


@cog_i18n(_)
class AdvArt(commands.Cog):
    """Adventure Art helper."""

    def __init__(self, bot: Red):
        self.bot = bot

        self.config = Config.get_conf(self, 2_750_301_101, force_registration=True)

        default_guild = {
            'adv_art_channel_id': None,
            'votes': {},
            'allowed_users': [],
            'upvote_emoji': None,
            'downvote_emoji': None,
        }

        self.config.register_guild(**default_guild)

    @commands.command()
    @commands.guild_only()
    @is_allowed_user()
    async def artchannel(self, ctx: commands.Context, *, channel: discord.TextChannel = None):
        """Set the adventure art channel."""

        await self.config.guild(ctx.guild).adv_art_channel_id.set(getattr(channel, 'id', None))

        if not channel:
            await ctx.send(_('Unset the adventure art channel.'))
        else:
            await ctx.send(_('Set {} as the adventure art channel.').format(channel.mention))

    @commands.command()
    @commands.guild_only()
    @is_allowed_user()
    async def emojis(self, ctx: commands.Context, upvote: discord.Emoji, downvote: discord.Emoji):
        """Set the upvote and downvote emojis."""

        await self.config.guild(ctx.guild).set_raw(
            'upvote_emoji', value={'name': upvote.name, 'id': upvote.id}
        )
        await self.config.guild(ctx.guild).set_raw(
            'downvote_emoji', value={'name': downvote.name, 'id': downvote.id}
        )

        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def allow(self, ctx: commands.Context, *, user: discord.User):
        """Add user to the allowed users list."""

        async with self.config.guild(ctx.guild).allowed_users() as allowed_users:
            if user.id not in allowed_users:
                allowed_users.append(user.id)
            await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def disallow(self, ctx: commands.Context, *, user: discord.User):
        """Remove user from the allowed users list."""

        async with self.config.guild(ctx.guild).allowed_users() as allowed_users:
            if user.id in allowed_users:
                allowed_users.remove(user.id)
                await ctx.tick()
            else:
                await ctx.send(_('User {} is not in allowed user lists.').format(user.name))

    @commands.command()
    @commands.guild_only()
    @is_allowed_user()
    async def votes(self, ctx: commands.Context, message_id: int):
        """Show the number of votes for an art submission."""

        votes = await self.config.guild(ctx.guild).votes()

        if str(message_id) not in votes:
            return await ctx.send(_('Votes not recorded for the given message id.'))

        up, down = self.count_votes(votes[str(message_id)])

        await ctx.send(
            _('Upvotes: {up}\nDownvotes: {down}\nTotal: {total}').format(
                up=up, down=down, total=up + down
            )
        )

    @commands.command()
    @commands.guild_only()
    @is_allowed_user()
    async def allvotes(self, ctx: commands.Context, sort: bool = False):
        """Show the number of votes for all stored art submissions."""

        votes = await self.config.guild(ctx.guild).votes()
        channel: discord.TextChannel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).adv_art_channel_id()
        )

        if not channel:
            return await ctx.send(_('Cannot find the adventure art channel.'))

        subs = []
        for message_id in votes:
            try:
                message: discord.Message = await channel.fetch_message(message_id)
            except Exception as e:
                log.error(f'Error fetching message {message_id} in {ctx.guild.name}: {e}')
                continue

            if len(message.attachments) < 1:
                continue

            up, down = self.count_votes(votes[message_id])

            embed = discord.Embed(
                description=_('{}\n\n[Jump to message!]({})').format(
                    message.content, message.jump_url
                ),
                color=0xFFCA33,
            )
            embed.add_field(name='Upvotes', value=up)
            embed.add_field(name='Downvotes', value=down)
            embed.add_field(name='Total', value=up + down)

            embed.set_image(url=message.attachments[0].proxy_url)

            subs.append((embed, up - down))

        if not subs:
            return await ctx.send(_('No submissions recorded!'))

        if sort:
            subs.sort(key=itemgetter(1), reverse=True)

        pages = []
        for i, (embed, __) in enumerate(subs):
            embed.set_footer(text=_('Page {} of {}').format(i + 1, len(subs)))
            pages.append(embed)

        await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60)

    @staticmethod
    def count_votes(votes):
        up, down = 0, 0
        for (__, score) in votes.items():
            if score == 1:
                up += 1
            elif score == -1:
                down += 1

        return up, down

    @commands.command()
    @commands.guild_only()
    @is_allowed_user()
    async def clearvotes(self, ctx: commands.Context):
        """Clears all the stored votes."""

        # SOURCE: https://github.com/aikaterna/gobcog/blob/7721dbfb96622d84ceb3e0dc8c7b60e13a592423/adventure/charsheet.py#L2177  # noqa: E501

        confirm_token = ''.join(random.choices((*ascii_letters, *digits), k=16))
        await ctx.send(
            'Running this command will **clear all stored votes.** '
            'You should only use it at the end of a contest, after results have been announced. '
            'If you wish to continue, enter this token as your next message.'
            f'\n\n{confirm_token}'
        )
        try:
            message = await ctx.bot.wait_for(
                'message',
                check=lambda m: m.channel.id == ctx.channel.id and m.author.id == ctx.author.id,
                timeout=60,
            )
        except asyncio.TimeoutError:
            await ctx.send(_('Did not get confirmation, cancelling.'))
            return False
        else:
            if message.content.strip() != confirm_token:
                await ctx.send(_('Did not get a matching confirmation, cancelling.'))
                return False

        async with self.config.guild(ctx.guild).votes() as votes:
            votes.clear()

        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @is_allowed_user()
    async def addreact(self, ctx: commands.Context, message_id: int):
        """Adds the upvote, downvote, and clear emojis to the given message."""

        adv_art_channel_id = await self.config.guild(ctx.guild).adv_art_channel_id()
        if not (channel := ctx.guild.get_channel(adv_art_channel_id)):
            return await ctx.send(_('Cannot find the adventure art channel.'))

        message: discord.Message = await channel.fetch_message(message_id)
        if not message:
            return await ctx.send(_('Cannot find the message with provided id.'))

        up = await self.config.guild(ctx.guild).upvote_emoji()
        down = await self.config.guild(ctx.guild).downvote_emoji()

        if not up or not down:
            return await ctx.send(_('Upvote/downvote emojis not set.'))

        await message.add_reaction(discord.PartialEmoji(name=up['name'], id=up['id']))
        await message.add_reaction(discord.PartialEmoji(name=down['name'], id=down['id']))
        await message.add_reaction('❌')

        async with self.config.guild(ctx.guild).votes() as votes:
            if str(message_id) not in votes:
                votes[str(message_id)] = {}

        await ctx.tick()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        if not payload.guild_id or not (guild := self.bot.get_guild(payload.guild_id)):
            return

        config = self.config.guild(guild)

        adv_art_channel_id = await config.adv_art_channel_id()
        if payload.channel_id != adv_art_channel_id:
            return

        emoji: discord.PartialEmoji = payload.emoji

        up = await config.upvote_emoji()
        down = await config.downvote_emoji()

        if not up or not down:
            return

        score = 0
        if emoji.name == up['name']:
            score = 1
        elif emoji.name == down['name']:
            score = -1

        async with self.config.guild(guild).votes() as votes:
            msg_id = str(payload.message_id)

            if msg_id in votes:
                votes[msg_id][payload.user_id] = score
            else:
                votes[msg_id] = {payload.user_id: score}

        if not (channel := guild.get_channel(payload.channel_id)):
            return

        message = await channel.fetch_message(payload.message_id)
        await message.remove_reaction(emoji, discord.Object(payload.user_id))
