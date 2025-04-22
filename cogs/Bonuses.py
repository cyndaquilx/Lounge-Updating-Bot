import discord
from discord import app_commands
from discord.ext import commands
import API.get, API.post
from models import LeaderboardConfig
from custom_checks import command_check_staff_roles, app_command_check_staff_roles, app_command_check_admin_roles
from util import get_leaderboard, get_leaderboard_slash, update_roles
import custom_checks
from typing import Optional
import csv

class Bonuses(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    bonus_group = app_commands.Group(name="bonus", description="Manage bonuses", guild_only=True)

    async def give_bonus(self, ctx: commands.Context, lb: LeaderboardConfig, amount:int, name: str, reason: str | None):
        player = await API.get.getPlayer(lb.website_credentials, name)
        if player is None:
            await ctx.send("Player not found!")
            return
        bonus, error = await API.post.createBonus(lb.website_credentials, player.name, amount)
        if bonus is None:
            await ctx.send(f"An error occurred while giving the bonus:\n{error}")
            return
        rankChange = await update_roles(ctx, lb, player, bonus.prev_mmr, bonus.new_mmr)

        embed_title = "Bonus added"
        e = discord.Embed(title=embed_title)
        e.add_field(name="Player", value=bonus.player_name, inline=False)
        e.add_field(name="Amount", value=f"{bonus.amount}")
        e.add_field(name="Given by", value=ctx.author.mention)
        if reason:
            e.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(content=f"Successfully added {bonus.amount} MMR bonus to {bonus.player_name}\n{rankChange} (ID: {bonus.id})", embed=e)

        assert ctx.guild is not None
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if updating_log is not None:
            assert isinstance(updating_log, discord.TextChannel)
            await updating_log.send(embed=e, content=rankChange)
        if player.discord_id:
            member = ctx.guild.get_member(int(player.discord_id))
            if not member:
                return
            try:
                await member.send(f"You were given a +{amount} MMR bonus in {ctx.guild.name}. Reason: {reason}")
            except Exception as e:
                pass

    @commands.check(command_check_staff_roles)
    @commands.command(name="bonus")
    async def bonus_text(self, ctx: commands.Context, amount:int, *, args: str):
        lb = get_leaderboard(ctx)
        splitArgs = args.split(";")
        name = splitArgs[0]
        reason = None
        if len(splitArgs) > 1:
            reason = splitArgs[1].strip()
        absAmount = abs(amount)

        await self.give_bonus(ctx, lb, absAmount, name, reason)

    @app_commands.check(app_command_check_staff_roles)
    @bonus_group.command(name="new")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def bonus_slash(self, interaction: discord.Interaction, amount:app_commands.Range[int, 1, 200], name:str, 
                           reason:str | None, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.give_bonus(ctx, lb, amount, name, reason)

    @app_commands.check(app_command_check_admin_roles)
    @bonus_group.command(name="csv")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def bonus_csv(self, interaction: discord.Interaction, csv_file: discord.Attachment, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await ctx.send("Working...")
        # takes in a CSV file with 2 columns - Name and MMR
        file = await csv_file.read()
        decoded_file = file.decode().splitlines()
        row_count = len(decoded_file)
        reader = csv.reader(decoded_file)
        for i, row in enumerate(reader):
            player_ids = row[:-2]
            # tournament placement is row[-2], not used
            bonus_amount = int(row[-1])
            for player_id in player_ids:
                player = await API.get.getPlayerFromLounge(lb.website_credentials, int(player_id))
                if player is None:
                    await ctx.send(f"Player with ID {player_id} not found")
                    continue
                await self.give_bonus(ctx, lb, bonus_amount, player.name, reason="Tournament Prize")
            if (i+1) % 100 == 0:
                await ctx.send(f"{i+1}/{row_count}")
        await ctx.send("Done")


async def setup(bot):
    await bot.add_cog(Bonuses(bot))