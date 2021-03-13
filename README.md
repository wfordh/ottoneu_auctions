# ottoneu_auctions

This repository runs a script to help decision making in free agent auctions for my Ottoneu league and deploys the gathered information in HTML tables to a web page using GitHub actions and pages. It is currently only set up for one league, though I hope to set it up for multiple in the near future.

## TO DO
- Figure out why `playerid_lookup()` prints the message each time. Either get it to stop printing each time or find a way to filter that out of the web page.
- Extend it to both of my leagues, preferably with an index page that links to individual pages for each league.
- Stretch goal for this project is to make it possible to enter your league number and get that days auctions, which effectively extends it to any league.
- Remove test variables and move GH action trigger to cron from push
- Once season starts, rework it to get active auctions instead of transactions
- Refactor so logic and UI are more effectively split. May require making a class
- Add date to HTML
