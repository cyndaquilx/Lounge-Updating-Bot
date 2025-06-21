import discord
from discord.ext import commands
from models import ServerConfig, LeaderboardConfig, UpdatingBot
from util.Exceptions import GuildNotFoundException
from util.Leaderboards import get_server_config, get_server_config_from_interaction
from discord import app_commands
from typing import List

# check if user has any roles in the list of IDs
def check_role_list(member, check_roles):
    for role in check_roles:
        if member.get_role(role) is not None:
            return True
    return False

def command_check_roles(ctx: commands.Context[UpdatingBot], check_roles: list[int]):
    if ctx.guild is None:
        raise GuildNotFoundException
    if check_role_list(ctx.author, check_roles):
        return True
    error_roles = [role.name for role_id in check_roles if (role := ctx.guild.get_role(role_id)) is not None]
    raise commands.MissingAnyRole(error_roles) #type: ignore

def app_command_check_roles(interaction: discord.Interaction[UpdatingBot], check_roles: list[int]):
    if interaction.guild is None:
        raise GuildNotFoundException
    if check_role_list(interaction.user, check_roles):
        return True
    error_roles: List[str] = [role.name for role_id in check_roles if (role := interaction.guild.get_role(role_id)) is not None]
    raise app_commands.MissingAnyRole(error_roles) #type: ignore

# check if user has reporter or staff roles
def check_reporter_roles(ctx: commands.Context[UpdatingBot]):
    if ctx.guild is None:
        return False
    server_info: ServerConfig | None = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.reporter_roles + server_info.updater_roles + server_info.staff_roles + server_info.admin_roles)
    return check_role_list(ctx.author, check_roles)

# check if user has updater or staff roles
def check_updater_roles(ctx: commands.Context[UpdatingBot]):
    if ctx.guild is None:
        return False
    server_info: ServerConfig | None = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.updater_roles + server_info.staff_roles + server_info.admin_roles)
    return check_role_list(ctx.author, check_roles)
    
# check if user has staff roles
def check_staff_roles(ctx: commands.Context[UpdatingBot]):
    if ctx.guild is None:
        return False
    server_info: ServerConfig | None = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.staff_roles + server_info.admin_roles)
    return check_role_list(ctx.author, check_roles)

# lounge staff + mkc + admin
def check_all_staff_roles(ctx: commands.Context[UpdatingBot]):
    if ctx.guild is None:
        return False
    server_info: ServerConfig | None = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.mkc_roles + server_info.staff_roles + server_info.admin_roles)
    return check_role_list(ctx.author, check_roles)

# check if user is chat restricted
def check_chat_restricted_roles(bot: UpdatingBot, member: discord.Member):
    server_info: ServerConfig | None = bot.config.servers.get(member.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.chat_restricted_roles)
    return check_role_list(member, check_roles)

# check if user is name restricted
def check_name_restricted_roles(ctx: commands.Context[UpdatingBot], member: discord.Member):
    server_info: ServerConfig | None = ctx.bot.config.servers.get(member.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.name_restricted_roles)
    return check_role_list(member, check_roles)

