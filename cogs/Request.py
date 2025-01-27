import discord
from discord import app_commands
from discord.ext import commands

from util import get_leaderboard_slash, set_multipliers
from models import LeaderboardConfig, ServerConfig
from custom_checks import request_validation_check, app_command_check_reporter_roles
import API.get
import custom_checks

from typing import Optional
from enum import Enum
import math

class PenaltyInstance:
    def __init__(self, penalty_name, amount, player_name, total_repick, reason, is_strike):
        self.penalty_name = penalty_name
        self.amount = amount
        self.player_name = player_name
        self.total_repick = total_repick
        self.reason = reason
        self.is_strike = is_strike

penalty_static_info = {
    "Late": (50, True),
    "Drop mid mogi": (50, True),
    "Drop before start": (100, True),
    "Tag penalty": (50, False),
    "Repick": (50, False),
    "No video proof": (50, True),
    "Host issues": (50, True),
    "Host carelessness prevents a table from being made": (100, True),
    "No host": (50, True)
}

class Request(commands.Cog):
    def __init__ (self, bot):
        self.bot = bot

    request_group = app_commands.Group(name="request", description="Requests to staff")

    #Dictionary containing: message ID -> penalty instance
    request_queue = {}

    async def penalty_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        choices = [app_commands.Choice(name=penalty_name, value=penalty_name) for penalty_name in penalty_static_info.keys()]
        return choices

    #Enum type to limit command args
    RepickSize = Enum('RepickSize', [('1', 1), ('2', 2), ('3', 3), ('4', 4), ('5', 5), ('6', 6), ('7', 7), ('8', 8), ('9', 9), ('10', 10), ('11', 11)])

    async def add_penalty_to_channel(self, ctx: commands.Context, lb: LeaderboardConfig, penalty_type: str, player_name: str, repick_number=0, reason=""):
        e = discord.Embed(title="Penalty request")
        e.add_field(name="Player", value=player_name, inline=False)
        e.add_field(name="Penalty type", value=penalty_type)
        if penalty_type == "Repick":
            e.add_field(name="Number of repick", value=repick_number)
        e.add_field(name="Issued from", value=ctx.channel.mention)
        if reason != "" and reason != None:
            e.add_field(name="Reason from reporter", value=reason, inline=False)
        penalty_channel = ctx.guild.get_channel(lb.penalty_channel)
        embed_message = await penalty_channel.send(embed=e)
        
        #Reply for the reporter
        await ctx.send(f"Penalty request issued for player {player_name}. Reason: {penalty_type}\nLink to request: {embed_message.jump_url}", ephemeral=True)
        
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        e.add_field(name="Requested by", value=ctx.author, inline=False)
        embed_message_log = await updating_log.send(embed=e)

        penalty_accepted, user = await request_validation_check(ctx, embed_message)
        await embed_message.delete()
        if user == None:
            ctx.send("Error while trying to validate request")
            return
        if not penalty_accepted:
            e_refused = discord.Embed(title="Penalty request refused")
            e_refused.add_field(name="Request", value=embed_message_log.jump_url)
            e_refused.add_field(name="Refused by", value=user.mention, inline=False)
            await updating_log.send(embed=e_refused)
        else:
            e_accepted = discord.Embed(title="Penalty request accepted")
            e_accepted.add_field(name="Request", value=embed_message_log.jump_url)
            e_accepted.add_field(name="Accepted by", value=user.mention, inline=False)
            await updating_log.send(embed=e_accepted)

            penalties_cog = self.bot.get_cog('Penalties')
            ctx.author = user
            if penalty_type == "Late":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type == "Drop mid mogi":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type == "Drop before start":
                await penalties_cog.add_penalty(ctx, lb, 100, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type == "Tag penalty":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=False, is_request=True)
            elif penalty_type == "Repick":
                total_pen_func_call = math.ceil(repick_number/4)
                for i in range(total_pen_func_call):
                    if i == total_pen_func_call-1:
                        need_strike = repick_number > 1
                        await penalties_cog.add_penalty(ctx, lb, 50*(repick_number-(4*(total_pen_func_call-1))), "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=need_strike, is_request=True)
                    else:
                        await penalties_cog.add_penalty(ctx, lb, 200, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=False, is_request=True)
            elif penalty_type == "No video proof":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type == "Host issues":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type == "Host carelessness prevents a table from being made":
                await penalties_cog.add_penalty(ctx, lb, 100, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type == "No host":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type, is_anonymous=True, is_strike=True, is_request=True)

    async def add_loss_reduction_to_channel(self, ctx: commands.Context, lb: LeaderboardConfig, table_id: int, player_name: str, races_played_alone: int):
        e = discord.Embed(title="Loss reduction request")
        e.add_field(name="Player", value=player_name, inline=False)
        e.add_field(name="Table ID", value=table_id)
        e.add_field(name="Races played alone", value=races_played_alone)
        penalty_channel = ctx.guild.get_channel(lb.penalty_channel)
        embed_message = await penalty_channel.send(embed=e)

        #Reply for the reporter
        await ctx.send(f"Loss reduction request issued for player {player_name}.\nLink to request: {embed_message.jump_url}", ephemeral=True)

        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        e.add_field(name="Requested by", value=ctx.author, inline=False)
        embed_message_log = await updating_log.send(embed=e)

        loss_reduction_accepted, user = await request_validation_check(ctx, embed_message)
        await embed_message.delete()
        if user == None:
            ctx.send("Error while trying to validate request")
            return
        if not loss_reduction_accepted:
            e_refused = discord.Embed(title="Loss reduction request refused")
            e_refused.add_field(name="Request", value=embed_message_log.jump_url)
            e_refused.add_field(name="Refused by", value=user.mention, inline=False)
            await updating_log.send(embed=e_refused)
        else:
            e_accepted = discord.Embed(title="Loss reduction request accepted")
            e_accepted.add_field(name="Request", value=embed_message_log.jump_url)
            e_accepted.add_field(name="Accepted by", value=user.mention, inline=False)
            await updating_log.send(embed=e_accepted)

            #Multiplier value is written using 2 digit precision
            ctx.author = user
            multiplier = "%.2f" % (races_played_alone / 12)
            print(multiplier)
            if races_played_alone < 3:
                multiplier = "1"
            if races_played_alone > 7:
                multiplier = "0"
            setml_args = player_name + " " + multiplier

            await set_multipliers(ctx, lb, table_id, setml_args)

    #Used to monitor when someone reacts to a request in the penalty channel
    @commands.Cog.listener(name='on_reaction_add')
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return
        server_info: ServerConfig = self.bot.config.servers.get(reaction.message.guild.id, None)
        if not server_info:
            return
        channel_check = False #Used in order to avoid as much as possible further checks from unrelated reactions 
        for key, leaderboard_config in server_info.leaderboards.items():
            if reaction.message.channel.id == leaderboard_config.penalty_channel:
                channel_check = True
                break
        if not channel_check:
            return
        #TODO: Check for all stored messages

    @app_commands.check(app_command_check_reporter_roles)
    @request_group.command(name="penalty")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.autocomplete(penalty_type=penalty_autocomplete)
    async def append_penalty_slash(self, interaction: discord.Interaction, penalty_type: str, player_name: str, repick_number: Optional[RepickSize], reason: Optional[str], leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        repick_number = repick_number.value if repick_number != None else 0
        if penalty_type not in penalty_static_info.keys():
            await ctx.send("This penalty type doesn't exist", ephemeral=True)
        await self.add_penalty_to_channel(ctx, lb, penalty_type, player_name, repick_number=repick_number, reason=reason)

    @app_commands.check(app_command_check_reporter_roles)
    @request_group.command(name="loss_reduction")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def append_loss_reduction_slash(self, interaction: discord.Interaction, table_id: int, player_name: str, races_played_alone: int, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        if races_played_alone < 0 or races_played_alone > 12:
            await ctx.send("You entered a wrong number of races")
            return
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is False:
            await ctx.send("Table couldn't be found")
            return
        await self.add_loss_reduction_to_channel(ctx, lb, table_id, player_name, races_played_alone)


async def setup(bot):
    await bot.add_cog(Request(bot))