#!/bin/bash
# One-shot manual run: hunter + reporter + open the summary.
#
# Usage:
#   ./run.sh             # full pipeline (Slickdeals live + Keepa if configured)
#   ./run.sh --offline   # use sample data instead of live fetch
#   ./run.sh --quick     # skip Keepa even if KEEPA_API_KEY is set
#
# Make executable once:  chmod +x run.sh
# Then run with:         ./run.sh

set -e
cd "$(dirname "$0")"

EXTRA_ARGS=""
TELEGRAM_ARG=""
for arg in "$@"; do
  case "$arg" in
    --offline) EXTRA_ARGS="$EXTRA_ARGS --offline" ;;
    --quick) EXTRA_ARGS="$EXTRA_ARGS --no-keepa" ;;
    --no-telegram) TELEGRAM_ARG="" ;;
    --telegram) TELEGRAM_ARG="--telegram" ;;
    *) EXTRA_ARGS="$EXTRA_ARGS $arg" ;;
  esac
done

if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ] && [ -z "$TELEGRAM_ARG" ]; then
  TELEGRAM_ARG="--telegram"
fi

echo ""
echo "=== Deal Hunter ==="
python3 hunter.py $EXTRA_ARGS 2>&1 | tee run.log

echo ""
echo "=== Reporter ==="
python3 reporter.py --top 10 $TELEGRAM_ARG

echo ""
echo "=== Done ==="
echo "Opening executive summary..."
if command -v open >/dev/null 2>&1; then
  open executive_summary.md
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open executive_summary.md
fi
