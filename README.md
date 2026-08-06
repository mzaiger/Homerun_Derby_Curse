# Home Run Derby Curse 🏆

A tracker for the "Home Run Derby Curse" — the long-running baseball superstition that players who participate in the MLB Home Run Derby see their second-half power numbers drop off. The project pulls each derby contestant's pre- and post-All-Star-break hitting splits from the MLB Stats API and displays the year-over-year "curse" effect in a simple web page.

## How it works

- **`Contestants.json`** — the source list of every Home Run Derby field by year, including the winner and runner-up.
- **`GetSplitsDerbyPlayers.py`** — fetches each contestant's 1st-half (`preas`) and 2nd-half (`posas`) hitting splits from the [MLB Stats API](https://statsapi.mlb.com/) and writes the results to `derby_splits.json`.
- **`derby_splits.json`** — the generated dataset consumed by the web page. It holds one record per contestant per year.
- **`index.html`** — a static, single-page dashboard that reads `derby_splits.json` and color-codes each player's home-run drop-off between halves.

## Keeping stats current

`GetSplitsDerbyPlayers.py` only fetches and refreshes data for the **current calendar year**. It looks up that year's contestant list in `Contestants.json`, pulls fresh splits for just those players, and merges the result back into `derby_splits.json` — leaving every prior year's data untouched. This keeps the in-season numbers (like the current 2nd-half stats) up to date without re-processing the entire historical archive on every run.

If no contestants are listed yet for the current year (e.g. before the derby field is announced), the script exits without making any changes.

### Run it manually

```bash
pip install -r requirements.txt
python GetSplitsDerbyPlayers.py
```

## Automated daily updates

A GitHub Actions workflow (`.github/workflows/update-splits.yml`) runs the script once a day, and also supports being triggered manually from the **Actions** tab (`workflow_dispatch`). When the script produces changes, the workflow commits the updated `derby_splits.json` straight back to the repository.

- **Schedule:** daily at 09:00 UTC (edit the `cron` line in the workflow file to change this)
- **Permissions:** the workflow needs `contents: write` (already set) so it can push its commit
- **No secrets required:** the MLB Stats API is public, and the workflow uses the automatically provided `GITHUB_TOKEN` to push commits

## Project structure

```
.
├── Contestants.json                    # Source list of derby fields by year
├── GetSplitsDerbyPlayers.py            # Fetches & merges current-year splits
├── derby_splits.json                   # Generated dataset used by the site
├── index.html                          # Static dashboard
├── requirements.txt                    # Python dependencies
└── .github/workflows/update-splits.yml # Daily automation
```

## Data source

All player stats come from the public [MLB Stats API](https://statsapi.mlb.com/). This project is unofficial and not affiliated with MLB.
