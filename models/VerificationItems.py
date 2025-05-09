import discord
from models.UpdatingBot import UpdatingBot
from models.Config import LeaderboardConfig
import API.get
from util.Players import fix_player_role
from util.Verification import get_pending_verification, add_verification
from models.Verification import VerificationRequestData

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
        discord_check = await API.get.getPlayerFromDiscord(self.lb.website_credentials, interaction.user.id)
        if discord_check:
            await interaction.followup.send("You are already verified in this server!")
            await fix_player_role(interaction.guild, self.lb, discord_check, interaction.user)
            return
        name_check = await API.get.getPlayer(self.lb.website_credentials, name)
        if name_check:
            await interaction.followup.send("Another player has this name on the leaderboard! Please choose another", ephemeral=True)
            return
        request_data = VerificationRequestData(interaction.guild.id, self.lb.name, 0, interaction.user.id, name, "pending")
        existing_request = await get_pending_verification(interaction.client.db_wrapper, request_data)
        if existing_request:
            if existing_request.discord_id == interaction.user.id:
                await interaction.followup.send("You have already requested to be verified! Please wait for a staff member to view your request.", ephemeral=True)
            else:
                await interaction.followup.send("Another player has already requested to be verified with this name! Please choose another name.", ephemeral=True)
            return
        await add_verification(interaction.client.db_wrapper, request_data)
        await interaction.followup.send("Sent your data in for verification! It may take 24-48 hours to get verified, so please be patient.", ephemeral=True)


class VerifyView(discord.ui.View):
    @discord.ui.button(label="Verify", custom_id="verify_button", style=discord.ButtonStyle.green)
    async def verify_callback(self, interaction: discord.Interaction[UpdatingBot], button: discord.ui.Button):
        assert interaction.guild_id is not None
        server_config = interaction.client.config.servers.get(interaction.guild_id, None)
        if not server_config:
            await interaction.response.send_message("This server cannot be found in the bot config")
            return
        leaderboard = next(iter(server_config.leaderboards.values()))
        await interaction.response.send_modal(VerifyForm(leaderboard))