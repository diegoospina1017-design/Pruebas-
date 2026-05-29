# Amazon Arbitrage Toolkit

Personal Amazon FBA arbitrage automation for Kelly Riveros (Christiansburg, VA, USA).
This file briefs any AI assistant (Claude Code, Cursor, etc.) on the project state
so a fresh session can pick up immediately.

---

## Project context

**Owner**: Kelly Riveros — pre-launch FBA seller based in Christiansburg, Virginia (ZIP 24073).
Has not opened an Amazon Seller Professional account yet. Has not made first FBA sale yet.
Email: diego.ospina@tekni-plex.com

**Goal**: Build an automated pipeline that finds arbitrage opportunities — products to buy
in physical/online US retailers and resell on Amazon FBA at 30%+ ROI.

**Repo**: `github.com/diegoospina1017-design/Pruebas-`
**Working branch**: `claude/adoring-fermat-SGK5v`
**Working directory on her Mac**: `~/Documents/Pruebas-/amazon-arbitrage/deal_hunter/`

**Hardware**: Mac (zsh shell), Python 3.14 via Homebrew.

---

## Directory layout

```
amazon-arbitrage/
├── calculator/                  FBA fee + shipping cost math
│   ├── fees.py                  Referral fees, FBA fulfillment, storage tables (2024-2025)
│   ├── shipping.py              UPS Ground rates from 24073 (Christiansburg VA) to FBA hubs
│   └── profit.py                Profit/ROI calculator with interactive mode
│
├── tracker/                     CSV inventory tracker
│   ├── inventory_tracker.csv    Template with 2 example rows
│   └── README_TRACKER.md        Column-by-column guide
│
├── deal_hunter/                 Main agents directory
│   ├── CLAUDE.md                This file
│   │
│   ├── sources/
│   │   ├── slickdeals.py        Fetches public Slickdeals RSS feeds
│   │   ├── keepa.py             Keepa API client (search, products_bulk)
│   │   ├── keepa_debug.py       Diagnostic for raw Keepa responses
│   │   └── sample_deals.json    Offline test data
│   │
│   ├── sourcing_from_excel.py   Reads Keepa best-sellers Excel exports → sourcing_*.json
│   ├── find_niches.py           Re-ranks viables by opportunity score (not just margin)
│   ├── refresh_targets.py       Re-checks top niches against current Keepa data
│   │
│   ├── hunter.py                Main daily hunter (Slickdeals → filter → analyze → notify)
│   ├── filters.py               Rule engine for hunter
│   ├── analyzer.py              Bridges deals to the calculator + optional Keepa lookup
│   ├── target_matcher.py        Cross-checks Slickdeals deals against sourcing targets
│   ├── notifier.py              macOS notifications + Telegram bot integration
│   ├── reporter.py              Aggregates everything into executive_summary.md
│   ├── report.py                Renders hunter.py's report.md
│   │
│   ├── gemini_searcher.py       Gemini 2.5 Flash + Google Search grounding agent
│   ├── claude_searcher.py       Claude Opus 4.7 + web_search tool agent
│   │
│   ├── run.sh                   One-shot: hunter + reporter + open summary
│   ├── config.json              Filter rules (price, discount, retailers, keywords)
│   ├── asin_map.json            Manual ASIN → Amazon data cache (sample entries)
│   │
│   ├── targets_list.txt         100 ASINs (initial Keepa export)
│   ├── *_keepa.xlsx             Raw Keepa Best Sellers Excel exports
│   │
│   └── sourcing_*.json          Processed sourcing target lists (committed, ~82 viable total)
│                                Files: sourcing_pet_supplies_keepa.json (14 viable),
│                                       sourcing_sports_outdoors_keepa.json (39),
│                                       sourcing_toys_games_keepa.json (29)
```

### Files that get regenerated (gitignored)

These are produced by the scripts and should never be committed:
- `report.md` — hunter output
- `executive_summary.md` — reporter output
- `niches.json`, `niches_report.md` — find_niches output
- `refresh.json`, `refresh_report.md` — refresh_targets output
- `claude_deals.json`, `claude_report.md` — claude_searcher output
- `gemini_deals.json`, `gemini_report.md` — gemini_searcher output
- `candidates.json` — analyzer JSON
- `run.log`

