import discord
from discord import app_commands
from discord.ext import commands
from models import LeaderboardConfig
import API.get, API.post
from custom_checks import check_valid_name, yes_no_check, command_check_admin_mkc_roles, command_check_all_staff_roles, command_check_staff_roles, check_staff_roles, find_member
import custom_checks
from util import get_leaderboard, get_leaderboard_slash, place_player_with_mmr, give_placement_role, fix_player_role
from typing import Optional, Union

class Players(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    player_group = app_commands.Group(name="player", description="Manage players")

    async def add_player(self, ctx: commands.Context, lb: LeaderboardConfig, mkcID: int, member: discord.Member | int, name: str, mmr: int | None):
        if isinstance(member, int):
            member_id = member
            if member != 0:
                member = ctx.guild.get_member(member)
                if not member:
                    await ctx.send("Member not found")
                    return
        else:
            member_id = member.id
        name = name.strip()
        if not await check_valid_name(ctx, lb, name):
            return
        content = "Please confirm the player details within 30 seconds"
        e = discord.Embed(title="New Player")
        e.add_field(name="Name", value=name)
        e.add_field(name="MKC ID", value=mkcID)
        if mmr is not None:
            e.add_field(name="Placement MMR", value=mmr)
        if isinstance(member, discord.Member):
            e.add_field(name="Discord", value=member.mention)
        embedded = await ctx.send(content=content, embed=e)
        if not await yes_no_check(ctx, embedded):
            return

        if mmr is not None:
            success, player = await API.post.createPlayerWithMMR(lb.website_credentials, mkcID, mmr, name, member_id)
        else:
            success, player = await API.post.createNewPlayer(lb.website_credentials, mkcID, name, member_id)
        if success is False:
            await ctx.send("An error occurred while trying to add the player: %s"
                           % player)
            return
        
        roleGiven = ""
        if isinstance(member, discord.Member):
            roles = []
            player_role = ctx.guild.get_role(lb.player_role_id)
            if player_role:
                roles.append(player_role)
            if mmr is not None:
                rank = lb.get_rank(mmr)
                rank_role = ctx.guild.get_role(rank.role_id)
                if rank_role:
                    roles.append(rank_role)
            else:
                placement_role = ctx.guild.get_role(lb.placement_role_id)
                if placement_role:
                    roles.append(placement_role)
            role_names = ", ".join([role.name for role in roles])
            try:
                await member.add_roles(*roles)
                if member.display_name != name:
                    await member.edit(nick=name)
                roleGiven += f"\nAlso gave {member.mention} {role_names} role"
            except Exception as e:
                roleGiven += f"\nCould not give {role_names} roles to the player due to the following: {e}"
                pass

            if lb.enable_verification_dms:
                quick_start_channel = ctx.guild.get_channel(lb.quick_start_channel)
                verification_msg = f"Your account has been successfully verified in {ctx.guild.name}! For information on how to join matches, " + \
                    f"check the {quick_start_channel.mention} channel." + \
                    f"\n{ctx.guild.name}への登録が完了しました！ 模擬への参加方法は{quick_start_channel.mention} をご覧下さい。"
                try:
                    await member.send(verification_msg)
                    roleGiven += f"\nSuccessfully sent verification DM to the player"
                except Exception as e:
                    roleGiven += f"\nPlayer does not accept DMs from the bot, so verification DM was not sent"

        await embedded.delete()
        url = f"{lb.website_credentials.url}/PlayerDetails/{player.id}"
        await ctx.send(f"Successfully added the new player: {url}{roleGiven}")
        e = discord.Embed(title="Added new player")
        e.add_field(name="Name", value=name)
        e.add_field(name="MKC ID", value=mkcID)
        if isinstance(member, discord.Member):
            e.add_field(name="Discord", value=member.mention)
        if mmr is not None:
            e.add_field(name="MMR", value=mmr)
        e.add_field(name="Added by", value=ctx.author.mention, inline=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if updating_log is not None:
            await updating_log.send(embed=e)

    @commands.check(command_check_admin_mkc_roles)
    @commands.command(name="addPlayer", aliases=["add"])
    async def add_player_text(self, ctx, mkc_id:int, member:discord.Member | int, *, name):
        lb = get_leaderboard(ctx)
        await self.add_player(ctx, lb, mkc_id, member, name, None)

    @commands.check(command_check_admin_mkc_roles)
    @commands.command(name="addAndPlace", aliases=['apl'])
    async def add_and_place_text(self, ctx, mkcID:int, mmr:int, member:discord.Member | int, *, name):
        lb = get_leaderboard(ctx)
        await self.add_player(ctx, lb, mkcID, member, name, mmr)

    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="add")
    async def add_player_slash(self, interaction: discord.Interaction, mkc_id:int, member:discord.Member, name: str, mmr: int | None, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.add_player(ctx, lb, mkc_id, member, name, mmr)

    async def hide_player(self, ctx, lb: LeaderboardConfig, name: str):
        success, text = await API.post.hidePlayer(lb.website_credentials, name)
        if success is False:
            await ctx.send(f"An error occurred: {text}")
            return
        await ctx.send("Successfully hid player")

    @commands.check(command_check_staff_roles)
    @commands.command(name="hide")
    async def hide_text(self, ctx, *, name):
        lb = get_leaderboard(ctx)
        await self.hide_player(ctx, lb, name)

    @app_commands.check(custom_checks.app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="hide")
    async def hide_slash(self, interaction: discord.Interaction, name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.hide_player(ctx, lb, name)

    async def update_discord(self, ctx: commands.Context, lb: LeaderboardConfig, discord_id: int, name: str):
        player = await API.get.getPlayer(lb.website_credentials, name)
        if player is None:
            await ctx.send("The player couldn't be found!")
            return
        success, response = await API.post.updateDiscord(lb.website_credentials, name, discord_id)
        if success is False:
            await ctx.send(f"An error occurred: {response}")
            return
        await ctx.send("Discord ID change successful")
        e = discord.Embed(title="Discord ID changed")
        e.add_field(name="Player", value=player.name)
        if player.discord_id:
            e.add_field(name="Old Discord", value=f"<@{player.discord_id}>")
        e.add_field(name="New Discord", value=f"<@{discord_id}>")
        e.add_field(name="Changed by", value=ctx.author.mention, inline=False)
        e.add_field(name="Changed in", value=ctx.channel.mention, inline=False)
        channel = ctx.guild.get_channel(lb.mute_ban_list_channel)
        if channel is not None:
            await channel.send(embed=e)

    @commands.check(command_check_staff_roles)
    @commands.command(name="updateDiscord", aliases=['ud'])
    async def update_discord_text(self, ctx, member:Union[discord.Member, int], *, name):
        if isinstance(member, discord.Member):
            member = member.id
        lb = get_leaderboard(ctx)
        await self.update_discord(ctx, lb, member, name)

    @app_commands.check(custom_checks.app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="update_discord")
    async def update_discord_slash(self, interaction: discord.Interaction, member: discord.Member, name: str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_discord(ctx, lb, member.id, name)

    async def fix_member_role(self, ctx: commands.Context, lb: LeaderboardConfig, member: discord.Member):
        player = await API.get.getPlayerFromDiscord(lb.website_credentials, member.id)
        if player is None:
            await ctx.send("Player could not be found on lounge site")
            return
        await fix_player_role(ctx, lb, player, member)
        await ctx.send("Fixed player's roles")

    @commands.command(name="fixRole")
    async def fix_role_text(self, ctx, member_str=None):
        if (not check_staff_roles(ctx)) and (member_str is not None):
            await ctx.send("You cannot change other people's roles without a staff role")
            return
        converter = commands.MemberConverter()
        if member_str is None:
            member = ctx.author
        else:
            member = await converter.convert(ctx, member_str)
        lb = get_leaderboard(ctx)
        await self.fix_member_role(ctx, lb, member)

    @app_commands.check(custom_checks.app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="fixrole")
    async def fix_role_slash(self, interaction: discord.Interaction, member: discord.Member, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.fix_member_role(ctx, lb, member)

    async def unhide_player(self, ctx, lb: LeaderboardConfig, name):
        success, text = await API.post.unhidePlayer(lb.website_credentials, name)
        if success is False:
            await ctx.send(f"An error occurred: {text}")
            return
        await ctx.send("Successfully unhid player")

    @commands.check(command_check_staff_roles)
    @commands.command(name="unhide")
    async def unhide_text(self, ctx, *, name):
        lb = get_leaderboard(ctx)
        await self.unhide_player(ctx, lb, name)

    @app_commands.check(custom_checks.app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="unhide")
    async def unhide_slash(self, interaction: discord.Interaction, name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.unhide_player(ctx, lb, name)

    async def refresh_player(self, ctx, lb: LeaderboardConfig, name):
        if name.isdigit():
            player = await API.get.getPlayerFromDiscord(lb.website_credentials, name)
            if player is None:
                await ctx.send("Player could not be found!")
                return
            name = player.name
        success, text = await API.post.refreshPlayerData(lb.website_credentials, name)
        if success is False:
            await ctx.send(f"An error occurred: {text}")
            return
        await ctx.send("Successfully refreshed player data")

    @commands.check(command_check_all_staff_roles)
    @commands.command(name="refresh")
    async def refresh_text(self, ctx, *, name):
        lb = get_leaderboard(ctx)
        await self.refresh_player(ctx, lb, name)

    @app_commands.check(custom_checks.app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="refresh")
    async def refresh_slash(self, interaction: discord.Interaction, name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.refresh_player(ctx, lb, name)

    async def update_player_mkc(self, ctx, lb: LeaderboardConfig, new_mkc_id: int, name: str):
        content = "Please confirm the MKC ID change within 30 seconds"
        e = discord.Embed(title="MKC ID Change")
        e.add_field(name="Name", value=name)
        e.add_field(name="New MKC ID", value=new_mkc_id)
        embedded = await ctx.send(content=content, embed=e)
        if not await yes_no_check(ctx, embedded):
            return
        player = await API.get.getPlayer(lb.website_credentials, name)
        if player is None:
            await ctx.send("The player couldn't be found!")
            return
        success = await API.post.updateMKCid(lb.website_credentials, name, new_mkc_id)
        await embedded.delete()
        if success is not True:
            await ctx.send("An error occurred trying to change the MKC ID:\n%s" % success)
            return
        await ctx.send("MKC ID change successful")
        e = discord.Embed(title="MKC ID Changed")
        e.add_field(name="Player", value=player.name)
        e.add_field(name="Old MKC ID", value=player.mkc_id)
        e.add_field(name="New MKC ID", value=new_mkc_id)
        if player.discord_id:
            e.add_field(name="Mention", value=f"<@{player.discord_id}>")
        e.add_field(name="Changed by", value=ctx.author.mention, inline=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if updating_log is not None:
            await updating_log.send(embed=e)

    @commands.check(command_check_staff_roles)
    @commands.command(name="updateMKC", aliases=['um'])
    async def update_mkc_text(self, ctx, newID:int, *, name):
        lb = get_leaderboard(ctx)
        await self.update_player_mkc(ctx, lb, newID, name)

    @app_commands.check(custom_checks.app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="mkc")
    async def update_mkc_slash(self, interaction: discord.Interaction, new_mkc_id: int, name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_player_mkc(ctx, lb, new_mkc_id, name)

    async def place_player_in_rank(self, ctx: commands.Context, lb: LeaderboardConfig, rank: str, name: str):
        rank = rank.lower()
        if rank not in lb.place_rank_mmrs:
            await ctx.send("Please enter one of the following ranks: %s"
                           % (", ".join(lb.place_rank_mmrs.keys())))
            return False
        placeMMR = lb.place_rank_mmrs[rank]
        player, error = await API.post.placePlayer(lb.website_credentials, placeMMR, name)
        if not player:
            await ctx.send(f"An error occurred while trying to place the player: {error}")
            return False
        await give_placement_role(ctx, lb, player, placeMMR)
        await ctx.send(f"Successfully placed {player.name} in {rank} with {placeMMR} MMR")
        return True
    
    # @commands.check(command_check_staff_roles)
    # @commands.command(name="place")
    # async def place_rank_text(self, ctx, rank, *, name):
    #     lb = get_leaderboard(ctx)
    #     await self.place_player_in_rank(ctx, lb, rank, name)

    @commands.check(command_check_staff_roles)
    @commands.command(name="place", aliases=['placemmr'])
    async def place_mmr_text(self, ctx, mmr:int, *, name):
        lb = get_leaderboard(ctx)
        await place_player_with_mmr(ctx, lb, mmr, name)
    
    @app_commands.check(custom_checks.app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="place")
    async def place_mmr_slash(self, interaction: discord.Interaction, mmr:app_commands.Range[int, 0], name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await place_player_with_mmr(ctx, lb, mmr, name)

    @commands.check(command_check_admin_mkc_roles)
    @commands.command(name="forcePlace")
    async def force_place_text(self, ctx, mmr:int, *, name):
        lb = get_leaderboard(ctx)
        await place_player_with_mmr(ctx, lb, mmr, name, True)

    @commands.command(name='mkcPlayer', aliases=['mkc'])
    async def mkc_search_text(self, ctx, mkcid:int):
        lb = get_leaderboard(ctx)
        player = await API.get.getPlayerFromMKC(lb.website_credentials, mkcid)
        if player is None:
            await ctx.send("The player couldn't be found!")
            return
        player_url = f"{lb.website_credentials.url}/PlayerDetails/{player.id}"
        mkc_url = f"https://www.mariokartcentral.com/forums/index.php?members/{player.mkc_id}/"
        mkc_field = f"[{player.mkc_id}]({mkc_url})"
        e = discord.Embed(title="Player Data", url=player_url, description=player.name)
        e.add_field(name="MKC ID", value=mkc_field)
        await ctx.send(embed=e)

    @commands.check(command_check_admin_mkc_roles)
    @commands.command(name="addAllDiscords")
    async def add_all_discords_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        players = await API.get.getPlayerList(lb.website_credentials)
        if players is None:
            await ctx.send("An error occurred getting the player list")
            return
        for player in players:
            if player.discord_id is not None:
                continue
            if player.mmr is None:
                role_id = lb.placement_role_id
            else:
                role_id = lb.get_rank(player.mmr).role_id
            member = find_member(ctx, player.name, role_id)
            if member is None:
                print(f"could not find member with name {player.name}")
                continue
            success, _ = await API.post.updateDiscord(lb.website_credentials, player.name, member.id)
            if success is True:
                print(f"Added discord id for {player.name}: {member.id}")

async def setup(bot):
    await bot.add_cog(Players(bot))
