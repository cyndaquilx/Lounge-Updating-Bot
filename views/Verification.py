import discord
from models.UpdatingBot import UpdatingBot
from models.Config import LeaderboardConfig
import API.get, API.post
from models.Verification import VerificationRequestData
from mkcentral import searchMKCPlayersByDiscordID, getMKCPlayerFromID
from views.Views import LeaderboardSelectView
from util import get_leaderboard_interaction, get_existing_pending_verification, add_verification, get_user_latest_verification, fix_player_role
from custom_checks import check_valid_name

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

        # find their MKC account from their Discord ID
        mkc_check = await searchMKCPlayersByDiscordID(interaction.client.config.mkc_credentials, interaction.user.id)
        if mkc_check is None:
            await interaction.followup.send("An error occurred while searching MKCentral. Please try again later.\nMKCentralの検索中にエラーが発生しました。後でもう一度お試しください。",
                                            ephemeral=True)
            return
        if not mkc_check.player_count:
            await interaction.followup.send(f"Your Discord ID is not linked with an MKCentral account. Please make an account at {interaction.client.config.mkc_credentials.url}, link your Discord account to it and try again."
                                            + f"\nあなたのDiscord IDはMKCentralアカウントに登録されていません。{interaction.client.config.mkc_credentials.url} にてアカウントを作成し、Discordアカウントを登録してから再度お試しください。",
                                            ephemeral=True)
            return
        
        # prevent banned players from verifying
        mkc_player = mkc_check.player_list[0]
        if mkc_player.is_banned:
            await interaction.followup.send("You are banned from MKCentral and cannot request to be verified. If you believe this to be a mistake, please create a ticket." +
                                            "\nあなたはMKCentralからBANされているため、認証をリクエストすることができません。これが誤りだと思われる場合は、チケットを作成してください。",
                                            ephemeral=True)
            return
        
        # check if the user's discord account is already verified.
        # if they are verified and have this leaderboard in their registrations list,
        # fix their role.
        # else, register them in this server and give them placement role
        discord_check = await API.get.getPlayerAllGamesFromDiscord(self.lb.website_credentials, interaction.user.id)
        if discord_check:
            if discord_check.is_hidden:
                await interaction.followup.send(f"Your Lounge profile is hidden. Please make a ticket if you believe this is an error.", ephemeral=True)
                return
            if mkc_player.id != discord_check.mkc_id:
                await interaction.followup.send("Your Discord account is linked to a different MKC profile than what is linked to your Lounge profile. Please create a ticket.", ephemeral=True)
                return
            if self.lb.website_credentials.game in discord_check.registrations:
                player = await API.get.getPlayerFromLounge(self.lb.website_credentials, discord_check.id)
                await interaction.followup.send("You are already verified in this server!\nあなたは既にこのサーバーで認証されています！", ephemeral=True)
                await fix_player_role(interaction.guild, self.lb, player, interaction.user)
                return
            else:
                player, error = await API.post.registerPlayer(self.lb.website_credentials, discord_check.name, None)
                if not player:
                    await interaction.followup.send(f"An error occurred when verifying you in {interaction.guild.name}: {error}. Please try again later or contact a staff member",
                                                    ephemeral=True)
                    return
                await interaction.followup.send(f"You have been successfully verified in {interaction.guild.name}!", ephemeral=True)
                await fix_player_role(interaction.guild, self.lb, player, interaction.user)
                return
            
        # check if discord ID in lounge profile is different from discord ID in mkc profile
        mkc_id = mkc_check.player_list[0].id
        mkc_id_check = await API.get.getPlayerAllGamesFromMKC(self.lb.website_credentials, mkc_id)
        if mkc_id_check:
            await interaction.followup.send("Your MKCentral account is linked to a Lounge profile, but your Lounge profile has a different Discord account linked to it. Please create a ticket for assistance."
                                            + "\nあなたのMKCentralアカウントは既にLoungeに登録されていますが、このアカウントとは異なるDiscord Idが登録されています。サポートチケットを作成してください。",
                                            ephemeral=True)
            return
        
        # check if their name is taken on the leaderboard
        name_check = await API.get.getPlayerAllGames(self.lb.website_credentials, name)
        if name_check:
            await interaction.followup.send("Another player has this name on the leaderboard! Please choose another.\nこの名前はすでに別のプレイヤーが使用しています！別の名前を入力してください。", 
                                            ephemeral=True)
            return
        
        valid_fcs = list(filter(lambda f: f.type == "switch", mkc_player.friend_codes))
        if not len(valid_fcs):
            await interaction.followup.send("You must have at least 1 Switch FC to be verified!", ephemeral=True)
            return

        is_valid, error = check_valid_name(self.lb, name)
        if not is_valid:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        
        # check if player has already requested to be verified, or if another player requested to be verified with the same name
        request_data = VerificationRequestData(interaction.guild.id, self.lb.name, mkc_id, interaction.user.id, name, "pending", mkc_player.country_code)
        existing_request = await get_existing_pending_verification(interaction.client.db_wrapper, request_data)
        if existing_request:
            if existing_request.discord_id == interaction.user.id:
                await interaction.followup.send("You have already requested to be verified! Please wait for a staff member to view your request." +
                                                "\nあなたは既に認証をリクエストを完了しています。スタッフが確認するまでお待ちください。", ephemeral=True)
            else:
                await interaction.followup.send("Another player has already requested to be verified with this name! Please choose another name." +
                                                "\n既に別のプレイヤーがこの名前で認証リクエストをしています！別の名前を入力してください。", ephemeral=True)
            return
        
        # add the player's verification request to the db
        verification_id = await add_verification(interaction.client.db_wrapper, request_data)
        if verification_id is None:
            await interaction.followup.send("An error occurred when sending your request. Try again later.\n認証リクエストの送信中にエラーが発生しました。後でもう一度お試しください。")
            return
        await interaction.followup.send("Sent your data in for verification! It may take 24-48 hours to get verified, so please be patient." +
                                        "\n認証用データを送信しました！認証には24〜48時間かかる場合がありますので、しばらくお待ちください。", ephemeral=True)

        # send new verification to updating log
        verification_log = interaction.guild.get_channel(self.lb.verification_log_channel)
        if not verification_log:
            return
        assert isinstance(verification_log, discord.TextChannel)
        e = discord.Embed(title="New Verification Request")
        e.add_field(name="ID", value=verification_id)
        e.add_field(name="Leaderboard", value=self.lb.name)
        e.add_field(name="Requested Name", value=request_data.requested_name, inline=False)
        e.add_field(name="Country", value=mkc_player.country_code)
        e.add_field(name="MKC ID", value=f"[{request_data.mkc_id}]({interaction.client.config.mkc_credentials.url}/registry/players/profile?id={request_data.mkc_id})")
        e.add_field(name="Mention", value=interaction.user.mention)
        e.add_field(name="Friend Codes", value="\n".join([f.fc for f in valid_fcs]), inline=False)
        await verification_log.send(embed=e)