---

## Environment variables

| Variable | Status | Purpose |
|---|---|---|
| `KEEPA_API_KEY` | Configured (free tier, 1 token/min) | Used by `refresh_targets.py` and `hunter.py --keepa` |
| `GEMINI_API_KEY` | Configured (free tier) | Used by `gemini_searcher.py` |
| `ANTHROPIC_API_KEY` | NOT configured | Would be used by `claude_searcher.py` if she pays |
| `TELEGRAM_BOT_TOKEN` | NOT configured | Optional notifier channel |
| `TELEGRAM_CHAT_ID` | NOT configured | Optional notifier channel |

Persisted via `~/.zshrc`.

---

## External services

| Service | Account status | Plan |
|---|---|---|
| Keepa | Active | **Free tier** — 1 token/min refill, low bucket. Used for product data refresh. |
| Google AI Studio (Gemini) | Active | **Free tier** — 15 req/min on `gemini-2.5-flash` |
| Anthropic Console | NOT created | Would cost ~$0.18/run if activated |
| Amazon Seller Professional | NOT created | $39.99/mo when activated |
| Target RedCard | NOT applied | 5% off automatic — discussed, not done |
| Payoneer / Wise | NOT needed | She is US-based, regular US bank works |
| Telegram BotFather | NOT set up | Optional alerts |

---

## Strategy decisions (already made)

1. **Hidden gems > best sellers.** Top BSR products have brutal competition and gated brands. Real money is in BSR 5K-100K with 1-5 FBA sellers and non-gated brands. `find_niches.py` enforces this scoring.

2. **Strict brand match.** Same generic product from different brand = SKIP. Causes "not as described" returns and Amazon account suspension. `gemini_searcher.py` and `claude_searcher.py` system prompts enforce this character-for-character.

3. **Minimum $1 margin between deal_price and max_buy.** A $0.07 margin gets wiped out by one return. The agent prompts skip deals within $1 of max buy.

4. **Confidence medium + caveats = treat as near-miss, not hot buy.** Learned the hard way from the Woof Pupsicle false-positive — Gemini's notes warned "out of stock" and "pack size doesn't match" but the report classified it as HOT BUY. Improvement still pending.

5. **Focus categories**: Sports & Outdoors (best), Toys & Games (good), Pet Supplies (decent — supplements not food). Avoid Home consumables, Health & Personal Care, Grocery, Beauty (heavily gated).

6. **Christiansburg VA shipping baseline.** All FBA inbound shipping calculations assume ZIP 24073 → typical FBA hub (CLT, ATL, GSP). Uses Amazon Partnered Carrier rate (~35% discount on UPS Ground).

7. **Output formats**:
   - `*_deals.json` for the hunter pipeline (machine-readable)
   - `*_report.md` for human reading (HOT BUYS / near-miss / not-found-yet sections)

---

## Common commands

### Daily

```bash
cd ~/Documents/Pruebas-/amazon-arbitrage/deal_hunter

# Slickdeals + cross-check (FREE)
./run.sh

# Gemini web search (~$0.04, also runs free tier)
python3 gemini_searcher.py --limit 30 --include-gated
```

### Weekly

```bash
# Validate top niches against current Keepa data (~22 Keepa tokens)
python3 refresh_targets.py --limit 20

# Regenerate niches.json (free, no API)
python3 find_niches.py --exclude-gated
```

### Monthly

```bash
# Process new Keepa Best Sellers Excel exports
python3 sourcing_from_excel.py new_category.xlsx

# Then regenerate niches and run searcher
python3 find_niches.py --exclude-gated
python3 gemini_searcher.py --limit 30
```

### Alias she uses

```bash
alias hunt="cd ~/Documents/Pruebas-/amazon-arbitrage/deal_hunter && git pull && python3 find_niches.py --exclude-gated && python3 gemini_searcher.py --from-niches --limit 15 && open gemini_report.md"
```

---

## Known issues / gotchas

1. **Git SSL fails on her corporate network** (Tekni-Plex). The `git pull` returns SSL cert errors or 403. Workarounds:
   - `GIT_SSL_NO_VERIFY=true git pull` (one-off bypass)
   - Switch to home WiFi
   - Future: install `gh` CLI for proper auth

