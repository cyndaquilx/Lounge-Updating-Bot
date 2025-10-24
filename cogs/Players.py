import discord
from discord import app_commands
from discord.ext import commands
from models import LeaderboardConfig, UpdatingBot, PlayerAllGames
import API.get, API.post
from custom_checks import yes_no_check, command_check_admin_verification_roles, command_check_all_staff_roles, command_check_updater_roles, command_check_staff_roles, check_staff_roles, find_member
import custom_checks
from util import get_leaderboard, get_leaderboard_slash, place_player_with_mmr, fix_player_role, add_player, country_code_to_emoji
from typing import Optional, Union
import re

class Players(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    player_group = app_commands.Group(name="player", description="Manage players", guild_only=True)

    @commands.check(command_check_admin_verification_roles)
    @commands.command(name="addPlayer", aliases=["add"])
    @commands.guild_only()
    async def add_player_text(self, ctx, mkc_id:int, member:discord.Member | int, *, name):
        lb = get_leaderboard(ctx)
        await add_player(ctx, lb, mkc_id, member, name, None)

    @commands.check(command_check_admin_verification_roles)
    @commands.command(name="addAndPlace", aliases=['apl'])
    @commands.guild_only()
    async def add_and_place_text(self, ctx, mkcID:int, mmr:int, member:discord.Member | int, *, name):
        lb = get_leaderboard(ctx)
        await add_player(ctx, lb, mkcID, member, name, mmr)

    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="add")
    async def add_player_slash(self, interaction: discord.Interaction, mkc_id:int, member:discord.Member, name: str, mmr: int | None, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await add_player(ctx, lb, mkc_id, member, name, mmr)

    async def register_player(self, ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, player: PlayerAllGames):
        assert ctx.guild is not None
        registered_player, error = await API.post.registerPlayer(lb.website_credentials, player.name)
        if not registered_player:
            await ctx.send(f"An error occurred when registering the player: {error}")
            return
        await ctx.send(f"Successfully registered the player in this server")
        if registered_player.discord_id:
            await fix_player_role(ctx.guild, lb, registered_player, int(registered_player.discord_id))

    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="register")
    async def register_player_slash(self, interaction: discord.Interaction, member:discord.Member, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        player = await API.get.getPlayerAllGamesFromDiscord(lb.website_credentials, member.id)
        if not player:
            await ctx.send("Player with that Discord ID was not found")
            return
        await self.register_player(ctx, lb, player)

    async def hide_player(self, ctx, lb: LeaderboardConfig, name: str):
        success, text = await API.post.hidePlayer(lb.website_credentials, name)
        if success is False:
            await ctx.send(f"An error occurred: {text}")
            return
        await ctx.send("Successfully hid player")

    @commands.check(command_check_staff_roles)
    @commands.command(name="hide")
    @commands.guild_only()
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

    async def update_discord(self, ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, discord_id: int, name: str):
        assert isinstance(ctx.channel, Union[discord.TextChannel, discord.Thread])
        assert ctx.guild is not None

        discord_player = await API.get.getPlayerAllGamesFromDiscord(lb.website_credentials, discord_id)
        if discord_player:
            await ctx.send(f"Another player ({discord_player.name}) already uses this Discord ID.")
            return
        
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
            assert isinstance(channel, discord.TextChannel)
            await channel.send(embed=e)

    @commands.check(command_check_staff_roles)
    @commands.command(name="updateDiscord", aliases=['ud'])
    @commands.guild_only()
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
        assert ctx.guild is not None
        player = await API.get.getPlayerFromDiscord(lb.website_credentials, member.id)
        if player is None:
            await ctx.send("Player could not be found on lounge site")
            return
        await fix_player_role(ctx.guild, lb, player, member)
        await ctx.send("Fixed player's roles")

    @commands.command(name="fixRole")
    @commands.guild_only()
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
    @commands.guild_only()
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

    async def refresh_player(self, ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, name: str):
        if name.isdigit():
            player = await API.get.getPlayerAllGamesFromDiscord(lb.website_credentials, int(name))
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
    @commands.guild_only()
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

    async def update_player_mkc(self, ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, new_mkc_id: int, name: str):
        assert ctx.guild is not None
        content = "Please confirm the MKC ID change within 30 seconds"
        e = discord.Embed(title="MKC ID Change")
        e.add_field(name="Name", value=name)
        e.add_field(name="New MKC ID", value=new_mkc_id)
        embedded = await ctx.send(content=content, embed=e)
        if not await yes_no_check(ctx, embedded):
            return
        player = await API.get.getPlayerAllGames(lb.website_credentials, name)
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
            assert isinstance(updating_log, discord.TextChannel)
            await updating_log.send(embed=e)

    @commands.check(command_check_staff_roles)
    @commands.command(name="updateMKC", aliases=['um'])
    @commands.guild_only()
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

    @commands.check(command_check_updater_roles)
    @commands.command(name="place", aliases=['placemmr'])
    @commands.guild_only()
    async def place_mmr_text(self, ctx, mmr:int, *, name):
        lb = get_leaderboard(ctx)
        await place_player_with_mmr(ctx, lb, mmr, name)
    
    @app_commands.check(custom_checks.app_command_check_updater_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="place")
    async def place_mmr_slash(self, interaction: discord.Interaction, mmr:app_commands.Range[int, 0], name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await place_player_with_mmr(ctx, lb, mmr, name)

    @commands.check(command_check_admin_verification_roles)
    @commands.command(name="forcePlace")
    @commands.guild_only()
    async def force_place_text(self, ctx, mmr:int, *, name):
        lb = get_leaderboard(ctx)
        await place_player_with_mmr(ctx, lb, mmr, name, force=True)

    @commands.command(name='mkcPlayer', aliases=['mkc'])
    @commands.guild_only()
    async def mkc_search_text(self, ctx: commands.Context[UpdatingBot], mkcid:int):
        lb = get_leaderboard(ctx)
        player = await API.get.getPlayerAllGamesFromMKC(lb.website_credentials, mkcid)
        if player is None:
            await ctx.send("The player couldn't be found!")
            return
        player_url = f"{lb.website_credentials.url}/PlayerDetails/{player.id}"
        mkc_url = f"https://mkcentral.com/registry/players/profile?id={player.mkc_id}"
        mkc_field = f"[{player.mkc_id}]({mkc_url})"
        e = discord.Embed(title="Player Data", url=player_url, description=player.name)
        e.add_field(name="MKC ID", value=mkc_field)
        await ctx.send(embed=e)

    @commands.check(command_check_admin_verification_roles)
    @commands.command(name="addAllDiscords")
    @commands.guild_only()
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

    async def player_data(self, ctx: commands.Context[UpdatingBot], name: str, lb: LeaderboardConfig):
        await ctx.defer()
        name = name.strip()
        if len(name) == 0:
            name = str(ctx.author.id)
        if name.isdigit():
            player = await API.get.getPlayerFromDiscord(lb.website_credentials, int(name))
        elif re.match(r'^\d{4}-\d{4}-\d{4}$', name):
            player = await API.get.getPlayerFromFC(lb.website_credentials, name)
        else:
            player = await API.get.getPlayer(lb.website_credentials, name)
        if player is None:
            await ctx.send(f"The following player could not be found: {name}")
            return
        e = discord.Embed(title=f"Player Data",
                          description=f"{country_code_to_emoji(player.country_code) if player.country_code else ''} {player.name}",
                          url=f"{lb.website_credentials.url}/{lb.website_credentials.game}/PlayerDetails/{player.id}")
        e.add_field(name="MKC ID", value=f"[{player.mkc_id}](https://mkcentral.com/registry/players/profile?id={player.mkc_id})", inline=False)
        if player.discord_id:
            e.add_field(name="Discord", value=f"<@{player.discord_id}> ({player.discord_id})", inline=False)
        e.add_field(name="Friend Code", value=player.fc, inline=False)
        e.add_field(name="MMR", value=player.mmr, inline=False)
        e.add_field(name="Peak MMR", value=player.peak_mmr, inline=False)
        e.add_field(name="Hidden", value=player.is_hidden, inline=False)
        await ctx.send(embed=e)

    @commands.check(command_check_updater_roles)
    @commands.command(name="data")
    @commands.guild_only()
    async def player_data_text(self, ctx, *, name: str):
        lb = get_leaderboard(ctx)
        await self.player_data(ctx, name, lb)
    
    @app_commands.check(custom_checks.app_command_check_updater_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @player_group.command(name="data")
    async def player_data_slash(self, interaction: discord.Interaction, name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.player_data(ctx, name, lb)

async def setup(bot):
    await bot.add_cog(Players(bot))
