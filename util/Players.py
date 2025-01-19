import discord
from discord.ext import commands
from models import LeaderboardConfig, Player, PlayerBasic
import API.get, API.post

async def give_placement_role(ctx: commands.Context, lb: LeaderboardConfig, player: Player, placeMMR: int):
    new_role_id = lb.get_rank(placeMMR).role_id
    new_role = ctx.guild.get_role(new_role_id)
    if not player.discord_id:
        await ctx.send("Player does not have a discord ID on the site, please give them one to give them placement roles")
        return False
    member = ctx.guild.get_member(int(player.discord_id))
    if member is None:
        await ctx.send(f"Couldn't find member {player.name}, please give them roles manually")
        return False
    for role in member.roles:
        for rank in lb.ranks:
            if role.id == rank.role_id:
                await member.remove_roles(role)
        if role.id == lb.placement_role_id:
            await member.remove_roles(role)
    if new_role not in member.roles:
        await member.add_roles(new_role)
    await ctx.send(f"Managed to find member {member.display_name} and edit their roles")
    return True

async def place_player_with_mmr(ctx: commands.Context, lb: LeaderboardConfig, mmr: int, name: str, force=False):
    player, error = await API.post.placePlayer(lb.website_credentials, mmr, name, force=force)
    if player is None:
        await ctx.send(f"An error occurred while trying to place {name}: {error}")
        return False
    await ctx.send(f"Successfully placed {player.name} with {mmr} MMR")
    success = await give_placement_role(ctx, lb, player, mmr)
    if not success:
        return
    if force:
        e = discord.Embed(title="Player force placed")
        e.add_field(name="Player", value=player.name, inline=False)
        e.add_field(name="MMR", value=mmr)
        if player.discord_id:
            e.add_field(name="Mention", value=f"<@{player.discord_id}>")
        e.add_field(name="Placed by", value=ctx.author.mention, inline=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if updating_log:
            await updating_log.send(embed=e)
    return True

async def update_roles(ctx: commands.Context, lb: LeaderboardConfig, player: PlayerBasic, oldMMR:int, newMMR:int):
    old_rank = lb.get_rank(oldMMR)
    new_rank = lb.get_rank(newMMR)
    rank_changes = ""
    if old_rank != new_rank:
        discord_id = int(player.discord_id) if player.discord_id else None
        member = ctx.guild.get_member(discord_id)
        if member is not None:
            memName = member.mention
        else:
            memName = player.name
        rank_changes += f"{memName} -> {new_rank.emoji}\n"
        old_role = ctx.guild.get_role(old_rank.role_id)
        new_role = ctx.guild.get_role(new_rank.role_id)
        if member:
            if old_role and old_role in member.roles:
                await member.remove_roles(old_role)
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role)
    return rank_changes

async def fix_player_role(ctx: commands.Context, lb: LeaderboardConfig, player: Player | None, member: discord.Member):
    player_roles: list[discord.Role] = []
    placement_role = ctx.guild.get_role(lb.placement_role_id)
    player_role = ctx.guild.get_role(lb.player_role_id)

    # get all the player's rank/player roles
    for role in member.roles:
        for rank in lb.ranks:
            if role.id == rank.role_id:
                player_roles.append(role)
        if role.id == placement_role.id:
            player_roles.append(role)
        if role.id == player_role.id:
            player_roles.append(role)

    # if the player doesn't exist, just remove all of these roles
    if player is None:
        try:
            await member.remove_roles(*player_roles)
        except Exception as e:
            print(e)
        return
    
    # if player hasn't been placed yet their current rank role
    # is placement role, otherwise just get their rank role
    if player.mmr is None:
        rank_role = placement_role
    else:
        rank = lb.get_rank(player.mmr)
        rank_role = ctx.guild.get_role(rank.role_id)
    
    # if we have a rank role that we shouldn't, remove it
    to_remove: list[discord.Role] = []
    for role in player_roles:
        if role.id == player_role.id:
            continue
        if role.id != rank_role.id:
            to_remove.append(role)
            
    if len(to_remove) > 0:
        try:
            await member.remove_roles(*to_remove)
        except Exception as e:
            print(e)

    # if we don't have the player role or the role
    # of our current rank, add them
    to_add: list[discord.Role] = []
    if rank_role not in player_roles:
        to_add.append(rank_role)
    if player_role not in player_roles:
        to_add.append(player_role)
    
    if len(to_add) > 0:
        try:
            await member.add_roles(*to_add)
        except Exception as e:
            print(e)

    # fix nickname, if applicable (will fail on admins so use try/except)
    if member.display_name != player.name:
        try:
            await member.edit(nick=player.name)
        except:
            pass