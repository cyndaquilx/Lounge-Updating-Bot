"""Views"""
from typing import Callable, Awaitable
from discord.ui import View, Select, Button
from discord import SelectOption, Interaction
from models import LeaderboardConfig, UpdatingBot
from util.Leaderboards import get_server_config_from_interaction
import discord

class LeaderboardSelectView(View):
    """
    A reusable select view component for leaderboards

    After the option is selected, calls the callback
    function with the selected option
    """

    def __init__(
        self,
        leaderboards: dict[str, LeaderboardConfig],
        callback: Callable[[Interaction[UpdatingBot], str], Awaitable[None]],
        timeout: int | None = None
    ):
        super().__init__(timeout=timeout)

        options = [
            SelectOption(
                label=lb,
                value=lb,
            ) for lb in leaderboards.keys()
        ]

        select = Select(
            placeholder="Select a leaderboard",
            min_values=1,
            max_values=1,
            options=options
        )

        async def select_callback(interaction: Interaction[UpdatingBot]):
            await callback(interaction, select.values[0])

        select.callback = select_callback
        self.add_item(select)

class RequestButton(View):
    """
    Request button view
    
    When the button is clicked, calls the callback function.
    If there exists more than one leaderboard in the server
    config, an ephemeral Leaderboard select will appear first

    To implement, subclass this and define leaderboard_callback
    """

    def __init__(
        self,
        label: str,
        custom_id: str,
        timeout: int | None = None,
        **kwargs):

        super().__init__(timeout=timeout)

        button = Button(
            label=label,
            custom_id=custom_id,
            style=discord.ButtonStyle.green,
            **kwargs
        )

        async def button_callback(interaction: Interaction[UpdatingBot]):
            server_info = get_server_config_from_interaction(interaction)
            leaderboards = server_info.leaderboards
            if len(leaderboards) > 1:
                await interaction.response.send_message(
                    view=LeaderboardSelectView(
                        leaderboards,
                        self.leaderboard_callback
                    ),
                    ephemeral=True,
                    delete_after=30
                )
                return

            await self.leaderboard_callback(interaction, None)

        button.callback = button_callback
        self.add_item(button)

    async def leaderboard_callback(
        self,
        interaction: Interaction[UpdatingBot],
        leaderboard: str | None):
        """
        What to do after the button click
        and selecting the leaderboard

        Implement on subclasses
        """
        raise NotImplementedError
