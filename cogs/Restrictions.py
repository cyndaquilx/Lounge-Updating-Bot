import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta, timezone
from io import StringIO

from custom_checks import check_chat_restricted_roles, command_check_staff_roles
from models import ServerConfig

class Restrictions(commands.Cog):
    def __init__ (self, bot: commands.Bot):
        self.bot = bot
        with open('./allowed_phrases.json', 'r', encoding='utf-8') as f:
            self.phrases: dict[str, list[str]] = json.load(f)
        #self.allowed_phrases = self.phrases["ALLOWED_PHRASES"]

        #Dictionary containing a list of illegal messages sent by chat restricted users.
        self.violations: dict[discord.Member, list[datetime]] = {}
        #Dictionary containing lists of valid messages sent by chat restricted users.
        self.restricted_msgs: dict[discord.Member, list[datetime]] = {}

        self._remove_task = self.remove_expired_violations.start()

    # Removes any restriction violations / allowed message timestamps that are over a minute old
    @tasks.loop(seconds=5)
    async def remove_expired_violations(self):
        for time_list in self.violations.values():
            for i in range(len(time_list)-1, -1, -1):
                if time_list[i] + timedelta(minutes=1) > datetime.now(timezone.utc):
                    time_list.pop(i)
        for time_list in self.restricted_msgs.values():
            for i in range(len(time_list)-1, -1, -1):
                if time_list[i] + timedelta(minutes=1) > datetime.now(timezone.utc):
                    time_list.pop(i)

    async def add_violation(self, message:discord.Message):
        if message.author not in self.violations.keys():
            self.violations[message.author] = []
        self.violations[message.author].append(datetime.now(timezone.utc))
        if len(self.violations[message.author]) >= 3:
            await message.author.timeout(timedelta(minutes=5), reason="5-minute timeout for restricted message violation")
            await message.channel.send(f"{message.author.mention} you have been timed out for 5 minutes for violating chat restriction rules", delete_after=15.0)

    async def add_message(self, message:discord.Message):
        if message.author not in self.restricted_msgs.keys():
            self.restricted_msgs[message.author] = []
        self.restricted_msgs[message.author].append(datetime.now(timezone.utc))
        if len(self.restricted_msgs[message.author]) >= 5:
            await message.author.timeout(timedelta(minutes=5), reason="5-minute timeout for restricted message violation")
            await message.channel.send(f"{message.author.mention} you have been timed out for 5 minutes for violating chat restriction rules", delete_after=15.0)

    @commands.Cog.listener(name='on_message')
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return
        server_info: ServerConfig = self.bot.config.servers.get(message.guild.id, None)
        if server_info is None:
            return
        # don't want to delete CR'd messages in tickets
        if message.channel.category_id in server_info.ticket_categories:
            return
        if check_chat_restricted_roles(self.bot, message.author):
            # get the list of allowed phrases for this server
            server_allowed_phrases: list[str] = self.phrases.get(str(message.guild.id), None)
            if not server_allowed_phrases:
                return
            if message.reference is not None:
                await self.add_violation(message)
                await message.delete()
            elif message.content.lower() not in server_allowed_phrases:
                await self.add_violation(message)
                await message.delete()
            else:
                await self.add_message(message)

    @commands.Cog.listener(name='on_message_edit')
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.guild is None:
            return
        if after.author.bot:
            return
        server_info: ServerConfig = self.bot.config.servers.get(after.guild.id, None)
        if server_info is None:
            return
        # don't want to delete CR'd messages in tickets
        if after.channel.category_id in server_info.ticket_categories:
            return
        if check_chat_restricted_roles(self.bot, after.author):
            # get the list of allowed phrases for this server
            server_allowed_phrases: list[str] = self.phrases.get(str(after.guild.id), None)
            if not server_allowed_phrases:
                return
            if after.content.lower() not in server_allowed_phrases:
                await self.add_violation(after)
                await after.delete()

    @commands.command(aliases=['rw'])
    @commands.cooldown(1, 300, commands.BucketType.member)
    async def restrictedwords(self, ctx: commands.Context):
        server_allowed_phrases: list[str] = self.phrases.get(str(ctx.guild.id), None)
        if server_allowed_phrases is None:
            await ctx.send("There are no restricted words in this server.")
            return
        file = StringIO()
        json.dump(server_allowed_phrases, file, ensure_ascii=False, indent=4)
        file.seek(0)
        f = discord.File(fp=file, filename="phrases.json")
        await ctx.send(file=f)

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['addrw'])
    async def add_restricted_word(self, ctx: commands.Context, *, phrase: str):
        server_allowed_phrases: list[str] = self.phrases.get(str(ctx.guild.id), None)
        if server_allowed_phrases is None:
            server_allowed_phrases = []
            self.phrases[str(ctx.guild.id)] = server_allowed_phrases
        if phrase.lower() in server_allowed_phrases:
            await ctx.send("Already a restricted word")
            return
        server_allowed_phrases.append(phrase.lower())
        with open('./allowed_phrases.json', 'w', encoding='utf-8') as f:
            json.dump(self.phrases, f, ensure_ascii=False, indent=4)
        await ctx.send("added phrase")

    @commands.check(command_check_staff_roles)
    @commands.command(aliases=['delrw'])
    async def remove_restricted_word(self, ctx: commands.Context, *, phrase: str):
        server_allowed_phrases: list[str] = self.phrases.get(str(ctx.guild.id), None)
        if server_allowed_phrases is None:
            await ctx.send("not a restricted word")
        if phrase.lower() not in server_allowed_phrases:
            await ctx.send("not a restricted word")
            return
        server_allowed_phrases.remove(phrase.lower())
        with open('./allowed_phrases.json', 'w', encoding='utf-8') as f:
            json.dump(self.phrases, f, ensure_ascii=False, indent=4)
        await ctx.send("removed phrase")
    
async def setup(bot):
    await bot.add_cog(Restrictions(bot))
