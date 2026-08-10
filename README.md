# Claude Code Setup

My complete Claude Code configuration — skills, global instructions, settings and
custom commands. Cloning this repo and running one command rebuilds my whole setup
on a new machine.

```bash
git clone <this-repo> ~/claude-setup
cd ~/claude-setup
./install.sh
```

Then restart Claude Code. That's the entire process.

---

## What this installs

| From | To | What it is |
|---|---|---|
| `skills/` | `~/.claude/skills/` | 63 skills, available in **every** project on the machine |
| `home/CLAUDE.md` | `~/.claude/CLAUDE.md` | Global instructions applied to every session |
| `home/settings.json` | `~/.claude/settings.json` | Model, theme, effort level, hook wiring |
| `home/commands/` | `~/.claude/commands/` | Custom slash commands (`/rn-prettier`) |
| `home/hooks/` | `~/.claude/hooks/` | Hook scripts referenced by `settings.json` |

`~/.claude/` is created by Claude Code itself on first launch — there is no need to
make it by hand. The installer creates any missing subdirectories.

## Options

| Option | Effect |
|---|---|
| *(none)* | Copy skills into `~/.claude/skills/` and restore the config files |
| `--dry-run` | Print the plan and exit without writing anything |
| `--symlink` | Symlink skills instead of copying them |
| `--skills-only` | Install skills, leave `~/.claude` config alone |
| `--target DIR` | Install skills somewhere else (implies `--skills-only`) |
| `--help` | Usage |

Safe to re-run at any time. Config files that would be overwritten are copied to
`~/.claude/backups/setup-<timestamp>/` first.

### Copy or symlink?

Copy (the default) makes real folders, so `~/.claude/skills/` keeps working even if
this repo is moved or deleted. Editing a skill means editing it here and re-running
`./install.sh`.

`--symlink` points `~/.claude/skills/` back at this repo, so an edit applies to the
next session with no re-install — convenient while actively writing skills, but it
breaks if the repo folder moves. Use copy on any machine where this repo might not
stay put, and always for `--target` installs.

---

## How skills work

A skill is a folder containing a `SKILL.md`. Two things are worth knowing:

**Only `name` and `description` load each session.** Claude Code scans its skill
directories at session start and reads those two frontmatter fields — not the body.
The body loads only when the skill is actually invoked, which is why a 300 KB skill
costs almost nothing until it is needed.

**The `description` is the trigger, not documentation.** Claude picks a skill by
matching the task against these descriptions. Write them as a *situation*, not a
subject: `Use when encountering any bug, test failure, or unexpected behavior, before
proposing fixes` fires reliably; `Debugging guide` does not.

**`name` must match the folder name.** The `name:` field is the registered identity;
when it disagrees with the directory the skill can fail to register. Every folder in
`skills/` here already matches, and `install.sh` reconciles any that don't as a safety
net for skills added later.

### Where skills can live

| Location | Scope |
|---|---|
| `~/.claude/skills/` | Personal — every project on the machine. **This is what `install.sh` targets.** |
| `<project>/.claude/skills/` | That project only. Commit them so the team gets them. |
| Plugin marketplaces | Installed through the plugin system |

Anywhere else is invisible to Claude Code.

## Keeping this private at a new job

If you don't want a company repo to reveal that you use AI tooling, the whole job is
done by `home/gitignore_global` — installed to `~/.gitignore_global` and wired up with
`core.excludesFile`. It hides `.claude/`, `CLAUDE.md`, `.mcp.json` and a few other
assistant conventions from **every** repo on the machine, automatically.

**Why not a project `.gitignore`?** Because that file is committed and pushed. A line
reading `.claude/` in a company repo announces precisely what you were keeping quiet.
`~/.gitignore_global` is never committed anywhere.

Commit attribution is handled too — `home/settings.json` sets:

```json
"attribution": { "commit": "", "pr": "" }
```

Without that, commits authored through Claude Code carry a `Co-Authored-By: Claude`
trailer into company history.

### Order of operations at a new job

Do these **before** the first `git add` in any work repo:

```bash
git clone <your-private-repo> ~/claude-setup
cd ~/claude-setup && ./install.sh          # sets both protections
git config --global core.excludesFile      # verify: ~/.gitignore_global
```

Then, in the first work repo you clone, sanity-check before committing:

```bash
git status --porcelain -uall | grep -iE 'claude|\.mcp|agents\.md'
# no output = clean
```

Keep `~/claude-setup` in your **home** directory, never inside a work folder — a repo
nested in a work checkout can be picked up by the outer repo.

### The one thing this cannot fix

A global gitignore only affects **untracked** files. Anything already committed stays
tracked and keeps showing up in `git status` forever, ignore rules or not. To stop
tracking something that is already in a repo:

