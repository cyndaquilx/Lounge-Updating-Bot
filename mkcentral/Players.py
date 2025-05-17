import aiohttp
from models import MKCentralCredentials, MKCPlayerList, MKCPlayer
import msgspec

headers = {'Content-type': 'application/json'}

async def searchMKCPlayersByDiscordID(credentials: MKCentralCredentials, discord_id: int) -> MKCPlayerList | None:
    request_url = f"{credentials.url}/api/registry/players?discord_id={discord_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            player_list = msgspec.convert(data, MKCPlayerList, strict=False)
        return player_list
    
async def getMKCPlayerFromID(credentials: MKCentralCredentials, mkc_id: int) -> MKCPlayer | None:
    request_url = f"{credentials.url}/api/registry/players/{mkc_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(request_url,headers=headers) as resp:
            print(resp.status)
            print(request_url)
            if resp.status != 200:
                return None
            data = await resp.json()
            player = msgspec.convert(data, MKCPlayer, strict=False)
        return player