def app_command_check_name_restricted_roles(interaction: discord.Interaction[UpdatingBot]):
    """App command version of check_name_restricted_roles"""
    if interaction.guild is None:
        raise GuildNotFoundException
    server_info: ServerConfig | None = interaction.client.config.servers.get(
        interaction.guild.id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = server_info.name_restricted_roles
    return check_role_list(interaction.user, (check_roles))

# command version of check_reporter_roles; throws error if false
def command_check_reporter_roles(ctx: commands.Context[UpdatingBot]):
    server_info = get_server_config(ctx)
    check_roles = (server_info.reporter_roles + server_info.updater_roles + server_info.staff_roles + server_info.admin_roles)
    return command_check_roles(ctx, check_roles)

def app_command_check_reporter_roles(interaction: discord.Interaction[UpdatingBot]):
    server_info = get_server_config_from_interaction(interaction)
    check_roles = (server_info.reporter_roles + server_info.updater_roles + server_info.staff_roles + server_info.admin_roles)
    return app_command_check_roles(interaction, check_roles)

# command version of check_reporter_roles; throws error if false
def command_check_updater_roles(ctx: commands.Context[UpdatingBot]):
    server_info = get_server_config(ctx)
    check_roles = (server_info.updater_roles + server_info.staff_roles + server_info.admin_roles)
    return command_check_roles(ctx, check_roles)

def app_command_check_updater_roles(interaction: discord.Interaction[UpdatingBot]):
    server_info = get_server_config_from_interaction(interaction)
    check_roles = (server_info.updater_roles + server_info.staff_roles + server_info.admin_roles)
    return app_command_check_roles(interaction, check_roles)

# command version of check_staff_roles; throws error if false
def command_check_staff_roles(ctx):
    server_info = get_server_config(ctx)
    check_roles = (server_info.staff_roles + server_info.admin_roles)
    return command_check_roles(ctx, check_roles)

def app_command_check_staff_roles(interaction: discord.Interaction[UpdatingBot]):
    server_info = get_server_config_from_interaction(interaction)
    check_roles = (server_info.staff_roles + server_info.admin_roles)
    return app_command_check_roles(interaction, check_roles)

def command_check_admin_verification_roles(ctx: commands.Context[UpdatingBot]):
    server_info = get_server_config(ctx)
    check_roles = (server_info.verification_roles + server_info.admin_roles)
    return command_check_roles(ctx, check_roles)

def app_command_check_admin_verification_roles(interaction: discord.Interaction[UpdatingBot]):
    server_info = get_server_config_from_interaction(interaction)
    check_roles = (server_info.verification_roles + server_info.admin_roles)
    return app_command_check_roles(interaction, check_roles)

# lounge staff + mkc + admin
def command_check_all_staff_roles(ctx: commands.Context[UpdatingBot]):
    server_info = get_server_config(ctx)
    check_roles = (server_info.mkc_roles + server_info.staff_roles + server_info.verification_roles + server_info.admin_roles)
    return command_check_roles(ctx, check_roles)

def app_command_check_all_staff_roles(interaction: discord.Interaction[UpdatingBot]):
    server_info = get_server_config_from_interaction(interaction)
    check_roles = (server_info.mkc_roles + server_info.staff_roles + server_info.admin_roles)
    return app_command_check_roles(interaction, check_roles)

def command_check_admin_roles(ctx: commands.Context[UpdatingBot]):
    server_info = get_server_config(ctx)
    check_roles = server_info.admin_roles
    return command_check_roles(ctx, check_roles)

def app_command_check_admin_roles(interaction: discord.Interaction[UpdatingBot]):
    server_info = get_server_config_from_interaction(interaction)
    check_roles = server_info.admin_roles
    return app_command_check_roles(interaction, check_roles)

def check_valid_name(lb: LeaderboardConfig, name: str) -> tuple[bool, str | None]:
    if len(name) > 16:
        return False, "Names can only be up to 16 characters! Please choose a different name"
    if len(name) < 2:
        return False, "Names must be at least 2 characters long"
    if name.startswith("_") or name.endswith("_"):
        return False, "Names cannot start or end with `_` (underscore)"
    if name.startswith(".") or name.endswith("."):
        return False, "Names cannot start or end with `.` (period)"
    if not lb.allow_numbered_names and name.isdigit():
        return False, "Names cannot be all numbers!"
    allowed_characters = 'abcdefghijklmnopqrstuvwxyz._ -1234567890'
    for c in range(len(name)):
        if name[c].lower() not in allowed_characters:
            return False, f"The character {name[c]} is not allowed in names!"
    return True, None

# Return true if the input string can be displayed with limited side-effect
def check_displayable_name(name: str):
    if len(name) > 16:
        return False
    allowed_characters = 'abcdefghijklmnopqrstuvwxyz._ -1234567890'
    for c in range(len(name)):
        if name[c].lower() not in allowed_characters:
            return False
    return True

async def yes_no_check(ctx: commands.Context, message: discord.Message):
    #ballot box with check emoji
    CHECK_BOX = "\U00002611"
    X_MARK = "\U0000274C"
    await message.add_reaction(CHECK_BOX)
    await message.add_reaction(X_MARK)
    def check(reaction, user):
        if user != ctx.author:
            return False
        if reaction.message != message:
            return False
        if str(reaction.emoji) == X_MARK:
            return True
        if str(reaction.emoji) == CHECK_BOX:
            return True
    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=30.0, check=check)
    except:
        await message.delete()
        return False

    if str(reaction.emoji) == X_MARK:
        await message.delete()
        return False
    
    return True

async def leaderboard_autocomplete(interaction: discord.Interaction[UpdatingBot], current: str) -> list[app_commands.Choice[str]]:
    assert interaction.guild_id is not None
    server_info: ServerConfig | None = interaction.client.config.servers.get(interaction.guild_id, None)
    if not server_info:
        return []
    choices = [app_commands.Choice(name=lb, value=lb) for lb in server_info.leaderboards]
    return choices

def find_member(ctx, name, roleid):
    members = ctx.guild.members
    role = ctx.guild.get_role(roleid)
    def pred(m):
        if m.nick is not None:
            if m.nick.lower() == name.lower():
                return True
            return False
        if m.name.lower() != name.lower():
            return False
        if role not in m.roles:
            return False
        return True
    return discord.utils.find(pred, members)