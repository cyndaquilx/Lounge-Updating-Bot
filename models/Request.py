from dataclasses import dataclass
import urllib.parse

@dataclass
class PenaltyRequest:
    id: int
    penalty_name: str
    table_id: int
    number_of_races: int
    reporter_id: int
    reporter_name: str
    player_id: int
    player_name: str

    @classmethod
    def from_api_response(cls, body: dict):
        id = body["id"]
        penalty_name = urllib.parse.unquote(body["penaltyName"])
        table_id = body["tableId"]
        number_of_races = body["numberOfRaces"]
        reporter_id = body["reporterId"]
        reporter_name = body["reporterName"]
        player_id = body["playerId"]
        player_name = body["playerName"]
        return cls(id, penalty_name, table_id, number_of_races, reporter_id, reporter_name, player_id, player_name)

    @classmethod
    def from_list_api_response(cls, body: list[dict]):
        requests: list[PenaltyRequest] = []
        for request in body:
            requests.append(PenaltyRequest.from_api_response(request))
        return requests