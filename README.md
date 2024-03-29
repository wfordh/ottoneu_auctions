# Ottoneu Auctions

This repository runs a script to help decision making in free agent auctions for my Ottoneu league and deploys the gathered information in HTML tables to a web page using GitHub actions and pages.

## Usage
All the end user needs to do is visit [this page](https://wfordh.github.io/ottoneu_auctions) to see all of the leagues whose auctions are actively being checked.

## How It Works
The script pulls the active auctions for the league each day at approximately 7 am PST. If there are active auctions, then it hits the players' Ottoneu pages for basic player info before pulling down the statcast leaderboards and getting the selected data points there.

## TO DO
- Figure out why `playerid_lookup()` prints the message each time. Either get it to stop printing each time or find a way to filter that out of the web page.
- Stretch goal for this project is to make it possible to enter your league number and get that day's auctions, which effectively extends it to any league. Streamlit, [hex](https://hex.tech/) and PyWebIO are options.
- Curate columns for HTML more
- Add Fangraphs' projections for RoS. Preferably an average of Depth Charts, ZiPS, Steamer, and THE BAT, converted to the FG Points system for Ottoneu.
  - Might be something to add to `pybaseball`
- Change percentiles to ints instead of floats. Not currently possible b/c of `NaN` percentiles
- Get better check to see if statcast data available for player's current year
- Safely fail individual players so that the run itself doesn't fail
- Combine stats when player appears for multiple teams? How to handle multiple teams vs multiple levels?
- Better handle 5x5 pulls
- Have example page to see during the offseason
