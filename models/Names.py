from dataclasses import dataclass
from datetime import datetime
import dateutil.parser

@dataclass
class NameChangeRequest:
    player_id: int
    current_name: str
    new_name: str
    requested_on: datetime
    message_id: int | None
    discord_id: int | None

    @classmethod
    def from_api_response(cls, body: dict):
        player_id = body['id']
        current_name = body['name']
        new_name = body['newName']
        def parse_date(field_name: str):
            return dateutil.parser.isoparse(body[field_name])
        requested_on = parse_date('requestedOn')
        message_id = body.get('messageId', None)
        discord_id = body.get('discordId', None)
        request = cls(player_id, current_name, new_name, requested_on, message_id, discord_id)
        return request

    @classmethod
    def list_from_api_response(cls, body: dict):
        change_requests: list[NameChangeRequest] = []
        for player in body['players']:
            change_requests.append(cls.from_api_response(player))
        return change_requests