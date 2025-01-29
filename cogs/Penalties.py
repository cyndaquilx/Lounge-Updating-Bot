import discord
from discord import app_commands
from discord.ext import commands
import API.get, API.post
from models import LeaderboardConfig, Player
from util import update_roles, get_leaderboard, get_leaderboard_slash
from custom_checks import app_command_check_staff_roles, command_check_staff_roles
import custom_checks
from typing import Optional
from datetime import timedelta

class Penalties(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    penalty_group = app_commands.Group(name="penalty", description="Manage penalties")

    async def get_strike_history(self, lb: LeaderboardConfig, name: str):
        strikes, _ = await API.get.getStrikes(lb.website_credentials, name)
        if not strikes or not len(strikes):
            return ""
        
        start_index = 0
        expire_date = strikes[0].awarded_on + timedelta(days=30)
        num_strikes = 1
        i = 1
        while i < len(strikes):
            # if there's 3 strikes in current strike limit, start new strike limit with 1 strike
            if num_strikes == 3:
                start_index = i
                expire_date = strikes[start_index].awarded_on + timedelta(days=30)
                num_strikes = 1
                i += 1
                continue
            # if it's been 30 days between current strike and starting strike's expiration date,
            # restart the loop from the strike immediately after the starting index
            if strikes[i].awarded_on >= expire_date:
                start_index += 1
                expire_date = strikes[start_index].awarded_on + timedelta(days=30)
                num_strikes = 1
                i = start_index
            else:
                num_strikes += 1
            i += 1
        strike_str = ""
        last_5 = strikes[::-1][:5]
        for i, strike in enumerate(last_5):
            # add a divider for strikes counting towards the current limit
            if i == num_strikes:
                strike_str += "----------\n"
            date_formatted = discord.utils.format_dt(strike.awarded_on, style="d")
            date_relative = discord.utils.format_dt(strike.awarded_on, "R")
            strike_str += f"{date_formatted} ({date_relative})\n"
        return strike_str

    async def pen_channel(self, ctx: commands.Context, lb: LeaderboardConfig, player: Player, tier: str, reason: str | None, 
                          amount: int, channel: discord.TextChannel, is_anonymous: bool, is_strike: bool, is_request=False):
        pen, error = await API.post.createPenalty(lb.website_credentials, player.name, abs(amount), is_strike)
        if pen is None:
            await ctx.send(f"An error occurred while penalizing {player.name}:\n{error}")
            return None
        embed_title = "Penalty added"
        if is_strike:
            embed_title = "Penalty + strike added"
        tier = tier.upper()
        e = discord.Embed(title=embed_title)
        e.add_field(name="Player", value=pen.player_name, inline=False)
        e.add_field(name="Amount", value="-%d" % abs(amount))
        e.add_field(name="ID", value=pen.id)
        if tier != "":
            e.add_field(name="Tier", value=tier)
        if not is_anonymous:
            e.add_field(name="Given by", value=ctx.author.mention)
        if reason:
            e.add_field(name="Reason", value=reason, inline=False)
        if is_strike:
            strike_str = await self.get_strike_history(lb, player.name)
            if len(strike_str):
                e.add_field(name="Strikes", value=strike_str, inline=False)
        rank_change = await update_roles(ctx, lb, player, pen.prev_mmr, pen.new_mmr)
        pen_msg = await channel.send(embed=e, content=rank_change)
        member = ctx.guild.get_member(player.discord_id)
        if member:
            try:
                if not is_anonymous:
                    # change from mention to name because we are in DMs
                    e.set_field_at(4, name='Given by', value=ctx.author.display_name)
                if is_strike:
                    dm_content = "You received a strike in 150cc Lounge:"
                else:
                    dm_content = "You received a penalty in 150cc Lounge:"
                await member.send(embed=e, content=dm_content)
            except Exception as ex:
                pass
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if updating_log:
            if is_anonymous:
                e.add_field(name="Given by", value=ctx.author.mention)
            else:
                e.set_field_at(4, name='Given by', value=ctx.author.mention)
            await updating_log.send(embed=e, content=rank_change)
        if ctx.channel.id == channel.id:
            try:
                await ctx.message.delete()
            except discord.NotFound:
                pass
        else:
            if not is_request:
                await ctx.send(f"Added -{abs(amount)} penalty to {pen.player_name} in {pen_msg.jump_url} (ID: {pen.id})")
        return pen.id

    async def add_penalty(self, ctx: commands.Context, lb: LeaderboardConfig, amount:int, tier: str, names: list[str], reason: str | None, is_anonymous=False, is_strike=False, is_request=False):
        tier = tier.upper()
        if tier not in lb.tier_results_channels.keys() and not is_request:
            await ctx.send(f"Your tier is not valid! Valid tiers are: {list(lb.tier_results_channels.keys())}")
            return [None]
        if abs(amount) > 200:
            await ctx.send("Individual penalties can only be 200 points or lower")
            return [None]
        channel = ctx.guild.get_channel(lb.tier_results_channels[tier]) if is_request == False else ctx.guild.get_channel(lb.penalty_channel)
        players: list[Player] = []
        for name in names:
            if name.isdigit():
                player = await API.get.getPlayerFromDiscord(lb.website_credentials, name)
                if player is None:
                    await ctx.send(f"The following player could not be found: {name}")
                    return [None]
                players.append(player)
            else:
                player = await API.get.getPlayer(lb.website_credentials, name)
                if player is None:
                    await ctx.send(f"The following player could not be found: {name}")
                    return [None]
                players.append(player)
        id_result = []
        for player in players:
            id_result.append(await self.pen_channel(ctx, lb, player, tier, reason, amount, channel, is_anonymous, is_strike, is_request=is_request))
        return id_result

    async def parse_and_add_penalty(self, ctx: commands.Context, lb: LeaderboardConfig, amount:int, tier, args: str, is_anonymous=False, is_strike=False):
        split_args = args.split(";")
        names = [s.strip() for s in split_args[0].split(",")]
        if len(set(names)) < len(names):
            await ctx.send("There is at least one duplicate name in your input, try again")
            return
        reason = None
        if len(split_args) > 1:
            reason = split_args[1].strip()
        await self.add_penalty(ctx, lb, amount, tier, names, reason, is_anonymous, is_strike)

    @penalty_group.command(name="new")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def penalty_slash(self, interaction: discord.Interaction, amount:app_commands.Range[int, 1, 200], tier:str, names: str, 
                                reason:str | None, leaderboard: Optional[str], strike: bool = False, anonymous: bool = False):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        parsed_names = [n.strip() for n in names.split(",")]
        await self.add_penalty(ctx, lb, amount, tier, parsed_names, reason, anonymous, strike)

    @penalty_group.command(name="strike")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def strike_slash(self, interaction: discord.Interaction, amount:app_commands.Range[int, 1, 200], tier:str, names: str, 
                                reason:str | None, leaderboard: Optional[str], anonymous: bool = False):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        parsed_names = [n.strip() for n in names.split(",")]
        await self.add_penalty(ctx, lb, amount, tier, parsed_names, reason, anonymous, True)

    @commands.check(command_check_staff_roles)
    @commands.command(name="penalty", aliases=['pen'])
    async def penalty_text(self, ctx, amount:int, tier, *, args):
        lb = get_leaderboard(ctx)
        await self.parse_and_add_penalty(ctx, lb, amount, tier, args)

    @commands.check(command_check_staff_roles)
    @commands.command(name="anonymousPenalty", aliases=['apen', 'apenalty'])
    async def penalty_anonymous_text(self, ctx, amount:int, tier, *, args):
        lb = get_leaderboard(ctx)
        await self.parse_and_add_penalty(ctx, lb, amount, tier, args, is_anonymous=True)

    @commands.check(command_check_staff_roles)
    @commands.command(name="strike", aliases=['str'])
    async def strike_text(self, ctx, amount:int, tier, *, args):
        lb = get_leaderboard(ctx)
        await self.parse_and_add_penalty(ctx, lb, amount, tier, args, is_strike=True)

    @commands.check(command_check_staff_roles)
    @commands.command(name="anonymousStrike", aliases=['astr', 'astrike'])
    async def strike_anonymous_text(self, ctx, amount:int, tier, *, args):
        lb = get_leaderboard(ctx)
        await self.parse_and_add_penalty(ctx, lb, amount, tier, args, is_strike=True, is_anonymous=True)

    async def delete_penalty(self, ctx: commands.Context, lb: LeaderboardConfig, pen_id: int, reason: str | None):
        success, error = await API.post.deletePenalty(lb.website_credentials, pen_id)
        if success is True:
            await ctx.send(f"Successfully deleted penalty ID {pen_id}")
        else:
            await ctx.send(f"An error occurred: {error}")
            return
        e = discord.Embed(title="Deleted Penalty")
        e.add_field(name="Penalty ID", value=pen_id)
        e.add_field(name="Removed by", value=ctx.author.mention)
        e.add_field(name="Removed in", value=ctx.channel.mention)
        if reason:
            e.add_field(name="Reason", value=reason, inline=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if updating_log:
            await updating_log.send(embed=e)

    @commands.check(command_check_staff_roles)
    @commands.command(name="deletePenalty")
    async def delete_penalty_text(self, ctx, pen_id:int, *, reason=None):
        lb = get_leaderboard(ctx)
        await self.delete_penalty(ctx, lb, pen_id, reason)

    @penalty_group.command(name="delete")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def delete_penalty_slash(self, interaction: discord.Interaction, pen_id: int, reason: Optional[str], leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.delete_penalty(ctx, lb, pen_id, reason)

    @commands.check(command_check_staff_roles)
    @commands.command(name="strikelist")
    async def get_strikes_text(self, ctx: commands.Context, *, name: str):
        lb = get_leaderboard(ctx)
        strike_str = await self.get_strike_history(lb, name)
        if strike_str:
            await ctx.send(strike_str)
        else:
            await ctx.send("No strikes")

async def setup(bot):
    await bot.add_cog(Penalties(bot))