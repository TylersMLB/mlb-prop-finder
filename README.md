# Diamond Edge MLB v3

Version 3 adds a real data-driven MLB moneyline model and a light, easier-to-read design.

## New in this version

- Light background and dark text
- Current MLB schedule
- Current standings and run differential
- Probable pitcher statistics
- Model win probabilities
- Model fair moneyline odds
- Best sportsbook moneyline price
- Edge and expected value
- Green, yellow, and red bet grades
- Game-by-game model explanations

## Install

Replace the existing files in your GitHub repository with:

- `app.py`
- `requirements.txt`
- `README.md`

Commit the changes. Streamlit should automatically redeploy.

## Live odds

In Streamlit Secrets, add:

```toml
ODDS_API_KEY = "your_key_here"
```

Without the key, the model still produces game predictions and fair odds.

## Important

This version is data-driven but is not yet a trained machine-learning model. Weather, injuries, confirmed lineups, bullpen workload, umpire data, and player-prop projections are planned next.
