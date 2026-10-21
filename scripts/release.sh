#!/usr/bin/env bash
# Prepare a g-usi release tag. See docs/COMPAT.md ("Releases and
# versioning") for the scheme: annotated vX.Y.Z tags, cut from dev.
#
# This script PREPARES ONLY. It creates the tag locally and prints the
# push command; the human executes the push (and mirror syncs). Run it
# from a checkout whose HEAD is exactly origin/dev - i.e. right after
# the release's PR merged and you pulled.
#
# Usage:
#   scripts/release.sh vX.Y.Z [--dry-run]
#
# --dry-run: run every check (including nix flake check) and print
# what would happen, but create no tag. The HEAD==origin/dev gate is a
# warning in dry-run so releases can be rehearsed from feature
# branches.
set -euo pipefail

say()  { printf '%s\n' "$*"; }
err()  { printf 'release.sh: %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

TAG=""
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '/^# Prepare a g-usi release tag\./,/^# branches\.$/p' "$0"; exit 0 ;;
    *) [ -z "$TAG" ] && TAG="$arg" || die "unexpected argument: $arg (usage: $0 vX.Y.Z [--dry-run])" ;;
  esac
done
[ -n "$TAG" ] || die "usage: $0 vX.Y.Z [--dry-run]"
[[ "$TAG" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] \
  || die "tag '$TAG' does not match vX.Y.Z (no leading zeros, plain numbers)"

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || die "not inside a git checkout"
cd "$REPO_ROOT"

# --- state checks ---------------------------------------------------------
# Clean tree first: it needs no network, and an offline rehearsal
# should fail fast on dirt rather than on the fetch.
[ -z "$(git status --porcelain)" ] || die "working tree is not clean (commit or stash first)"

say "==> fetching origin (dev + tags)"
git fetch origin dev --tags --quiet

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  die "tag '$TAG' already exists locally"
fi
remote_tag=$(git ls-remote --tags origin "refs/tags/$TAG") \
  || die "cannot reach origin to check whether '$TAG' already exists"
[ -n "$remote_tag" ] && die "tag '$TAG' already exists on origin"

HEAD_SHA=$(git rev-parse HEAD)
DEV_SHA=$(git rev-parse origin/dev)
if [ "$HEAD_SHA" != "$DEV_SHA" ]; then
  msg="HEAD ($HEAD_SHA) is not origin/dev ($DEV_SHA) - tags are cut from dev only"
  if [ "$DRY_RUN" -eq 1 ]; then
    err "WARNING (dry-run only): $msg"
  else
    die "$msg"
  fi
fi

# --- verification gate ----------------------------------------------------
say "==> nix flake check"
if ! nix flake check; then
  die "nix flake check failed - release aborted"
fi

# --- tag message ----------------------------------------------------------
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
if [ -n "$LAST_TAG" ]; then
  RANGE="$LAST_TAG..HEAD"
  RANGE_LABEL="since $LAST_TAG"
else
  RANGE="HEAD"
  RANGE_LABEL="(no previous tag - entire history)"
fi
say "==> changelog $RANGE_LABEL"
if [ -n "$LAST_TAG" ]; then
  git log --oneline --no-decorate "$RANGE"
else
  git log --oneline --no-decorate -15 HEAD
  COUNT=$(git rev-list --count HEAD)
  say "    ... ($COUNT commits total, showing 15)"
fi

NL=$'\n'
MSG="g-usi $TAG${NL}${NL}Release per docs/COMPAT.md. Cut from dev at $HEAD_SHA."

# --- create (or rehearse) the tag -----------------------------------------
if [ "$DRY_RUN" -eq 1 ]; then
  say ""
  say "==> DRY RUN: would run:"
  say "      git tag -a '$TAG' -m '<multi-line message>'"
  say "    message would be:"
  printf '%s\n' "$MSG" | sed 's/^/      | /'
  say "    then the human pushes:"
  say "      git push origin '$TAG'"
  say "    and syncs the mirrors (codeberg, github) so every flake URL resolves the tag."
  exit 0
fi

say "==> creating annotated tag $TAG"
git tag -a "$TAG" -m "$MSG"

say ""
say "Tag $TAG created at $HEAD_SHA."
say "Next (human):"
say "  git push origin $TAG"
say "  # then sync mirrors (codeberg, github) - COMPAT.md: same tag must"
say "  # resolve everywhere a flake input URL can point."
say "  # Optional: attach a forge release (nixpkgs rev + glibc, packaged"
say "  # Pants range, parameter-surface changes)."
say "  # To amend the message: git tag -f -a $TAG -m '...' - but ONLY"
say "  # before pushing. Never force-amend a pushed/mirrored tag: the"
say "  # whole scheme rests on a tag resolving to one commit everywhere."
