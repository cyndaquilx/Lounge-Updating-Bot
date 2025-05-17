import discord
from discord import app_commands
from discord.ext import commands
from models import UpdatingBot, LeaderboardConfig, VerificationRequest
import custom_checks
from typing import Optional
from util import get_leaderboard_slash, get_verifications, add_player, update_verification_approvals, get_verification_by_id, get_user_latest_verification
from views import VerifyView, OldLoungeVerifyView

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    verify_group = app_commands.Group(name="verify", description="Manage verification requests", guild_only=True)

    @verify_group.command(name="new_view")
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def new_verify_view(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        e = discord.Embed(title=f"{interaction.guild.name}")
        e.add_field(name="Verify", value="Click the button below to get verified.")
        await interaction.response.send_message(embed=e, view=VerifyView(timeout=None))

    @verify_group.command(name="new_old_lounge_view")
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def new_old_lounge_verify_view(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        e = discord.Embed(title=f"{interaction.guild.name}")
        e.add_field(name="Verify with MK8DX Lounge Profile", value="Click the button below to get verified.")
        await interaction.response.send_message(embed=e, view=OldLoungeVerifyView(timeout=None))

    @verify_group.command(name="pending")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def pending_verifications(self, interaction: discord.Interaction[UpdatingBot], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verifications = await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "pending")
        if not len(verifications):
            await ctx.send("There are no pending verification requests")
            return
        msg = f"### {len(verifications)} Pending Requests"
        for v in verifications:
            curr_line = f"\n\tID: {v.id} | {v.leaderboard} | Name: {v.requested_name} | [MKC Profile]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={v.mkc_id}) | <@{v.discord_id}>"
            if len(msg) + len(curr_line) > 2000:
                await ctx.send(msg)
                msg = ""
            msg += curr_line
        if len(msg):
            await ctx.send(msg)

    @verify_group.command(name="pending_tickets")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def pending_ticket_verifications(self, interaction: discord.Interaction[UpdatingBot], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verifications = await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "ticket")
        if not len(verifications):
            await ctx.send("There are no verification requests with pending tickets")
            return
        msg = f"### {len(verifications)} Verification Ticket Requests"
        for v in verifications:
            curr_line = f"\n\tID: {v.id} | {v.leaderboard} | Name: {v.requested_name} | [MKC Profile]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={v.mkc_id}) | <@{v.discord_id}>"
            if len(msg) + len(curr_line) > 2000:
                await ctx.send(msg)
                msg = ""
            msg += curr_line
        if len(msg):
            await ctx.send(msg)

    async def approve_verifications(self, ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, verifications: list[VerificationRequest]):
        successes: list[int] = []
        for verification in verifications:
            add_success = await add_player(ctx, lb, verification.mkc_id, verification.discord_id, verification.requested_name, None, confirm=False)
            if add_success:
                successes.append(verification.id)
        await update_verification_approvals(ctx.bot.db_wrapper, verification.guild_id, lb, "approved", successes)

    @verify_group.command(name="approve")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def approve_pending_verification(self, interaction: discord.Interaction[UpdatingBot], id: int, leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verification = await get_verification_by_id(interaction.client.db_wrapper, interaction.guild.id, lb, id)
        if not verification:
            await ctx.send("Verification with that ID not found")
            return
        if verification.approval_status == "denied":
            await ctx.send("Verification is already denied")
            return
        if verification.approval_status == "approved":
            await ctx.send("Verification is already approved")
            return
        await self.approve_verifications(ctx, lb, [verification])
        await ctx.send("Successfully approved the verification")

    @verify_group.command(name="approve_all")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def approve_all_pending_verifications(self, interaction: discord.Interaction[UpdatingBot], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verifications = await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "pending")
        if not len(verifications):
            await ctx.send("There are no pending verification requests")
        await self.approve_verifications(ctx, lb, verifications)
        await ctx.send("Approved all pending verification requests")

    @verify_group.command(name="deny")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def deny_pending_verification(self, interaction: discord.Interaction[UpdatingBot], id: int, reason: Optional[str], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verification = await get_verification_by_id(interaction.client.db_wrapper, interaction.guild.id, lb, id)
        if not verification:
            await ctx.send("Verification with that ID not found")
            return
        if verification.approval_status == "denied":
            await ctx.send("Verification is already denied")
            return
        if verification.approval_status == "approved":
            await ctx.send("Verification is already approved")
            return
        await update_verification_approvals(interaction.client.db_wrapper, interaction.guild.id, lb, "denied", [verification.id], reason)
        found_member = interaction.guild.get_member(verification.discord_id)
        if not found_member:
            await ctx.send("Could not find member in this server, so denial DM was not sent")
            return
        denial_msg = f"Your request to be verified in {interaction.guild.name} was denied. Reason: {reason}"
        try:
            await found_member.send(denial_msg)
            await ctx.send("Successfully sent DM to member")
        except:
            await ctx.send("Member does not accept DMs from the bot, so denial DM was not sent")
        await ctx.send(f"Successfully denied verification")

        # send denied verification to updating log
        updating_log = interaction.guild.get_channel(lb.updating_log_channel)
        if not updating_log:
            return
        assert isinstance(updating_log, discord.TextChannel)
        e = discord.Embed(title="Verification Request Denied")
        e.add_field(name="ID", value=verification.id)
        e.add_field(name="Leaderboard", value=lb.name)
        e.add_field(name="Requested Name", value=verification.requested_name, inline=False)
        e.add_field(name="MKC ID", value=f"[{verification.mkc_id}]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={verification.mkc_id})")
        e.add_field(name="Mention", value=interaction.user.mention)
        e.add_field(name="Denied by", value=ctx.author.mention, inline=False)
        e.add_field(name="Reason", value=reason, inline=False)
        await updating_log.send(embed=e)

    @verify_group.command(name="request_ticket")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def request_ticket_for_verification(self, interaction: discord.Interaction[UpdatingBot], id: int, reason: Optional[str], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verification = await get_verification_by_id(interaction.client.db_wrapper, interaction.guild.id, lb, id)
        if not verification:
            await ctx.send("Verification with that ID not found")
            return
        if verification.approval_status != "pending":
            await ctx.send("Verification is not pending")
            return
        await update_verification_approvals(interaction.client.db_wrapper, interaction.guild.id, lb, "ticket", [verification.id], reason)
        found_member = interaction.guild.get_member(verification.discord_id)
        if not found_member:
            await ctx.send("Could not find member in this server, so denial DM was not sent")
            return
        denial_msg = f"Update to your verification request in {interaction.guild.name}: Please make a ticket to get verified. Reason: {reason}"
        try:
            await found_member.send(denial_msg)
            await ctx.send("Successfully sent DM to member")
        except:
            await ctx.send("Member does not accept DMs from the bot, so DM was not sent")
        await ctx.send(f"Successfully updated verification status")

        # send denied verification to updating log
        updating_log = interaction.guild.get_channel(lb.updating_log_channel)
        if not updating_log:
            return
        assert isinstance(updating_log, discord.TextChannel)
        e = discord.Embed(title="Requested Ticket for Verification Request")
        e.add_field(name="ID", value=verification.id)
        e.add_field(name="Leaderboard", value=lb.name)
        e.add_field(name="Requested Name", value=verification.requested_name, inline=False)
        e.add_field(name="MKC ID", value=f"[{verification.mkc_id}]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={verification.mkc_id})")
        e.add_field(name="Mention", value=interaction.user.mention)
        e.add_field(name="Handled by", value=ctx.author.mention, inline=False)
        e.add_field(name="Reason", value=reason, inline=False)
        await updating_log.send(embed=e)

    async def send_verification_info(self, ctx: commands.Context[UpdatingBot], verification: VerificationRequest):
        e = discord.Embed(title="Verification Request")
        e.add_field(name="ID", value=verification.id)
        e.add_field(name="Leaderboard", value=verification.leaderboard)
        e.add_field(name="Requested Name", value=verification.requested_name, inline=False)
        e.add_field(name="MKC ID", value=f"[{verification.mkc_id}]({ctx.bot.config.mkc_credentials.url}/registry/players/profile?id={verification.mkc_id})")
        e.add_field(name="Mention", value=f"<@{verification.discord_id}>")
        e.add_field(name="Status", value=verification.approval_status, inline=False)
        if verification.reason:
            e.add_field(name="Reason", value=verification.reason)
        await ctx.send(embed=e)

    @verify_group.command(name="info")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def verification_info(self, interaction: discord.Interaction[UpdatingBot], id: int, leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verification = await get_verification_by_id(interaction.client.db_wrapper, interaction.guild.id, lb, id)
        if not verification:
            await ctx.send("Verification with that ID not found")
            return
        await self.send_verification_info(ctx, verification)

    @verify_group.command(name="info_discord")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_mkc_roles)
    async def verification_info_by_discord_id(self, interaction: discord.Interaction[UpdatingBot], member: discord.Member, leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verification = await get_user_latest_verification(interaction.client.db_wrapper, interaction.guild.id, lb, member.id)
        if not verification:
            await ctx.send("Verification with that ID not found")
            return
        await self.send_verification_info(ctx, verification)

async def setup(bot: UpdatingBot):
    await bot.add_cog(Verification(bot))
    bot.add_view(VerifyView(timeout=None))
    bot.add_view(OldLoungeVerifyView(timeout=None))
