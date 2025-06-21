from database import DBWrapper
from models.Config import LeaderboardConfig
from models.Verification import VerificationRequestData, VerificationRequest, VerificationApproval

async def get_existing_pending_verification(db_wrapper: DBWrapper, request: VerificationRequestData):
    async with db_wrapper.connect() as db:
        async with db.execute("""SELECT id, guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status, reason, country_code
                                FROM verification_requests 
                                WHERE guild_id = ? AND leaderboard = ?
                                AND (requested_name = ? OR discord_id = ?) AND (approval_status=? OR approval_status=?)""", 
                                (request.guild_id, request.leaderboard,
                                 request.requested_name, request.discord_id, "pending", "ticket")) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            request_id, guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status, reason, country_code = row
            return VerificationRequest(guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status, country_code, request_id, reason)
        
async def get_user_latest_verification(db_wrapper: DBWrapper, guild_id: int, leaderboard: LeaderboardConfig, discord_id: int):
    async with db_wrapper.connect() as db:
        async with db.execute("""SELECT id, guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status, reason, country_code
                                FROM verification_requests 
                                WHERE guild_id = ? AND leaderboard = ?
                                AND discord_id = ?
                                ORDER BY id DESC""", (guild_id, leaderboard.name, discord_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            request_id, guild_id, leaderboard_name, mkc_id, discord_id, requested_name, approval_status, reason, country_code = row
            return VerificationRequest(guild_id, leaderboard_name, mkc_id, discord_id, requested_name, approval_status, country_code, request_id, reason)
            
async def add_verification(db_wrapper: DBWrapper, request: VerificationRequestData) -> int | None:
    async with db_wrapper.connect() as db:
        row = await db.execute_insert("""INSERT INTO verification_requests(
                                guild_id, leaderboard, mkc_id, discord_id,
                                requested_name, approval_status, country_code) VALUES(
                                ?, ?, ?, ?, ?, ?, ?)""", 
                                (request.guild_id, request.leaderboard,
                                request.mkc_id, request.discord_id,
                                request.requested_name, request.approval_status,
                                request.country_code))
        await db.commit()
        if row:
            return int(row[0])
        return None

async def get_verification_by_id(db_wrapper: DBWrapper, guild_id: int, leaderboard: LeaderboardConfig, id: int):
    async with db_wrapper.connect() as db:
        async with db.execute("""SELECT id, guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status, reason, country_code
                                FROM verification_requests
                                WHERE guild_id = ? AND leaderboard = ?
                                AND id = ?""", (guild_id, leaderboard.name, id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            request_id, guild_id, leaderboard_name, mkc_id, discord_id, requested_name, approval_status, reason, country_code = row
            return VerificationRequest(guild_id, leaderboard_name, mkc_id, discord_id, requested_name, approval_status, country_code, request_id, reason)

async def get_verifications(db_wrapper: DBWrapper, guild_id: int, leaderboard: LeaderboardConfig, approval_status: VerificationApproval, country_filter: str | None = None):
    verifications: list[VerificationRequest] = []
    country_stmt = ""
    if country_filter == "JP":
        country_stmt = "AND country_code = 'JP'"
    elif country_filter == "West":
        country_stmt = "AND country_code != 'JP'"
    async with db_wrapper.connect() as db:
        async with db.execute(f"""SELECT id, guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status, reason, country_code
                                FROM verification_requests
                                WHERE guild_id = ? AND leaderboard = ?
                                AND approval_status = ? {country_stmt}""", (guild_id, leaderboard.name, approval_status)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                request_id, guild_id, leaderboard_name, mkc_id, discord_id, requested_name, approval_status, reason, country_code = row
                verification = VerificationRequest(guild_id, leaderboard_name, mkc_id, discord_id, requested_name, approval_status, country_code, request_id, reason)
                verifications.append(verification)
    return verifications

async def update_verification_approvals(db_wrapper: DBWrapper, guild_id: int, leaderboard: LeaderboardConfig, approval_status: VerificationApproval, ids: list[int], reason: str | None = None):
    async with db_wrapper.connect() as db:
        variable_parameters = [(approval_status, reason, guild_id, leaderboard.name, id) for id in ids]
        await db.executemany("UPDATE verification_requests SET approval_status = ?, reason = ? WHERE guild_id = ? AND leaderboard = ? AND id = ?",
                                variable_parameters)
        await db.commit()