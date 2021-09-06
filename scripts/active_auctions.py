# get date and league through argv or argparse
# get auctions started and players cut from that day
# using pybaseball, scrape statcast info
# v2: scrape RoS steamer / zips projections
import argparse

import auction_utils
from ottoneu_league import ottoneuLeague
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument("-l", "--league", help="The league id of interest", required=True)


def main():
    args = parser.parse_args()
    command_args = dict(vars(args))
    league_id = command_args.pop("league", None)
    otto_league = ottoneuLeague(league_id)
    otto_league.setup_league_params()
    auctions = otto_league.get_players(is_waiver=False)
    waivers = otto_league.get_players(is_waiver=True)

    auction_players = list()
    # add check to see if there are auctions?
    # everything same for waivers, just the claim/bid header
    for elem in tqdm(auctions):
        # workaround for days with no auctions
        if elem.find("a") is None:
            break
        player_dict = auction_utils.get_player_page(elem)

        is_hitter, is_pitcher = auction_utils.get_position_group(
            player_dict["Position"]
        )
        player_dict["is_hitter"] = is_hitter
        player_dict["is_pitcher"] = is_pitcher

        # why not just get the position groups here and pass whole dict in?
        player_dict = auction_utils.get_ottoneu_player_page(player_dict, otto_league)

        player_dict["mlbam_id"] = auction_utils.get_mlbam_id(player_dict)

        auction_players.append(player_dict)

    hitters = [player for player in auction_players if player["is_hitter"]]
    pitchers = [player for player in auction_players if player["is_pitcher"]]

    hitters = auction_utils.get_hitters_statcast(hitters, otto_league)
    pitchers = auction_utils.get_pitchers_statcast(pitchers, otto_league)

    html = auction_utils.format_html(hitters, pitchers, league_id)
    print(html)


if __name__ == "__main__":
    main()
