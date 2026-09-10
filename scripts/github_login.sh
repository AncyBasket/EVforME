#!/bin/zsh
export PATH="/opt/homebrew/bin:$PATH"
echo "Apro login GitHub CLI…"
gh auth login --hostname github.com --git-protocol https --web
gh auth status
gh api user --jq '"Loggato come: \(.login)"'
