#!/usr/bin/env bash
#
# install.sh — restore a complete Claude Code setup on any machine.
#
# Installs:
#   skills/    -> ~/.claude/skills/       (every skill, personal scope)
#   home/      -> ~/.claude/              (CLAUDE.md, settings.json, commands/)
#
# Claude Code only discovers skills in directories it scans. This repo is not
# one of them, so the files have to be installed before they take effect.
#
# Usage:
#   ./install.sh                 # copy skills + restore home config  (default)
#   ./install.sh --dry-run       # show what would happen, change nothing
#   ./install.sh --symlink       # symlink skills instead of copying
#   ./install.sh --skills-only   # skip the ~/.claude config files
#   ./install.sh --target DIR    # install skills elsewhere, e.g. a project's
#                                #   .claude/skills for project-scoped skills
#
# Safe to re-run. Existing config files are backed up before being replaced.

set -euo pipefail

# --- configuration ----------------------------------------------------------

# Skills that ship with Claude Code already. Installing ours would create two
# skills with the same name and no predictable winner. Remove a name from this
# list if you ever want your copy to take over.
SKIP_SKILLS=(docx pdf pptx xlsx claude-api)

# --- arguments --------------------------------------------------------------

DRY_RUN=0
MODE=copy
DO_HOME=1
TARGET="$HOME/.claude/skills"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)     DRY_RUN=1 ;;
    --symlink)     MODE=symlink ;;
    --copy)        MODE=copy ;;
    --skills-only) DO_HOME=0 ;;
    --target)
      shift
      [ $# -gt 0 ] || { echo "error: --target needs a directory" >&2; exit 1; }
      TARGET="$1"
      DO_HOME=0   # a custom target means project scope; never touch ~/.claude
      ;;
    -h|--help) sed -n '3,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "error: unknown option '$1' (try --help)" >&2; exit 1 ;;
  esac
  shift
done

# Resolve this script's own directory, so the repo works from any path on any
# machine regardless of where it was cloned or how it is invoked.
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SKILLS_SRC="$ROOT/skills"
HOME_SRC="$ROOT/home"

[ -d "$SKILLS_SRC" ] || { echo "error: no skills directory at $SKILLS_SRC" >&2; exit 1; }

run() { [ "$DRY_RUN" -eq 1 ] || "$@"; }

# --- helpers ----------------------------------------------------------------

# A skill's registered identity is the `name:` in its SKILL.md frontmatter, not
# its folder name. This repo keeps the two in sync, but a skill added later or
# pulled from elsewhere may not — so reconcile at install time and the installed
# directory always matches the identity Claude registers.
skill_name_from_frontmatter() {
  awk '
    NR == 1 && /^---[[:space:]]*$/ { in_fm = 1; next }
    in_fm && /^---[[:space:]]*$/   { exit }
    in_fm && /^name:/ {
      sub(/^name:[[:space:]]*/, "")
      gsub(/^["'"'"']|["'"'"'][[:space:]]*$/, "")
      sub(/[[:space:]]+$/, "")
      print
      exit
    }
  ' "$1" 2>/dev/null
}

in_skip_list() {
  local candidate="$1" skip
  for skip in "${SKIP_SKILLS[@]}"; do
    [ "$candidate" = "$skip" ] && return 0
  done
  return 1
}

# --- report -----------------------------------------------------------------

[ "$DRY_RUN" -eq 1 ] && echo "DRY RUN — nothing will be written"
echo "source: $ROOT"
echo "skills: $TARGET  ($MODE)"
[ "$DO_HOME" -eq 1 ] && echo "config: $HOME/.claude"
echo

# --- skills -----------------------------------------------------------------

run mkdir -p "$TARGET"

installed=0 skipped=0 renamed=0 blocked=0

