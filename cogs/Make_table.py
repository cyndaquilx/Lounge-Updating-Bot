import discord
import re

from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from typing import Union

player_score = {}


class Make_table(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._remove_score_task = self.remove_expired_score.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, Union[discord.TextChannel, discord.Thread]):
            return
        if message.author.bot or message.guild is None or "tier" not in message.channel.name or "results" in message.channel.name:
            return

        if message.content.isdecimal() and 12 <= int(message.content) <= 180:
            player_score[message.author.display_name] = {"time": datetime.now(), "score": message.content}
            
    @tasks.loop(minutes=1)
    async def remove_expired_score(self):
        expired_date = datetime.now()-timedelta(minutes=30)
        for player, data in list(player_score.items()):
            if data['time'] < expired_date:
                player_score.pop(player)


@app_commands.context_menu(name="Make table")
async def make_table(interaction: discord.Interaction, message: discord.Message):
    """setup the command to submit table"""

    if "**Poll Ended!**" not in message.content or not isinstance(message.channel, Union[discord.TextChannel, discord.Thread]):
        return await interaction.response.send_message(content="invalid message", ephemeral=True)

    scoreboard_split = message.content.split("!scoreboard")
    if len(scoreboard_split) < 2:
        await interaction.response.send_message("It appears this is a Lounge Queue room, try using `/scoreboard`.", ephemeral=True)
        return
    player_data = scoreboard_split[1]
    player_split = player_data.replace("`", '').split()
    player_count = player_split[0]
    player_list = " ".join(player_split[1:]).replace("`", '').split(", ")
    formated_players = ""
    tier = re.split("-|_", message.channel.name)[1]

    for player in player_list:
        if player in player_score:
            formated_players += f"{player} {player_score[player]['score']}\n"
        else:
            formated_players += f"{player} 0\n"

    await interaction.response.send_message(content=f"!submit {str(round(12/int(player_count)))} {tier}\n{formated_players}")


async def setup(bot: commands.Bot):
    bot.tree.add_command(make_table)
    await bot.add_cog(Make_table(bot))