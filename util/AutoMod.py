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

#Return true is the word can be displayed by the bot
async def check_against_automod_lists(ctx: commands.Context, message: str):
    rules = await ctx.guild.fetch_automod_rules()
    for rule in rules:
        long_word_pattern = []
        short_word_pattern = []
        for word in rule.trigger.keyword_filter:
            word = word.replace("*", "")
            pattern = create_pattern(word)
            
            #Short words can more easily appear in larger and authorized words. It checks if they are surrounded by 1 or 0 alphanumerical char left and right to avoid false positive
            if len(word) <= 4:
                short_word_pattern.append(r'(^|[^a-zA-Z0-9])([a-zA-Z0-9]?' + pattern + r'[a-zA-Z0-9]?)(?=[^a-zA-Z0-9]|$)')
            else:
                long_word_pattern.append(r'\b' + pattern + r'\b')

        #Should also account for messages that contain repeated innapropriate words
        word_sequence_pattern = []
        for word in rule.trigger.keyword_filter:
            word = word.replace("*", "")
            pattern = create_pattern(word)
            word_sequence_pattern.append(r'(^|[^a-zA-Z0-9])(' + pattern + r'){2,}(?=[^a-zA-Z0-9]|$)')
        
        combined_pattern = "|".join(short_word_pattern + long_word_pattern + word_sequence_pattern)
        if re.findall(combined_pattern, message, re.IGNORECASE):
            return False
    return True