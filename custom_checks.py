import discord
from discord.ext import commands
from models import ServerConfig, LeaderboardConfig
from util.Exceptions import GuildNotFoundException
from discord import app_commands

# check if user has any roles in the list of IDs
def check_role_list(member, check_roles):
    for role in check_roles:
        if member.get_role(role) is not None:
            return True
    return False

# check if user has reporter or staff roles
def check_reporter_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.reporter_roles + server_info.staff_roles + server_info.admin_roles)
    return check_role_list(ctx.author, check_roles)
    
# check if user has staff roles
def check_staff_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.staff_roles + server_info.admin_roles)
    return check_role_list(ctx.author, check_roles)

# lounge staff + mkc + admin
def check_all_staff_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.mkc_roles + server_info.staff_roles + server_info.admin_roles)
    return check_role_list(ctx.author, check_roles)

# check if user is chat restricted
def check_chat_restricted_roles(bot, member):
    server_info: ServerConfig = bot.config.servers.get(member.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.chat_restricted_roles)
    return check_role_list(member, check_roles)

# check if user is name restricted
def check_name_restricted_roles(ctx, member):
    server_info: ServerConfig = ctx.bot.config.servers.get(member.guild.id, None)
    if not server_info:
        return False
    check_roles = (server_info.name_restricted_roles)
    return check_role_list(member, check_roles)
    
# command version of check_reporter_roles; throws error if false
def command_check_reporter_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.reporter_roles + server_info.staff_roles + server_info.admin_roles)
    if check_role_list(ctx.author, check_roles):
        return True
    error_roles = [ctx.guild.get_role(role).name for role in check_roles if ctx.guild.get_role(role) is not None]
    raise commands.MissingAnyRole(error_roles)

def app_command_check_reporter_roles(interaction: discord.Interaction):
    server_info: ServerConfig = interaction.client.config.servers.get(interaction.guild_id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.reporter_roles + server_info.staff_roles + server_info.admin_roles)
    if check_role_list(interaction.user, check_roles):
        return True
    error_roles = [interaction.guild.get_role(role).name for role in check_roles if interaction.guild.get_role(role) is not None]
    raise app_commands.MissingAnyRole(error_roles)

# command version of check_staff_roles; throws error if false
def command_check_staff_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.staff_roles + server_info.admin_roles)
    if check_role_list(ctx.author, check_roles):
        return True
    error_roles = [ctx.guild.get_role(role).name for role in check_roles if ctx.guild.get_role(role) is not None]
    raise commands.MissingAnyRole(error_roles)

def app_command_check_staff_roles(interaction: discord.Interaction):
    server_info: ServerConfig = interaction.client.config.servers.get(interaction.guild_id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.staff_roles + server_info.admin_roles)
    if check_role_list(interaction.user, check_roles):
        return True
    error_roles = [interaction.guild.get_role(role).name for role in check_roles if interaction.guild.get_role(role) is not None]
    raise app_commands.MissingAnyRole(error_roles)

def command_check_admin_mkc_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.mkc_roles + server_info.admin_roles)
    if check_role_list(ctx.author, check_roles):
        return True
    error_roles = [ctx.guild.get_role(role).name for role in check_roles if ctx.guild.get_role(role) is not None]
    raise commands.MissingAnyRole(error_roles)

def app_command_check_admin_mkc_roles(interaction: discord.Interaction):
    server_info: ServerConfig = interaction.client.config.servers.get(interaction.guild_id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.mkc_roles + server_info.admin_roles)
    if check_role_list(interaction.user, check_roles):
        return True
    error_roles = [interaction.guild.get_role(role).name for role in check_roles if interaction.guild.get_role(role) is not None]
    raise app_commands.MissingAnyRole(error_roles)

# lounge staff + mkc + admin
def command_check_all_staff_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.mkc_roles + server_info.staff_roles + server_info.admin_roles)
    if check_role_list(ctx.author, check_roles):
        return True
    error_roles = [ctx.guild.get_role(role).name for role in check_roles if ctx.guild.get_role(role) is not None]
    raise commands.MissingAnyRole(error_roles)

def app_command_check_all_staff_roles(interaction: discord.Interaction):
    server_info: ServerConfig = interaction.client.config.servers.get(interaction.guild_id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = (server_info.mkc_roles + server_info.staff_roles + server_info.admin_roles)
    if check_role_list(interaction.user, check_roles):
        return True
    error_roles = [interaction.guild.get_role(role).name for role in check_roles if interaction.guild.get_role(role) is not None]
    raise app_commands.MissingAnyRole(error_roles)

# lounge staff + mkc + admin
def command_check_admin_roles(ctx):
    server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = server_info.admin_roles
    if check_role_list(ctx.author, check_roles):
        return True
    error_roles = [ctx.guild.get_role(role).name for role in check_roles if ctx.guild.get_role(role) is not None]
    raise commands.MissingAnyRole(error_roles)

def app_command_check_admin_roles(interaction: discord.Interaction):
    server_info: ServerConfig = interaction.client.config.servers.get(interaction.guild_id, None)
    if not server_info:
        raise GuildNotFoundException
    check_roles = server_info.admin_roles
    if check_role_list(interaction.user, check_roles):
        return True
    error_roles = [interaction.guild.get_role(role).name for role in check_roles if interaction.guild.get_role(role) is not None]
    raise app_commands.MissingAnyRole(error_roles)

async def check_valid_name(ctx: commands.Context, lb: LeaderboardConfig, name: str):
    if len(name) > 16:
        await ctx.send("Names can only be up to 16 characters! Please choose a different name")
        return False
    if len(name) < 2:
        await ctx.send("Names must be at least 2 characters long")
        return
    if name.startswith("_") or name.endswith("_"):
        await ctx.send("Names cannot start or end with `_` (underscore)")
        return False
    if name.startswith(".") or name.endswith("."):
        await ctx.send("Names cannot start or end with `.` (period)")
        return False
    if not lb.allow_numbered_names and name.isdigit():
        await ctx.send("Names cannot be all numbers!")
        return False
    allowed_characters = 'abcdefghijklmnopqrstuvwxyz._ -1234567890'
    for c in range(len(name)):
        if name[c].lower() not in allowed_characters:
            await ctx.send(f"The character {name[c]} is not allowed in names!")
            return False
    return True

# Return true if the input string can be displayed with limited side-effect
def check_displayable_name(name: str):
    if len(name) > 16:
        return False
    allowed_characters = 'abcdefghijklmnopqrstuvwxyz._ -1234567890'
    for c in range(len(name)):
        if name[c].lower() not in allowed_characters:
            return False
    return True

async def request_validation_check(ctx: commands.Context, message: discord.Message):
    CHECK_BOX = "\U00002611"
    X_MARK = "\U0000274C"
    await message.add_reaction(CHECK_BOX)
    await message.add_reaction(X_MARK)
    def check(reaction, user):
        server_info: ServerConfig = ctx.bot.config.servers.get(ctx.guild.id, None)
        if user != ctx.author and not check_role_list(user, (server_info.admin_roles + server_info.staff_roles)):
            return False
        if reaction.message != message:
            return False
        if str(reaction.emoji) == X_MARK:
            return True
        if str(reaction.emoji) == CHECK_BOX and check_role_list(user, (server_info.admin_roles + server_info.staff_roles)):
            return True
    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', check=check)
    except:
        return (False, None)

    if str(reaction.emoji) == X_MARK:
        return (False, user)

    return (True, user)

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

async def leaderboard_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
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