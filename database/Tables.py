verification_requests = """CREATE TABLE IF NOT EXISTS verification_requests(
    id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    leaderboard TEXT NOT NULL,
    mkc_id INTEGER NOT NULL,
    discord_id INTEGER NOT NULL,
    requested_name TEXT NOT NULL,
    approval_status TEXT NOT NULL,
    reason TEXT,
    country_code TEXT
)"""

all_tables = [verification_requests]