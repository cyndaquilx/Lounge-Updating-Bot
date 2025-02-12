import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str

from util import get_leaderboard_slash
from models import LeaderboardConfig, ServerConfig
from custom_checks import app_command_check_reporter_roles, check_role_list, command_check_staff_roles
import API.get
import custom_checks

from typing import Optional

class PenaltyInstance:
    def __init__(self, penalty_name, amount, lounge_id, discord_id, total_repick, races_played_alone, table_id, is_strike):
        self.penalty_name = penalty_name
        self.amount = amount
        self.lounge_id=lounge_id
        self.discord_id=discord_id
        self.total_repick = total_repick
        self.races_played_alone = races_played_alone
        self.table_id = table_id
        self.is_strike = is_strike

penalty_static_info = {
    "Late": (50, True),
    "Drop mid mogi": (50, True),
    "Drop before start": (100, True),
    "Tag penalty": (50, False),
    "FFA name violation": (50, False),
    "Repick": (50, False),
    "No video proof": (50, True),
    "Host issues": (50, True),
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
        choices = [app_commands.Choice(name=locale_str(penalty_name), value=penalty_name) for penalty_name in penalty_static_info.keys()]
        return choices

    #Parameters: the staff accepting the request, the message_id from the request message in the dedicated request channel
    async def refuse_request(self, player: discord.User, message_id: int):
        penalty_data = self.request_queue.get(message_id, None)
        if penalty_data == None:
            return f"Unregistered request with message id {message_id}" #Indicate that the request has already been processed

        embed_message_log = penalty_data[1]
        initial_ctx = penalty_data[2]
        lb = penalty_data[3]
        penalty_channel = initial_ctx.guild.get_channel(lb.penalty_channel)

        #To catch error due to event listener or other commands
        try:
            del self.request_queue[message_id]
            request_message = await penalty_channel.fetch_message(message_id)
            await request_message.delete()
        except:
            return "Request already handled " + embed_message_log.jump_url
            
        edited_embed = embed_message_log.embeds[0]
        edited_embed.title="Penalty request refused"
        edited_embed.add_field(name="Refused by", value=player.mention, inline=False)
        await embed_message_log.edit(embed=edited_embed)

        return f"Request successfully deleted {embed_message_log.jump_url}"

    #Parameters: the staff accepting the request, the message_id from the request message in the dedicated request channel
    async def accept_request(self, staff: discord.User, message_id: int):

        penalty_data = self.request_queue.get(message_id, None)
        if penalty_data == None:
            return f"Unregistered request with message id {message_id}" #Indicate that the request has already been processed

        penalty_instance: PenaltyInstance = penalty_data[0]
        embed_message_log = penalty_data[1]
        initial_ctx = penalty_data[2]
        lb = penalty_data[3]
        penalty_channel = initial_ctx.guild.get_channel(lb.penalty_channel)

        #To catch error due to event listener or other commands
        try:
            del self.request_queue[message_id]
            request_message = await penalty_channel.fetch_message(message_id)
            await request_message.delete()
        except:
            return "Request already handled " + embed_message_log.jump_url
        
        #Used to get the most up to date name for the player with the lounge ID
        player = await API.get.getPlayerFromLounge(lb.website_credentials, penalty_instance.lounge_id)
        if player == None:
            return f"Player with lounge ID {penalty_instance.lounge_id} has not been found."

        penalties_cog = self.bot.get_cog('Penalties')
        initial_ctx.channel = penalty_channel
        initial_ctx.interaction = None #To remove the automatic reply to first message
        initial_ctx.author = staff #The penalties and multipliers will be shown as applied by the staff that accepted the request and not the person that requested it
        id_result = []
        ml_error_string = ""
        if penalty_instance.penalty_name == "Repick":
            #Repick automation
            for i in range(penalty_instance.total_repick):
                if i == 0:
                    id_result += await penalties_cog.add_penalty(initial_ctx, lb, penalty_instance.amount, "", [player.name], reason=penalty_instance.penalty_name, is_anonymous=True, is_strike=False, is_request=True)
                else:
                    id_result += await penalties_cog.add_penalty(initial_ctx, lb, penalty_instance.amount, "", [player.name], reason=penalty_instance.penalty_name, is_anonymous=True, is_strike=True, is_request=True)
        else:
            if penalty_instance.penalty_name == "Drop mid mogi" and penalty_instance.races_played_alone >= 3:
                #Handle setml here
                initial_ctx.prefix = '!' #Hacky solution to avoid responding to original message, but a working one
                updating_cog = self.bot.get_cog('Updating')
                mlraces_args = player.name + " " + str(penalty_instance.races_played_alone)
                ml_error_string = await updating_cog.multiplierRaces(initial_ctx, penalty_instance.table_id, extraArgs=mlraces_args)

            id_result += await penalties_cog.add_penalty(initial_ctx, lb, penalty_instance.amount, "", [player.name], reason=penalty_instance.penalty_name, is_anonymous=True, is_strike=penalty_instance.is_strike, is_request=True)

        edited_embed = embed_message_log.embeds[0]
        edited_embed.add_field(name="Accepted by", value=staff.mention, inline=False)
        if None not in id_result and ml_error_string == "":
            edited_embed.title="Penalty request accepted"
        else:
            edited_embed.title="Penalty request error"
            if ml_error_string != "":
                edited_embed.add_field(name="Error", value=ml_error_string)

        id_string = ""
        for index, id in enumerate(id_result):
            if id != None:
                if index != 0:
                    id_string += " / "
                id_string += str(id)
        if id_string != "":
            edited_embed.add_field(name="Penalty ID(s)", value=id_string, inline=False)
        
        await embed_message_log.edit(embed=edited_embed)

        return_message = edited_embed.title + f": {embed_message_log.jump_url}"
        return_message = return_message if id_string == "" else return_message + " ID(s): " + id_string
        return return_message

    async def add_penalty_to_channel(self, ctx: commands.Context, lb: LeaderboardConfig, penalty_type: str, player_name: str, repick_number=0, races_played_alone=0, table_id=0, reason=""):
        #Reply for the reporter
        player = await API.get.getPlayer(lb.website_credentials, player_name)
        if(player == None):
            await ctx.send(f"The following player could not be found: {player_name}", ephemeral=True)
            return
        
        e = discord.Embed(title="Penalty request")
        e.add_field(name="Player", value=player_name, inline=False)
        e.add_field(name="Penalty type", value=penalty_type)
        if penalty_type == "Repick":
            e.add_field(name="Number of repick", value=repick_number)
        if penalty_type == "Drop mid mogi":
            e.add_field(name="Number of races with a missing teammate", value=races_played_alone)
        e.add_field(name="Issued from", value=ctx.channel.mention)
        if table_id != 0 and table_id != None:
            e.add_field(name="Table ID", value=table_id)
        if reason != "" and reason != None:
            e.add_field(name="Reason from reporter", value=reason, inline=False)
        penalty_channel = ctx.guild.get_channel(lb.penalty_channel)
        embed_message = await penalty_channel.send(embed=e)
                
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        e.add_field(name="Requested by", value=ctx.author.mention, inline=False)
        embed_message_log = await updating_log.send(embed=e)

        await ctx.send(f"Penalty request issued for player {player_name}. Reason: {penalty_type}\nLink to request: {embed_message.jump_url}", ephemeral=True)

        try:
            await embed_message.add_reaction(CHECK_BOX)
            await embed_message.add_reaction(X_MARK)
        except:
            pass

        penalty_data = penalty_static_info.get(penalty_type)
        self.request_queue[embed_message.id] = (PenaltyInstance(penalty_type, penalty_data[0], player.id, player.discord_id, repick_number, races_played_alone, table_id, penalty_data[1]), embed_message_log, ctx, lb)


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

        ctx = penalty_data[2]
        server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)

        if str(reaction.emoji) == X_MARK and (user == ctx.author or check_role_list(user, (server_info.admin_roles + server_info.staff_roles))):
            await self.refuse_request(user, reaction.message.id)

        if str(reaction.emoji) == CHECK_BOX and check_role_list(user, (server_info.admin_roles + server_info.staff_roles)):
            await self.accept_request(user, reaction.message.id)
            


    @app_commands.check(app_command_check_reporter_roles)
    @request_group.command(name="penalty")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.autocomplete(penalty_type=penalty_autocomplete)
    @app_commands.describe(penalty_type="Type of penalty you want to report someone for",
            player_name="The player being reported",
            number_of_races="'Drop mid mogi': number of races played alone / 'Repick': number of races repicked",
            reason="Additional information you would like to give to the staff")
    async def append_penalty_slash(self, interaction: discord.Interaction, penalty_type: str, player_name: str, number_of_races: Optional[int], table_id: Optional[int], reason: Optional[str], leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        if penalty_type not in penalty_static_info.keys():
            await ctx.send("This penalty type doesn't exist", ephemeral=True)
            return
        if number_of_races == None:
                if penalty_type == "Repick":
                    number_of_races = 1
                else:
                    number_of_races = 0
        if penalty_type == "Drop mid mogi" and number_of_races >= 3: #If the number of races is not sufficient for a reduction loss, no need to have a table_id
            if table_id == None:
                await ctx.send("This penalty requires you to give a valid table id", ephemeral=True)
                return
            table = await API.get.getTable(lb.website_credentials, table_id)
            if table is False:
                await ctx.send("This penalty requires you to give a valid table id", ephemeral=True)
                return
            if number_of_races < 0 or number_of_races > 12:
                await ctx.send("You entered an invalid number of races", ephemeral=True)
                return
        if penalty_type == "Repick" and (number_of_races <= 0 or number_of_races > 11):
            await ctx.send("You entered an invalid number of races", ephemeral=True)
            return
        await self.add_penalty_to_channel(ctx, lb, penalty_type, player_name, repick_number=number_of_races, races_played_alone=number_of_races, table_id=table_id, reason=reason)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['pending_requests'])
    async def pending_requests_command(self, ctx: commands.Context):
        request_copy = dict(self.request_queue)
        if len(request_copy) == 0:
            await ctx.send("There is no pending request")
            return
        result_string = ""
        for message_id, penalty_data in request_copy.items():
            penalty_instance: PenaltyInstance = penalty_data[0]
            initial_ctx = penalty_data[2]
            lb = penalty_data[3]
            penalty_channel = initial_ctx.guild.get_channel(lb.penalty_channel)
            request_message = await penalty_channel.fetch_message(message_id)

            current_line = penalty_instance.penalty_name + " for player with discord ID " + str(penalty_instance.discord_id) + f" {request_message.jump_url}\n"
            if len(result_string) + len(current_line) > 2000:
                    await ctx.send(result_string)
                    result_string = ""
            result_string += current_line

        if len(result_string) > 0:
            await ctx.send(result_string)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['accept'])
    async def accept_request_command(self, ctx: commands.Context, messageid: int):
        request_data = self.request_queue.get(messageid, None)
        if request_data == None:
            await ctx.send(f"The request with message id {messageid} doesn't exist.")
        else:
            await ctx.send(await self.accept_request(ctx.author, messageid))

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['refuse'])
    async def refuse_request_command(self, ctx: commands.Context, messageid: int):
        request_data = self.request_queue.get(messageid, None)
        if request_data == None:
            await ctx.send(f"The request with message id {messageid} doesn't exist.")
        else:
            await ctx.send(await self.refuse_request(ctx.author, messageid))

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['accept_all'])
    async def accept_all_requests(self, ctx: commands.Context):
        request_copy = list(self.request_queue.keys())
        remaining_requests = len(request_copy)
        remaining_message = await ctx.send(f"Remaining requests: {remaining_requests}, please wait.")
        
        for message_id in request_copy:
            await ctx.send(await self.accept_request(ctx.author, message_id))
            remaining_requests -= 1
            await remaining_message.edit(content=f"Remaining requests: {remaining_requests}, please wait.")
        
        try:
            await remaining_message.delete()
        except:
            pass
        await ctx.send("All requests have been accepted.")

async def setup(bot):
    await bot.add_cog(Request(bot))