from dataclasses import dataclass
from typing import Literal

VerificationApproval = Literal["approved", "pending", "denied", "ticket"]

@dataclass
class VerificationRequestData:
    guild_id: int
    leaderboard: str
    mkc_id: int
    discord_id: int
    requested_name: str
    approval_status: VerificationApproval
    country_code: str | None

@dataclass
class VerificationRequest(VerificationRequestData):
    id: int
    reason: str | None