2. **`gh` CLI not installed.** Install when convenient:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install gh
   gh auth login
   ```

3. **`datetime.utcnow()` DeprecationWarning** in `gemini_searcher.py` line 322. Cosmetic, doesn't break anything. Fixed in repo commit but her local copy may still have it if she patched manually.

4. **Python 3.14 + openpyxl** sometimes needs `--break-system-packages` flag on install.

5. **Records missing `sale_price`**: some viable entries in old sourcing JSONs could lack `sale_price`. Searchers now filter these defensively. Regenerate by running `sourcing_from_excel.py` on the .xlsx files if it keeps warning.

6. **Comment lines (`#`) pasted in zsh** return "command not found". Harmless — she's been told to skip those or run `setopt interactive_comments`.

7. **Gemini 503 UNAVAILABLE** during peak Google demand. `gemini_searcher.py` retries 4 times with exponential backoff (5s/10s/20s/40s). If still failing, try later or smaller `--limit`.

---

## Pending work / decisions

Things discussed but not yet implemented:

| Item | Status |
|---|---|
| Auto-demote `confidence: medium` deals with caveats to near-miss | Discussed, not coded |
| Add DealNews and BrickSeek as additional Slickdeals-like sources | Mentioned, not coded |
| Telegram bot integration | Code exists in `notifier.py`, user has not set up bot |
| Price-drop watcher (alerts when target ASIN drops below max buy) | Discussed for future |
| Keepa Product Finder integration (auto-discovery of hidden gems) | Future, requires more tokens |
| SP-API integration (for restrictions check, listing creation) | Future, requires active Seller account |
| Cron / launchd scheduled runs | Discussed, not yet scheduled |

---

## Active opportunity to watch (as of last session)

**Zesty Paws Wild Alaskan Omega-3 Blend** (ASIN `B0CXKHT5K2`)
- Currently at Target.com: $12.99
- Her max buy: $12.92
- Difference: $0.07 over
- **With Target RedCard 5%**: $12.34 → **$0.58 below max buy = viable**

Action: If she gets RedCard, this is her likely first FBA purchase candidate.

---

## False positive learned

**Woof Pupsicle Refill Pops** (ASIN `B0FY32LBVV`) was flagged as HOT BUY by Gemini at $14.99 from Rocky & Maggie's. Investigation revealed:
- Listing was OUT OF STOCK (Gemini noted this in description)
- Pack size didn't match (target ASIN didn't specify; deal showed 7 or 10 pops)
- Flavor mismatch (target said "Peanut Butter and Chicken"; alternate retailers showed "Peanut Butter & Beef")

Lesson: prompt now requires exact brand + pack + flavor match. Future improvement: auto-demote any deal with caveat words in notes ("but", "however", "out of stock", "implying", "doesn't match").

---

## Anti-patterns / things NOT to do

- Don't restore Anthropic API code paths into Gemini's file (user explicitly chose Gemini for now)
- Don't add new categories of products without running them through find_niches first
- Don't commit `*_deals.json`, `*_report.md`, `niches.json` — all in .gitignore
- Don't relax the strict brand-match rules in agent system prompts
- Don't suggest she buys before she has Amazon Seller account set up
- Don't recommend chasing mainstream gated brands (Hydro Flask, Stanley, Pokemon, etc.) until she's verified gating per-ASIN in Amazon Seller App

---

## Quick mental model

```
Keepa best-seller Excel  →  sourcing_from_excel.py  →  sourcing_*.json (viables)
                                                              │
                                                              ▼
                                                        find_niches.py
                                                              │ (opportunity scoring)
                                                              ▼
                                                          niches.json
                                                              │
                                          ┌───────────────────┼───────────────────┐
                                          ▼                   ▼                   ▼
                              gemini_searcher.py    refresh_targets.py     hunter.py
                              (web search Google)   (re-validate Keepa)    (Slickdeals)
                                          │                   │                   │
                                          └─────────┬─────────┴─────────┬─────────┘
                                                    ▼                   ▼
                                              *_report.md       executive_summary.md
                                                                        │
                                                                        ▼
                                                          macOS notification + (Telegram)
```
