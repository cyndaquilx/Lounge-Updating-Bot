import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str

from util.Translator import CustomTranslator
from util import get_leaderboard_slash, get_leaderboard, set_multipliers, check_against_automod_lists
from models import LeaderboardConfig, ServerConfig
from custom_checks import app_command_check_reporter_roles, app_command_check_staff_roles, check_role_list, command_check_staff_roles, check_staff_roles
import API.get
import custom_checks

from typing import Optional
from operator import itemgetter
from dataclasses import dataclass

class PenaltyInstance:
    def __init__(self, penalty_name, amount, lounge_id, discord_id, table_id, is_strike):
        self.penalty_name = penalty_name
        self.amount = amount
        self.lounge_id=lounge_id
        self.discord_id=discord_id
        self.table_id = table_id
        self.is_strike = is_strike
    
    def create_embed(self, ctx, player_name: str, reason: str):
        e = discord.Embed(title="Penalty request")
        e.add_field(name="Player", value=player_name, inline=False)
        e.add_field(name="Penalty type", value=self.penalty_name)
        e.add_field(name="Issued from", value=ctx.channel.mention)
        if self.table_id != 0 and self.table_id != None:
            e.add_field(name="Table ID", value=self.table_id)
        if reason != "" and reason != None:
            e.add_field(name="Reason from reporter", value=reason, inline=False)
        return e

    async def send_request_to_channel(self, ctx, lb, embed):
        penalty_channel = ctx.guild.get_channel(lb.penalty_channel)
        embed_message = await penalty_channel.send(embed=embed)
                
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        embed.add_field(name="Requested by", value=ctx.author.mention, inline=False)
        embed_message_log = await updating_log.send(embed=embed)

        try:
            await embed_message.add_reaction(CHECK_BOX)
            await embed_message.add_reaction(X_MARK)
        except:
            pass

        return (embed_message, embed_message_log)
    
class RepickInstance(PenaltyInstance):
    def __init__(self, penalty_name, amount, lounge_id, discord_id, table_id, is_strike, total_repick):
        super().__init__(penalty_name, amount, lounge_id, discord_id, table_id, is_strike)
        self.total_repick = total_repick

    def create_embed(self, ctx, player_name: str, reason: str):
        partial_embed = PenaltyInstance.create_embed(self, ctx, player_name, reason)
        partial_embed.add_field(name="Number of repick", value=self.total_repick)
        return partial_embed

class DropInstance(PenaltyInstance):
    def __init__(self, penalty_name, amount, lounge_id, discord_id, table_id, is_strike, races_played_alone):
        super().__init__(penalty_name, amount, lounge_id, discord_id, table_id, is_strike)
        self.races_played_alone = races_played_alone

    def create_embed(self, ctx, player_name: str, reason: str):
        partial_embed = PenaltyInstance.create_embed(self, ctx, player_name, reason)
        if self.races_played_alone != 0:
            partial_embed.add_field(name="Number of races with a missing teammate", value=self.races_played_alone)
        return partial_embed

    async def same_team_players(self, lb, player_name_new, player_name_old):
        try:
            table = await API.get.getTable(lb.website_credentials, self.table_id)
            if table == None:
                return None
            team = table.get_team(player_name_new)
            for tablescore in team.scores:
                if tablescore.player.name == player_name_old:
                    return True
        except:
            return None
        return False

    async def apply_multiplier(self, lb, bot, ctx, player_name, request_queue):
        if self.races_played_alone >= 3:
            #In case the team concerned by the multiplier already received one, it will not apply a new one
            for request in request_queue.values():
                if request.penalty_instance.table_id == self.table_id and isinstance(request.penalty_instance, DropInstance):
                    player = await API.get.getPlayerFromLounge(lb.website_credentials, request.penalty_instance.lounge_id)
                    result = await self.same_team_players(lb, player_name, player.name)
                    if result == None or result == True:
                        return

            #Handle setml here
            ctx.prefix = '!' #Hacky solution to avoid responding to original message
            updating_cog = bot.get_cog('Updating')
            mlraces_args = player_name + " " + str(self.races_played_alone)
            await updating_cog.multiplierRaces(ctx, self.table_id, extraArgs=mlraces_args)

    async def remove_multiplier(self, lb, ctx, player_name, request_queue):
            #In case the team concerned by the multiplier received multiple drop mid mogi penalty, it will not try to remove the multiplier associated with it
            for request in request_queue.values():
                if request.penalty_instance.table_id == self.table_id and isinstance(request.penalty_instance, DropInstance):
                    player = await API.get.getPlayerFromLounge(lb.website_credentials, request.penalty_instance.lounge_id)
                    result = await self.same_team_players(lb, player_name, player.name)
                    if result == None or result:
                        return

            #Handle the removal here
            table = await API.get.getTable(lb.website_credentials, self.table_id)
            if table != None:
                team = table.get_team(player_name)
                if type(team) != type(None):
                    setml_args = ""
                    for tablescore in team.scores:
                        setml_args += tablescore.player.name + " 1, "
                    if setml_args != "":
                        setml_args = setml_args[:-2]
                    await set_multipliers(ctx, lb, self.table_id, setml_args)
            

