from dataclasses import dataclass
from datetime import datetime
import dateutil.parser

@dataclass
class Penalty:
    id: int
    season: int
    awarded_on: datetime
    is_strike: bool
    prev_mmr: int
    new_mmr: int
    amount: int
    player_id: int
    player_name: str

    @classmethod
    def from_api_response(cls, body: dict):
        id = body['id']
        season = body['season']
        def parse_date(field_name: str):
            return dateutil.parser.isoparse(body[field_name])
        awarded_on = parse_date('awardedOn')
        is_strike = body['isStrike']
        prev_mmr = body['prevMmr']
        new_mmr = body['newMmr']
        amount = body['amount']
        player_id = body['playerId']
        player_name = body['playerName']
        return cls(id, season, awarded_on, is_strike, prev_mmr,
                   new_mmr, amount, player_id, player_name)
    
    @classmethod
    def from_list_api_response(cls, body: list[dict]):
        penalties: list[Penalty] = []
        for pen in body:
            penalties.append(Penalty.from_api_response(pen))
        return penalties