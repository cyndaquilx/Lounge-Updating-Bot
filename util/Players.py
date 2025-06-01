import discord
from discord.ext import commands
from models import LeaderboardConfig, Player, PlayerBasic, UpdatingBot, ListPlayer
from custom_checks import check_valid_name, yes_no_check
import API.get, API.post

async def add_player(ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, mkcID: int, member: discord.Member | int, name: str, mmr: int | None, confirm=True) -> bool:
    assert ctx.guild is not None

    # if 0 is passed in, set member_id to None (used in text commands if we don't want to add a discord for the player)
    if isinstance(member, int):
        if member == 0:
            member_id = None
            found_member = None
        else:
            found_member = ctx.guild.get_member(member)
            if not found_member:
                await ctx.send(f"Member with ID {member} not found")
                return False
            member_id = found_member.id
    else:
        member_id = member.id
        found_member = member
    name = name.strip()
    is_valid, error = check_valid_name(lb, name)
    if not is_valid:
        await ctx.send(str(error))
        return False
    
    embedded = None
    if confirm:
        content = "Please confirm the player details within 30 seconds"
        e = discord.Embed(title="New Player")
        e.add_field(name="Name", value=name)
        e.add_field(name="MKC ID", value=mkcID)
        if mmr is not None:
            e.add_field(name="Placement MMR", value=mmr)
        if found_member:
            e.add_field(name="Discord", value=found_member.mention)
        embedded = await ctx.send(content=content, embed=e)
        if not await yes_no_check(ctx, embedded):
            return False

    if mmr is not None:
        player, error = await API.post.createPlayerWithMMR(lb.website_credentials, mkcID, mmr, name, member_id)
    else:
        player, error = await API.post.createNewPlayer(lb.website_credentials, mkcID, name, member_id)
    if player is None:
        await ctx.send(f"An error occurred while trying to verify player {name}: {error}")
        return False
    
    roleGiven = ""
    if found_member:
        roles: list[discord.Role] = []
        player_role = ctx.guild.get_role(lb.player_role_id)
        if player_role:
            roles.append(player_role)
        if mmr is not None:
            rank = lb.get_rank(mmr)
            rank_role = ctx.guild.get_role(rank.role_id)
            if rank_role:
                roles.append(rank_role)
        else:
            placement_role = ctx.guild.get_role(lb.placement_role_id)
            if placement_role:
                roles.append(placement_role)
        role_names = ", ".join([role.name for role in roles])
        try:
            await found_member.add_roles(*roles)
            if found_member.display_name != name:
                await found_member.edit(nick=name)
            roleGiven += f"\nAlso gave {found_member.mention} {role_names} role"
        except Exception as e:
            roleGiven += f"\nCould not give {role_names} roles to the player due to the following: {e}"
            pass

        if lb.enable_verification_dms:
            quick_start_channel = ctx.guild.get_channel(lb.quick_start_channel)
            if quick_start_channel:
                verification_msg = f"Your account has been successfully verified in {ctx.guild.name}! For information on how to join matches, " + \
                    f"check the {quick_start_channel.mention} channel." + \
                    f"\n{ctx.guild.name}への登録が完了しました！ 模擬への参加方法は{quick_start_channel.mention} をご覧下さい。"
                try:
                    await found_member.send(verification_msg)
                    roleGiven += f"\nSuccessfully sent verification DM to the player"
                except Exception as e:
                    roleGiven += f"\nPlayer does not accept DMs from the bot, so verification DM was not sent"

    if embedded:
        await embedded.delete()
    url = f"{lb.website_credentials.url}/PlayerDetails/{player.id}"
    await ctx.send(f"Successfully added the new player: {url}{roleGiven}")
    e = discord.Embed(title="Added new player")
    e.add_field(name="Name", value=name)
    e.add_field(name="MKC ID", value=mkcID)
    if found_member:
        e.add_field(name="Discord", value=found_member.mention)
    if mmr is not None:
        e.add_field(name="MMR", value=mmr)
    e.add_field(name="Added by", value=ctx.author.mention, inline=False)
    verification_log = ctx.guild.get_channel(lb.verification_log_channel)
    if verification_log is not None:
        assert isinstance(verification_log, discord.TextChannel)
        await verification_log.send(embed=e)
    return True

async def give_placement_role(ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, player: Player, placeMMR: int):
    assert ctx.guild is not None
    rank = lb.get_rank(placeMMR)
    new_role = ctx.guild.get_role(rank.role_id)
    if not new_role:
        await ctx.send(f"Rank role {rank.name} with ID {rank.role_id} was not found in this server")
        return False
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

async def place_player_with_mmr(ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, mmr: int, name: str, force=False):
    assert ctx.guild is not None
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
            assert isinstance(updating_log, discord.TextChannel)
            await updating_log.send(embed=e)
    return True

async def update_roles(ctx: commands.Context[UpdatingBot], lb: LeaderboardConfig, player: PlayerBasic, oldMMR: int, newMMR: int) -> str:
    assert ctx.guild is not None
    old_rank = lb.get_rank(oldMMR)
    new_rank = lb.get_rank(newMMR)
    rank_changes = ""
    if old_rank != new_rank:
        discord_id = int(player.discord_id) if player.discord_id else None
        if discord_id:
            member = ctx.guild.get_member(discord_id)
        else:
            member = None
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

async def fix_player_role(guild: discord.Guild, lb: LeaderboardConfig, player: Player | ListPlayer | None, member: discord.Member):
    player_roles: list[discord.Role] = []
    placement_role = guild.get_role(lb.placement_role_id)
    player_role = guild.get_role(lb.player_role_id)
    assert placement_role is not None
    assert player_role is not None

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
        rank_role = guild.get_role(rank.role_id)
        assert rank_role is not None
    
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