@dataclass
class RequestInstance:
    message: discord.Message #In the penalty channel
    message_log: discord.Message #In the log channel
    penalty_instance: PenaltyInstance
    initial_ctx: commands.Context
    leaderboard: LeaderboardConfig
    is_table_verified: bool #State of the given tab ID when the request is created

penalty_static_info = {
    "Late": (50, True),
    "Drop mid mogi": (50, True),
    "3+ dcs": (50, True),
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

    #request_group = app_commands.Group(name="request", description="Requests to staff")

    #Dictionary containing: Message ID -> RequestInstance
    request_queue = {}

    #List of applied multiplier but not updated tab: [(tab_id, lb)]
    multiplier_protection = []

    #Check if the highest tab in the multiplier list has been verified -> clear the list in that case
    async def check_and_clear_multiplier_list(self, lb):
        id_list = []
        for tuple in self.multiplier_protection:
            if tuple[1] == lb:
                id_list.append(tuple)
        if len(id_list) == 0:
            return
        highest_id = max(id_list, key=itemgetter(0))[0]
        table = await API.get.getTable(lb.website_credentials, highest_id)
        if table == None:
            return
        if table.verified_on != None:
            try:
                self.multiplier_protection = [item for item in self.multiplier_protection if item not in id_list]
            except:
                return

    def get_request_from_lb(self, queue, lb: LeaderboardConfig):
        new_dict = {}
        for key, value in queue.items():
            if value.leaderboard == lb:
                new_dict[key] = value
        return new_dict

    async def penalty_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        translator = CustomTranslator()
        user_locale = interaction.locale
        filtered = []
        for penalty_name in penalty_static_info.keys():
            translation = await translator.translate(locale_str(penalty_name), user_locale, None)
            if translation == None:
                filtered.append(penalty_name)
                continue
            #Check if characters appear in order but are not necessarily contiguous
            result = True
            index = 0
            try: #Still continue even if it is not possible to lower a character
                current = current.lower()
                translation = translation.lower()
            except:
                pass
            for char in current:
                index = translation.find(char, index)
                if index == -1:
                    result = False
                    break
                index += 1
            if result:
                filtered.append(penalty_name)
        choices = [app_commands.Choice(name=locale_str(penalty_name), value=penalty_name) for penalty_name in filtered]
        return choices

    #Parameters: the player refusing the request, the message_id from the request message in the dedicated request channel
    async def refuse_request_process(self, player: discord.Member, message_id: int):
        request_data: RequestInstance = self.request_queue.get(message_id, None)
        if request_data == None:
            return f"Unregistered request with message id {message_id}" #Indicate that the request has already been processed

        #If this is a drop penalty and the tab has been verified while the request was pending, prevent a reporter from deleting it (force player to commit for multipliers AND strike)
        if not request_data.is_table_verified:
            server_info: ServerConfig = request_data.initial_ctx.bot.config.servers.get(request_data.initial_ctx.guild.id, None)
            if isinstance(request_data.penalty_instance, DropInstance) and not check_role_list(player, (server_info.admin_roles + server_info.staff_roles)):
                if request_data.penalty_instance.table_id != None:
                    table = await API.get.getTable(request_data.leaderboard.website_credentials, request_data.penalty_instance.table_id)
                    if table != None and table.verified_on != None:
                        return

        #To catch error due to event listener or other commands
        try:
            del self.request_queue[message_id]
            await request_data.message.delete()
        except:
            return "Request already handled " + request_data.message_log.jump_url
        
        #Remove the multiplier only if it is the last remaining DropMidMogiInstance for the given team
        if isinstance(request_data.penalty_instance, DropInstance):
            player_ = await API.get.getPlayerFromLounge(request_data.leaderboard.website_credentials, request_data.penalty_instance.lounge_id)
            await request_data.penalty_instance.remove_multiplier(request_data.leaderboard, request_data.initial_ctx, player_.name, self.get_request_from_lb(dict(self.request_queue), request_data.leaderboard))
            
        edited_embed = request_data.message_log.embeds[0]
        edited_embed.title="Penalty request refused"
        edited_embed.add_field(name="Refused by", value=player.mention, inline=False)
        await request_data.message_log.edit(embed=edited_embed)

        return f"Request successfully deleted {request_data.message_log.jump_url}"

    #Parameters: the staff accepting the request, the message_id from the request message in the dedicated request channel
    async def accept_request_process(self, staff: discord.Member, message_id: int):
        request_data: RequestInstance = self.request_queue.get(message_id, None)
        if request_data == None:
            return f"Unregistered request with message id {message_id}" #Indicate that the request has already been processed

        #To catch error due to event listener or other commands
        try:
            del self.request_queue[message_id]
            await request_data.message.delete()
        except:
            return "Request already handled " + request_data.message_log.jump_url
        
        #Used to get the most up to date name for the player with the lounge ID
        player = await API.get.getPlayerFromLounge(request_data.leaderboard.website_credentials, request_data.penalty_instance.lounge_id)
        if player == None:
            return f"Player with lounge ID {request_data.penalty_instance.lounge_id} has not been found."

        #Lock any new mulitplier for this tab as long as the tab has not been updated
        if isinstance(request_data.penalty_instance, DropInstance):
            if request_data.penalty_instance.table_id != None:
                self.multiplier_protection.append((request_data.penalty_instance.table_id, request_data.leaderboard))

        penalties_cog = self.bot.get_cog('Penalties')
        request_data.initial_ctx.author = staff #The penalties will be shown as applied by the staff that accepted the request and not the person that requested it
        id_result = []
        if isinstance(request_data.penalty_instance, RepickInstance):
            #Repick automation
            for i in range(request_data.penalty_instance.total_repick):
                if i == 0:
                    id_result += await penalties_cog.add_penalty(request_data.initial_ctx, request_data.leaderboard, request_data.penalty_instance.amount, "", [player.name], reason=request_data.penalty_instance.penalty_name, table_id=request_data.penalty_instance.table_id, is_anonymous=True, is_strike=False, is_request=True)
                else:
                    id_result += await penalties_cog.add_penalty(request_data.initial_ctx, request_data.leaderboard, request_data.penalty_instance.amount, "", [player.name], reason=request_data.penalty_instance.penalty_name, table_id=request_data.penalty_instance.table_id, is_anonymous=True, is_strike=True, is_request=True)
        else:
            id_result += await penalties_cog.add_penalty(request_data.initial_ctx, request_data.leaderboard, request_data.penalty_instance.amount, "", [player.name], reason=request_data.penalty_instance.penalty_name, table_id=request_data.penalty_instance.table_id, is_anonymous=True, is_strike=request_data.penalty_instance.is_strike, is_request=True)

        edited_embed = request_data.message_log.embeds[0]
        edited_embed.add_field(name="Accepted by", value=staff.mention, inline=False)
        if None not in id_result:
            edited_embed.title="Penalty request accepted"
        else:
            edited_embed.title="Penalty request error"

        id_string = ""
        for index, id in enumerate(id_result):
            if id != None:
                if index != 0:
                    id_string += " / "
                id_string += str(id)
        if id_string != "":
            edited_embed.add_field(name="Penalty ID(s)", value=id_string, inline=False)
        
        await request_data.message_log.edit(embed=edited_embed)

        return_message = edited_embed.title + f": {request_data.message_log.jump_url}"
        return_message = return_message if id_string == "" else return_message + " ID(s): " + id_string
        return return_message

    #Used to monitor when someone reacts to a request in the penalty channel
    @commands.Cog.listener(name='on_raw_reaction_add')
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.bot:
            return
        request_data: RequestInstance = self.request_queue.get(payload.message_id, None)
        if request_data == None:
            return
        server_info: ServerConfig = request_data.initial_ctx.bot.config.servers.get(request_data.initial_ctx.guild.id, None)

        if str(payload.emoji) == X_MARK and (payload.member == request_data.initial_ctx.author or check_role_list(payload.member, (server_info.admin_roles + server_info.staff_roles))):
            await self.refuse_request_process(payload.member, request_data.message.id)

        if str(payload.emoji) == CHECK_BOX and check_role_list(payload.member, (server_info.admin_roles + server_info.staff_roles)):
            await self.accept_request_process(payload.member, request_data.message.id)
            

    @app_commands.check(app_command_check_reporter_roles)
    @app_commands.command(name="request_penalty")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.autocomplete(penalty_type=penalty_autocomplete)
    @app_commands.describe(penalty_type="Type of penalty you want to report someone for",
            player_name="The player being reported",
            number_of_races="'Drop mid mogi': number of races played alone / 'Repick': number of races repicked",
            reason="Additional information you would like to give to the staff")
    async def append_penalty_slash(self, interaction: discord.Interaction, penalty_type: str, player_name: str, table_id: int, number_of_races: Optional[int], reason: Optional[str], leaderboard: Optional[str]):
        await interaction.response.defer(ephemeral=True)
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        if penalty_type not in penalty_static_info.keys():
            found_name = False
            for name in penalty_static_info.keys():
                if name.lower() == penalty_type:
                    penalty_type = name
                    found_name = True
                    break
            if not found_name:
                #Quick check in case discord autocomplete failed at forcing a particular value from the penalty choice list
                translation = CustomTranslator().translation_reverse_check(penalty_type)
                if translation != None and translation in penalty_static_info.keys():
                    penalty_type = translation
                else:
                    await ctx.send("This penalty type doesn't exist", ephemeral=True)
                    return
        if table_id == None:
            await ctx.send("This penalty requires you to give a valid table id", ephemeral=True)
            return
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table == None:
            await ctx.send("This penalty requires you to give a valid table id", ephemeral=True)
            return
        player = await API.get.getPlayer(lb.website_credentials, player_name)
        if(player == None):
            await ctx.send(f"The following player could not be found: {player_name}", ephemeral=True)
            return
        if not check_staff_roles(ctx):
            #Check that the reporter is in the tab
            is_in_tab = False
            for table_team in table.teams:
                for score in table_team.scores:
                    if score.player.discord_id != None and score.player.discord_id == str(interaction.user.id):
                        is_in_tab = True
            if not is_in_tab:
                await ctx.send("You need to be on the tab to ask for a penalty", ephemeral=True)
                return
            #FFA name violation check on table author
            if penalty_type == "FFA name violation":
                if ctx.author.id != table.author_id and player.discord_id != table.author_id:
                    await ctx.send("You are not allowed to ask for a FFA name violation if you're not the table author or if you're not reporting the table author")
                    return
        if number_of_races == None:
                if penalty_type == "Repick":
                    number_of_races = 1
                else:
                    number_of_races = 0
        if number_of_races < 0 or number_of_races > 12:
            await ctx.send("You entered an invalid number of races", ephemeral=True)
            return
        if penalty_type == "3+ dcs" and number_of_races < 3:
            await ctx.send("Please enter the exact number of races mate(s) of the reported player played alone in \"number_of_races\".", ephemeral=True)
            return
        if penalty_type == "Repick" and (number_of_races <= 0 or number_of_races > 11):
            await ctx.send("You entered an invalid number of races", ephemeral=True)
            return
        
        #Create penalty, create embed, send embed, add penalty to queue
        penalty = None
        penalty_data = penalty_static_info.get(penalty_type)
        if penalty_type == "Drop mid mogi" or penalty_type == "3+ dcs" or penalty_type == "Drop before start":
            penalty = DropInstance(penalty_type, penalty_data[0], player.id, player.discord_id, table_id, penalty_data[1], number_of_races)
        elif penalty_type == "Repick":
            penalty = RepickInstance(penalty_type, penalty_data[0], player.id, player.discord_id, table_id, penalty_data[1], number_of_races)
        else:
            penalty = PenaltyInstance(penalty_type, penalty_data[0], player.id, player.discord_id, table_id, penalty_data[1])

        embed = penalty.create_embed(ctx, player_name, reason)
        (embed_message, embed_message_log) = await penalty.send_request_to_channel(ctx, lb, embed)

        await ctx.send(f"Penalty request issued for player {player_name}. Reason: {penalty_type}\nLink to request: {embed_message.jump_url}", ephemeral=True)

        #To be done on every request by default while we don't have a solution working directly on the website
        await self.check_and_clear_multiplier_list(lb)

        penalty_channel = ctx.guild.get_channel(lb.penalty_channel)
        ctx.channel = penalty_channel
        ctx.interaction = None #To remove the automatic reply to first message
        if isinstance(penalty, DropInstance) and table_id != None and (table_id, lb) not in self.multiplier_protection:
            await penalty.apply_multiplier(lb, self.bot, ctx, player_name, self.get_request_from_lb(dict(self.request_queue), lb))

        self.request_queue[embed_message.id] = RequestInstance(embed_message, embed_message_log, penalty, ctx, lb, table.verified_on != None)

    async def pending_requests(self, ctx: commands.Context, lb: LeaderboardConfig):
        request_copy = self.get_request_from_lb(dict(self.request_queue), lb)
        if len(request_copy) == 0:
            await ctx.send("There are no pending requests")
            return
        request_list = []
        for request_data in request_copy.values():
            request_list.append((request_data.penalty_instance.table_id, request_data.penalty_instance.penalty_name, "<@" + str(request_data.penalty_instance.discord_id) + ">", request_data.message.jump_url))
        def sort_request(elem):
            return elem[0]
        request_list.sort(key=sort_request)
        result_string = ""
        for request_data in request_list:
            current_line = str(request_data[0]) + " | " + request_data[2] + " | " + request_data[1] + f" | {request_data[3]}\n"
            if len(result_string) + len(current_line) > 2000:
                    await ctx.send(result_string)
                    result_string = ""
            result_string += current_line

        if len(result_string) > 0:
            await ctx.send(result_string)

    @commands.check(command_check_staff_roles)
    @commands.command(name='pendingPenalties', aliases=['penalties', 'pens'])
    async def pending_requests_command_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.pending_requests(ctx, lb)

    @app_commands.check(app_command_check_staff_roles)
    @app_commands.command(name='pending_penalties')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def pending_requests_command_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.pending_requests(ctx, lb)

    async def accept_request(self, ctx: commands.Context, lb: LeaderboardConfig, message_id: int):
        request_data: RequestInstance = self.request_queue.get(message_id, None)
        if request_data == None:
            await ctx.send(f"The request with message id {message_id} doesn't exist.")
        else:
            if request_data.leaderboard != lb:
                await ctx.send("You are trying to access a request from another leaderboard.")
            else:
                await ctx.send(await self.accept_request_process(ctx.author, message_id))

    @commands.check(command_check_staff_roles)
    @commands.command(name='acceptPenalty', aliases=['acceptPen'])
    async def accept_request_command_text(self, ctx: commands.Context, message_id: int = commands.parameter(description="Discord ID of the message in the penalty channel")):
        lb = get_leaderboard(ctx)
        await self.accept_request(ctx, lb, message_id)

    @app_commands.check(app_command_check_staff_roles)
    @app_commands.command(name='accept_penalty')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.describe(message_id="Discord ID of the message in the penalty channel")
    async def accept_request_command_slash(self, interaction: discord.Interaction, message_id: str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        try:
            id = int(message_id)    
        except:
            await ctx.send("Your message ID is not a valid ID")
            return
        await self.accept_request(ctx, lb, id)

    async def refuse_request(self, ctx: commands.Context, lb: LeaderboardConfig, message_id: int):
        request_data: RequestInstance = self.request_queue.get(message_id, None)
        if request_data == None:
            await ctx.send(f"The request with message id {message_id} doesn't exist.")
        else:
            if request_data.leaderboard != lb:
                await ctx.send("You are trying to access a request from another leaderboard.")
            else:
                await ctx.send(await self.refuse_request_process(ctx.author, message_id))

    @commands.check(command_check_staff_roles)
    @commands.command(name='refusePenalty', aliases=['refusePen', 'denyPen', 'denyPenalty'])
    async def refuse_request_command_text(self, ctx: commands.Context, message_id: int = commands.parameter(description="Discord ID of the message in the penalty channel")):
        lb = get_leaderboard(ctx)
        await self.refuse_request(ctx, lb, message_id)

    @app_commands.check(app_command_check_staff_roles)
    @app_commands.command(name='refuse_penalty')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.describe(message_id="Discord ID of the message in the penalty channel")
    async def refuse_request_command_slash(self, interaction: discord.Interaction, message_id: str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        try:
            id = int(message_id)    
        except:
            await ctx.send("Your message ID is not a valid ID")
            return
        await self.refuse_request(ctx, lb, id)

    async def accept_all_request(self, ctx: commands.Context, lb: LeaderboardConfig):
        request_copy = self.get_request_from_lb(dict(self.request_queue), lb)
        remaining_requests = len(request_copy)
        remaining_message = await ctx.send(f"Remaining requests: {remaining_requests}, please wait.")
        
        for id in request_copy.keys():
            await ctx.send(await self.accept_request_process(ctx.author, id))
            remaining_requests -= 1
            await remaining_message.edit(content=f"Remaining requests: {remaining_requests}, please wait.")
        
        try:
            await remaining_message.delete()
        except:
            pass
        await ctx.send("All requests have been accepted.")

    @commands.check(command_check_staff_roles)
    @commands.command(name='acceptAllPenalties', aliases=['acceptAllPens', 'uapens', 'aapens'])
    async def accept_all_requests_command_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.accept_all_request(ctx, lb)

    @app_commands.check(app_command_check_staff_roles)
    @app_commands.command(name='accept_all_penalties')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def accept_all_requests_command_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.accept_all_request(ctx, lb)

async def setup(bot):
    await bot.add_cog(Request(bot))