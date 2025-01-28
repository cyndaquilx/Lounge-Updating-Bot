import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from util import LeaderboardNotFoundException, GuildNotFoundException, get_config, Translator

config = get_config('./config.json')

logging.basicConfig(level=logging.INFO,
                    datefmt='%Y-%m-%d %H:%M:%S',
                    format='[{asctime}] [{levelname:<8}] {name}: {message}',
                    style='{')
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents, application_id = config.application_id)
bot = commands.Bot(command_prefix=config.get_prefixes(), case_insensitive=True, intents=intents,
                    tree = app_commands.CommandTree(client))
bot.config = config
print(bot.command_prefix)

initial_extensions = ['cogs.Updating', 'cogs.Tables', 'cogs.Admin', 'cogs.Restrictions', 'cogs.Make_table', 'cogs.Players', 
                      'cogs.Names', 'cogs.Penalties', 'cogs.Bonuses', 'cogs.Reactions', 'cogs.Request']
#initial_extensions = ['cogs.Admin',]

@bot.event
async def on_ready():
    print("Logged in as {0.user}".format(bot))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await(await ctx.send("Your command is missing an argument: `%s`" %
                       str(error.param))).delete(delay=10)
        return
    if isinstance(error, commands.CommandOnCooldown):
        await(await ctx.send("This command is on cooldown; try again in %.0fs"
                       % error.retry_after)).delete(delay=5)
        return
    if isinstance(error, commands.MissingAnyRole):
        await(await ctx.send("You need one of the following roles to use this command: `%s`"
                             % (", ".join(error.missing_roles)))
              ).delete(delay=10)
        return
    if isinstance(error, commands.BadArgument):
        await(await ctx.send("BadArgument Error: `%s`" % error.args)).delete(delay=10)
        return
    if isinstance(error, commands.BotMissingPermissions):
        await(await ctx.send("I need the following permissions to use this command: %s"
                       % ", ".join(error.missing_perms))).delete(delay=10)
        return
    if isinstance(error, commands.NoPrivateMessage):
        await(await ctx.send("You can't use this command in DMs!")).delete(delay=5)
        return
    if isinstance(error, commands.BadUnionArgument):
        await(await ctx.send("Please use either a integer or mention a user")).delete(delay=10)
        return
    if isinstance(error, LeaderboardNotFoundException):
        return
    if isinstance(error, GuildNotFoundException):
        await(await ctx.send("You cannot use this command in this server!")).delete(delay=10)
        return
    raise error

@bot.tree.error
async def on_app_command_error(interaction:discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(f"You are missing the following permissions to use this command: " +
            f"{','.join(error.missing_permissions)}", ephemeral=True)
        return
    if isinstance(error, LeaderboardNotFoundException):
        await interaction.response.send_message("Please enter a valid leaderboard to use this command")
        return
    if isinstance(error, GuildNotFoundException):
        await interaction.response.send_message("You cannot use this command in this server!")
        return
    if isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("You need one of the following roles to use this command: `%s`"
                             % (", ".join(error.missing_roles)))
        return
    raise error

async def main():
    async with bot:
        await bot.tree.set_translator(Translator.CustomTranslator())
        for extension in initial_extensions:
            await bot.load_extension(extension)
        await bot.start(bot.config.token)
        await bot.tree.sync()

asyncio.run(main())
