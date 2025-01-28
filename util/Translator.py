import discord
from discord import app_commands
from typing import Optional

class CustomTranslator(app_commands.Translator):
    async def load(self):
        return
    
    async def unload(self):
        return

    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> Optional[str]:
        message = string.message
        if locale is discord.Locale.french:
            if message == "Late":
                return "Retard"
            if message == "Host issues":
                return "Problème de host"
            if message == "No host":
                return "Pas de host"

            #TODO: Complete it manually

        return None