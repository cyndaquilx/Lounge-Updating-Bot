from util.Exceptions import LeaderboardNotFoundException, GuildNotFoundException
from models import ServerConfig, LeaderboardConfig, UpdatingBot
from discord.ext import commands

def get_server_config(ctx: commands.Context[UpdatingBot]) -> ServerConfig:
    assert ctx.guild is not None
    server_info: ServerConfig | None = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        raise GuildNotFoundException
    return server_info

def get_leaderboard(ctx: commands.Context) -> LeaderboardConfig:
    assert ctx.prefix is not None
    server_info = get_server_config(ctx)
    prefix = ctx.prefix.strip().replace('!', '')
    leaderboard_str = server_info.prefixes.get(prefix, None)
    if not leaderboard_str:
        raise LeaderboardNotFoundException
    leaderboard = server_info.leaderboards.get(leaderboard_str, None)
    if not leaderboard:
        raise LeaderboardNotFoundException
    return leaderboard

def get_leaderboard_slash(ctx: commands.Context, lb: str | None) -> LeaderboardConfig:
    server_info = get_server_config(ctx)
    # if we don't provide a leaderboard argument and there's only 1 leaderboard in the server
    # we should just return that leaderboard
    leaderboard = None
    if lb is None and len(server_info.leaderboards) == 1:
        leaderboard = next(iter(server_info.leaderboards.values()))
    elif lb:
        leaderboard = server_info.leaderboards.get(lb, None)
    if not leaderboard:
        raise LeaderboardNotFoundException
    return leaderboard