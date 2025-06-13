import discord
from discord import app_commands
from discord.ext import commands
import re

import API.post, API.get

from custom_checks import command_check_reporter_roles, check_staff_roles, leaderboard_autocomplete, check_displayable_name
from models import TableBasic, Player
from util import submit_table, delete_table, get_leaderboard
from datetime import datetime
from typing import Optional
from util import get_leaderboard_slash
import json

class Tables(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.check(command_check_reporter_roles)
    @commands.command(aliases=['undo'])
    async def delete(self, ctx, table_id:int, *, reason=""):
        lb = get_leaderboard(ctx)
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is None:
            await ctx.send("Table not found")
            return
        # players that aren't lounge staff can't delete other people's tables or already updated tables
        if not check_staff_roles(ctx):
            if table.verified_on:
                await ctx.send("This table has been updated already, so you can't delete it. If there's an error with the table, please contact a staff member.")
                return
            if ctx.author.id != table.author_id:
                await ctx.send("You are not the author of this table!")
                return
        await delete_table(ctx, lb, table, reason=reason)

    @commands.check(command_check_reporter_roles)
    @commands.command()
    async def submit(self, ctx: commands.Context, size:int, tier: str, *, data: str):
        lb = get_leaderboard(ctx)
        
        tier = tier.upper()
        if tier not in lb.tier_results_channels.keys():
            await ctx.send(f"Your tier is not valid. Correct tiers are: {list(lb.tier_results_channels.keys())}")
            return
        #functions for parsing lorenzi table data
        def isGps(scores:str):
            gps = re.split("[|+]", scores)
            for gp in gps:
                if gp.strip().isdigit() == False:
                    return False
        def get_gps(scores: str):
            gp_strings = re.split("[|+]", scores)
            gp_scores: list[int] = []
            for gp in gp_strings:
                gp_score = int(gp.strip())
                gp_scores.append(gp_score)
            # if there's only 1 gp per mogi for our lb,
            # just return the total sum
            if lb.gps_per_mogi == 1:
                return [sum(gp_scores)]
            return gp_scores

        def removeExtra(line):
            splitLine = line.split()
            if line.strip() == "":
                return False
            if len(splitLine) == 1:
                return False
            scores = splitLine[len(splitLine)-1]
            if scores.isdigit() == False and isGps(scores) == False:
                return False
            else:
                return True
            
        # parse date from input if it exists
        date_pattern = r"#date (\d{4}-\d{2}-\d{2})"
        match = re.search(date_pattern, data)
        date = None
        if match:
            date_str = match.group(0).replace("#date ", "")
            date = datetime.strptime(date_str, "%Y-%m-%d")

        lines = filter(removeExtra, data.split("\n"))
        names: list[str] = []
        scores: list[list[int]] = []
        for line in lines:
            # removes country flag brackets
            newline = re.sub(r"[\[].*?[\]]", "", line).split()
            names.append(" ".join(newline[0:len(newline)-1]))
            gps = newline[len(newline)-1]
            gp_scores = get_gps(gps)
            if len(gp_scores) != lb.gps_per_mogi:
                await ctx.send(f"One of your submitted scores has {len(gp_scores)} GPs but this leaderboard requires {lb.gps_per_mogi} GPs.")
                return
            scores.append(gp_scores)
        player_settings = lb.player_settings.get(len(names), None)
        if player_settings is None:
            valid_player_counts = " or ".join([str(c) for c in lb.player_settings.keys()])
            await ctx.send(f"Your table does not contain {valid_player_counts} valid score lines, try again!")
            return
        valid_formats = player_settings.valid_formats
        if size not in valid_formats:
            await ctx.send(f"Your size is not valid. Correct sizes are: {valid_formats}")
            return
        
        lower_names = [n.lower() for n in names]
        if len(set(lower_names)) < len(lower_names):
            await ctx.send("Duplicate names are not allowed, please try again.")
            return
        
        #checking names with the leaderboard API
        players = await API.get.getPlayers(lb.website_credentials, names)
        err_str = ""
        found_players: list[Player] = []
        for i, player in enumerate(players):
            if player is None:
                if check_displayable_name(names[i]):
                    err_str += f"{names[i]}\n"
                else:
                    err_str += f"<invalid_name>\n"
            else:
                found_players.append(player)
        if len(err_str) > 0:
            await ctx.send(f"The following players cannot be found on the leaderboard:\n{err_str}")
            return
        table = TableBasic.from_text(size, tier, found_players, scores, ctx.author.id, date)
        await submit_table(ctx, lb, table)

    @app_commands.guilds(280462328603082753)
    @app_commands.command(name="lorenzi_mk7")
    @app_commands.autocomplete(leaderboard=leaderboard_autocomplete)
    @app_commands.guild_only()
    async def parse_lorenzi_gb(self, interaction: discord.Interaction, json_file: discord.Attachment, from_id: Optional[int], to_id: Optional[int], leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await interaction.response.defer()
        file = await json_file.read()
        body = json.loads(file.decode())
        matches = body['data']['team']['matches'][::-1]
        for match in matches:
            match_id = match['index']+1
            if from_id and match_id < from_id:
                continue
            if to_id and match_id > to_id:
                continue
            match_data = json.loads(match['matchData'])
            size = int(8/len(match_data['teams']))
            if size == 8:
                size = 1
            date = datetime.fromtimestamp(match['playDate']/1000)
            names = []
            scores: list[list[int]] = []
            for team in match_data['teams']:
                for player in team['players']:
                    name = player['name'].strip()
                    player_scores = player['scores']
                    if len(player_scores) < 3:
                        score = [sum(player_scores), 0, 0]
                    else:
                        score = player_scores
                    names.append(name)
                    scores.append(score)
            #checking names with the leaderboard API
            players = await API.get.getPlayers(lb.website_credentials, names)
            err_str = ""
            found_players: list[Player] = []
            for i, player in enumerate(players):
                if player is None:
                    if check_displayable_name(names[i]):
                        err_str += f"{names[i]}\n"
                    else:
                        err_str += f"<invalid_name>\n"
                else:
                    found_players.append(player)
            if len(err_str) > 0:
                await ctx.send(f"The following players cannot be found on the leaderboard for table ID {match_id}:\n{err_str}")
                return
            table = TableBasic.from_text(size, "ALL", found_players, scores, ctx.author.id, date)
            res = await submit_table(ctx, lb, table, bypass_confirmation=True)
            if res is None:
                await ctx.send(f"Stopped before match ID {match_id}")
                return
        await ctx.send("Successfully submitted all tables")

       
async def setup(bot):
    await bot.add_cog(Tables(bot))
