from discord.ext import commands
from models import LeaderboardConfig, Table
import API.get, API.post
from util.Players import place_player_with_mmr
import re

def parse_multipliers(args: str):
    # multipliers are separated by comma: ex. Cynda 0.5, Vike 1.0
    mult_args = args.split(",")
    multipliers: dict[str, float] = {}
    for mult in mult_args:
        split_mult = mult.split()
        if len(split_mult) >= 2:
            # the player name is every word of the split multiplier besides the last one,
            # which is the number
            player_name = " ".join(split_mult[:-1]).strip()
            player_mult = split_mult[-1].strip()
            try:
                if float(player_mult) < 0.0 or float(player_mult) > 2.0:
                    errMsg = f"{player_mult} is not a valid multiplier!"
                    return None, errMsg
                multipliers[player_name] = float(player_mult)
            except Exception as e:
                errMsg = f"{player_mult} is not a valid multiplier!"
                return None, errMsg
    return multipliers, None

def parse_scores(lb: LeaderboardConfig, args: str):
    # arguments are separated by commas: ex. Cynda 82, Vike 83
    player_scores = args.split(",")
    scores: dict[str, list[int]] = {}
    for score in player_scores:
        split_score = score.split()
        if len(split_score) >= 2:
            # the player name is every word of the split score besides the last one,
            # which is the number
            player_name = " ".join(split_score[:-1]).strip()
            player_score = split_score[-1].strip()
            player_gp_scores = re.split("[|+]", player_score)
            if len(player_gp_scores) != lb.gps_per_mogi:
                errMsg = f"Score for {player_name} has {len(player_gp_scores)} GPs but this leaderboard requires {lb.gps_per_mogi} GPs."
                return None, errMsg
            for gp_score in player_gp_scores:
                if not gp_score.isdigit():
                    errMsg = f"{gp_score} is not a valid score!"
                    return None, errMsg
                if int(gp_score) < 0 or int(gp_score) > 180:
                    errMsg = f"{gp_score} is not a valid score!"
                    return None, errMsg
            player_gp_scores = [int(gp) for gp in player_gp_scores]
            scores[player_name] = player_gp_scores
    return scores, None

async def set_multipliers(ctx: commands.Context, lb: LeaderboardConfig, table_id: int, args: str):
    multipliers, error = parse_multipliers(args)
    if multipliers is None:
        await ctx.send(error)
        return False
    if multipliers != {}:
        updatedMultipliers = await API.post.setMultipliers(lb.website_credentials, table_id, multipliers)
        if updatedMultipliers is not True:
            await ctx.send("Error setting multipliers:\n%s"
                            % updatedMultipliers)
            return False
    return True

async def check_placements(ctx: commands.Context, lb: LeaderboardConfig, table: Table):
    for team in table.teams:
        for score in team.scores:
            if score.prev_mmr is None:
                place_mmr = lb.get_place_mmr(score.score)
                await place_player_with_mmr(ctx, lb, place_mmr, score.player.name, log=False)
