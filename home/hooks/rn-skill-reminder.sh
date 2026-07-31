#!/usr/bin/env bash
#
# rn-skill-reminder.sh — PreToolUse hook for Edit|Write.
#
# Injects a reminder to consult the React Native skills before Claude edits a
# .ts/.tsx file, but ONLY inside an Expo project. Installed globally, it stays
# silent in every non-Expo repo, so one config covers all projects.
#
# Skills influence behaviour probabilistically; this hook fires deterministically.
# It can't force the skill to be used, but it guarantees the reminder is present
# at the moment of the edit rather than depending on recall.
#
# stdin:  {"tool_name":"Edit","tool_input":{"file_path":"/abs/path.tsx"},...}
# stdout: {"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"..."}}
#         or nothing at all, which is a no-op.

set -uo pipefail

payload=$(cat)
file=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Not a file edit, or no path — nothing to say.
[ -n "$file" ] || exit 0

case "$file" in
  *.ts|*.tsx) ;;
  *) exit 0 ;;
esac

# Walk up from the file looking for a package.json that declares Expo or React
# Native. Bounded by the filesystem root; stops at the first package.json found
# in a directory that also looks like a project root.
dir=$(dirname "$file")
manifest=""
while [ "$dir" != "/" ] && [ -n "$dir" ]; do
  if [ -f "$dir/package.json" ]; then
    manifest="$dir/package.json"
    break
  fi
  dir=$(dirname "$dir")
done

[ -n "$manifest" ] || exit 0

# Only fire for Expo / React Native projects.
jq -e '((.dependencies // {}) + (.devDependencies // {}))
       | has("expo") or has("react-native")' "$manifest" >/dev/null 2>&1 || exit 0

# Component/screen files get the full list; other .ts files get the shorter one,
# since composition and rendering guidance doesn't apply to plain modules.
case "$file" in
  *.tsx)
    skills='`react-native-skills` (components, lists, animations, navigation), `react-native-best-practices` (re-renders, FlashList, jank, TTI), `vercel-composition-patterns` (prop sprawl, compound components)'
    ;;
  *)
    skills='`react-native-skills` and `react-native-best-practices`'
    ;;
esac

reminder="This is an Expo / React Native project and you are about to write ${file##*/}.

Before writing, consider invoking: ${skills}.

If a skill applies, invoke it with the Skill tool and follow it — do not work from
memory of what it probably says. If none applies to this specific edit, proceed
without one; this reminder is not an instruction to invoke a skill every time."

jq -n --arg ctx "$reminder" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $ctx}}'
