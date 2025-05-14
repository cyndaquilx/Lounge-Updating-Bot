import aiohttp
from models import Table, WebsiteCredentials, Player, PlayerDetailed, NameChangeRequest, ListPlayer, Penalty

headers = {'Content-type': 'application/json'}

async def getStrikes(credentials: WebsiteCredentials, name: str):
    request_url = f"{credentials.url}/api/penalty/list?name={name}&isStrike=true"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None, await resp.text()
            body = await resp.json()
            strikes = Penalty.from_list_api_response(body)
            return strikes, None

async def getPlayers(credentials: WebsiteCredentials, names: list[str]):
    base_url = f"{credentials.url}/api/player"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        players: list[Player | None] = []
        for name in names:
            request_url = f"{base_url}?name={name}"
            async with session.get(request_url, headers=headers) as resp:
                if resp.status != 200:
                    players.append(None)
                    continue
                body = await resp.json()
                player = Player.from_api_response(body)
                players.append(player)
        return players
        
async def getPlayer(credentials: WebsiteCredentials, name: str):
    request_url = f"{credentials.url}/api/player?name={name}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            player = Player.from_api_response(body)
            return player

async def getPlayerFromMKC(credentials: WebsiteCredentials, mkc_id: int):
    request_url = f"{credentials.url}/api/player?mkcId={mkc_id}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            player = Player.from_api_response(body)
            return player

async def getPlayerFromLounge(credentials: WebsiteCredentials, lounge_id: int):
    request_url = f"{credentials.url}/api/player?id={lounge_id}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            player = Player.from_api_response(body)
            return player
        
async def getPlayerFromDiscord(credentials: WebsiteCredentials, discord_id: int):
    request_url = f"{credentials.url}/api/player?discordId={discord_id}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            player = Player.from_api_response(body)
            return player
        
async def getPlayerDetails(credentials: WebsiteCredentials, name: str):
    request_url = f"{credentials.url}/api/player/details?name={name}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            playerData = await resp.json()
            player = PlayerDetailed.from_api_response(playerData)
            return player
        
async def getPlayerDetailsFromDiscord(credentials: WebsiteCredentials, discord_id: int):
    request_url = f"{credentials.url}/api/player/details?discordId={discord_id}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            playerData = await resp.json()
            player = PlayerDetailed.from_api_response(playerData)
            return player
        
async def getTable(credentials: WebsiteCredentials, table_id: int):
    request_url = f"{credentials.url}/api/table?tableId={table_id}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            table = await resp.json()
            return Table.from_api_response(table)

async def getPending(credentials: WebsiteCredentials):
    request_url = f"{credentials.url}/api/table/unverified"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            tables = Table.from_list_api_response(body)
            return tables
    
async def getPlayerList(credentials: WebsiteCredentials) -> list[ListPlayer] | None:
    request_url = f"{credentials.url}/api/player/list"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            players = ListPlayer.from_list_api_response(body)
            return players

async def getPendingNameChanges(credentials: WebsiteCredentials):
    request_url = f"{credentials.url}/api/player/listPendingNameChanges"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.get(request_url,headers=headers) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            changes = NameChangeRequest.list_from_api_response(body)
            return changes
