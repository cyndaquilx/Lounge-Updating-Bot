from dataclasses import dataclass

@dataclass
class WebsiteCredentials:
    url: str
    username: str
    password: str
    game: str | None

@dataclass
class MKCentralCredentials:
    url: str
    api_token: str | None

@dataclass
class LeaderboardRank:
    name: str
    emoji: str
    role_id: int
    color: str
    url: str
    mmr: int

@dataclass
class PlayerCountSettings:
    points_per_race: int
    valid_formats: list[int]

@dataclass
class LeaderboardConfig:
    name: str
    website_credentials: WebsiteCredentials
    placement_role_id: int
    player_role_id: int
    name_change_log_channel: int
    name_request_log_channel: int
    name_request_channel: int
    updating_log_channel: int
    verification_log_channel: int
    mute_ban_list_channel: int
    quick_start_channel: int
    player_settings: dict[int, PlayerCountSettings]
    races_per_mogi: int
    gps_per_mogi: int
    enable_verification_dms: bool
    enable_bulk_placement_endpoint: bool
    allow_numbered_names: bool
    ranks: list[LeaderboardRank]
    tier_results_channels: dict[str, int]
    penalty_channel: int
    place_rank_mmrs: dict[str, int]
    place_scores: dict[int, int]

    def get_rank(self, mmr:int):
        # get all the ranks where our MMR is higher than the minimum MMR
        valid_ranks = [r for r in self.ranks if r.mmr <= mmr]
        # get the highest mmr of those ranks
        rank = max(valid_ranks, key=lambda r: r.mmr)
        return rank
    
    def get_place_mmr(self, score: int):
        # get all the scores that we scored higher or equal to
        valid_scores = [p for p in self.place_scores.keys() if p <= score]
        # get the highest score of those scores
        highest_score = max(valid_scores)
        # find the placement MMR of that score
        place_mmr = self.place_scores[highest_score]
        return place_mmr

@dataclass
class ServerConfig:
    prefixes: dict[str, str]
    reporter_roles: list[int]
    updater_roles: list[int]
    staff_roles: list[int]
    admin_roles: list[int]
    mkc_roles: list[int]
    verification_roles: list[int]
    chat_restricted_roles: list[int]
    name_restricted_roles: list[int]
    tier_channel_categories: list[int]
    ticket_categories: list[int]
    leaderboards: dict[str, LeaderboardConfig]
    reaction_log_channel: int | None

@dataclass
class BotConfig:
    token: str
    application_id: int
    db_directory: str
    db_filename: str
    mkc_credentials: MKCentralCredentials
    servers: dict[int, ServerConfig]
    
    def get_prefixes(self):
        prefixes = []
        for server in self.servers.values():
            for prefix in server.prefixes:
                if prefix == "":
                    prefixes.append("!")
                else:
                    prefixes.append(f"!{prefix} ")
        prefixes = list(set(prefixes))
        prefixes.sort(key=len, reverse=True) # sort in descending order of length to ensure all can be used
        return prefixes