for dir in "$SKILLS_SRC"/*/; do
  [ -d "$dir" ] || continue
  folder="$(basename "$dir")"
  manifest="$dir/SKILL.md"

  if [ ! -f "$manifest" ]; then
    printf '  %-34s no SKILL.md — not a skill, skipping\n' "$folder"
    skipped=$((skipped + 1)); continue
  fi

  name="$(skill_name_from_frontmatter "$manifest")"
  [ -n "$name" ] || name="$folder"

  if in_skip_list "$folder" || in_skip_list "$name"; then
    printf '  %-34s skipped — Claude Code has a built-in with this name\n' "$folder"
    skipped=$((skipped + 1)); continue
  fi

  dest="$TARGET/$name"
  note=""
  if [ "$name" != "$folder" ]; then
    note=" (installed as '$name' to match its SKILL.md)"
    renamed=$((renamed + 1))
  fi

  # A real directory here may be a hand-written skill that exists nowhere else.
  # Refuse to delete it. Symlinks and previous copies from this repo are ours.
  if [ -d "$dest" ] && [ ! -L "$dest" ] && [ ! -f "$dest/.installed-by-claude-setup" ]; then
    printf '  %-34s BLOCKED — %s exists and was not installed by this repo\n' "$folder" "$dest"
    blocked=$((blocked + 1)); continue
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  %-34s would %s%s\n' "$folder" "$MODE" "$note"
    installed=$((installed + 1)); continue
  fi

  rm -rf -- "$dest"
  if [ "$MODE" = copy ]; then
    cp -R -- "${dir%/}" "$dest"
    # Marks this directory as ours, so a re-run may safely replace it while
    # still refusing to touch anything the user created by hand.
    touch "$dest/.installed-by-claude-setup"
  else
    ln -s -- "${dir%/}" "$dest"
  fi
  printf '  %-34s %s%s\n' "$folder" "$MODE" "$note"
  installed=$((installed + 1))
done

echo
echo "skills: $installed installed, $skipped skipped, $renamed renamed, $blocked blocked"

# --- home config ------------------------------------------------------------

if [ "$DO_HOME" -eq 1 ] && [ -d "$HOME_SRC" ]; then
  echo
  echo "config:"
  # One timestamped backup directory per run, so an accidental overwrite is
  # always recoverable. Created only when there is something to back up.
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup="$HOME/.claude/backups/setup-$stamp"

  install_file() {
    local src="$1" dest="$2" label="$3"
    [ -f "$src" ] || return 0
    if [ -f "$dest" ] && ! cmp -s "$src" "$dest"; then
      if [ "$DRY_RUN" -eq 1 ]; then
        printf '  %-24s would replace (existing backed up)\n' "$label"; return 0
      fi
      mkdir -p "$backup"
      cp "$dest" "$backup/$(basename "$dest")"
      printf '  %-24s replaced (old copy -> %s)\n' "$label" "${backup/#$HOME/\~}"
    elif [ -f "$dest" ]; then
      printf '  %-24s already up to date\n' "$label"; return 0
    else
      printf '  %-24s %s\n' "$label" "$([ "$DRY_RUN" -eq 1 ] && echo 'would install' || echo installed)"
    fi
    run mkdir -p "$(dirname "$dest")"
    run cp "$src" "$dest"
  }

  install_file "$HOME_SRC/CLAUDE.md"     "$HOME/.claude/CLAUDE.md"     "CLAUDE.md"
  install_file "$HOME_SRC/settings.json" "$HOME/.claude/settings.json" "settings.json"

  if [ -d "$HOME_SRC/commands" ]; then
    for cmd in "$HOME_SRC/commands"/*.md; do
      [ -f "$cmd" ] || continue
      install_file "$cmd" "$HOME/.claude/commands/$(basename "$cmd")" \
                   "commands/$(basename "$cmd")"
    done
  fi

  # Hook scripts referenced by settings.json. These must land before the
  # settings that point at them are useful, but order doesn't matter here —
  # a hook whose script is missing simply no-ops until the next run.
  if [ -d "$HOME_SRC/hooks" ]; then
    for hk in "$HOME_SRC/hooks"/*.sh; do
      [ -f "$hk" ] || continue
      dest="$HOME/.claude/hooks/$(basename "$hk")"
      install_file "$hk" "$dest" "hooks/$(basename "$hk")"
      # Cloud-drive and zip transfers drop the executable bit; settings.json
      # invokes these via `bash`, but restore it anyway so they stay runnable
      # by hand.
      run chmod +x "$dest"
    done
  fi
fi

# --- next steps -------------------------------------------------------------

if [ "$DRY_RUN" -eq 0 ] && [ "$installed" -gt 0 ]; then
  echo
  echo "Done. Restart Claude Code — skills and config are read at session start."
fi
