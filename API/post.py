import aiohttp
from models import TableBasic, Table, WebsiteCredentials, Player, NameChangeRequest, Penalty, Bonus, PlayerPlacement
from typing import Tuple

headers = {'Content-type': 'application/json'}

async def createBonus(credentials: WebsiteCredentials, name: str, amount: int):
    request_url = f"{credentials.url}/api/bonus/create?name={name}&amount={amount}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status != 201:
                error = await resp.text()
                return None, error
            body = await resp.json()
            bonus = Bonus.from_api_response(body)
            return bonus, None

async def bonusMKC(credentials: WebsiteCredentials, mkc:int, amount:int):
    request_url = f"{credentials.url}/api/bonus/create?mkcId={mkc}&amount={amount}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status != 201:
                error = await resp.text()
                return None, error
            body = await resp.json()
            bonus = Bonus.from_api_response(body)
            return bonus, None

async def createPenalty(credentials: WebsiteCredentials, name: str, amount: int, isStrike: bool):
    request_url = f"{credentials.url}/api/penalty/create?name={name}&amount={amount}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    if isStrike:
        request_url += "&isStrike=true"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url, headers=headers) as resp:
            if resp.status == 404:
                error = "Player not found"
                return None, error
            if resp.status != 201:
                error = await resp.text()
                return None, error
            body = await resp.json()
            penalty = Penalty.from_api_response(body)
            return penalty, None

async def deletePenalty(credentials: WebsiteCredentials, pen_id: int):
    request_url = f"{credentials.url}/api/penalty?id={pen_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.delete(request_url,headers=headers) as resp:
            if resp.status == 200:
                return True, None
            return False, resp.status

async def createNewPlayer(credentials: WebsiteCredentials, mkcid:int, name, discordid: int | None = None) -> Tuple[Player | None, str | None]:
    request_url = f"{credentials.url}/api/player/create?name={name}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    if mkcid > 0:
        request_url += f"&mkcid={mkcid}"
    if discordid:
        request_url += f"&discordId={discordid}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status != 201:
                error = await resp.text()
                return None, error
            body = await resp.json()
            player = Player.from_api_response(body)
            return player, None

async def createPlayerWithMMR(credentials: WebsiteCredentials, mkcid:int, mmr:int, name: str, discordid: int | None = None) -> Tuple[Player | None, str | None]:
    request_url = f"{credentials.url}/api/player/create?name={name}&mmr={mmr}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    if mkcid > 0:
        request_url += f"&mkcid={mkcid}"
    if discordid:
        request_url += f"&discordId={discordid}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status != 201:
                error = await resp.text()
                return None, error
            body = await resp.json()
            player = Player.from_api_response(body)
            return player, None
        
async def registerPlayer(credentials: WebsiteCredentials, name: str, mmr: int | None = None) -> Tuple[Player | None, str | None]:
    request_url = f"{credentials.url}/api/player/register?game={credentials.game}&name={name}"
    if mmr is not None:
        request_url += f"&mmr={mmr}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status != 201:
                error = await resp.text()
                return None, error
            body = await resp.json()
            player = Player.from_api_response(body)
            return player, None
        
async def placePlayer(credentials: WebsiteCredentials, mmr:int, name:str, force=False):
    request_url = f"{credentials.url}/api/player/placement?name={name}&mmr={mmr}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    if force:
        request_url += "&force=true"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status != 201:
                error = await resp.text()
                return None, error
            body = await resp.json()
            player = Player.from_api_response(body)
            return player, None
        
async def placeManyPlayers(credentials: WebsiteCredentials, placements: list[PlayerPlacement]):
    request_url = f"{credentials.url}/api/player/bulkPlacement"
    if credentials.game:
        request_url += f"?game={credentials.game}"
    body = {"playerPlacements": [{"name": p.name, "mmr": p.mmr} for p in placements]}
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers,json=body) as resp:
            if resp.status != 204:
                error = await resp.text()
                return False, error
            return True, None

async def updatePlayerName(credentials: WebsiteCredentials, oldName: str, newName: str):
    request_url = f"{credentials.url}/api/player/update/name?name={oldName}&newName={newName}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status == 204:
                return None
            if resp.status == 404:
                return("User with the current name doesn't exist")
            if resp.status == 400:
                return("User with that new name already exists")

async def updateMKCid(credentials: WebsiteCredentials, name, newID):
    request_url = f"{credentials.url}/api/player/update/mkcId?name={name}&newMkcId={newID}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status == 404:
                return("Could not find user specified")
            if resp.status != 204:
                return await resp.text()
            return True          

