#!/bin/bash
# push.sh — one command instead of add/commit/push every time.
#
# Usage:
#   ./push.sh "Day 2: added ball-by-ball models"
#
# If no message is given, it auto-generates one with a timestamp.

set -e  # stop immediately if any git command fails

MSG="${1:-Update $(date '+%Y-%m-%d %H:%M')}"

git add .
git commit -m "$MSG" || echo "Nothing new to commit."
git push

echo "✅ Pushed: $MSG"
