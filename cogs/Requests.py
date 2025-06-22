import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import locale_str

from util.Translator import CustomTranslator
from util import get_leaderboard_slash, get_leaderboard, set_multipliers
from models import LeaderboardConfig, PenaltyRequest, UpdatingBot
from custom_checks import app_command_check_reporter_roles, app_command_check_updater_roles, command_check_updater_roles, check_updater_roles
import API.get, API.post
import custom_checks

from typing import Optional

class PenaltyInstance:
    def __init__(self, penalty_name, lounge_id, table_id):
        self.penalty_name = penalty_name
        self.lounge_id=lounge_id
        self.table_id = table_id
    
    def create_embed(self, ctx, request_id, player_name, reason):
        e = discord.Embed(title="Penalty request")
        e.add_field(name="Request ID", value=request_id)
        e.add_field(name="Player", value=player_name, inline=False)
        e.add_field(name="Penalty type", value=self.penalty_name)
        e.add_field(name="Issued from", value=ctx.channel.mention)
        if self.table_id != 0 and self.table_id != None:
            e.add_field(name="Table ID", value=self.table_id)
        if reason != "" and reason != None:
            e.add_field(name="Reason from reporter", value=reason, inline=False)
        return e

    async def send_request_to_channel(self, ctx, lb, embed, tier):
        tier_channel = get_pen_channel(ctx, lb, tier)
        embed_message = await tier_channel.send(embed=embed)
                
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        embed.add_field(name="Requested by", value=ctx.author.mention, inline=False)
        embed_message_log = await updating_log.send(embed=embed)

        return embed_message
    
    async def apply_multiplier(self, lb, ctx, bot, table, player_name, requests_list: list[PenaltyRequest]):
        pass

    async def apply_penalty(self, lb, ctx, penalties_cog, tier, player_name, amount, is_strike):
        id_result = []
        id_result += await penalties_cog.add_penalty(ctx, lb, amount, tier, [player_name], reason=self.penalty_name, table_id=self.table_id, is_anonymous=True, is_strike=is_strike)
        return id_result

class RepickInstance(PenaltyInstance):
    def __init__(self, penalty_name, lounge_id, table_id, total_repick):
        super().__init__(penalty_name, lounge_id, table_id)
        self.total_repick = total_repick

    def create_embed(self, ctx, request_id, player_name, reason):
        partial_embed = PenaltyInstance.create_embed(self, ctx, request_id, player_name, reason)
        partial_embed.add_field(name="Number of repick", value=self.total_repick)
        return partial_embed

    async def apply_penalty(self, lb, ctx, penalties_cog, tier, player_name, amount, is_strike):
        id_result = []
        for _ in range(self.total_repick):    
            id_result += await penalties_cog.add_penalty(ctx, lb, amount, tier, [player_name], reason=self.penalty_name, table_id=self.table_id, is_anonymous=True, is_strike=is_strike)
        return id_result

class DropInstance(PenaltyInstance):
    def __init__(self, penalty_name, lounge_id, table_id, races_played_alone):
        super().__init__(penalty_name, lounge_id, table_id)
        self.races_played_alone = races_played_alone

    def create_embed(self, ctx, request_id, player_name, reason):
        partial_embed = PenaltyInstance.create_embed(self, ctx, request_id, player_name, reason)
        if self.races_played_alone != 0:
            partial_embed.add_field(name="Number of races with a missing teammate", value=self.races_played_alone)
        return partial_embed

    async def same_team_players(self, lb, table, player_name_new, player_name_old):
        try:
            team = table.get_team(player_name_new)
            if team is None:
                return None
            for tablescore in team.scores:
                if tablescore.player.name == player_name_old:
                    return True
        except:
            return None
        return False

    async def apply_multiplier(self, lb, ctx, bot, table, player_name, requests_list):
        no_ml_players = []
        max_number_of_races = 0
        for request in requests_list:
            if request.table_id == self.table_id and isinstance(penalty_instance_builder(request.penalty_name, request.player_id, request.table_id, request.number_of_races), DropInstance):
                result = await self.same_team_players(lb, table, player_name, request.player_name)
                if result == None:
                    return
                if result == True:
                    no_ml_players.append(request.player_name)
                    if request.number_of_races > max_number_of_races:
                        max_number_of_races = request.number_of_races

        #Keep a copy of some variables
        channel_copy = ctx.channel
        interaction_copy = ctx.interaction
        prefix_copy = ctx.prefix
        
        ctx.channel = get_pen_channel(ctx, lb, table.tier)
        ctx.interaction = None #To remove the automatic reply to first message
        ctx.prefix = '!' #Hacky solution to avoid responding to original message

        #Handle setml here
        updating_cog = bot.get_cog('Updating')
        if len(no_ml_players) > 0:
            mlraces_args = no_ml_players[0] + " " + str(max_number_of_races)
            await updating_cog.multiplierRaces(ctx, self.table_id, extraArgs=mlraces_args)
            setml_args = ""
            for player in no_ml_players:
                setml_args += player + " 1, "
            if setml_args != "":
                setml_args = setml_args[:-2]
            await set_multipliers(ctx, lb, self.table_id, setml_args)
        else:
            team = table.get_team(player_name)
            setml_args = ""
            for tablescore in team.scores:
                setml_args += tablescore.player.name + " 1, "
            if setml_args != "":
                setml_args = setml_args[:-2]
            await set_multipliers(ctx, lb, self.table_id, setml_args)
        ctx.channel = channel_copy
        ctx.interaction = interaction_copy
        ctx.prefix = prefix_copy
            