class VerifyView(discord.ui.View):
    async def leaderboard_callback(self, interaction: discord.Interaction[UpdatingBot], leaderboard: str | None):
        lb = get_leaderboard_interaction(interaction, leaderboard)
        await interaction.response.send_modal(VerifyForm(lb))
    
    @discord.ui.button(label="Verify", custom_id="verify_button", style=discord.ButtonStyle.green)
    async def verify_callback(self, interaction: discord.Interaction[UpdatingBot], button: discord.ui.Button):
        assert interaction.guild is not None
        server_config = interaction.client.config.servers.get(interaction.guild.id, None)
        if not server_config:
            await interaction.response.send_message("This server cannot be found in the bot config", ephemeral=True)
            return
        leaderboards = server_config.leaderboards
        if len(leaderboards) > 1:
            await interaction.response.send_message(
                view=LeaderboardSelectView(
                    leaderboards,
                    self.leaderboard_callback
                ),
                ephemeral=True,
                delete_after=30
            )
        else:
            leaderboard_name = next(iter(server_config.leaderboards.keys()))
            await self.leaderboard_callback(interaction, leaderboard_name)

    async def transfer_leaderboard_callback(self, interaction: discord.Interaction[UpdatingBot], leaderboard: str | None):
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)
        lb = get_leaderboard_interaction(interaction, leaderboard)
        # find their MKC account from their Discord ID
        mkc_check = await searchMKCPlayersByDiscordID(interaction.client.config.mkc_credentials, interaction.user.id)
        if mkc_check is None:
            await interaction.followup.send("An error occurred while searching MKCentral. Please try again later.\nMKCentralの検索中にエラーが発生しました。後でもう一度お試しください。",
                                            ephemeral=True)
            return
        if not mkc_check.player_count:
            await interaction.followup.send(f"Your Discord ID is not linked with an MKCentral account. Please make an account at {interaction.client.config.mkc_credentials.url}, link your Discord account to it and try again."
                                            + f"\nあなたのDiscord IDはMKCentralアカウントに登録されていません。{interaction.client.config.mkc_credentials.url} にてアカウントを作成し、Discordアカウントを登録してから再度お試しください。",
                                            ephemeral=True)
            return
        
        # prevent banned players from verifying
        mkc_player = mkc_check.player_list[0]
        if mkc_player.is_banned:
            await interaction.followup.send("You are banned from MKCentral and cannot request to be verified. If you believe this to be a mistake, please create a ticket." +
                                            "\nあなたはMKCentralからBANされているため、認証をリクエストすることができません。これが誤りだと思われる場合は、チケットを作成してください。",
                                            ephemeral=True)
            return
        
        # check if the user's discord account is already verified.
        # if they are verified and have this leaderboard in their registrations list,
        # fix their role.
        # else, register them in this server and give them placement role
        discord_check = await API.get.getPlayerAllGamesFromDiscord(lb.website_credentials, interaction.user.id)
        if discord_check is None:
            await interaction.followup.send("Your Discord account is not currently linked to a Lounge profile. Use the Verify button instead.", ephemeral=True)
            return
        
        if discord_check.is_hidden:
            await interaction.followup.send(f"Your Lounge profile is hidden. Please make a ticket if you believe this is an error.", ephemeral=True)
            return
        
        if discord_check.mkc_id != mkc_player.id:
            await interaction.followup.send("Your Discord account is linked to a different MKC profile than what is linked to your Lounge profile. Please create a ticket.", ephemeral=True)
            return
        
        if lb.website_credentials.game in discord_check.registrations:
            player = await API.get.getPlayerFromLounge(lb.website_credentials, discord_check.id)
            await interaction.followup.send("You are already verified in this server!\nあなたは既にこのサーバーで認証されています！", ephemeral=True)
            await fix_player_role(interaction.guild, lb, player, interaction.user)
        else:
            player, error = await API.post.registerPlayer(lb.website_credentials, discord_check.name, None)
            if not player:
                await interaction.followup.send(f"An error occurred when verifying you in {interaction.guild.name}: {error}. Please try again later or contact a staff member",
                                                ephemeral=True)
                return
            await interaction.followup.send(f"You have been successfully verified in {interaction.guild.name}!", ephemeral=True)
            await fix_player_role(interaction.guild, lb, player, interaction.user)

    @discord.ui.button(label="Transfer", custom_id="transfer_button", style=discord.ButtonStyle.primary)
    async def transfer_callback(self, interaction: discord.Interaction[UpdatingBot], button: discord.ui.Button):
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        server_config = interaction.client.config.servers.get(interaction.guild.id, None)
        if not server_config:
            await interaction.response.send_message("This server cannot be found in the bot config", ephemeral=True)
            return
        leaderboards = server_config.leaderboards
        if len(leaderboards) > 1:
            await interaction.response.send_message(
                view=LeaderboardSelectView(
                    leaderboards,
                    self.transfer_leaderboard_callback
                ),
                ephemeral=True,
                delete_after=30
            )
        else:
            leaderboard_name = next(iter(server_config.leaderboards.keys()))
            await self.transfer_leaderboard_callback(interaction, leaderboard_name)

    async def status_leaderboard_callback(self, interaction: discord.Interaction[UpdatingBot], leaderboard: str | None):
        assert interaction.guild is not None
        lb = get_leaderboard_interaction(interaction, leaderboard)
        verification = await get_user_latest_verification(interaction.client.db_wrapper, interaction.guild.id, lb, interaction.user.id)
        if not verification:
            await interaction.followup.send("You do not have a pending verification; use the Verify button to request to be verified." +
                                            "\n保留中の認証リクエストはありません。「認証」ボタンを使ってリクエストしてください。", ephemeral=True)
            return
        # fix role if latest verification is approved
        if verification.approval_status == "approved":
            discord_check = await API.get.getPlayerFromDiscord(lb.website_credentials, interaction.user.id)
            if discord_check:
                assert isinstance(interaction.user, discord.Member)
                await interaction.followup.send("You are already verified in this server!\nあなたは既にこのサーバーで認証されています！", ephemeral=True)
                await fix_player_role(interaction.guild, lb, discord_check, interaction.user)
                return
            else:
                await interaction.followup.send("You have a previously approved verification, but your Discord account is not linked to a Lounge account. Please make a ticket for support."
                                                + "\n既に認証済みですが、このDiscord アカウントは過去認証に使用されたDiscordアカウントと異なります。サポートチケットを作成して下さい。",
                                                ephemeral=True)
        elif verification.approval_status == "pending":
            await interaction.followup.send("Your verification is still pending; please wait for a staff member to approve it." +
                                            "\nあなたの認証はまだ保留中です。スタッフの承認をお待ちください。", ephemeral=True)
        elif verification.approval_status == "denied":
            await interaction.followup.send(f"Your verification request has been denied; please make a ticket if you need more information. Reason: {verification.reason}"
                                            + f"\nあなたの認証リクエストは拒否されました。詳細が必要な場合はチケットを作成してください。理由： {verification.reason}",
                                            ephemeral=True)
        elif verification.approval_status == "ticket":
            await interaction.followup.send(f"Please make a ticket to get verified. Reason: {verification.reason}" +
                                            f"\n認証を受けるにはチケットを作成してください。理由： {verification.reason}", ephemeral=True)
        
    @discord.ui.button(label="Check Status", custom_id="verify_status_button", style=discord.ButtonStyle.secondary)
    async def status_callback(self, interaction: discord.Interaction[UpdatingBot], button: discord.ui.Button):
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        server_config = interaction.client.config.servers.get(interaction.guild.id, None)
        if not server_config:
            await interaction.followup.send("This server cannot be found in the bot config", ephemeral=True)
            return
        leaderboards = server_config.leaderboards
        if len(leaderboards) > 1:
            await interaction.response.send_message(
                view=LeaderboardSelectView(
                    leaderboards,
                    self.status_leaderboard_callback
                ),
                ephemeral=True,
                delete_after=30
            )
        else:
            leaderboard_name = next(iter(server_config.leaderboards.keys()))
            await self.status_leaderboard_callback(interaction, leaderboard_name)