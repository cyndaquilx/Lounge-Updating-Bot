from discord.ext import commands
from models.Config import BotConfig
from database import DBWrapper

class UpdatingBot(commands.Bot):
    def __init__(self, config: BotConfig, db_wrapper: DBWrapper, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.db_wrapper = db_wrapper