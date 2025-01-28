import discord
from discord import app_commands
from discord.ext import commands

from util import get_leaderboard_slash
from models import LeaderboardConfig, ServerConfig
from custom_checks import app_command_check_reporter_roles, check_role_list, command_check_staff_roles
import API.get
import custom_checks

from typing import Optional
from enum import Enum
import math

class PenaltyInstance:
    def __init__(self, penalty_name, amount, player_name, total_repick, races_played_alone, table_id, reason, is_strike):
        self.penalty_name = penalty_name
        self.amount = amount
        self.player_name = player_name
        self.total_repick = total_repick
        self.races_played_alone = races_played_alone
        self.table_id = table_id
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

CHECK_BOX = "\U00002611"
X_MARK = "\U0000274C"

class Request(commands.Cog):
    def __init__ (self, bot):
        self.bot = bot

    request_group = app_commands.Group(name="request", description="Requests to staff")

    #Dictionary containing: message ID -> (penalty instance, request log, context, leaderboardconfig)
    request_queue = {}

    async def penalty_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        choices = [app_commands.Choice(name=penalty_name, value=penalty_name) for penalty_name in penalty_static_info.keys()]
        return choices

    #Enum type to limit command args
    RepickSize = Enum('RepickSize', [('1', 1), ('2', 2), ('3', 3), ('4', 4), ('5', 5), ('6', 6), ('7', 7), ('8', 8), ('9', 9), ('10', 10), ('11', 11)])

    #Parameters: the staff accepting the request, the message_id from the request message in the dedicated request channel
    async def accept_request(self, staff: discord.User, message_id: int, clean_message=True):
        penalty_data = self.request_queue.get(message_id, None)
        if penalty_data == None:
            return
        penalty_instance: PenaltyInstance = penalty_data[0]
        embed_message_log = penalty_data[1]
        initial_ctx = penalty_data[2]
        lb = penalty_data[3]
        updating_log = initial_ctx.guild.get_channel(lb.updating_log_channel)
        penalty_channel = initial_ctx.guild.get_channel(lb.penalty_channel)
        
        penalties_cog = self.bot.get_cog('Penalties')
        initial_ctx.channel = penalty_channel
        initial_ctx.interaction = None #To remove the automatic reply to first message
        no_error = True
        if penalty_instance.penalty_name == "Repick":
            #Repick automation
            total_pen_func_call = math.ceil(penalty_instance.total_repick/4)
            for i in range(total_pen_func_call):
                if i == total_pen_func_call-1:
                    need_strike = penalty_instance.total_repick > 1
                    no_error = no_error and await penalties_cog.add_penalty(initial_ctx, lb, penalty_instance.amount*(penalty_instance.total_repick-(4*(total_pen_func_call-1))), "", [penalty_instance.player_name], reason=penalty_instance.penalty_name, is_anonymous=True, is_strike=need_strike, is_request=True)
                else:
                    no_error = no_error and await penalties_cog.add_penalty(initial_ctx, lb, penalty_instance.amount*4, "", [penalty_instance.player_name], reason=penalty_instance.penalty_name, is_anonymous=True, is_strike=False, is_request=True)
        else:
            if penalty_instance.penalty_name == "Drop mid mogi":
                #Handle setml here
                updating_cog = self.bot.get_cog('Updating')
                mlraces_args = penalty_instance.player_name + " " + str(penalty_instance.races_played_alone)
                await updating_cog.multiplierRaces(initial_ctx, penalty_instance.table_id, extraArgs=mlraces_args)

            #no_error = no_error and await penalties_cog.add_penalty(initial_ctx, lb, penalty_instance.amount, "", [penalty_instance.player_name], reason=penalty_instance.reason, is_anonymous=True, is_strike=penalty_instance.is_strike, is_request=True)

        if no_error:
            e_accepted = discord.Embed(title="Penalty request accepted")
            e_accepted.add_field(name="Request", value=embed_message_log.jump_url)
            e_accepted.add_field(name="Accepted by", value=staff.mention, inline=False)
            await updating_log.send(embed=e_accepted)
        else:
            e_error = discord.Embed(title="Penalty request error")
            e_error.add_field(name="Request", value=embed_message_log.jump_url)
            e_error.add_field(name="Accepted by", value=staff.mention, inline=False)
            await updating_log.send(embed=e_error)

        if clean_message:
            del self.request_queue[message_id]
        request_message = await penalty_channel.fetch_message(message_id)
        await request_message.delete()

    async def add_penalty_to_channel(self, ctx: commands.Context, lb: LeaderboardConfig, penalty_type: str, player_name: str, repick_number=0, races_played_alone=0, table_id=0, reason=""):
        e = discord.Embed(title="Penalty request")
        e.add_field(name="Player", value=player_name, inline=False)
        e.add_field(name="Penalty type", value=penalty_type)
        if penalty_type == "Repick":
            e.add_field(name="Number of repick", value=repick_number)
        e.add_field(name="Issued from", value=ctx.channel.mention)
        if table_id != 0 and table_id != None:
            e.add_field(name="Table ID", value=table_id)
        if reason != "" and reason != None:
            e.add_field(name="Reason from reporter", value=reason, inline=False)
        penalty_channel = ctx.guild.get_channel(lb.penalty_channel)
        embed_message = await penalty_channel.send(embed=e)
                
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if penalty_type == "Drop mid mogi":
            e.add_field(name="Number of races with missing teammate", value=races_played_alone)
        e.add_field(name="Requested by", value=ctx.author, inline=False)
        embed_message_log = await updating_log.send(embed=e)

        #Reply for the reporter
        await ctx.send(f"Penalty request issued for player {player_name}. Reason: {penalty_type}\nLink to request: {embed_message.jump_url}", ephemeral=True)

        await embed_message.add_reaction(CHECK_BOX)
        await embed_message.add_reaction(X_MARK)

        penalty_data = penalty_static_info.get(penalty_type)
        self.request_queue[embed_message.id] = (PenaltyInstance(penalty_type, penalty_data[0], player_name, repick_number, races_played_alone, table_id, reason, penalty_data[1]), embed_message_log, ctx, lb)


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
        penalty_data = self.request_queue.get(reaction.message.id, None)
        if penalty_data == None:
            return

        print("Has reacted to a correct message")
        
        embed_message_log = penalty_data[1]
        ctx = penalty_data[2]
        lb = penalty_data[3]
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)

        if str(reaction.emoji) == X_MARK and (user == ctx.author or check_role_list(user, (server_info.admin_roles + server_info.staff_roles))):
            e_refused = discord.Embed(title="Penalty request refused")
            e_refused.add_field(name="Request", value=embed_message_log.jump_url)
            e_refused.add_field(name="Refused by", value=user.mention, inline=False)
            await updating_log.send(embed=e_refused)
            
            del self.request_queue[reaction.message.id]
            await reaction.message.delete()

        if str(reaction.emoji) == CHECK_BOX and check_role_list(user, (server_info.admin_roles + server_info.staff_roles)):
            await self.accept_request(user, reaction.message.id)
            


    @app_commands.check(app_command_check_reporter_roles)
    @request_group.command(name="penalty")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.autocomplete(penalty_type=penalty_autocomplete)
    async def append_penalty_slash(self, interaction: discord.Interaction, penalty_type: str, player_name: str, repick_number: Optional[RepickSize], races_played_alone: Optional[int], table_id: Optional[int], reason: Optional[str], leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        repick_number = repick_number.value if repick_number != None else 0
        if penalty_type not in penalty_static_info.keys():
            await ctx.send("This penalty type doesn't exist", ephemeral=True)
        if penalty_type == "Drop mid mogi":
            if table_id == None:
                await ctx.send("This penalty requires you to give a valid table id", ephemeral=True)
                return
            table = await API.get.getTable(lb.website_credentials, table_id)
            if table is False:
                await ctx.send("This penalty requires you to give a valid table id", ephemeral=True)
                return
            if races_played_alone == None:
                races_played_alone = 0

        await self.add_penalty_to_channel(ctx, lb, penalty_type, player_name, repick_number=repick_number, races_played_alone=races_played_alone, table_id=table_id, reason=reason)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['accept_all'])
    async def accept_all_requests(self, ctx: commands.Context):
        messages_to_clean = []
        for message_id in self.request_queue.keys():
            await self.accept_request(ctx.author, message_id, False)
            messages_to_clean.append(message_id)
        for id in messages_to_clean:
            del self.request_queue[id]

async def setup(bot):
    await bot.add_cog(Request(bot))