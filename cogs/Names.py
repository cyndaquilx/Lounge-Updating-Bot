import discord
from discord import app_commands
from discord.ext import commands
from custom_checks import check_name_restricted_roles, check_valid_name, yes_no_check, app_command_check_staff_roles, command_check_staff_roles
import custom_checks
from models import LeaderboardConfig
import API.get, API.post
from datetime import datetime, timedelta, timezone
from util import get_leaderboard, get_leaderboard_slash
from typing import Optional

class Names(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    name_group = app_commands.Group(name="name", description="Manage nicknames", guild_only=True)

    async def player_request_name(self, ctx: commands.Context, lb: LeaderboardConfig, name: str):
        assert ctx.guild is not None
        if check_name_restricted_roles(ctx, ctx.author):
            await ctx.send("You are nickname restricted and cannot use this command")
            return
        if ctx.channel.id != lb.name_request_channel:
            await ctx.send(f"You may only use this command in <#{lb.name_request_channel}>")
            return
        name = name.strip()
        if not await check_valid_name(ctx, lb, name):
            return
        player = await API.get.getPlayerDetailsFromDiscord(lb.website_credentials, ctx.author.id)
        if player is None:
            await ctx.send("Your Discord ID is not linked to a Lounge profile, please make a support ticket for help.")
            return
        last_change_date = player.name_history[0].changed_on
        now = datetime.now(timezone.utc)
        days_since_change = (now - last_change_date).days
        if days_since_change < 60:
            allowed_change_date = (last_change_date + timedelta(days=60)).strftime('%m/%d/%Y')
            await ctx.send(f"You changed your name less than 60 days ago. You can request a new name on {allowed_change_date}.")
            return
        content = "Please confirm the name change within 30 seconds to make a name change request"
        e = discord.Embed(title="Name Change")
        e.add_field(name="Current Name", value=player.name, inline=False)
        e.add_field(name="New Name", value=name, inline=False)
        embedded = await ctx.send(content=content, embed=e)
        if not await yes_no_check(ctx, embedded):
            return
        success, request = await API.post.requestNameChange(lb.website_credentials, player.name, name)
        await embedded.delete()
        if success is False:
            await ctx.send(f"An error occurred trying to request a name:\n{request}")
            return
        await ctx.send("Your name change request has been sent to staff for approval. Please wait, you will receive a DM when this request is accepted or denied (if you have server member DMs enabled).")
        log_channel = ctx.guild.get_channel(lb.name_request_log_channel)
        if log_channel:
            assert isinstance(log_channel, discord.TextChannel)
            e = discord.Embed(title="New Name Change Request")
            e.add_field(name="Current Name", value=player.name, inline=False)
            e.add_field(name="New Name", value=name, inline=False)
            log_msg = await log_channel.send(embed=e)
            await API.post.setNameChangeMessageId(lb.website_credentials, player.name, log_msg.id)

    @commands.command(name="requestname", aliases=['rn'])
    @commands.guild_only()
    async def request_name_text(self, ctx: commands.Context, *, name):
        lb = get_leaderboard(ctx)
        await self.player_request_name(ctx, lb, name)

    @app_commands.command(name="requestname")
    @app_commands.guild_only()
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def request_name_slash(self, interaction: discord.Interaction, name:str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.player_request_name(ctx, lb, name)

    async def approve_name_change(self, ctx: commands.Context, lb: LeaderboardConfig, old_name: str):
        assert ctx.guild is not None
        name_request, error = await API.post.acceptNameChange(lb.website_credentials, old_name)
        if not name_request:
            await ctx.send(f"An error occurred approving name change for {old_name}:\n{error}")
            return
        await ctx.send(f"Approved the name change: {name_request.current_name} -> {name_request.new_name}")
        e = discord.Embed(title="Name change request approved")
        e.add_field(name="Current Name", value=name_request.current_name)
        e.add_field(name="New Name", value=name_request.new_name, inline=False)
        e.add_field(name="Mention", value=f"<@{name_request.discord_id}>")
        e.add_field(name="Approved by", value=ctx.author.mention, inline=False)

        name_change_log = ctx.guild.get_channel(lb.name_change_log_channel)
        if name_change_log:
            assert isinstance(name_change_log, discord.TextChannel)
            await name_change_log.send(embed=e)
        name_request_log = ctx.guild.get_channel(lb.name_request_log_channel)
        if name_request_log and name_request.message_id:
            assert isinstance(name_request_log, discord.TextChannel)
            react_msg = await name_request_log.fetch_message(name_request.message_id)
            if react_msg is not None:
                CHECK_BOX = "\U00002611"
                await react_msg.add_reaction(CHECK_BOX)
        if not name_request.discord_id:
            return
        try:
            member = await ctx.guild.fetch_member(name_request.discord_id)
        except:
            await ctx.send(f"Couldn't find member in server, please change their nickname manually")
            return
        try:
            await member.send(f"Your name change request from {name_request.current_name} to {name_request.new_name} has been approved.")
        except Exception as e:
            pass
        try:
            await member.edit(nick=name_request.new_name)
        except Exception as e:
            pass

    @name_group.command(name="approve")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def approve_name_slash(self, interaction: discord.Interaction, old_name: str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.approve_name_change(ctx, lb, old_name)

    @commands.check(command_check_staff_roles)
    @commands.command(name="approveName", aliases=['an'])
    async def approve_name_text(self, ctx: commands.Context, *, old_name: str):
        lb = get_leaderboard(ctx)
        await self.approve_name_change(ctx, lb, old_name)

    async def get_pending_names(self, ctx: commands.Context, lb: LeaderboardConfig):
        changes = await API.get.getPendingNameChanges(lb.website_credentials)
        if changes is None:
            await ctx.send("An error occurred when getting the name changes. Please try again later.")
            return
        if len(changes) == 0:
            await ctx.send("There are no pending name changes")
            return
        msg = "**Pending name changes**\n```"
        for change in changes:
            msg += f"{change.current_name} -> {change.new_name}\n"
        msg += "```"
        await ctx.send(msg)

    @commands.check(command_check_staff_roles)
    @commands.command(name="pendingNames", aliases=['pn'])
    async def pending_names_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.get_pending_names(ctx, lb)

    @name_group.command(name="pending")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def pending_names_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.get_pending_names(ctx, lb)

    async def approve_all_name_changes(self, ctx: commands.Context, lb: LeaderboardConfig):
        changes = await API.get.getPendingNameChanges(lb.website_credentials)
        if changes is None:
            await ctx.send("An error occurred when getting the name changes. Please try again later.")
            return
        if len(changes) == 0:
            await ctx.send("There are no pending name changes")
            return
        for change in changes:
            await self.approve_name_change(ctx, lb, change.current_name)
        await ctx.send("Approved all name changes")

    @commands.check(command_check_staff_roles)
    @commands.command(name="approveNamesAll", aliases=['ana'])
    async def approve_all_names_text(self, ctx: commands.Context):
        lb = get_leaderboard(ctx)
        await self.approve_all_name_changes(ctx, lb)

    @name_group.command(name="approve_all")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def approve_all_names_slash(self, interaction: discord.Interaction, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.approve_all_name_changes(ctx, lb)

    async def reject_name_change(self, ctx: commands.Context, lb: LeaderboardConfig, old_name: str, reason: str | None):
        assert ctx.guild is not None
        name_request, error = await API.post.rejectNameChange(lb.website_credentials, old_name)
        if name_request is None:
            await ctx.send(f"An error occurred trying to reject name change from {old_name}:\n{error}")
            return
        await ctx.send("Rejected the name change")
        name_request_log = ctx.guild.get_channel(lb.name_request_log_channel)
        if not name_request_log:
            return
        assert isinstance(name_request_log, discord.TextChannel)
        try:
            if name_request.message_id:
                react_msg = await name_request_log.fetch_message(name_request.message_id)
                X_MARK = "\U0000274C"
                await react_msg.add_reaction(X_MARK)
        except:
            pass
        e = discord.Embed(title="Name change request denied")
        e.add_field(name="Current Name", value=name_request.current_name, inline=False)
        e.add_field(name="Requested Name", value=name_request.new_name, inline=False)
        e.add_field(name="Denied by", value=ctx.author.mention)
        if reason:
            e.add_field(name="Reason", value=reason, inline=False)
        await name_request_log.send(embed=e)
        if name_request.discord_id:
            try:
                member = await ctx.guild.fetch_member(name_request.discord_id)
            except:
                return
            try:
                await member.send(f"Your name change request from {name_request.current_name} to {name_request.new_name} has been denied. Reason: {reason}")
            except Exception as e:
                pass

    @commands.check(command_check_staff_roles)
    @commands.command(name="rejectName", aliases=['rjn'])
    async def reject_name_text(self, ctx: commands.Context, *, args: str):
        lb = get_leaderboard(ctx)
        splitArgs = args.split(";")
        name = splitArgs[0].strip()
        reason = None
        if len(splitArgs) > 1:
            reason = ";".join(splitArgs[1:]).strip()
        await self.reject_name_change(ctx, lb, name, reason)

    @name_group.command(name="reject")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def reject_name_slash(self, interaction: discord.Interaction, old_name: str, reason: str | None, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.reject_name_change(ctx, lb, old_name, reason)

    async def update_player_name(self, ctx: commands.Context, lb: LeaderboardConfig, oldName: str, newName: str):
        assert ctx.guild is not None
        if not await check_valid_name(ctx, lb, newName):
            return
        player = await API.get.getPlayer(lb.website_credentials, oldName)
        if player is None:
            await ctx.send("Player with old name can't be found")
            return
        if player.discord_id:
            try:
                member = await ctx.guild.fetch_member(int(player.discord_id))
            except Exception as e:
                member = None
            if member is not None:
                is_name_restricted = check_name_restricted_roles(ctx, member)
                if is_name_restricted:
                    await ctx.send("This player is name restricted, so they can't change their name.")
                    return
            
        content = "Please confirm the name change within 30 seconds to change the name"
        e = discord.Embed(title="Name Change")
        e.add_field(name="Current Name", value=oldName, inline=False)
        e.add_field(name="New Name", value=newName, inline=False)
        
        embedded = await ctx.send(content=content, embed=e)
        if not await yes_no_check(ctx, embedded):
            return

        error = await API.post.updatePlayerName(lb.website_credentials, oldName, newName)
        await embedded.delete()
        if error:
            await ctx.send(f"An error occurred trying to change the name:\n{error}")
            return
        await ctx.send(f"Name change successful: {player.name} -> {newName}")
        name_change_log = ctx.guild.get_channel(lb.name_change_log_channel)
        if name_change_log:
            assert isinstance(name_change_log, discord.TextChannel)
            e = discord.Embed(title="Name changed by staff")
            e.add_field(name="Current Name", value=player.name)
            e.add_field(name="New Name", value=newName, inline=False)
            if player.discord_id:
                e.add_field(name="Mention", value=f"<@{player.discord_id}>")
            e.add_field(name="Changed by", value=ctx.author.mention, inline=False)
            await name_change_log.send(embed=e)
        
        if player.discord_id is None:
            await ctx.send("Player does not have a discord ID on the site, please update their nickname manually")
            return
        member = ctx.guild.get_member(int(player.discord_id))
        if member is None:
            await ctx.send(f"Couldn't find member {player.name}, please change their nickname manually")
            return
        await member.edit(nick=newName)
        await ctx.send("Successfully changed their nickname in server")

    @commands.check(command_check_staff_roles)
    @commands.command(name="updateName", aliases=['un'])
    async def update_name_text(self, ctx, *, args):
        lb = get_leaderboard(ctx)
        names = args.split(",")
        if len(names) != 2:
            await ctx.send("Please send 2 names separated by commas: ex. `!updateName Old Name, New Name`")
            return
        oldName = names[0].strip()
        newName = names[1].strip()
        await self.update_player_name(ctx, lb, oldName, newName)

    @name_group.command(name="update")
    @app_commands.check(app_command_check_staff_roles)
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    async def update_name_slash(self, interaction: discord.Interaction, old_name: str, new_name: str, leaderboard: Optional[str]):
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        await self.update_player_name(ctx, lb, old_name, new_name)

async def setup(bot):
    await bot.add_cog(Names(bot))