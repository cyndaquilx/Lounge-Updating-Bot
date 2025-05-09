import discord
from discord.ext import commands
from models import VerifyView, UpdatingBot

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def sb(self, ctx: commands.Context[UpdatingBot]):
        assert ctx.guild is not None
        e = discord.Embed(title=f"{ctx.guild.name}")
        e.add_field(name="Verify", value="Click the button below to get verified.")
        await ctx.send(embed=e, view=VerifyView(timeout=None))

async def setup(bot: UpdatingBot):
    await bot.add_cog(Verification(bot))
    bot.add_view(VerifyView(timeout=None))
