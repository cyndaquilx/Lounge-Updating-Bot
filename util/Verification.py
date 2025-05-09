from database import DBWrapper
from models.Config import LeaderboardConfig
from models.Verification import VerificationRequestData, VerificationRequest

async def get_pending_verification(db_wrapper: DBWrapper, request: VerificationRequestData):
    async with db_wrapper.connect() as db:
        async with db.execute("""SELECT id, guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status
                                FROM verification_requests 
                                WHERE guild_id = ? AND leaderboard = ?
                                AND (requested_name = ? OR discord_id = ?) AND approval_status='pending'""", 
                                (request.guild_id, request.leaderboard,
                                 request.requested_name, request.discord_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            request_id, guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status = row
            return VerificationRequest(guild_id, leaderboard, mkc_id, discord_id, requested_name, approval_status, request_id)
            
        
async def add_verification(db_wrapper: DBWrapper, request: VerificationRequestData):
    async with db_wrapper.connect() as db:
        await db.execute("""INSERT INTO verification_requests(
                                guild_id, leaderboard, mkc_id, discord_id,
                                requested_name, approval_status) VALUES(
                                ?, ?, ?, ?, ?, ?)""", 
                                (request.guild_id, request.leaderboard,
                                request.mkc_id, request.discord_id,
                                request.requested_name, request.approval_status))
        await db.commit()