# -*- coding: utf-8 -*-
from .advart import AdvArt


async def setup(bot):
    cog = AdvArt(bot)
    await bot.add_cog(cog)
