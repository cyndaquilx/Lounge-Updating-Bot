from dataclasses import dataclass

@dataclass
class MKCDiscord:
    discord_id: str
    username: str
    discriminator: str
    global_name: str | None
    avatar: str | None

@dataclass
class MKCFriendCode:
    id: int
    fc: str
    type: str
    player_id: int
    is_verified: bool
    is_primary: bool
    creation_date: int
    description: str | None = None
    is_active: bool = True

@dataclass
class MKCPlayer:
    id: int
    name: str
    country_code: str
    is_hidden: bool
    is_shadow: bool
    is_banned: bool
    join_date: int
    discord: MKCDiscord | None
    friend_codes: list[MKCFriendCode]

@dataclass
class MKCPlayerList:
    player_list: list[MKCPlayer]
    player_count: int
    page_count: int