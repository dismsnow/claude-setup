#!/usr/bin/env python3
"""Audit Claude Code's native file-based memory store.

Checks a memory directory (`~/.claude/projects/<slug>/memory/`) for the defects that
break recall silently: files missing from the MEMORY.md index, index lines pointing at
nothing, slugs that can't be reached by [[wikilink]], and bloat in the always-loaded index.

    memcheck.py                 # store for the current working directory
    memcheck.py --dir PATH      # an explicit store
    memcheck.py --all           # every ~/.claude/projects/*/memory
    memcheck.py --fix           # re-index orphans (index reconciliation only)

Exit status: 0 when clean, 1 when defects remain, 2 on usage/IO error.
Python 3 stdlib only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

INDEX = "MEMORY.md"

# Body size past which a memory is a split candidate.
BODY_WARN_BYTES = 4096
# A single index line is paid for every session; keep the hook short.
INDEX_LINE_WARN_CHARS = 120
# Index size past which grouping under headings starts to pay off.
INDEX_WARN_BYTES = 8192
# Slug-token overlap at which two memories are worth a look. A shared project prefix
# (`smartplantation-*`) would make almost every pair look similar, so tokens appearing in
# more than DUP_COMMON_RATIO of the corpus are dropped first, and a pair must then share at
# least two distinctive tokens. Tuned for precision: an advisory note that fires on
# unrelated pairs gets ignored, so this misses two-token near-dupes rather than crying wolf.
DUP_TOKEN_OVERLAP = 0.6
DUP_MIN_SHARED = 2
DUP_COMMON_RATIO = 0.3

VALID_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
INDEX_LINK = re.compile(r"\]\(([^)]+\.md)\)")
WIKILINK = re.compile(r"\[\[([^\]\n]+)\]\]")
FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")

RESET, BOLD, RED, YELLOW, CYAN, GREEN = (
    ("\033[0m", "\033[1m", "\033[31m", "\033[33m", "\033[36m", "\033[32m")
    if sys.stdout.isatty()
    else ("", "", "", "", "", "")
)


# --- store discovery --------------------------------------------------------


def store_for_cwd(cwd: Path) -> Path:
    """Mirror the harness's slug rule: absolute path with '/' replaced by '-'."""
    return Path.home() / ".claude" / "projects" / str(cwd).replace("/", "-") / "memory"


def all_stores() -> list[Path]:
    root = Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*/memory") if p.is_dir())


# --- parsing ----------------------------------------------------------------


def read_frontmatter(text: str) -> dict[str, str]:
    """Parse the flat subset of YAML these files use. No PyYAML dependency.

    Handles top-level `key: value` and one level of indented keys (metadata.type),
    which is the entire shape the harness writes.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for raw in text[3:end].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line[:1].isspace()
        key, sep, value = line.strip().partition(":")
        if not sep:
            continue
        value = value.strip().strip("\"'")
        if not value:  # a block scalar (`description: >-`) or a nested-map header
            continue
        out[("meta." if indented else "") + key.strip()] = value
    return out


def block_description(text: str) -> str:
    """Recover a `description: >-` / `|` folded block from the frontmatter."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    lines = text[3:end].splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("description:"):
            continue
        if stripped.partition(":")[2].strip().strip("\"'").lstrip(">|-").strip():
            continue  # inline value, not a block
        body: list[str] = []
        for nxt in lines[i + 1 :]:
            if nxt.strip() and not nxt[:1].isspace():
                break
            if nxt.strip():
                body.append(nxt.strip())
        return " ".join(body)
    return ""


def strip_code(text: str) -> str:
    """Blank out code spans so literals like [[lat,lng]] aren't read as wikilinks."""
    return INLINE_CODE.sub(" ", FENCE.sub(" ", text))


def tokens(slug: str) -> set[str]:
    return {t for t in re.split(r"[-_]", slug) if len(t) > 2}


def distinctive_tokens(slugs: list[str]) -> dict[str, set[str]]:
    """Token sets with corpus-wide boilerplate (shared project prefixes) removed."""
    freq: dict[str, int] = {}
    per_slug = {s: tokens(s) for s in slugs}
    for ts in per_slug.values():
        for t in ts:
            freq[t] = freq.get(t, 0) + 1
    cutoff = max(2, int(len(slugs) * DUP_COMMON_RATIO))
    return {s: {t for t in ts if freq[t] < cutoff} for s, ts in per_slug.items()}


