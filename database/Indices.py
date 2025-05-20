verifications_guild_id_leaderboard = """CREATE INDEX IF NOT EXISTS verifications_guild_id_leaderboard
    ON verification_requests(guild_id, leaderboard)"""

all_indices = [verifications_guild_id_leaderboard]