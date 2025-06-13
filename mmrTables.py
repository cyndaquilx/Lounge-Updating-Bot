import matplotlib
matplotlib.use('Agg')
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.font_manager import FontProperties
import math
from io import BytesIO
from models import LeaderboardConfig, Table
from matplotlib.figure import Figure
import asyncio

async def create_mmr_table(lb: LeaderboardConfig, table: Table):
    b = BytesIO()
    def plot():
        fig = Figure()
        ax = fig.subplots()
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        ax.axis('off')
        matplotlib.rcParams.update(matplotlib.rc_params_from_file('lounge_style.mplstyle'))

        #dark red, gray, and green
        mapcolors = ["#C00000", "#D9D9D9", "#548235"]
        #basically the same thing as a color scale in excel. used for mmr changes
        cmap = LinearSegmentedColormap.from_list("gainloss", mapcolors)

        title_color = "#0a2d61"
        header_color = "#1e2630"
        name_color = "#212121"
        data_color = "#273c5a"
        peak_mmr_color = "#F1C232"

        if table.size == 1:
            format_text = "Free for All"
        elif table.size > 1 and table.size < 6:
            format_text = f"{table.size}v{table.size} Mogi"
        else:
            format_text = "6 vs 6"
        
        if table.tier == "SQ":
            tier_text = "Squad Queue"
        else:
            tier_text = f"Tier {table.tier}"
        
        col_labels = ["", format_text, "", "", "", tier_text, ""]

        num_players = sum([1 for t in table.teams for _ in t.scores])
        
        top_row_colors = [title_color]*7
        if table.size > 1:
            #num of blank rows + num players + num extra rows
            num_rows = int(num_players/table.size - 1 + num_players+3)
        else:
            num_rows = num_players + 3

        cell_data = []
        cell_colors = []
        #2nd row of the MMR Table
        cell_data.append(["Rank", "Player", "Score", "MMR", "+/-", "New MMR", "Promotions"])
        cell_colors.append([header_color]*7)

        #adding in rows for each player
        for i, team in enumerate(table.teams):
            # empty row for team separators
            if i > 0 and table.size > 1:
                cell_data.append([""]*7)
                cell_colors.append(["#000000"]*7)
            for j, score in enumerate(team.scores):
                # want to put the team's placement roughly in the middle row of that placement
                if j == math.ceil(table.size/2-1):
                    placement_text = team.rank
                else:
                    placement_text = ""
                assert score.new_mmr is not None
                assert score.prev_mmr is not None
                assert score.delta is not None
                new_rank = lb.get_rank(score.new_mmr)
                old_rank = lb.get_rank(score.prev_mmr)
                promotion_text = ""
                if new_rank != old_rank:
                    updown = "+" if score.delta > 0 else "-"
                    promotion_text = f"{updown} {new_rank.name}"

                row_data = [placement_text, score.player.name, score.score, score.prev_mmr, f"{score.delta:+d}", score.new_mmr, promotion_text]
                row_colors = [data_color, name_color, data_color, data_color, cmap(score.delta/350+0.5), data_color, data_color]
                cell_data.append(row_data)
                cell_colors.append(row_colors)
        
        cell_data.append(["Races:", lb.races_per_mogi, "", "", "", "ID:", table.id])
        cell_colors.append([header_color]*7)

        mmr_table = ax.table(cellText=cell_data,
                      colWidths = [.13, .3, .13, .16, .12, .16, .25],
                      colLabels=col_labels,
                      colColours=top_row_colors,
                      cellColours=cell_colors,
                      loc='center',
                      cellLoc='center',
                      edges='closed',
                      fontsize=14)
        mmr_table.auto_set_font_size(False)
        mmr_table.scale(1.15, 1.75)

        cells = mmr_table.get_celld()

        # styling the first row
        for j in range(7):
            cells[(0, j)].set_fontsize(20)
            cells[(0, j)].set_height(0.1)
            cells[(0, j)].set_edgecolor(title_color)

        # Right-align allows tier text to overflow to the left,
        # for some reason it doesn't let you overflow to the right
        cells[(0, 5)].set_text_props(ha='right')

        for i, team in enumerate(table.teams):
            for j, score in enumerate(team.scores):
                # get the number of rows above current row which are
                # dividers between teams
                divider_offset = i if table.size > 1 else 0
                row_index = int(2 + i*table.size + j + divider_offset)

                if table.size > 1:
                    cells[(row_index, 0)].set_edgecolor(data_color)

                cells[(row_index, 4)].set_text_props(color='black')

                if score.is_peak:
                    cells[(row_index, 5)].set_text_props(color=peak_mmr_color, fontproperties=FontProperties(weight='bold', style='italic'))

                assert score.new_mmr is not None
                new_rank = lb.get_rank(score.new_mmr)
                cells[(row_index, 6)].set_text_props(color=new_rank.color)
                
        # style the last row of the table
        row_index = num_rows - 1
        for j in range(7):
            cells[(row_index, j)].set_edgecolor(header_color)        
        
        fig.savefig(b, format='png', bbox_inches='tight', transparent=True)
        b.seek(0)
        fig.clear()

    await asyncio.to_thread(plot)
    return b