# Diamond Edge MLB v6

Version 6 fixes the missing-player-props problem by using The Odds API's event-level odds endpoint.

## New features
- Loads MLB player props one game at a time
- Supports pitcher strikeouts, outs, hits allowed, walks, earned runs, and win props
- Supports batter total bases, hits, home runs, RBIs, runs, H+R+RBI, walks, strikeouts, singles, doubles, triples, and stolen bases
- Shows every sportsbook price
- Shows the best price for each exact player, side, and line
- Ranks line-shopping value using a no-vig sportsbook consensus
- Displays estimated API-credit usage before loading
- Provides CSV downloads

## Important
The Odds API charges event-level requests by markets × regions. Start with 3–5 games and your favorite markets to conserve credits.

## Upload
Replace all six files:
- app.py
- constants.py
- data_sources.py
- model.py
- requirements.txt
- README.md

## Streamlit secret
```toml
ODDS_API_KEY = "your_key_here"
```
