from discord.ext import commands

import re

#Bidirectional correspondence
character_connection = {
    'i': '[i1|!]',
    '1': '[i1|!]',
    '|': '[i1|!]',
    '!': '[i1|!]',

    'a': '[a4]',
    '4': '[a4]',
    
    'e': '[e3]',
    '3': '[e3]',
    
    'o': '[o0]',
    '0': '[o0]',
    
    's': '[s5]',
    '5': '[s5]',
    
    't': '[t7]',
    '7': '[t7]'
}

def create_pattern(word: str):
    return "".join(character_connection.get(char, char) for char in word)

async def check_against_automod_lists(ctx: commands.Context, message: str):
    rules = await ctx.guild.fetch_automod_rules()
    for rule in rules:
        regex_patterns = [create_pattern(word.replace("*", "")) for word in rule.trigger.keyword_filter]
        combined_pattern = r"\b(" + "|".join(regex_patterns) + r")\b"
        if re.search(combined_pattern, message, re.IGNORECASE):
            return False
    return True
