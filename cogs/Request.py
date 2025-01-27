import discord
from discord import app_commands
from discord.ext import commands

from util import get_leaderboard_slash, set_multipliers
from models import LeaderboardConfig
from custom_checks import request_validation_check, app_command_check_reporter_roles
import API.get

from typing import Optional
from enum import Enum
import math

class Request(commands.Cog):
    def __init__ (self, bot):
        self.bot = bot

    request_group = app_commands.Group(name="request", description="Requests to staff")

    #Enum types to limit command args
    PenaltyType = Enum('PenaltyType', [('Late', 1), ('Drop mid mogi', 2), ('Drop before start', 3), ('Tag penalty', 4), ('Repick', 5), ('No video proof', 6), ('Host issues', 7), ('Host carelessness prevents a table from being made', 8), ('No host', 9)])
    RepickSize = Enum('RepickSize', [('1', 1), ('2', 2), ('3', 3), ('4', 4), ('5', 5), ('6', 6), ('7', 7), ('8', 8), ('9', 9), ('10', 10), ('11', 11)])

    async def add_penalty_to_channel(self, ctx: commands.Context, lb: LeaderboardConfig, penalty_type: PenaltyType, player_name: str, repick_number=1, reason=""):
        e = discord.Embed(title="Penalty request")
        e.add_field(name="Player", value=player_name, inline=False)
        e.add_field(name="Penalty type", value=penalty_type.name)
        if penalty_type.name == "Repick":
            e.add_field(name="Number of repick", value=repick_number)
        e.add_field(name="Issued from", value=ctx.channel.mention)
        if reason != "" and reason != None:
            e.add_field(name="Reason from reporter", value=reason, inline=False)
        penalty_channel = ctx.guild.get_channel(lb.penalty_channel)
        embed_message = await penalty_channel.send(embed=e)
        
        #Reply for the reporter
        await ctx.send(f"Penalty request issued for player {player_name}. Reason: {penalty_type.name}\nLink to request: {embed_message.jump_url}", ephemeral=True)
        
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
            if penalty_type.name == "Late":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type.name == "Drop mid mogi":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type.name == "Drop before start":
                await penalties_cog.add_penalty(ctx, lb, 100, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type.name == "Tag penalty":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=False, is_request=True)
            elif penalty_type.name == "Repick":
                total_pen_func_call = math.ceil(repick_number/4)
                for i in range(total_pen_func_call):
                    if i == total_pen_func_call-1:
                        need_strike = repick_number > 1
                        await penalties_cog.add_penalty(ctx, lb, 50*(repick_number-(4*(total_pen_func_call-1))), "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=need_strike, is_request=True)
                    else:
                        await penalties_cog.add_penalty(ctx, lb, 200, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=False, is_request=True)
            elif penalty_type.name == "No video proof":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type.name == "Host issues":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type.name == "Host carelessness prevents a table from being made":
                await penalties_cog.add_penalty(ctx, lb, 100, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=True, is_request=True)
            elif penalty_type.name == "No host":
                await penalties_cog.add_penalty(ctx, lb, 50, "", [player_name], reason=penalty_type.name, is_anonymous=True, is_strike=True, is_request=True)

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


    @app_commands.check(app_command_check_reporter_roles)
    @request_group.command(name="penalty")
    async def append_penalty_slash(self, interaction: discord.Interaction, penalty_type: PenaltyType, player_name: str, repick_number: Optional[RepickSize], reason: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, None)
        repick_number = repick_number.value if repick_number != None else 1
        await self.add_penalty_to_channel(ctx, lb, penalty_type, player_name, repick_number=repick_number, reason=reason)

    @app_commands.check(app_command_check_reporter_roles)
    @request_group.command(name="loss_reduction")
    async def append_loss_reduction_slash(self, interaction: discord.Interaction, table_id: int, player_name: str, races_played_alone: int):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, None)
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