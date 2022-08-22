# -*- coding: utf-8 -*-
from .advart import AdvArt


async def setup(bot):
    cog = AdvArt(bot)
    bot.add_cog(cog)