# --- audit ------------------------------------------------------------------


class Report:
    def __init__(self, store: Path) -> None:
        self.store = store
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.orphans: list[Path] = []

    def ok(self) -> bool:
        return not self.errors


def audit(store: Path) -> Report:
    rep = Report(store)
    index_path = store / INDEX

    if not store.is_dir():
        rep.errors.append(f"no memory store at {store}")
        return rep
    if not index_path.is_file():
        rep.errors.append(f"missing {INDEX} — every memory in this store is unreachable")
        return rep

    index_text = index_path.read_text(encoding="utf-8")
    bodies = sorted(p for p in store.glob("*.md") if p.name != INDEX)
    by_slug = {p.stem: p for p in bodies}

    linked = {t for t in INDEX_LINK.findall(index_text)}

    # -- orphans: on disk, absent from the index -> unreachable
    for path in bodies:
        if path.name not in linked:
            rep.orphans.append(path)
            rep.errors.append(f"orphan: {path.name} is not linked from {INDEX}")

    # -- dangling: index points at a file that isn't there
    for target in sorted(linked):
        if not (store / target).is_file():
            rep.errors.append(f"dangling index link: {INDEX} -> {target} (no such file)")

    # -- identity: basename == frontmatter name == a valid kebab slug
    fm_cache: dict[Path, dict[str, str]] = {}
    for path in bodies:
        text = path.read_text(encoding="utf-8")
        fm = read_frontmatter(text)
        fm_cache[path] = fm
        if not VALID_SLUG.match(path.stem):
            rep.errors.append(
                f"non-kebab filename: {path.name} — [[{path.stem}]] links cannot resolve"
            )
        name = fm.get("name")
        if name and name != path.stem:
            rep.errors.append(
                f"identity mismatch: {path.name} declares name: {name}"
            )
        elif not name:
            rep.warnings.append(f"no frontmatter name: in {path.name}")

    # -- wikilinks, ignoring code spans and non-slug targets
    for path in bodies:
        text = strip_code(path.read_text(encoding="utf-8"))
        for target in sorted(set(WIKILINK.findall(text))):
            target = target.strip()
            if not VALID_SLUG.match(target):
                # A non-kebab target that still names a real file is a convention violation
                # waiting to break on rename — report it. One that names nothing is prose or
                # a decorative literal (`[[lat,lng]]`), so stay quiet.
                if target in by_slug:
                    rep.warnings.append(
                        f"non-kebab wikilink: {path.name} -> [[{target}]] — resolves today, "
                        "breaks the moment that file is renamed to kebab-case"
                    )
                continue
            if target not in by_slug:
                rep.warnings.append(
                    f"broken wikilink: {path.name} -> [[{target}]] (unwritten or typo)"
                )

    # -- index cost
    size = len(index_text.encode("utf-8"))
    entries = [ln for ln in index_text.splitlines() if ln.lstrip().startswith("- [")]
    if size > INDEX_WARN_BYTES:
        rep.warnings.append(
            f"{INDEX} is {size / 1024:.1f} KB across {len(entries)} entries — "
            "loaded every session; group under headings or prune"
        )
    long_lines = sorted(
        (ln for ln in entries if len(ln) > INDEX_LINE_WARN_CHARS), key=len, reverse=True
    )
    if long_lines:
        rep.notes.append(
            f"{len(long_lines)}/{len(entries)} index lines exceed {INDEX_LINE_WARN_CHARS} "
            f"chars (longest {len(long_lines[0])}) — the hook should say when it matters, "
            "not summarise the file"
        )
        for line in long_lines[:3]:
            rep.notes.append(f"  worst ({len(line)}): {line[:72]}...")

    # -- oversized bodies
    for path in bodies:
        n = path.stat().st_size
        if n > BODY_WARN_BYTES:
            rep.notes.append(f"large body ({n / 1024:.1f} KB): {path.name} — split candidate")

    # -- type mix. `type:` belongs under `metadata:`, but a flat top-level `type:` is a
    # legitimate older shape — read both, and say so rather than reporting it as unknown.
    counts: dict[str, int] = {}
    for path, fm in fm_cache.items():
        if "meta.type" in fm:
            kind = fm["meta.type"]
        elif "type" in fm:
            kind = fm["type"]
            rep.warnings.append(
                f"flat frontmatter: {path.name} has top-level type: — belongs under metadata:"
            )
        else:
            kind = "(missing)"
            rep.warnings.append(f"no type: in {path.name}")
        counts[kind] = counts.get(kind, 0) + 1
    mix = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    rep.notes.append(f"type mix: {mix}")
    if not counts.get("feedback") and not counts.get("user"):
        rep.notes.append(
            "no feedback/user memories — durable preferences aren't being captured"
        )

    # -- near-duplicate slugs (review candidates only, never auto-merged)
    distinctive = distinctive_tokens([p.stem for p in bodies])
    for i, a in enumerate(bodies):
        ta = distinctive[a.stem]
        if not ta:
            continue
        for b in bodies[i + 1 :]:
            tb = distinctive[b.stem]
            if not tb:
                continue
            shared = ta & tb
            overlap = len(shared) / min(len(ta), len(tb))
            if len(shared) >= DUP_MIN_SHARED and overlap >= DUP_TOKEN_OVERLAP:
                rep.notes.append(
                    f"similar slugs: {a.stem} / {b.stem} "
                    f"(shared: {', '.join(sorted(shared))}) — merge candidate?"
                )

    return rep


