import discord
from discord import app_commands
from discord.ext import commands
from models import UpdatingBot, LeaderboardConfig, VerificationRequest
import custom_checks
from typing import Optional
from util import get_leaderboard_slash, get_verifications, add_player, update_verification_approvals, get_verification_by_id, get_user_latest_verification, fix_player_role
from views import VerifyView
import API.get, API.post

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    verify_group = app_commands.Group(name="verify", description="Manage verification requests", guild_only=True)

    @verify_group.command(name="new_view")
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def new_verify_view(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        e = discord.Embed(title=f"{interaction.guild.name}")
        e.add_field(name="Verify", value="Click the button below to get verified.")
        await interaction.response.send_message(embed=e, view=VerifyView(timeout=None))

    @verify_group.command(name="pending")
    @app_commands.choices(
        countries=[
            app_commands.Choice(name="Non-Japanese", value="West"),
            app_commands.Choice(name="Japanese", value="JP"),
            app_commands.Choice(name="All", value="All")
        ]
    )
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def pending_verifications(self, interaction: discord.Interaction[UpdatingBot], countries: app_commands.Choice[str], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verifications = await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "pending", countries.value)
        if not len(verifications):
            await ctx.send("There are no pending verification requests")
            return
        msg = f"### {len(verifications)} Pending Requests"
        for v in verifications:
            curr_line = f"\n\tID: {v.id} | {v.leaderboard} | Country: {v.country_code} | Name: {v.requested_name} | [MKC Profile]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={v.mkc_id}) | <@{v.discord_id}>"
            if len(msg) + len(curr_line) > 2000:
                await ctx.send(msg)
                msg = ""
            msg += curr_line
        if len(msg):
            await ctx.send(msg)

    @verify_group.command(name="pending_tickets")
    @app_commands.choices(
        countries=[
            app_commands.Choice(name="Non-Japanese", value="West"),
            app_commands.Choice(name="Japanese", value="JP"),
            app_commands.Choice(name="All", value="All")
        ]
    )
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def pending_ticket_verifications(self, interaction: discord.Interaction[UpdatingBot], countries: app_commands.Choice[str], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        lb = get_leaderboard_slash(ctx, leaderboard)
        verifications = await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "ticket", countries.value)
        if not len(verifications):
            await ctx.send("There are no verification requests with pending tickets")
            return
        msg = f"### {len(verifications)} Verification Ticket Requests"
        for v in verifications:
            curr_line = f"\n\tID: {v.id} | {v.leaderboard} | Country: {v.country_code} | Name: {v.requested_name} | [MKC Profile]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={v.mkc_id}) | <@{v.discord_id}>"
            if len(msg) + len(curr_line) > 2000:
                await ctx.send(msg)
                msg = ""
            msg += curr_line
        if len(msg):
            await ctx.send(msg)

    async def approve_verifications(self, ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, verifications: list[VerificationRequest]):
        assert ctx.guild is not None
        successes: list[int] = []
        for verification in verifications:
            # check if player has already been verified for another game in the meantime,
            # then register them / fix their role
            all_games_check = await API.get.getPlayerAllGamesFromDiscord(lb.website_credentials, verification.discord_id)
            if all_games_check:
                if lb.website_credentials.game not in all_games_check.registrations:
                    player, error = await API.post.registerPlayer(lb.website_credentials, all_games_check.name)
                    if error:
                        await ctx.send(f"Failed to register player {all_games_check.name} for verification ID {verification.id} - {error}")
                        continue
                    await ctx.send(f"Successfully approved verification ID {verification.id}")
                    await fix_player_role(ctx.guild, lb, player, verification.discord_id)
                else:
                    await ctx.send(f"Player {all_games_check.name} is already verified - skipping verification ID {verification.id}")
                    player = await API.get.getPlayerFromLounge(lb.website_credentials, all_games_check.id)
                    if player:
                        await fix_player_role(ctx.guild, lb, player, verification.discord_id)
                successes.append(verification.id)
                continue

            # if player hasn't been verified already just accept the request as normal
            add_success = await add_player(ctx, lb, verification.mkc_id, verification.discord_id, verification.requested_name, None, confirm=False, check_exists=False)
            if add_success:
                successes.append(verification.id)
                await ctx.send(f"Successfully approved verification ID {verification.id}")
            else:
                await ctx.send(f"Failed to approve verification ID {verification.id}")
        await update_verification_approvals(ctx.bot.db_wrapper, verification.guild_id, lb, "approved", successes)
        return successes

    @verify_group.command(name="approve")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def approve_pending_verification(self, interaction: discord.Interaction[UpdatingBot], id: int, leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        await ctx.defer()
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

    @verify_group.command(name="approve_many")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def approve_many_pending_verifications(self, interaction: discord.Interaction[UpdatingBot], request_ids: str, leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        await ctx.defer()
        lb = get_leaderboard_slash(ctx, leaderboard)
        ids: list[int] = []
        for id in request_ids.split():
            if not id.isdigit():
                await ctx.send(f"{id} is not a valid integer. Be sure to type the request IDs as a space-separated list (ex. 1 2 3)")
                return
            ids.append(int(id))
        verifications = await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "pending")
        verifications.extend(await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "ticket"))
        verification_dict = {v.id: v for v in verifications}
        approve_list: list[VerificationRequest] = []
        for id in ids:
            v = verification_dict.get(id, None)
            if v is None:
                await ctx.send(f"Verification with ID {id} not found")
                return
            approve_list.append(v)
        await self.approve_verifications(ctx, lb, approve_list)

    #@verify_group.command(name="approve_all")
    @app_commands.choices(
        countries=[
            app_commands.Choice(name="Non-Japanese", value="West"),
            app_commands.Choice(name="Japanese", value="JP"),
            app_commands.Choice(name="All", value="All")
        ]
    )
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def approve_all_pending_verifications(self, interaction: discord.Interaction[UpdatingBot], countries: app_commands.Choice[str], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        await ctx.defer()
        lb = get_leaderboard_slash(ctx, leaderboard)
        verifications = await get_verifications(interaction.client.db_wrapper, interaction.guild.id, lb, "pending", countries.value)
        if not len(verifications):
            await ctx.send("There are no pending verification requests")
        await self.approve_verifications(ctx, lb, verifications)
        await ctx.send("Approved all pending verification requests")

    @verify_group.command(name="deny")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def deny_pending_verification(self, interaction: discord.Interaction[UpdatingBot], id: int, reason: Optional[str], send_dm: Optional[bool], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        await ctx.defer()
        lb = get_leaderboard_slash(ctx, leaderboard)
        verification = await get_verification_by_id(interaction.client.db_wrapper, interaction.guild.id, lb, id)
        if not verification:
            await ctx.send(f"Verification ID {id} not found")
            return
        if verification.approval_status == "denied":
            await ctx.send(f"Verification ID {id} is already denied")
            return
        if verification.approval_status == "approved":
            await ctx.send(f"Verification ID {id} is already approved")
            return
        await update_verification_approvals(interaction.client.db_wrapper, interaction.guild.id, lb, "denied", [verification.id], reason)
        if send_dm:
            found_member = interaction.guild.get_member(verification.discord_id)
            if not found_member:
                await ctx.send("Could not find member in this server, so denial DM was not sent")
                return
            denial_msg = (f"Your request to be verified in {interaction.guild.name} was denied. Reason: {reason}" +
                f"\n{interaction.guild.name} へのあなたの認証リクエストは拒否されました。理由： {reason}")
            try:
                await found_member.send(denial_msg)
                await ctx.send("Successfully sent DM to member")
            except:
                await ctx.send("Member does not accept DMs from the bot, so denial DM was not sent")
        await ctx.send(f"Successfully denied verification ID {verification.id}")

        # send denied verification to updating log
        verification_log = interaction.guild.get_channel(lb.verification_log_channel)
        if not verification_log:
            return
        assert isinstance(verification_log, discord.TextChannel)
        e = discord.Embed(title="Verification Request Denied")
        e.add_field(name="ID", value=verification.id)
        e.add_field(name="Leaderboard", value=lb.name)
        e.add_field(name="Requested Name", value=verification.requested_name, inline=False)
        e.add_field(name="MKC ID", value=f"[{verification.mkc_id}]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={verification.mkc_id})")
        e.add_field(name="Mention", value=f"<@{verification.discord_id}>")
        e.add_field(name="Denied by", value=ctx.author.mention, inline=False)
        e.add_field(name="Reason", value=reason, inline=False)
        await verification_log.send(embed=e)

    @verify_group.command(name="request_ticket")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
    async def request_ticket_for_verification(self, interaction: discord.Interaction[UpdatingBot], id: int, reason: Optional[str], leaderboard: Optional[str]):
        assert interaction.guild is not None
        ctx = await commands.Context.from_interaction(interaction)
        await ctx.defer()
        lb = get_leaderboard_slash(ctx, leaderboard)
        verification = await get_verification_by_id(interaction.client.db_wrapper, interaction.guild.id, lb, id)
        if not verification:
            await ctx.send(f"Verification ID {id} not found")
            return
        if verification.approval_status != "pending":
            await ctx.send(f"Verification ID {id} is not pending")
            return
        await update_verification_approvals(interaction.client.db_wrapper, interaction.guild.id, lb, "ticket", [verification.id], reason)
        found_member = interaction.guild.get_member(verification.discord_id)
        if not found_member:
            await ctx.send("Could not find member in this server, so denial DM was not sent")
            return
        denial_msg = (f"Update to your verification request in {interaction.guild.name}: Please make a ticket to get verified. Reason: {reason}"
                      + f"\n{interaction.guild.name} への認証リクエストに関する連絡：認証を受けるにはチケットを作成してください。理由：{reason}")
        try:
            await found_member.send(denial_msg)
            await ctx.send("Successfully sent DM to member")
        except:
            await ctx.send("Member does not accept DMs from the bot, so DM was not sent")
        await ctx.send(f"Successfully set verification ID {id} status to ticket")

        # send denied verification to updating log
        verification_log = interaction.guild.get_channel(lb.verification_log_channel)
        if not verification_log:
            return
        assert isinstance(verification_log, discord.TextChannel)
        e = discord.Embed(title="Requested Ticket for Verification Request")
        e.add_field(name="ID", value=verification.id)
        e.add_field(name="Leaderboard", value=lb.name)
        e.add_field(name="Requested Name", value=verification.requested_name, inline=False)
        e.add_field(name="MKC ID", value=f"[{verification.mkc_id}]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={verification.mkc_id})")
        e.add_field(name="Mention", value=interaction.user.mention)
        e.add_field(name="Handled by", value=ctx.author.mention, inline=False)
        e.add_field(name="Reason", value=reason, inline=False)
        await verification_log.send(embed=e)

    async def send_verification_info(self, ctx: commands.Context[UpdatingBot], verification: VerificationRequest):
        e = discord.Embed(title="Verification Request")
        e.add_field(name="ID", value=verification.id)
        e.add_field(name="Leaderboard", value=verification.leaderboard)
        e.add_field(name="Requested Name", value=verification.requested_name, inline=False)
        e.add_field(name="Country", value=verification.country_code)
        e.add_field(name="MKC ID", value=f"[{verification.mkc_id}]({ctx.bot.config.mkc_credentials.url}/registry/players/profile?id={verification.mkc_id})")
        e.add_field(name="Mention", value=f"<@{verification.discord_id}>")
        e.add_field(name="Status", value=verification.approval_status, inline=False)
        if verification.reason:
            e.add_field(name="Reason", value=verification.reason)
        await ctx.send(embed=e)

    @verify_group.command(name="info")
    @app_commands.autocomplete(leaderboard=custom_checks.leaderboard_autocomplete)
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
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
    @app_commands.check(custom_checks.app_command_check_admin_verification_roles)
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
