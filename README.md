# Diamond Edge Pro v8

Version 8 changes Player Props from a raw price board into a ranked shortlist.

## Main improvement
- Shows only the strongest player props by default
- Keeps one best prop per player
- Requires configurable sportsbook coverage
- Filters by minimum edge
- Ranks by no-vig consensus, expected value, price quality, and book coverage
- Keeps all raw prices hidden in an optional expander
- Downloads only the best-props shortlist

## Upload
Replace all six files in GitHub:
- app.py
- constants.py
- data_sources.py
- model.py
- requirements.txt
- README.md

Keep your existing `ODDS_API_KEY` in Streamlit Secrets.

## Important
The free version ranks line-shopping value using sportsbook consensus. It does not yet contain a separately trained player-performance projection model.
