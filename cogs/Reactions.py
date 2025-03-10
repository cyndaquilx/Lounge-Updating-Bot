import discord
from discord.ext import commands, tasks
from models import ServerConfig

class Reactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_queue: dict[discord.TextChannel, list[discord.Embed]] = {}
        
        self._embedqueue_task = self.send_queued_embeds.start()

    @tasks.loop(seconds=5)
    async def send_queued_embeds(self):
        for channel in self.embed_queue:
            curr_embeds: list[discord.Embed] = []
            # remove all the embeds from the queue in backwards order
            # (this is so that new embeds can still be added after
            #  the function starts without them being lost)
            # ordering doesn't really matter since this is just a log
            for i in range(len(self.embed_queue[channel]), -1, -1):
                e = self.embed_queue[channel].pop(i)
                if len(curr_embeds) == 10:
                    await channel.send(embeds=curr_embeds)
                    curr_embeds = []
                curr_embeds.append(e)
            if len(curr_embeds):
                await channel.send(embeds=curr_embeds)

    @commands.Cog.listener(name='on_reaction_add')
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return
        if reaction.message.author.bot:
            return
        
        server_info: ServerConfig = self.bot.config.servers.get(reaction.message.guild.id, None)
        if not server_info:
            return
        reaction_channel_id = server_info.reaction_log_channel
        channel = reaction.message.guild.get_channel(reaction_channel_id)
        if not channel:
            return
        e = discord.Embed(title="Reaction added")
        e.add_field(name="Message", value=reaction.message.jump_url)
        e.add_field(name="Message Author", value=reaction.message.author.mention)
        e.add_field(name="Reacted by", value=user.mention)
        if isinstance(reaction.emoji, discord.PartialEmoji):
            reaction_str = f"[{str(reaction.emoji)}]({reaction.emoji.url})"
        else:
            reaction_str = reaction.emoji
        e.add_field(name="Emoji", value=reaction_str)
        if channel not in self.embed_queue:
            self.embed_queue[channel] = []
        self.embed_queue[channel].append(e)

async def setup(bot):
    await bot.add_cog(Reactions(bot))