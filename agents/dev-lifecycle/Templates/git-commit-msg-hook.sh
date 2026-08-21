#!/usr/bin/env bash
# git commit-msg hook: enforce the issue-number prefix on commit messages.
#
# This is the git expression of `check-commit-prefix` in
# References/hook-contract.md. It is the preferred one: it runs for
# every commit in the clone regardless of which harness — or no
# harness — made it, and unlike a harness hook it can reject.
#
# Install (per clone; git hooks never travel with a push):
#   cp <agent>/Templates/git-commit-msg-hook.sh .git/hooks/commit-msg
#   chmod +x .git/hooks/commit-msg
#
# Or version it with the repo:
#   mkdir -p .githooks
#   cp <agent>/Templates/git-commit-msg-hook.sh .githooks/commit-msg
#   chmod +x .githooks/commit-msg
#   git config core.hooksPath .githooks
#
# Format enforced: #NNNN: message
#              or: owner/repo#NNNN: message   (cross-repo reference)
#
# Merge commits, fixup/squash commits, and reverts are exempt.
#
# This is bash rather than Python on purpose. It runs on every commit
# in a user's repository, so it must not add an interpreter dependency
# the repository did not already have. The Python-first rule in
# ARCHITECTURE.md governs `Tools/` — code this agent runs — not a file
# a user installs into their own clone.

COMMIT_MSG_FILE="$1"

# Read the first non-blank, non-comment line
COMMIT_MSG=""
while IFS= read -r line; do
    case "$line" in
        ""|\#\ *|\#[[:space:]]*) continue ;;   # blank or git comment
    esac
    COMMIT_MSG="$line"
    break
done < "$COMMIT_MSG_FILE"

# Empty message — let git handle it
[ -z "$COMMIT_MSG" ] && exit 0

# Allow merge commits
echo "$COMMIT_MSG" | grep -qE '^Merge ' && exit 0

# Allow fixup/squash commits
echo "$COMMIT_MSG" | grep -qE '^(fixup|squash)! ' && exit 0

# Allow reverts
echo "$COMMIT_MSG" | grep -qE '^Revert ' && exit 0

# Require the issue prefix
if ! echo "$COMMIT_MSG" | grep -qE '^([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#[0-9]+: .+'; then
    echo "ERROR: Commit message must start with an issue-number prefix."
    echo "  Format: #1234: descriptive message"
    echo "      or: owner/repo#1234: descriptive message"
    echo "  Got:    $COMMIT_MSG"
    echo ""
    echo "  Merge, fixup!/squash!, and Revert commits are exempt."
    exit 1
fi

exit 0
