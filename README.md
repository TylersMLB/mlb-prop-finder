# Diamond Edge Pro V8.3 — Single File Fix

This version eliminates all local Python-module imports.

## Delete from GitHub
Delete these old files if they exist:
- model.py
- edge_model.py
- data_sources.py
- constants.py

## Keep/upload only
- app.py
- requirements.txt
- README.md

The files must be in the repository root, not inside a folder.

In Streamlit Advanced settings, the main file path must be:

app.py

Keep your secret:

```toml
ODDS_API_KEY = "your_actual_key"
```
