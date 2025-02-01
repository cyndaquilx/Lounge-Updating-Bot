import discord
from discord import app_commands
from typing import Optional

class CustomTranslator(app_commands.Translator):

    #EN -> (JP, FR, ES)
    en_to_others = {
        #--------------Penalty type--------------
        "Late": (None, "Retard", None),
        "Drop mid mogi": (None, "Drop durant le mogi", None),
        "Drop before start": (None, "Drop avant le début du mogi", None),
        "Tag penalty": (None, "Pénalité de tag", None),
        "Repick": (None, "Repeat", None),
        "No video proof": (None, "Pas de preuve vidéo", None),
        "Host issues": (None, "Problème de host", None),
        "No host": (None, "Pas de host", None),
        #--------------Penalty description--------------
        "Type of penalty you want to report someone for": (None, "Type de pénalité pour laquelle vous voulez report quelqu'un", None),
        "The player being reported": (None, "Le joueur que vous voulez report", None),
        "'Drop mid mogi': number of races played alone / 'Repick': number of races repicked": (None, "'Drop durant le mogi': nombre de courses jouées seul / 'Repeat': nombre de courses repeat", None),
        "Additional reason you would like to give to the staff": (None, "Indication supplémentaire que vous voulez donner au staff", None)
    }

    async def load(self):
        return
    
    async def unload(self):
        return

    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> Optional[str]:
        message = string.message
        dummy_reply = (None, None, None)
        if locale is discord.Locale.japanese:
            return self.en_to_others.get(message, dummy_reply)[0]
        if locale is discord.Locale.french:
            return self.en_to_others.get(message, dummy_reply)[1]
        if locale is discord.Locale.spain_spanish:
            return self.en_to_others.get(message, dummy_reply)[2]

        return None