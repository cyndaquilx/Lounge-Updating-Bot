import discord
from discord.ext import commands
from models import TableBasic, Table, LeaderboardConfig
from custom_checks import yes_no_check
import API.post
from typing import Union

async def submit_table(ctx: commands.Context, lb: LeaderboardConfig, table: TableBasic, bypass_confirmation = False) -> Table | None:
    assert ctx.guild is not None
    total = table.score_total()
    expected_total = int(lb.races_per_mogi*lb.points_per_race)
    embedded = None
    if not bypass_confirmation:
        e = discord.Embed(title="Table")
        e.set_image(url=table.get_lorenzi_url())
        if total != expected_total:
            e.add_field(name="Warning", value=f"The total score of {total} might be incorrect! Most tables should add up to {expected_total} points")
        content = "Please react to this message with \U00002611 within the next 30 seconds to confirm the table is correct"
        embedded = await ctx.send(content=content, embed=e)
        if not await yes_no_check(ctx, embedded):
            return None

    sent_table, error = await API.post.createTable(lb.website_credentials, table)
    if sent_table is None:
        await ctx.send(f"An error occurred trying to send the table to the website!\n{error}")
        return None
    e = discord.Embed(title="Mogi Table", colour=int("0A2D61", 16))
    e.add_field(name="ID", value=sent_table.id)
    e.add_field(name="Tier", value=sent_table.tier)
    e.add_field(name="Submitted by", value=ctx.author.mention)
    e.add_field(name="Submitted from", value=ctx.channel.jump_url)
    e.add_field(name="View on website", value=(f"{lb.website_credentials.url}/TableDetails/{sent_table.id}"), inline=False)
    
    if total != expected_total:
        warning = f"The total score of {total} might be incorrect! Most tables should add up to {expected_total} points"
        e.add_field(name="Warning", value=warning, inline=False)

    table_image_url = f"{lb.website_credentials.url}{sent_table.get_table_image_url()}"
    e.set_image(url=table_image_url)
    channel = ctx.guild.get_channel(lb.tier_results_channels[table.tier])
    if channel:
        assert isinstance(channel, discord.TextChannel)
        tableMsg = await channel.send(embed=e)
    
    await API.post.setTableMessageId(lb.website_credentials, sent_table.id, tableMsg.id)
    if embedded is not None:
        await embedded.delete()
    if channel == ctx.channel:
        await ctx.message.delete()
    else:
        await ctx.send(f"Successfully sent table to {tableMsg.jump_url} `(ID: {sent_table.id})`")
    return sent_table

async def delete_table(ctx: commands.Context, lb: LeaderboardConfig, table: Table, reason="", send_log=True):
    assert ctx.guild is not None
    assert isinstance(ctx.channel, Union[discord.TextChannel, discord.Thread])
    rank_changes = ""
    if table.verified_on:
        for team in table.teams:
            for score in team.scores:
                # if this table was one where the player ranked up/down, we want to put them in their previous rank
                if score.new_mmr is None or score.prev_mmr is None:
                    continue
                old_rank = lb.get_rank(score.new_mmr)
                new_rank = lb.get_rank(score.prev_mmr)
                if old_rank == new_rank:
                    continue
                if score.player.discord_id:
                    member = ctx.guild.get_member(int(score.player.discord_id))
                else:
                    member = None
                # don't want to mention people in ticket threads and add them to it
                if member and not hasattr(ctx.channel, 'parent_id'):
                    player_name = member.mention
                else:
                    player_name = score.player.name
                emoji = new_rank.emoji
                rank_changes += f"{player_name} -> {emoji}\n"
                old_role = ctx.guild.get_role(old_rank.role_id)
                new_role = ctx.guild.get_role(new_rank.role_id)
                if member:
                    if old_role and old_role in member.roles:
                        await member.remove_roles(old_role)
                    if new_role and new_role not in member.roles:
                        await member.add_roles(new_role)
    channel = ctx.guild.get_channel(lb.tier_results_channels[table.tier])
    if channel:
        assert isinstance(channel, discord.TextChannel)
        if table.table_message_id:
            try:
                table_msg = await channel.fetch_message(table.table_message_id)
                if table_msg is not None:
                    await table_msg.delete()
            except:
                pass
        if table.update_message_id:
            try:
                update_msg = await channel.fetch_message(table.update_message_id)
                if update_msg is not None:
                    await update_msg.delete()
            except:
                pass
    success = await API.post.deleteTable(lb.website_credentials, table.id)
    if success is True:
        await ctx.send(f"Successfully deleted table with ID {table.id}\n{rank_changes}")
    else:
        await ctx.send(f"Table not found: Error {success}")

    if send_log:
        e = discord.Embed(title="Deleted Table")
        e.add_field(name="Table ID", value=table.id)
        e.add_field(name="Removed by", value=ctx.author.mention)
        e.add_field(name="Removed in", value=ctx.channel.mention)
        if len(reason):
            e.add_field(name="Reason", value=reason, inline=False)
        updating_log = ctx.guild.get_channel(lb.updating_log_channel)
        if updating_log is not None:
            assert isinstance(updating_log, discord.TextChannel)
            await updating_log.send(embed=e)