import discord
from models.UpdatingBot import UpdatingBot
from models.Config import LeaderboardConfig
import API.get
from util.Players import fix_player_role
from util.Verification import get_existing_pending_verification, add_verification, get_user_latest_verification
from models.Verification import VerificationRequestData
from mkcentral import searchMKCPlayersByDiscordID

class VerifyForm(discord.ui.Modal, title="Lounge Verification"):
    def __init__(self, lb: LeaderboardConfig):
        super().__init__()
        self.lb = lb

    requested_name = discord.ui.TextInput(
        label="Nickname",
        required=True,
        min_length=2,
        max_length=16,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction[UpdatingBot]):
        assert isinstance(interaction.user, discord.Member)
        assert interaction.guild is not None
        name = self.requested_name.value.strip()
        await interaction.response.defer(ephemeral=True)

        # check if the user's discord account is already verified, fix their role if so
        discord_check = await API.get.getPlayerFromDiscord(self.lb.website_credentials, interaction.user.id)
        if discord_check:
            await interaction.followup.send("You are already verified in this server!", ephemeral=True)
            await fix_player_role(interaction.guild, self.lb, discord_check, interaction.user)
            return
        
        # check if their name is taken on the leaderboard
        name_check = await API.get.getPlayer(self.lb.website_credentials, name)
        if name_check:
            await interaction.followup.send("Another player has this name on the leaderboard! Please choose another", ephemeral=True)
            return
        
        # find their MKC account from their Discord ID
        mkc_check = await searchMKCPlayersByDiscordID(interaction.client.config.mkc_credentials, interaction.user.id)
        if mkc_check is None:
            await interaction.followup.send("An error occurred while searching MKCentral. Please try again later.", ephemeral=True)
            return
        if not mkc_check.player_count:
            await interaction.followup.send(f"Your Discord ID is not linked with an MKCentral account. Please make an account at {interaction.client.config.mkc_credentials.url}, link your Discord account to it and try again.",
                                            ephemeral=True)
            return
        
        # prevent banned players from verifying
        mkc_player = mkc_check.player_list[0]
        if mkc_player.is_banned:
            await interaction.followup.send("You are banned from MKCentral and cannot request to be verified. If you believe this to be a mistake, please create a ticket.",
                                            ephemeral=True)
            return
        
        # check if discord ID in lounge profile is different from discord ID in mkc profile
        mkc_id = mkc_check.player_list[0].id
        mkc_id_check = await API.get.getPlayerFromMKC(self.lb.website_credentials, mkc_id)
        if mkc_id_check:
            await interaction.followup.send("Your MKCentral account is linked to a Lounge profile, but your Lounge profile has a different Discord account linked to it. Please create a ticket for assistance.",
                                            ephemeral=True)
            return
        
        # check if player has already requested to be verified, or if another player requested to be verified with the same name
        request_data = VerificationRequestData(interaction.guild.id, self.lb.name, mkc_id, interaction.user.id, name, "pending")
        existing_request = await get_existing_pending_verification(interaction.client.db_wrapper, request_data)
        if existing_request:
            if existing_request.discord_id == interaction.user.id:
                await interaction.followup.send("You have already requested to be verified! Please wait for a staff member to view your request.", ephemeral=True)
            else:
                await interaction.followup.send("Another player has already requested to be verified with this name! Please choose another name.", ephemeral=True)
            return
        
        # add the player's verification request to the db
        verification_id = await add_verification(interaction.client.db_wrapper, request_data)
        if verification_id is None:
            await interaction.followup.send("An error occurred when sending your request. Try again later.")
            return
        await interaction.followup.send("Sent your data in for verification! It may take 24-48 hours to get verified, so please be patient.", ephemeral=True)

        # send new verification to updating log
        updating_log = interaction.guild.get_channel(self.lb.updating_log_channel)
        if not updating_log:
            return
        assert isinstance(updating_log, discord.TextChannel)
        e = discord.Embed(title="New Verification Request")
        e.add_field(name="ID", value=verification_id)
        e.add_field(name="Leaderboard", value=self.lb.name)
        e.add_field(name="Requested Name", value=request_data.requested_name, inline=False)
        e.add_field(name="MKC ID", value=f"[{request_data.mkc_id}]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={request_data.mkc_id})")
        e.add_field(name="Mention", value=interaction.user.mention)
        await updating_log.send(embed=e)

class VerifyView(discord.ui.View):
    @discord.ui.button(label="Verify", custom_id="verify_button", style=discord.ButtonStyle.green)
    async def verify_callback(self, interaction: discord.Interaction[UpdatingBot], button: discord.ui.Button):
        assert interaction.guild_id is not None
        server_config = interaction.client.config.servers.get(interaction.guild_id, None)
        if not server_config:
            await interaction.response.send_message("This server cannot be found in the bot config", ephemeral=True)
            return
        leaderboard = next(iter(server_config.leaderboards.values()))
        await interaction.response.send_modal(VerifyForm(leaderboard))

    @discord.ui.button(label="Check Status", custom_id="verify_status_button", style=discord.ButtonStyle.blurple)
    async def status_callback(self, interaction: discord.Interaction[UpdatingBot], button: discord.ui.Button):
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        server_config = interaction.client.config.servers.get(interaction.guild.id, None)
        if not server_config:
            await interaction.followup.send("This server cannot be found in the bot config", ephemeral=True)
            return
        leaderboard = next(iter(server_config.leaderboards.values()))
        verification = await get_user_latest_verification(interaction.client.db_wrapper, interaction.guild.id, leaderboard, interaction.user.id)
        if not verification:
            await interaction.followup.send("You do not have a pending verification; use the Verify button to request to be verified.", ephemeral=True)
            return
        # fix role if latest verification is approved
        if verification.approval_status == "approved":
            discord_check = await API.get.getPlayerFromDiscord(leaderboard.website_credentials, interaction.user.id)
            if discord_check:
                assert isinstance(interaction.user, discord.Member)
                await interaction.followup.send("You are already verified in this server!", ephemeral=True)
                await fix_player_role(interaction.guild, leaderboard, discord_check, interaction.user)
                return
            else:
                await interaction.followup.send("You have a previously approved verification, but your Discord account is not linked to a Lounge account. Please make a ticket for support.",
                                                ephemeral=True)
        elif verification.approval_status == "pending":
            await interaction.followup.send("Your verification is still pending; please wait for a staff member to approve it.", ephemeral=True)
        elif verification.approval_status == "denied":
            await interaction.followup.send(f"Your verification request has been denied; please make a ticket if you need more information. Reason: {verification.reason}",
                                            ephemeral=True)
        elif verification.approval_status == "ticket":
            await interaction.followup.send(f"Please make a ticket to get verified. Reason: {verification.reason}", ephemeral=True)