async def deleteTable(credentials: WebsiteCredentials, table_id: int):
    request_url = f"{credentials.url}/api/table?tableId={table_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.delete(request_url,headers=headers) as resp:
            if resp.status == 200:
                return True
            return resp.status
        
async def createTable(credentials: WebsiteCredentials, table: TableBasic):
    request_url = f"{credentials.url}/api/table/create?"
    if credentials.game:
        request_url += f"game={credentials.game}"
    body = table.to_submission_format()
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers,json=body) as resp:
            if resp.status != 201:
                error = await resp.text()
                return None, error
            returnjson = await resp.json()
            table = Table.from_api_response(returnjson)
            return table, None

async def setMultipliers(credentials: WebsiteCredentials, table_id: int, multipliers):
    request_url = f"{credentials.url}/api/table/setMultipliers?tableId={table_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers,json=multipliers) as resp:
            if resp.status != 200:
                return(await resp.text())
            return True

async def setScores(credentials: WebsiteCredentials, table_id: int, scores: dict[str, list[int]]):
    request_url = f"{credentials.url}/api/table/setScores?tableId={table_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    body = {}
    for name, gp_scores in scores.items():
        if len(gp_scores) == 1:
            body[name] = sum(gp_scores)
        else:
            body[name] = gp_scores
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers,json=body) as resp:
            if resp.status != 200:
                return(await resp.text())
            return True

async def setTableMessageId(credentials: WebsiteCredentials, table_id:int, msg_id:int):
    request_url = f"{credentials.url}/api/table/setTableMessageId?tableId={table_id}&tableMessageId={msg_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            return

async def setUpdateMessageId(credentials: WebsiteCredentials, table_id:int, msg_id:int):
    request_url = f"{credentials.url}/api/table/setUpdateMessageId?tableId={table_id}&updateMessageId={msg_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            return

async def verifyTable(credentials: WebsiteCredentials, table_id:int):
    request_url = f"{credentials.url}/api/table/verify?tableId={table_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if resp.status != 200:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return None, error_msg
            body = await resp.json()
            table = Table.from_api_response(body)
            return table, None

async def updateDiscord(credentials: WebsiteCredentials, name, discord_id:int):
    request_url = f"{credentials.url}/api/player/update/discordId?name={name}&newDiscordId={discord_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return False, error_msg
            return True, await resp.text()

async def hidePlayer(credentials: WebsiteCredentials, name):
    request_url = f"{credentials.url}/api/player/hide?name={name}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return False, error_msg
            return True, await resp.text()

async def unhidePlayer(credentials: WebsiteCredentials, name):
    request_url = f"{credentials.url}/api/player/unhide?name={name}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return False, error_msg
            return True, await resp.text()

async def refreshPlayerData(credentials: WebsiteCredentials, name):
    request_url = f"{credentials.url}/api/player/refreshRegistryData?name={name}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return False, error_msg
            return True, await resp.text()

async def requestNameChange(credentials: WebsiteCredentials, old_name, new_name):
    request_url = f"{credentials.url}/api/player/requestNameChange?name={old_name}&newName={new_name}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url,headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return False, error_msg
            return True, await resp.json()

async def setNameChangeMessageId(credentials: WebsiteCredentials, current_name, message_id):
    request_url = f"{credentials.url}/api/player/setNameChangeMessageId?name={current_name}&messageId={message_id}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url, headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return False, error_msg
            return True, await resp.text()

async def acceptNameChange(credentials: WebsiteCredentials, current_name: str):
    request_url = f"{credentials.url}/api/player/acceptNameChange?name={current_name}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url, headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return None, error_msg
            body = await resp.json()
            name_change = NameChangeRequest.from_api_response(body)
            return name_change, None

async def rejectNameChange(credentials: WebsiteCredentials, current_name: str):
    request_url = f"{credentials.url}/api/player/rejectNameChange?name={current_name}"
    if credentials.game:
        request_url += f"&game={credentials.game}"
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(credentials.username, credentials.password)) as session:
        async with session.post(request_url, headers=headers) as resp:
            if int(resp.status/100) != 2:
                resp_text = await resp.text()
                error_msg = f"{resp.status} - {resp_text}"
                return None, error_msg
            body = await resp.json()
            name_change = NameChangeRequest.from_api_response(body)
            return name_change, None