```bash
git rm -r --cached .claude    # untrack, keep the files on disk
git commit -m "remove local config"
```

That stops future commits but does **not** erase it from history. Removing it from
history means rewriting commits and force-pushing — which is itself conspicuous. The
cheap, reliable move is to get the global ignore in place before the first commit at
a new job, so the situation never arises.

## Hooks: making skills fire reliably

Skills influence behaviour but nothing enforces them — Claude can simply not invoke
one. Hooks are different: the harness runs them, so they fire every time regardless
of what Claude remembers.

`home/hooks/rn-skill-reminder.sh` is a `PreToolUse` hook on `Edit|Write`. Before any
`.ts`/`.tsx` file is written it injects a reminder naming the relevant React Native
skills, so the prompt to consult them is present at the moment of the edit rather
than depending on recall.

It **self-detects Expo**: the script walks up from the file being edited, finds the
nearest `package.json`, and stays completely silent unless that manifest declares
`expo` or `react-native`. One global config therefore covers every RN project and
never fires in a Python repo or a docs folder.

It does not force a skill to be used, and deliberately says so in its own text —
a reminder that fired on every edit and demanded a skill each time would train the
opposite of judgment. It guarantees the reminder, not the outcome.

Test it without touching Claude Code:

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/path/to/a/Screen.tsx"}}' \
  | bash home/hooks/rn-skill-reminder.sh | jq -r '.hookSpecificOutput.additionalContext'
```

Prints the reminder inside an Expo project, prints nothing anywhere else. Run
`/hooks` in Claude Code to review or disable it.

## Project-scoped skills

Use the personal scope for how *you* work. Use project scope only for rules that belong
to a specific codebase:

```bash
./install.sh --target /path/to/project/.claude/skills
```

This copies rather than symlinks — a symlink into your home directory is meaningless
on a teammate's machine.

---

## Repo layout

```
claude-setup/
├── install.sh                  one command to rebuild everything
├── skills/                     68 skill folders (63 install, 5 skipped)
├── home/                       files restored into ~/.claude/
│   ├── CLAUDE.md
│   ├── settings.json
│   └── commands/
├── workflows/                  Expo/EAS command references
├── project-templates/          example project-scoped config
└── docs/
    ├── Claude-Code-Skills-Setup-Guide.docx
    └── build-setup-guide.py    regenerates the guide
```

### The 5 skipped skills

`docx`, `pdf`, `pptx`, `xlsx` and `claude-api` are kept in `skills/` but **not**
installed, because Claude Code ships built-in skills under those names and a collision
has no predictable winner. To override a built-in with the copy here, remove its name
from `SKIP_SKILLS` at the top of `install.sh`.

### `project-templates/`

`settings.local.json.example` is a PostToolUse hook that runs Prettier on save. It
contains **hardcoded absolute paths** (`/Users/marc/Desktop/...`) that must be updated
for the machine and project before use.

---

## Adding and editing skills

- **Add**: drop a folder containing a `SKILL.md` into `skills/`, run `./install.sh`, commit.
- **Edit**: change the file here, run `./install.sh`, commit. With `--symlink`, skip the re-run.
- **Remove**: delete from `skills/` and from `~/.claude/skills/`.
- **Write a new one**: use the `skill-creator` skill — it scaffolds the structure and can
  measure how reliably a description triggers.

Regenerate the setup guide after changing the library:

```bash
python3 -m pip install python-docx        # once
python3 docs/build-setup-guide.py
```

If pip refuses with `externally-managed-environment`, use a virtualenv:

```bash
python3 -m venv .venv && .venv/bin/pip install python-docx
.venv/bin/python docs/build-setup-guide.py
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| A skill doesn't appear | Restart Claude Code — skills load at session start |
| It appears under an odd name | Its `SKILL.md` `name:` differs from the folder; re-run `install.sh` |
| It appears but never triggers | The `description` doesn't match how the task gets phrased; rewrite it as a situation with concrete trigger words |
| `BLOCKED` during install | A real directory exists at that name and wasn't installed by this repo. Inspect it, then move or delete it before re-running |
| Skills broke after moving this repo | Only affects `--symlink` installs. Re-run `install.sh` from the new location |
| `permission denied` running the script | `bash install.sh`, or `chmod +x install.sh`. Cloud-drive syncs drop the executable bit |

## Backing this up

A private GitHub repo is the primary copy — it gives version history, so a broken skill
is one `git revert` away. A cloud-drive folder works as a secondary copy but has no
usable history and can be half-synced when you need it. Use `bash install.sh` there,
since cloud drives don't preserve the executable bit.
