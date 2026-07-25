# Diamond Edge MLB v5

A modular MLB betting-research dashboard.

## Connected
- MLB schedule, standings, probable pitchers, and pitcher season stats
- Open-Meteo game-time weather
- The Odds API moneylines, spreads, and totals
- Fair odds, edge, expected value, projected totals
- Session bet tracker with CSV export

## Honest limitations
Confirmed lineups, injuries, umpire assignments, advanced Statcast splits, and live player props require more data connections. The app labels these instead of generating fake information.

## Upload to GitHub
Replace the prior project with all six files:
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
