import discord
from discord import app_commands
from discord.ext import commands

import mmrTables
import API.post, API.get

from custom_checks import check_staff_roles, command_check_reporter_roles, command_check_staff_roles, app_command_check_staff_roles
import custom_checks

from typing import Optional
from util import submit_table, delete_table, get_leaderboard, get_leaderboard_slash, set_multipliers, update_roles, parse_scores, check_placements
from models import ServerConfig, LeaderboardConfig

import traceback
import copy

class Updating(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    update_group = app_commands.Group(name="update", description="Update tables")

    async def get_pending(self, ctx: commands.Context, lb: LeaderboardConfig):
        tables = await API.get.getPending(lb.website_credentials)
        if len(tables) == 0:
            await ctx.send("There are no pending tables")
            return
        msg = ""
        for tier in lb.tier_results_channels.keys():
            count = 0
            ids = []
            for table in tables:
                if table.tier == tier:
                    ids.append(table.id)
                    count += 1
            if count > 0:
                curr_line = f"\n<#{lb.tier_results_channels[tier]}> - {count} tables\n"
                if len(msg) + len(curr_line) > 2000:
                    await ctx.send(msg)
                    msg = ""
                msg += curr_line
                for tableid in ids:
                    curr_line = f"\tID {tableid}\n"
                    if len(msg) + len(curr_line) > 2000:
                        await ctx.send(msg)
                        msg = ""
                    msg += curr_line
        if len(msg) > 0:
            await ctx.send(msg) 

    @commands.check(command_check_staff_roles)
    @commands.command(name="pending")
    async def pending_text(self, ctx):
        lb = get_leaderboard(ctx)
        await self.get_pending(ctx, lb)
        
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.command(name="pending")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def pending_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.get_pending(ctx, lb)

    @app_commands.check(app_command_check_staff_roles)
    @update_group.command(name="table")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def update_table_slash(self, interaction: discord.Interaction, tableid: int, multipliers: Optional[str], leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_table(ctx, lb, tableid, extraArgs=multipliers)

    @commands.check(command_check_staff_roles)
    @commands.command(name="update", aliases=["u"])
    async def update_table_text(self, ctx, tableid: int, *, extraArgs=""):
        lb = get_leaderboard(ctx)
        await self.update_table(ctx, lb, tableid, extraArgs=extraArgs)

    async def update_all_tables(self, ctx: commands.Context, lb: LeaderboardConfig, tier:Optional[str] = None, until_id: Optional[int] = None):
        tables = await API.get.getPending(lb.website_credentials)
        if tables is False:
            await ctx.send("There are no pending tables")
            return
        for table in tables:
            if tier and table.tier != tier.upper():
                continue
            if until_id and table.id > until_id:
                continue
            try:
                success = await self.update_table(ctx, lb, table.id)
                if success is False:
                    return
            except Exception as e:
                traceback.print_exc()
        up_to = f"up to ID {until_id}" if until_id else ""
        in_tier = f"in Tier {tier.upper()}" if tier else ""
        await ctx.send(f"Updated all tables {up_to} {in_tier}")

    @app_commands.check(app_command_check_staff_roles)
    @update_group.command(name="all")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def update_all_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_all_tables(ctx, lb)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['ua'])
    async def updateAll(self, ctx):
        lb = get_leaderboard(ctx)
        await self.update_all_tables(ctx, lb)

    @app_commands.check(app_command_check_staff_roles)
    @update_group.command(name="tier")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def update_tier_slash(self, interaction: discord.Interaction, tier: str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_all_tables(ctx, lb, tier=tier)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['ut'])
    async def updateTier(self, ctx, tier):
        lb = get_leaderboard(ctx)
        await self.update_all_tables(ctx, lb, tier=tier)

    @app_commands.check(app_command_check_staff_roles)
    @update_group.command(name="until")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def update_until_slash(self, interaction: discord.Interaction, table_id: int, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_all_tables(ctx, lb, until_id=table_id)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['uu'])
    async def updateUntil(self, ctx, tableid:int):
        lb = get_leaderboard(ctx)
        await self.update_all_tables(ctx, lb, until_id=tableid)

    @app_commands.check(app_command_check_staff_roles)
    @update_group.command(name="tier_until")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def update_tier_until_slash(self, interaction: discord.Interaction, tier: str, table_id: int, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_all_tables(ctx, lb, tier=tier, until_id=table_id)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['utu'])
    async def updateTierUntil(self, ctx, tier: str, table_id:int):
        lb = get_leaderboard(ctx)
        await self.update_all_tables(ctx, lb, tier=tier, until_id=table_id)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['setml'])
    async def setMultipliers(self, ctx, table_id:int, *, extraArgs=""):
        lb = get_leaderboard(ctx)
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is False:
            await ctx.send("Table couldn't be found")
            return
        workmsg = await ctx.send("Working...")
        if not await set_multipliers(ctx, lb, table.id, extraArgs):
            return
        await workmsg.edit(content=f"Successfully set multipliers for table")

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['mlraces'])
    async def multiplierRaces(self, ctx: commands.Context, table_id: int, *, extraArgs=""):
        lb = get_leaderboard(ctx)
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is False:
            await ctx.send("Table couldn't be found")
            return
        workmsg = await ctx.send("Working...")
        race_args = extraArgs.split(",")
        missed_races = {}
        min_missed_races = 3
        no_loss_races = 8
        for arg in race_args:
            split_arg = arg.split()
            if len(split_arg) >= 2:
                player_name = " ".join(split_arg[:-1]).strip()
                player_races = split_arg[-1].strip()
                if not player_races.isdigit():
                    await workmsg.edit(content=f"{player_races} is not an integer between {min_missed_races}-12")
                    return
                player_races_int = int(player_races)
                if player_races_int < min_missed_races:
                    await workmsg.edit(content=f"The minimum number of races to be missed for increased loss is f{min_missed_races}")
                    return
                if player_name.isdigit():
                    player_name = table.get_score_from_discord(int(player_name)).player.name
                missed_races[player_name] = player_races_int
        if len(missed_races) == 0:
            await ctx.send("No valid arguments found")
            return
        
        multipliers = {}
        for player, races in missed_races.items():
            team = table.get_team(player)
            if team is None:
                await workmsg.edit(content=f"{player} not found on table ID {table_id}!")
                return
            if races >= no_loss_races:
                mult = 0
            else:
                mult = 1 - (races/lb.races_per_mogi)
            for team_player in team.scores:
                if team_player.player.name.lower() != player.lower():
                    multipliers[team_player.player.name] = mult

        updatedMultipliers = await API.post.setMultipliers(lb.website_credentials, table_id, multipliers)
        if updatedMultipliers is not True:
            await workmsg.edit(content=f"Error setting multipliers:\n{updatedMultipliers}")
            return
        
        mult_msg = "\n".join([f"{player}: {mult:.2f}" for player, mult in multipliers.items()])
        await workmsg.edit(content=f"Set the following multipliers:\n{mult_msg}")
            
    async def update_table(self, ctx: commands.Context, lb: LeaderboardConfig, table_id:int, *, extraArgs=""):
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is None:
            await ctx.send("Table couldn't be found")
            return
        workmsg = await ctx.send("Working...")
        if not await set_multipliers(ctx, lb, table_id, extraArgs):
            return
        
        #await self.check_placements(ctx, table)
        await check_placements(ctx, lb, table)

        updated_table, error = await API.post.verifyTable(lb.website_credentials, table_id)
        if not updated_table:
            await ctx.send(f"An error occurred while updating table ID {table_id}:\n{error}")
            return False
        
        placements = []
        names = []
        oldMMRs = []
        newMMRs = []
        peakMMRs = []
        scores = []

        channel = ctx.guild.get_channel(lb.tier_results_channels[updated_table.tier])

        for team in updated_table.teams:
            placements.append(team.rank)
            team.scores.sort(key=lambda s: s.score, reverse=True)
            for score in team.scores:
                names.append(score.player.name)
                oldMMRs.append(score.prev_mmr)
                newMMRs.append(score.new_mmr)
                peakMMRs.append(score.is_peak)
                scores.append(score.score)
        mmrTable = mmrTables.createMMRTable(lb, updated_table.size, updated_table.tier, placements, names, scores, oldMMRs, newMMRs, updated_table.id, peakMMRs)

        rankChanges = ""
        for team in updated_table.teams:
            for score in team.scores:
                rankChanges += await update_roles(ctx, lb, score.player.name, score.prev_mmr, score.new_mmr)
        
        f = discord.File(fp=mmrTable, filename='MMRTable.png',
                         description=" ".join(names))
        e = discord.Embed(title="MMR Table")
        if updated_table.table_message_id:
            try:
                reactMsg = await channel.fetch_message(updated_table.table_message_id)
            except:
                reactMsg = None
            if reactMsg is not None:
                CHECK_BOX = "\U00002611"
                await reactMsg.add_reaction(CHECK_BOX)
        else:
            reactMsg = None
        # link the table message if it was found
        id_field = f"[{updated_table.id}]({reactMsg.jump_url})" if reactMsg else str(updated_table.id)
        e.add_field(name="ID", value=id_field)
        e.add_field(name="Tier", value=updated_table.tier)
        e.add_field(name="Updated by", value=ctx.author.mention)
        e.set_image(url="attachment://MMRTable.png")
        if reactMsg is not None:
            updateMsg = await reactMsg.reply(content=rankChanges, embed=e, file=f)
        else:
            updateMsg = await channel.send(content=rankChanges, embed=e, file=f)
        if ctx.channel.id != channel.id:
            await workmsg.edit(content=f"Table ID `{table_id}` updated successfully; check {updateMsg.jump_url} to view")
        else:
            await workmsg.delete()
            try:
                await ctx.message.delete()
            except Exception as e:
                pass
        await API.post.setUpdateMessageId(lb.website_credentials, updated_table.id, updateMsg.id)
        return True
    
    async def update_scores(self, ctx: commands.Context, lb: LeaderboardConfig, table_id: int, args: str):
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is None:
            await ctx.send("Table couldn't be found")
            return
        if not check_staff_roles(ctx):
            if table.verified_on:
                await ctx.send("This table has been updated already, so you cannot edit the scores as a Reporter.")
                return
            if not table.get_score_from_discord(ctx.author.id):
                await ctx.send("You did not play in this event, so you cannot edit the scores for this table")
                return
        scores, error = parse_scores(args)
        if scores is None:
            await ctx.send(f"An error has occurred setting scores:\n{error}")
            return
        success = await API.post.setScores(lb.website_credentials, table_id, scores)
        if success is not True:
            await ctx.send(f"An error occurred setting scores:\n{success}")
            return
        if table.table_message_id:
            channel = ctx.guild.get_channel(lb.tier_results_channels[table.tier])
            table_msg = await channel.fetch_message(table.table_message_id)
            if table_msg is not None:
                # add info about who edited the table to the table msg
                table_embed = table_msg.embeds[0]
                table_embed.add_field(name=f"Edits by {ctx.author.display_name}",
                    value="\n".join([f"{name}: {scores[name]}" for name in scores.keys()]),
                    inline=False)
                await table_msg.edit(embed=table_embed)
        await ctx.send("Successfully edited scores")

    @commands.check(command_check_reporter_roles)
    @commands.command(name="updateScores", aliases=['us'])
    async def update_scores_slash(self, ctx, tableID:int, *, args):
        lb = get_leaderboard(ctx)
        await self.update_scores(ctx, lb, tableID, args)

    async def fix_table_names(self, ctx: commands.Context, lb: LeaderboardConfig, table_id: int, args: str):
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is None:
            await ctx.send("Table couldn't be found")
            return
        old_table = copy.deepcopy(table) # make a deep copy so we can preserve data after mutation
        names = args.split(",")
        if len(names) % 2 != 0:
            await ctx.send("You must enter an even number of names to use this command")
            return
        old_names = [names[i].strip() for i in range(0, len(names), 2)]
        new_names = [names[i].strip() for i in range(1, len(names), 2)]
        players = await API.get.getPlayers(lb.website_credentials, new_names)
        err_str = ""
        for i, player in enumerate(players):
            if not player:
                err_str += f"{new_names[i]}\n"
        if len(err_str) > 0:
            await ctx.send(f"The following players cannot be found on the leaderboard:\n{err_str}")
            return
        new_names = [p.name for p in players]
        for i in range(len(old_names)):
            score = table.get_score(old_names[i])
            if not score:
                await ctx.send(f"An error has occurred: Player {old_names[i]} not found on table ID {table_id}")
                return
            score.player.name = new_names[i]
        new_table = await submit_table(ctx, lb, table)
        if not new_table:
            return
        await delete_table(ctx, lb, old_table, send_log=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        e = discord.Embed(title="Table names fixed")
        e.add_field(name="Old ID", value=old_table.id)
        e.add_field(name="New ID", value=new_table.id)
        e.add_field(name="Updated by", value=ctx.author.mention, inline=False)
        if updating_log is not None:
            await updating_log.send(embed=e)

    @commands.check(command_check_staff_roles)
    @commands.command(name="fixNames")
    async def fix_names_text(self, ctx: commands.Context, table_id:int, *, args):
        lb = get_leaderboard(ctx)
        await self.fix_table_names(ctx, lb, table_id, args)

    async def fix_table_scores(ctx: commands.Context, lb: LeaderboardConfig, table_id: int, args: str):
        table = await API.get.getTable(lb.website_credentials, table_id)
        if table is None:
            await ctx.send("Table couldn't be found")
            return
        old_table = copy.deepcopy(table) # make a deep copy so we can preserve data after mutation
        parsed_scores, error = parse_scores(args)
        if parsed_scores is None:
            await ctx.send(f"An error has occurred parsing input:\n{error}")
            return
        for player in parsed_scores:
            table_score = table.get_score(player)
            if not table_score:
                await ctx.send(f"An error has occurred: Player {player} not found on table ID {table_id}")
                return
            table_score.score = parsed_scores[player]
        new_table = await submit_table(ctx, lb, table)
        if not new_table:
            return
        await delete_table(ctx, lb, old_table, send_log=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        e = discord.Embed(title="Table scores fixed")
        e.add_field(name="Old ID", value=old_table.id)
        e.add_field(name="New ID", value=new_table.id)
        e.add_field(name="Updated by", value=ctx.author.mention, inline=False)
        if updating_log is not None:
            await updating_log.send(embed=e)

    @commands.check(command_check_staff_roles)
    @commands.command(name="fixScores")
    async def fix_scores_text(self, ctx: commands.Context, table_id:int, *, args):
        lb = get_leaderboard(ctx)
        await self.fix_table_scores(ctx, lb, table_id, args)
        
    #adds correct roles and nicknames for players when they join server
    @commands.Cog.listener(name='on_member_join')
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        server_info: ServerConfig = self.bot.config.servers.get(member.guild.id, None)
        if not server_info:
            return
        for lb in server_info.leaderboards.values():
            player = await API.get.getPlayerFromDiscord(lb.website_credentials, member.id)
            if player is None:
                continue
            player_role = member.guild.get_role(lb.player_role_id)
            if member.display_name != player.name:
                await member.edit(nick=player.name)
            if player.mmr is None:
                role = member.guild.get_role(lb.placement_role_id)
                roles_to_add = [role, player_role]
                await member.add_roles(*roles_to_add)
                continue
            rank = lb.get_rank(player.mmr)
            role = member.guild.get_role(rank.role_id)
            roles_to_add = [role, player_role]
            await member.add_roles(*roles_to_add)
        
    #changes nicknames if someone changes their name to something else
    @commands.Cog.listener(name='on_user_update')
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.bot:
            return
        servers: dict[int, ServerConfig] = self.bot.config.servers
        for server_id in servers:
            server = self.bot.get_guild(server_id)
            if server is None:
                continue
            member = server.get_member(before.id)
            if member is None:
                continue
            if member.nick is not None:
                continue
            if before.display_name == after.display_name:
                continue
            for lb in servers[server_id].leaderboards.values():
                player = await API.get.getPlayerFromDiscord(lb.website_credentials, before.id)
                if player is None:
                    continue
                if player.name != after.display_name:
                    await member.edit(nick=player.name)
        
async def setup(bot):
    await bot.add_cog(Updating(bot))