def penalty_instance_builder(penalty_name, lounge_id, table_id, number_of_races = 0):
    if penalty_name == "Repick":
        return RepickInstance(penalty_name, lounge_id, table_id, number_of_races)
    if penalty_name == "Drop mid mogi" or penalty_name == "3+ dcs" or penalty_name == "Drop before start":
        return DropInstance(penalty_name, lounge_id, table_id, number_of_races)
    return PenaltyInstance(penalty_name, lounge_id, table_id)

penalty_static_info = {
    "Late": (50, True),
    "Drop mid mogi": (50, True),
    "3+ dcs": (50, True),
    "Drop before start": (100, True),
    "Tag penalty": (50, True),
    "FFA name violation": (50, True),
    "Repick": (50, True),
    "No video proof": (50, True),
    "Host issues": (50, True),
    "No host": (50, True)
}

def get_pen_channel(ctx, lb, tier): #Return the pen channel or the given tier channel if it doesn't exist
    pen_channel = ctx.guild.get_channel(lb.penalty_channel)
    if pen_channel == None:
        return ctx.guild.get_channel(lb.tier_results_channels[tier])
    else:
        return pen_channel

class Requests(commands.Cog):
    def __init__ (self, bot: UpdatingBot):
        self.bot = bot

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

    async def refuse_request_process(self, lb: LeaderboardConfig, ctx: commands.Context, request_data: PenaltyRequest):
        resp_code = await API.post.deletePenaltyRequest(lb.website_credentials, request_data.id)
        if resp_code is not None:
            return f"An error occured: {resp_code}"

        requests = await API.get.getPendingPenaltyRequests(lb.website_credentials)
        table = await API.get.getTable(lb.website_credentials, request_data.table_id)
        if table is None or requests is None:
            return "An error occured while accessing the database"

        await penalty_instance_builder(request_data.penalty_name, request_data.player_id, request_data.table_id, request_data.number_of_races).apply_multiplier(lb, ctx, self.bot, table, request_data.player_name, requests)

        embed = discord.Embed(title="Penalty request refused")
        embed.add_field(name="Request ID", value=request_data.id)
        assert ctx.guild is not None
        tier_channel = get_pen_channel(ctx, lb, table.tier)
        assert tier_channel is not None
        await tier_channel.send(embed=embed)

        embed.add_field(name="Refused by", value=ctx.author.mention, inline=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        assert updating_log is not None
        await updating_log.send(embed=embed)

        return f"Request {request_data.id} successfully deleted"

    async def accept_request_process(self, lb: LeaderboardConfig, ctx: commands.Context, request_data: PenaltyRequest):
        requests = await API.get.getPendingPenaltyRequests(lb.website_credentials)
        table = await API.get.getTable(lb.website_credentials, request_data.table_id)
        if table is None or requests is None:
            return "An error occured while accessing the database"

        penalty_instance = penalty_instance_builder(request_data.penalty_name, request_data.player_id, request_data.table_id, request_data.number_of_races)
        penalties_cog = self.bot.get_cog('Penalties')
        amount = penalty_static_info[request_data.penalty_name][0]
        is_strike = penalty_static_info[request_data.penalty_name][1]
        
        id_result = await penalty_instance.apply_penalty(lb, ctx, penalties_cog, table.tier, request_data.player_name, amount, is_strike)

        embed = discord.Embed()
        embed.title = "Penalty request accepted" if None not in id_result else "Penalty request error"
        embed.add_field(name="Request ID", value=request_data.id)
        id_string = ""
        for index, id in enumerate(id_result):
            if id != None:
                if index != 0:
                    id_string += " / "
                id_string += str(id)
        if id_string != "":
            embed.add_field(name="Penalty ID(s)", value=id_string, inline=False)
        
        assert ctx.guild is not None
        tier_channel = get_pen_channel(ctx, lb, table.tier)
        assert tier_channel is not None
        await tier_channel.send(embed=embed)

        embed.add_field(name="Accepted by", value=ctx.author.mention, inline=False)        
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        assert updating_log is not None
        embed_log = await updating_log.send(embed=embed)

        resp_code = await API.post.deletePenaltyRequest(lb.website_credentials, request_data.id)
        if resp_code is not None:
            return f"An error occured when removing the request with ID {request_data.id} from the database: {resp_code}. Please try removing it manually."

        assert embed_log is not None
        return_message = embed.title + ": " + embed_log.jump_url
        return_message = return_message if id_string == "" else return_message + " ID(s): " + id_string
        return return_message            

    @app_commands.check(app_command_check_reporter_roles)
    @app_commands.command(name="request_penalty")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.autocomplete(penalty_type=penalty_autocomplete)
    @app_commands.describe(penalty_type="Type of penalty you want to report someone for",
            player_name="The player being reported",
            number_of_races="'Drop mid mogi': number of races played alone / 'Repick': number of races repicked",
            reason="Additional information you would like to give to the staff")
    @app_commands.guild_only()
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
        if not check_updater_roles(ctx):
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
                    await ctx.send("You are not allowed to ask for a FFA name violation if you're not the table author or if you're not reporting the table author", ephemeral=True)
                    return
        if number_of_races == None:
            if penalty_type == "Repick":
                number_of_races = 1
            else:
                number_of_races = 0
        if reason == None:
            reason = ""
        if number_of_races < 0 or number_of_races > 12:
            await ctx.send("You entered an invalid number of races", ephemeral=True)
            return
        if penalty_type == "3+ dcs" and number_of_races < 3:
            await ctx.send("Please enter the exact number of races mate(s) of the reported player played alone in \"number_of_races\".", ephemeral=True)
            return
        if penalty_type == "Repick" and (number_of_races <= 0 or number_of_races > 11):
            await ctx.send("You entered an invalid number of races", ephemeral=True)
            return
        
        reporter = await API.get.getPlayerFromDiscord(lb.website_credentials, ctx.author.id)
        if reporter is None:
            await ctx.send("Your discord ID doesn't match any player in our database", ephemeral=True)
            return

        request, error = await API.post.createPenaltyRequest(lb.website_credentials, penalty_type, player_name, reporter.name, table_id, number_of_races)
        if request is None:
            await ctx.send(f"An error occurred while creating the request: {error}", ephemeral=True)
            return

        requests_list = await API.get.getPendingPenaltyRequests(lb.website_credentials)
        if requests_list is None:
            await ctx.send(f"An error occurred while accessing the database", ephemeral=True)
            return

        penalty_instance = penalty_instance_builder(penalty_type, player.id, table_id, number_of_races)

        embed = penalty_instance.create_embed(ctx, request.id, player_name, reason)
        embed_message = await penalty_instance.send_request_to_channel(ctx, lb, embed, table.tier)

        assert embed_message is not None
        await ctx.send(f"Penalty request issued for player {player_name}. Reason: {penalty_type}\nLink to request: {embed_message.jump_url}", ephemeral=True)

        assert ctx.guild is not None
        await penalty_instance.apply_multiplier(lb, ctx, self.bot, table, player_name, requests_list)

    async def pending_requests(self, ctx: commands.Context, lb: LeaderboardConfig):
        requests = await API.get.getPendingPenaltyRequests(lb.website_credentials)
        if requests is None:
            await ctx.send("An error occured while fetching the requests")
            return
        if len(requests) == 0:
            await ctx.send("There are no pending requests")
            return
        request_list = []
        for request_data in requests:
            request_list.append((request_data.table_id, request_data.penalty_name, request_data.player_name, request_data.id))
        def sort_request(elem):
            return elem[0]
        request_list.sort(key=sort_request)
        result_string = ""
        for request_data in request_list:
            current_line = str(request_data[0]) + " | " + request_data[2] + " | " + request_data[1] + f" | Request ID: {request_data[3]}\n"
            if len(result_string) + len(current_line) > 2000:
                    await ctx.send(result_string)
                    result_string = ""
            result_string += current_line

        if len(result_string) > 0:
            await ctx.send(result_string)

    @commands.check(command_check_updater_roles)
    @commands.command(name='pendingPenalties', aliases=['penalties', 'pens'])
    async def pending_requests_command_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.pending_requests(ctx, lb)

    @app_commands.check(app_command_check_updater_roles)
    @app_commands.command(name='pending_penalties')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.guild_only()
    async def pending_requests_command_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.pending_requests(ctx, lb)

    async def accept_request(self, ctx: commands.Context, lb: LeaderboardConfig, request_id: int):
        request_data = await API.get.getPenaltyRequest(lb.website_credentials, request_id)
        if request_data is None:
            await ctx.send(f"The request with id {request_id} doesn't exist.")
        else:
            assert isinstance(ctx.author, discord.Member)
            await ctx.send(await self.accept_request_process(lb, ctx, request_data))

    @commands.check(command_check_updater_roles)
    @commands.command(name='acceptPenalty', aliases=['acceptPen'])
    async def accept_request_command_text(self, ctx: commands.Context, request_id: int = commands.parameter(description="Request ID")):
        lb = get_leaderboard(ctx)
        await self.accept_request(ctx, lb, request_id)

    @app_commands.check(app_command_check_updater_roles)
    @app_commands.command(name='accept_penalty')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.describe(request_id="Request ID")
    @app_commands.guild_only()
    async def accept_request_command_slash(self, interaction: discord.Interaction, request_id: str, leaderboard: Optional[str]):
        await interaction.response.defer()
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        try:
            id = int(request_id)    
        except:
            await ctx.send("Your message ID is not a valid ID")
            return
        await self.accept_request(ctx, lb, id)

    async def refuse_request(self, ctx: commands.Context, lb: LeaderboardConfig, request_id: int):
        request_data = await API.get.getPenaltyRequest(lb.website_credentials, request_id)
        if request_data is None:
            await ctx.send(f"The request {request_id} doesn't exist.")
            return
        else:    
            assert isinstance(ctx.author, discord.Member)
            is_staff = check_updater_roles(ctx)
            if not is_staff:
                reporter = await API.get.getPlayerFromDiscord(lb.website_credentials, ctx.author.id)
                if reporter is None:
                    await ctx.send("Your discord ID doesn't match with a player on the leaderboard")
                    return                
                if reporter.id != request_data.reporter_id:
                    await ctx.send("You are not the author of this request.")
                    return
            await ctx.send(await self.refuse_request_process(lb, ctx, request_data))

    @commands.check(command_check_updater_roles)
    @commands.command(name='refusePenalty', aliases=['refusePen', 'denyPen', 'denyPenalty'])
    async def refuse_request_command_text(self, ctx: commands.Context, request_id: int = commands.parameter(description="Request ID")):
        lb = get_leaderboard(ctx)
        await self.refuse_request(ctx, lb, request_id)

    @app_commands.check(app_command_check_reporter_roles)
    @app_commands.command(name='refuse_penalty')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.guild_only()
    @app_commands.describe(request_id="Request ID")
    async def refuse_request_command_slash(self, interaction: discord.Interaction, request_id: int, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        is_staff = check_updater_roles(ctx)
        await interaction.response.defer(ephemeral = not is_staff)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.refuse_request(ctx, lb, request_id)

    async def accept_all_request(self, ctx: commands.Context, lb: LeaderboardConfig):
        requests_list = await API.get.getPendingPenaltyRequests(lb.website_credentials)
        if requests_list is None:
            await ctx.send("An error occured while fetching the requests")
            return
        remaining_requests = len(requests_list)
        if remaining_requests == 0:
            await ctx.send("There are no pending requests")
            return
        remaining_message = await ctx.send(f"Remaining requests: {remaining_requests}, please wait.")
        
        for penalty_request in requests_list:
            assert isinstance(ctx.author, discord.Member)
            await ctx.send(await self.accept_request_process(lb, ctx, penalty_request))
            remaining_requests -= 1
            await remaining_message.edit(content=f"Remaining requests: {remaining_requests}, please wait.")
        try:
            await remaining_message.delete()
        except:
            pass
        await ctx.send("All requests have been accepted.")

    @commands.check(command_check_updater_roles)
    @commands.command(name='acceptAllPenalties', aliases=['acceptAllPens', 'uapens', 'aapens'])
    async def accept_all_requests_command_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.accept_all_request(ctx, lb)

    @app_commands.check(app_command_check_updater_roles)
    @app_commands.command(name='accept_all_penalties')
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.guild_only()
    async def accept_all_requests_command_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.accept_all_request(ctx, lb)

async def setup(bot):
    await bot.add_cog(Requests(bot))