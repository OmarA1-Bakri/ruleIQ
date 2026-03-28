#!/usr/bin/env bash
# Remove historical secrets from Git using git-filter-repo.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "❌ This script must be run inside a Git repository." >&2
  exit 1
fi

cd "${REPO_ROOT}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "❌ Working tree is dirty. Commit or stash changes before rewriting history." >&2
  exit 1
fi

if ! command -v git-filter-repo >/dev/null 2>&1 && ! command -v git filter-repo >/dev/null 2>&1; then
  cat >&2 <<'MSG'
❌ git-filter-repo is required.
Install via:
  pip install git-filter-repo
or
  brew install git-filter-repo (macOS)
MSG
  exit 1
fi

if [[ "${ALLOW_HISTORY_REWRITE:-}" != "true" ]]; then
  cat >&2 <<'MSG'
⚠️  History rewrite is destructive.
Set ALLOW_HISTORY_REWRITE=true to acknowledge you have backups and rotated secrets.
Example:
  ALLOW_HISTORY_REWRITE=true scripts/tools/purge_secrets.sh
MSG
  exit 1
fi

BACKUP_REF="rewrite-backup-$(date +%Y%m%d-%H%M%S)"
BACKUP_BRANCH="refs/backup/${BACKUP_REF}"
REPLACEMENTS_FILE="${SECRETS_REPLACEMENTS_FILE:-scripts/tools/purge_secrets.local.txt}"

echo "📦 Creating safety tag ${BACKUP_REF}..."
git update-ref "${BACKUP_BRANCH}" HEAD

if [[ ! -f "${REPLACEMENTS_FILE}" ]]; then
  cat >&2 <<MSG
❌ Replacement file not found: ${REPLACEMENTS_FILE}

Create a local replacement file using the format documented in:
  scripts/tools/purge_secrets.example.txt

Then run:
  SECRETS_REPLACEMENTS_FILE=${REPLACEMENTS_FILE} ALLOW_HISTORY_REWRITE=true scripts/tools/purge_secrets.sh
MSG
  exit 1
fi

echo "🧹 Running git-filter-repo..."
if command -v git-filter-repo >/dev/null 2>&1; then
  FILTER_REPO="git-filter-repo"
else
  FILTER_REPO="git filter-repo"
fi

${FILTER_REPO} --force --replace-text "${REPLACEMENTS_FILE}"

echo "✅ History rewrite complete. Backup ref stored at ${BACKUP_BRANCH}."
echo "Next steps:"
echo "  1. Verify: git log --stat --since=1.month"
echo "  2. Force push once satisfied: git push origin --force --all && git push origin --force --tags"
echo "  3. Coordinate with team to reclone repositories."
