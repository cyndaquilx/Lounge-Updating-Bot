from dataclasses import dataclass

@dataclass
class VerificationRequestData:
    guild_id: int
    leaderboard: str
    mkc_id: int
    discord_id: int
    requested_name: str
    approval_status: str

@dataclass
class VerificationRequest(VerificationRequestData):
    id: int