from discord.ext import commands

async def check_against_automod_lists(ctx: commands.Context, message: str):
    rules = await ctx.guild.fetch_automod_rules()
    for rule in rules:
        for string in rule.trigger.keyword_filter:
            if string.replace("*", "") in message:
                return False
    return True