# --- fix --------------------------------------------------------------------


def title_from(path: Path, fm: dict[str, str]) -> str:
    name = fm.get("name", path.stem).replace("-", " ").replace("_", " ").strip()
    return name[:1].upper() + name[1:]


def reconcile_index(rep: Report) -> int:
    """Append a pointer line for each orphan, built from its own frontmatter."""
    if not rep.orphans:
        return 0
    index_path = rep.store / INDEX
    text = index_path.read_text(encoding="utf-8")
    added: list[str] = []
    for path in rep.orphans:
        body = path.read_text(encoding="utf-8")
        fm = read_frontmatter(body)
        desc = fm.get("description") or block_description(body) or "(no description)"
        desc = " ".join(desc.split())
        added.append(f"- [{title_from(path, fm)}]({path.name}) — {desc}")
    if not text.endswith("\n"):
        text += "\n"
    index_path.write_text(text + "\n".join(added) + "\n", encoding="utf-8")
    for line in added:
        print(f"  {GREEN}+{RESET} {line}")
    print(
        f"  {CYAN}note {RESET}  titles/hooks above are derived mechanically from frontmatter — "
        "reword them to say when the memory matters"
    )
    return len(added)


# --- output -----------------------------------------------------------------


def emit(rep: Report) -> None:
    print(f"\n{BOLD}{rep.store}{RESET}")
    for msg in rep.errors:
        print(f"  {RED}ERROR{RESET}  {msg}")
    for msg in rep.warnings:
        print(f"  {YELLOW}WARN {RESET}  {msg}")
    for msg in rep.notes:
        print(f"  {CYAN}note {RESET}  {msg}")
    if rep.ok() and not rep.warnings:
        print(f"  {GREEN}clean{RESET}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit a Claude Code memory store for orphans, broken links, and bloat."
    )
    ap.add_argument("--dir", type=Path, help="explicit memory directory")
    ap.add_argument("--all", action="store_true", help="audit every project store")
    ap.add_argument(
        "--fix",
        action="store_true",
        help="index reconciliation only: append a MEMORY.md line for each orphan",
    )
    args = ap.parse_args()

    if args.dir and args.all:
        print("--dir and --all are mutually exclusive", file=sys.stderr)
        return 2

    if args.all:
        stores = all_stores()
        if not stores:
            print("no memory stores found under ~/.claude/projects", file=sys.stderr)
            return 2
    elif args.dir:
        stores = [args.dir.expanduser().resolve()]
    else:
        stores = [store_for_cwd(Path(os.getcwd()).resolve())]

    failed = False
    for store in stores:
        rep = audit(store)
        emit(rep)
        if args.fix and rep.orphans:
            n = reconcile_index(rep)
            print(f"  {GREEN}fixed{RESET}  re-indexed {n} orphan(s); re-run to confirm")
            rep = audit(store)
        if not rep.ok():
            failed = True
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
