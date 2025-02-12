import discord
from discord import app_commands
from typing import Optional

class CustomTranslator(app_commands.Translator):

    #EN -> (JP, FR, ES, DE)
    dummy_reply = (None, None, None, None)
    en_to_others = {
        #--------------Penalty type--------------
        "Late":
            ("遅刻",
            "Retard",
            "Ingreso tardío a la sala",
            "Spät"),
        "Drop mid mogi":
            ("模擬中のドロップ",
            "Drop durant le mogi",
            "Abandono de medio mogi",
            "Verlassen während des Mogi"),
        "Drop before start":
            ("模擬開始前のドロップ",
            "Drop avant le début du mogi",
            "Abandono antes de iniciar",
            "Verlassen vor dem Start des Mogi"),
        "Tag penalty":
            ("タグ違反",
            "Pénalité de tag",
            "Penalización por tag",
            "Bestrafung für den falschen Tag"),
        "FFA name violation":
            (None,
            "Nom incorrect en FFA",
            None,
            None),
        "Repick":
            ("リピック",
            "Repeat",
            "Reelección de pista",
            "Erneutes auswählen einer Strecke"),
        "No video proof":
            ("証拠動画なし",
            "Pas de preuve vidéo",
            "Sin evidencia de desconexión",
            "Kein Videonachweis"),
        "Host issues":
            ("ホスト関連の問題",
            "Problème de host",
            "Problemas como host",
            "Host Probleme"),
        "No host":
            ("ホストなし",
            "Pas de host",
            "No host",
            "Kein Host"),
        #--------------Penalty description--------------
        "Type of penalty you want to report someone for": 
            ("報告したいペナルティの種類",
            "Type de pénalité pour laquelle vous voulez report quelqu'un",
            "Tipo de penalización por la que deseas reportar",
            "Art der Strafe, für die Sie jemanden melden möchten"),
        "The player being reported":
            ("報告したいプレイヤー",
            "Le joueur que vous voulez report",
            "Nombre del jugador reportado",
            "Der gemeldete Spieler"),
        "'Drop mid mogi': number of races played alone / 'Repick': number of races repicked":
            ("模擬中のドロップ：一人でプレイしたレースの数 / リピック：リピックしたレースの数",
            "'Drop durant le mogi': nombre de courses jouées seul / 'Repeat': nombre de courses repeat",
            "Número de carreras que jugó solo o número de pistas que se reeleccionaron",
            "Anzahl der allein gespielten Rennen oder Anzahl der Strecken wie wiederholt ausgewählt wurden."),
        "Additional information you would like to give to the staff":
            ("スタッフに伝えたいその他の追加情報",
            "Indication supplémentaire que vous voulez donner au staff",
            "Información adicional que te gustaría proporcionar al staff",
            "Zusätzliche Informationen, die Sie dem Staff mitteilen möchten")
    }

    async def load(self):
        return
    
    async def unload(self):
        return

    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> Optional[str]:
        message = string.message
        if locale is discord.Locale.japanese:
            return self.en_to_others.get(message, self.dummy_reply)[0]
        if locale is discord.Locale.french:
            return self.en_to_others.get(message, self.dummy_reply)[1]
        if locale is discord.Locale.spain_spanish:
            return self.en_to_others.get(message, self.dummy_reply)[2]
        if locale is discord.Locale.german:
            return self.en_to_others.get(message, self.dummy_reply)[3]

        return None