# get date and league through argv or argparse
# get auctions started and players cut from that day
# using pybaseball, scrape statcast info
# v2: scrape RoS steamer / zips projections
import argparse
from datetime import date
import requests
from bs4 import BeautifulSoup
from pybaseball import (
    statcast_batter_exitvelo_barrels,
    statcast_batter_percentile_ranks,
    statcast_batter_expected_stats,
    statcast_pitcher_expected_stats,
    statcast_pitcher_percentile_ranks,
    playerid_lookup,
    cache,
)
from tqdm import tqdm
from auction_utils import (
    clean_name,
    get_ottoneu_player_page,
    get_position_group,
    format_html,
)

parser = argparse.ArgumentParser()
parser.add_argument("-l", "--league", help="The league id of interest", required=True)


def main():
    args = parser.parse_args()
    command_args = dict(vars(args))
    league_id = command_args.pop("league", None)
    base_url = "https://ottoneu.fangraphs.com"
    today = date.today()
    if today.month < 4:
        current_year = today.year - 1
    else:
        current_year = today.year
    auction_url = f"{base_url}/{league_id}/auctions"
    resp = requests.get(auction_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    auctions = (
        soup.find("main")
        .find("section")
        .find("div", {"class": "table-container"})
        .find("table")
        .find_all("tr")
    )
    headers = [th.get_text().strip() for th in auctions.pop(0).find_all("th")]

    auction_players = list()
    for elem in tqdm(auctions):
        # workaround for days with no auctions
        if elem.find("a") is None:
            break
        player_dict = dict()
        # player_name
        player_dict["Player Name"] = elem.find("a").get_text().strip()
        player_page_url = elem.find("a")["href"]
        player_info = elem.find("span").get_text().split()
        player_dict["Hand"] = player_info.pop()
        if len(player_info) == 3:
            # if the player is MiLB, then remove the level
            player_info.pop(0)
        player_dict["Position"] = player_info.pop()
        player_dict["Team"] = player_info.pop()
        player_dict["ottoneu_id"] = player_page_url.rsplit("=")[1]
        player_salary_dict = get_ottoneu_player_page(
            player_dict["ottoneu_id"], league_id
        )
        player_dict.update(player_salary_dict)

        # turn this piece into a method?
        player_name = clean_name(player_dict["Player Name"])
        first_name, last_name = player_name.split(maxsplit=1)

        if player_dict["is_mlb"]:
            if "." in first_name:
                # lookup has "A.J." as "A. J." for some reason
                first_name = first_name.replace(".", ". ").strip()
            id_lookup = playerid_lookup(last_name, first_name)
            if id_lookup.shape[0] > 1:
                player_dict["mlbam_id"] = id_lookup.loc[
                    id_lookup.mlb_played_last == id_lookup.mlb_played_last.max()
                ].key_mlbam.values[0]
            elif id_lookup.shape[0] == 1:
                player_dict["mlbam_id"] = id_lookup.key_mlbam.values[0]
            else:
                player_dict["mlbam_id"] = None

        is_hitter, is_pitcher = get_position_group(player_dict["Position"])
        player_dict["is_hitter"] = is_hitter
        player_dict["is_pitcher"] = is_pitcher

        auction_players.append(player_dict)

    hitters = [player for player in auction_players if player["is_hitter"]]
    pitchers = [player for player in auction_players if player["is_pitcher"]]
    if hitters:
        # setting minBBE = 0 to avoid not getting someone
        # get rid of this indentation and just pull exit velo #s regardless?
        exit_velo_data = statcast_batter_exitvelo_barrels(current_year, minBBE=0)
        percentile_ranks = statcast_batter_percentile_ranks(current_year)
        exp_stats = statcast_batter_expected_stats(current_year, minPA=0)
        for player in hitters:
            if not player["is_mlb"] or not player["mlbam_id"]:
                # avoid index error for minor leaguers
                continue
            player_exit_velo = (
                exit_velo_data.loc[exit_velo_data.player_id == player["mlbam_id"]]
                .to_dict("records")
                .pop()
            )
            player_pctl_ranks = (
                percentile_ranks.loc[percentile_ranks.player_id == player["mlbam_id"]]
                .to_dict("records")
                .pop()
            )
            player_exp_stats = (
                exp_stats.loc[exp_stats.player_id == player["mlbam_id"]]
                .to_dict("records")
                .pop()
            )
            player["avg_exit_velo"] = player_exit_velo["avg_hit_speed"]
            player["max_exit_velo"] = player_exit_velo["max_hit_speed"]
            player["exit_velo_pctl"] = player_pctl_ranks["exit_velocity"]
            player["barrel_pa_rate"] = player_exit_velo["brl_pa"]
            player["barrel_bbe_rate"] = player_exit_velo["brl_percent"]
            player["barrel_bbe_pctl"] = player_pctl_ranks["brl_percent"]
            player["xwoba"] = player_exp_stats["xwoba"]
            player["woba_diff"] = player_exp_stats["est_woba_minus_woba_diff"]
            player["xwoba_pctl"] = player_pctl_ranks["xwoba"]

    if pitchers:
        # what to add for pitchers?
        percentile_ranks = statcast_pitcher_percentile_ranks(current_year)
        exp_stats = statcast_pitcher_expected_stats(current_year, 0)
        for player in pitchers:
            if not player["is_mlb"] or not player["mlbam_id"]:
                continue
            player_pctl_ranks = (
                percentile_ranks.loc[percentile_ranks.player_id == player["mlbam_id"]]
                .to_dict("records")
                .pop()
            )
            player_exp_stats = (
                exp_stats.loc[exp_stats.player_id == player["mlbam_id"]]
                .to_dict("records")
                .pop()
            )
            player["k_pctl"] = player_pctl_ranks["k_percent"]
            player["bb_pctl"] = player_pctl_ranks["bb_percent"]
            player["whiff_pctl"] = player_pctl_ranks["whiff_percent"]
            player["xwoba"] = player_exp_stats["xwoba"]
            player["woba_diff"] = player_exp_stats["est_woba_minus_woba_diff"]
            player["era_diff"] = player_exp_stats["era_minus_xera_diff"]

    hitter_columns = [
        "Player Name",
        "Hand",
        "Position",
        "Hand",
        "is_mlb",
        "All - Avg",
        "All - Med",
        "H2H - Avg",
        "H2H - Med",
        "All - Avg - L10",
        "All - Med - L10",
        "H2H - Avg - L10",
        "H2H - Med - L10",
        "avg_exit_velo",
        "max_exit_velo",
        "exit_velo_pctl",
        "barrel_pa_rate",
        "barrel_bbe_rate",
        "barrel_bbe_pctl",
        "xwoba",
        "woba_diff",
        "xwoba_pctl",
    ]
    pitcher_columns = [
        "Player Name",
        "Hand",
        "Position",
        "Hand",
        "is_mlb",
        "All - Avg",
        "All - Med",
        "H2H - Avg",
        "H2H - Med",
        "All - Avg - L10",
        "All - Med - L10",
        "H2H - Avg - L10",
        "H2H - Med - L10",
        "k_pctl",
        "bb_pctl",
        "whiff_pctl",
        "xwoba",
        "woba_diff",
        "era_diff",
    ]

    hitters = [
        {k: v for k, v in hitter.items() if k in hitter_columns} for hitter in hitters
    ]
    pitchers = [
        {k: v for k, v in pitcher.items() if k in pitcher_columns}
        for pitcher in pitchers
    ]

    html = format_html(hitters, pitchers, league_id)
    print(html)

    # get names via lookup. use cache.enable() for pybaseball here?
    # get statcast data for individual players or for league and then search for players?


if __name__ == "__main__":
    main()
