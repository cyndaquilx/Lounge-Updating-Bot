import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

import API.post, API.get
import asyncio

from util import get_leaderboard, get_leaderboard_slash, fix_player_role
from models import ServerConfig, LeaderboardConfig, PlayerPlacement
from custom_checks import leaderboard_autocomplete, app_command_check_admin_roles, command_check_admin_roles
from io import StringIO
import csv

class Admin(commands.Cog):
    def __init__ (self, bot):
        self.bot = bot

    @app_commands.autocomplete(leaderboard=leaderboard_autocomplete)
    @app_commands.check(app_command_check_admin_roles)
    @app_commands.command(name="place_everyone")
    async def place_everyone_slash(self, interaction: discord.Interaction, csv_file: discord.Attachment, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await ctx.send("Working...")
        # takes in a CSV file with 2 columns - Name and MMR
        file = await csv_file.read()
        decoded_file = file.decode().splitlines()
        row_count = len(decoded_file)
        reader = csv.reader(decoded_file)
        if lb.enable_bulk_placement_endpoint:
            placements: list[PlayerPlacement] = []
            for i, row in enumerate(reader):
                name, mmr = row
                placements.append(PlayerPlacement(name, mmr))
            success, error = await API.post.placeManyPlayers(lb.website_credentials, placements)
            if not success:
                await ctx.send(f"An error occurred: {error}")
                return
            else:
                await ctx.send("Done")
        else: 
            errors = "Errors:\n"
            for i, row in enumerate(reader):
                name, mmr = row
                player, error = await API.post.placePlayer(lb.website_credentials, mmr, name)
                if player is None:
                    errors += f"{name} - {error}\n"
                if (i+1) % 100 == 0:
                    await ctx.send(f"{i+1}/{row_count}")
                await asyncio.sleep(0.05)
            error_log = discord.File(StringIO(errors), filename="error_log.txt")
            await ctx.send(f"{row_count}/{row_count} - done", file=error_log)

    async def get_player_list(self, ctx: commands.Context, lb: LeaderboardConfig):
        await ctx.defer()
        players = await API.get.getPlayerList(lb.website_credentials)
        if not players:
            await ctx.send("Player list not found")
            return
        output = StringIO()
        writer = csv.writer(output)
        for player in players:
            writer.writerow([player.name, player.mmr, player.events_played])
        output.seek(0)
        f = discord.File(output, filename="players.csv")
        await ctx.send(file=f)

    @app_commands.autocomplete(leaderboard=leaderboard_autocomplete)
    @app_commands.check(app_command_check_admin_roles)
    @app_commands.command(name="get_player_list")
    async def get_player_list_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.get_player_list(ctx, lb)

    @commands.check(command_check_admin_roles)
    @commands.command(name="getPlayerList")
    async def get_player_list_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.get_player_list(ctx, lb)

    # use this after all players have been placed on the website for new season
    async def fix_all_player_roles(self, ctx: commands.Context, lb: LeaderboardConfig):
        member_count = len(ctx.guild.members)
        await ctx.send("Working...")
        for i, member in enumerate(ctx.guild.members):
            player = await API.get.getPlayerFromDiscord(lb.website_credentials, member.id)
            await fix_player_role(ctx, lb, player, member)
            if (i+1) % 100 == 0:
                await ctx.send(f"{i+1}/{member_count}")
        await ctx.send(f"{member_count}/{member_count} - done")
    
    @commands.check(command_check_admin_roles)
    @commands.command(name="fixAllRoles")
    async def fix_all_roles_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.fix_all_player_roles(ctx, lb)

    @app_commands.autocomplete(leaderboard=leaderboard_autocomplete)
    @app_commands.check(app_command_check_admin_roles)
    @app_commands.command(name="fix_all_roles")
    async def fix_all_roles_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.fix_all_player_roles(ctx, lb)

    async def unlockdown(self, channel:discord.TextChannel):
        overwrite = channel.overwrites_for(channel.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
        await channel.send("Unlocked " + channel.mention)

    @commands.check(command_check_admin_roles)
    @commands.command()
    async def startseason(self, ctx: commands.Context, season_num:int):
        server_config: ServerConfig | None = ctx.bot.config.get(ctx.guild.id, None)
        if server_config is None:
            await ctx.send("You cannot use this command in this server")
            return
        for channel in ctx.guild.channels:
            if channel.category_id in server_config.tier_channel_categories:
                await self.unlockdown(channel)
        await ctx.send(f"All tier chats have been unlocked. ENJOY SEASON {season_num}!! @everyone")
        
    @commands.command()
    async def countchannels(self, ctx: commands.Context):
        count = 0
        for _ in ctx.guild.channels:
            count += 1
        await ctx.send(count)

    @commands.command()
    @commands.is_owner()
    async def sync_server(self, ctx: commands.Context):
        await ctx.bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
        await ctx.send("synced")

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        await ctx.bot.tree.sync()
        await ctx.send("synced")

async def setup(bot):
    await bot.add_cog(Admin(bot))
