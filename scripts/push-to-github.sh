#!/usr/bin/env bash
# Pushes this project to GitHub safely.   bash scripts/push-to-github.sh ["commit message"]
# It refuses to push if a secret file would be included.
set -u
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
REPO_URL="https://github.com/neminorniel24-droid/nemin-s-FRIDAY.git"
MSG="${1:-NEMIII v17: studio, natural voice, progress bar, creations viewer, pause and stop}"

command -v git >/dev/null || { echo "git is not installed"; exit 1; }
[ -d .git ] || { git init -q -b main && git remote add origin "$REPO_URL"; echo "Started a new git repository here."; }
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REPO_URL"
git config user.name  >/dev/null || git config user.name  "Nemin Orniel D"
git config user.email >/dev/null || { echo "Set your email first:  git config --global user.email you@example.com"; exit 1; }

# make sure the secret files are ignored, then look at what would be uploaded
git add -A >/dev/null 2>&1
BAD=$(git diff --cached --name-only | grep -E '(^|/)(\.env|\.env\..*|credentials\.json|token\.json)$|backend/data/|\.pem$|\.key$|id_rsa|\.zip$|\.mp4$|\.task$' | grep -v -E '\.env\.example$|\.env\.local\.example$')
if [ -n "$BAD" ]; then
  echo "STOP. These files must never be pushed:"; echo "$BAD"
  git reset -q; echo "Nothing was staged. Add them to .gitignore and run again."; exit 1
fi
# look inside the files for key-looking text
if git diff --cached -U0 | grep -E '^\+' | grep -E 'gsk_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{30,}' >/dev/null; then
  echo "STOP. Something that looks like a real API key is in the files. Remove it, then run again."
  git reset -q; exit 1
fi

echo; git status --short | head -40; echo
read -r -p "Push these to $(git remote get-url origin)? [y/N] " a
[ "$a" = y ] || { git reset -q; echo "Cancelled."; exit 0; }

git commit -q -m "$MSG" || echo "(nothing new to commit)"
git branch -M main
git pull --rebase origin main 2>/dev/null || true
git push -u origin main && echo "Pushed. Open: ${REPO_URL%.git}" || {
  echo "Push failed. If it asks for a password, use a Personal Access Token (GitHub > Settings > Developer settings),"
  echo "or run:  gh auth login   and try again."; exit 1; }
