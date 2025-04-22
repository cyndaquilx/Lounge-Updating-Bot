from dataclasses import dataclass
from datetime import datetime
import dateutil.parser

@dataclass
class Bonus:
    id: int
    season: int
    awarded_on: datetime
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
        prev_mmr = body['prevMmr']
        new_mmr = body['newMmr']
        amount = body['amount']
        player_id = body['playerId']
        player_name = body['playerName']
        return cls(id, season, awarded_on, prev_mmr,
                   new_mmr, amount, player_id, player_name)