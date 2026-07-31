#!/usr/bin/env python3
"""Generate Claude-Code-Skills-Setup-Guide.docx.

The appendix is built by reading the real SKILL.md files, so regenerating the
guide after adding or removing a skill keeps the document accurate.

    pip install python-docx
    python3 build-setup-guide.py
"""

import re
import sys
from pathlib import Path

try:
    from docx import Document
except ModuleNotFoundError:
    sys.exit(
        "python-docx is not installed. Install it with:\n"
        "    python3 -m pip install python-docx\n"
        "If pip refuses (externally-managed-environment), use a virtualenv:\n"
        "    python3 -m venv .venv && .venv/bin/pip install python-docx\n"
        "    .venv/bin/python build-setup-guide.py"
    )

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor, Inches

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SKILLS_DIR = REPO / "skills"
OUTPUT = HERE / "Claude-Code-Skills-Setup-Guide.docx"

# Must stay in sync with SKIP_SKILLS in install.sh.
SKIPPED = {
    "docx": "Reading, writing and editing Word documents",
    "pdf": "Reading, extracting from and generating PDFs",
    "pptx": "Reading, writing and editing PowerPoint decks",
    "xlsx": "Reading, writing and editing spreadsheets",
    "claude-api": "Claude API / Anthropic SDK reference",
}

ACCENT = RGBColor(0xC1, 0x5F, 0x3C)
MUTED = RGBColor(0x6B, 0x66, 0x60)
CODE_BG = "F4F2EF"


# --- frontmatter parsing ----------------------------------------------------

def read_frontmatter(path: Path) -> dict:
    """Pull `name` and `description` out of a SKILL.md YAML frontmatter block.

    Hand-rolled rather than using a YAML library so the script has no dependency
    beyond python-docx. Handles plain scalars, quoted scalars, `>` and `|` block
    scalars, and bare indented continuation lines.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    if not match:
        return {}

    fields, key, buffer = {}, None, []

    def flush():
        if key:
            value = " ".join(p.strip() for p in buffer if p.strip())
            fields[key] = re.sub(r"\s+", " ", value).strip().strip("\"'")

    for line in match.group(1).split("\n"):
        header = re.match(r"^([A-Za-z_][\w-]*):(.*)$", line)
        if header:
            flush()
            key = header.group(1)
            rest = header.group(2).strip()
            buffer = [] if rest in (">", "|", ">-", "|-", "") else [rest]
        elif key and line.strip():
            buffer.append(line)
    flush()
    return fields


def collect_skills():
    """Return (installed, skipped) as sorted lists of (name, folder, description)."""
    installed, skipped = [], []
    for folder in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        manifest = folder / "SKILL.md"
        if not manifest.is_file():
            continue
        fields = read_frontmatter(manifest)
        name = fields.get("name") or folder.name
        desc = fields.get("description", "")
        (skipped if folder.name in SKIPPED else installed).append(
            (name, folder.name, desc)
        )
    return installed, skipped


# Boilerplate lead-ins that pad a description without adding meaning. Useful to
# the model as trigger text, pure noise in a printed table.
BOILERPLATE = re.compile(
    r"^(this skill should be used when the user asks to|"
    r"use this skill whenever the user (wants to|asks to)|"
    r"use this skill when the user asks to|"
    r"this skill should be used when|"
    r"use this skill to|use this skill when|use this when)\s*",
    re.IGNORECASE,
)


def summarize(description: str, limit: int = 175) -> str:
    """Trim a trigger-heavy description down to something scannable in a table."""
    text = description.strip()
    if not text:
        return "(no description)"
    text = BOILERPLATE.sub("Use when asked to ", text, count=1)
    # Descriptions often read "Use when X, triggers on Y" — the first sentence
    # carries the purpose, the rest is trigger vocabulary for the model.
    first = re.split(r"(?<=[.!?])\s+", text)[0]
    text = first if len(first) >= 40 else text
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text[0].upper() + text[1:] if text else text


# --- document helpers -------------------------------------------------------

def shade(cell, hex_color):
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    element = OxmlElement("w:shd")
    element.set(qn("w:val"), "clear")
    element.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(element)


def code_block(doc, lines):
    """A shaded single-cell table — the most reliable way to get a code block."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    cell = table.cell(0, 0)
    shade(cell, CODE_BG)
    cell.text = ""
    for index, line in enumerate(lines):
        para = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        para.paragraph_format.space_after = Pt(0)
        para.paragraph_format.space_before = Pt(0)
        run = para.add_run(line)
        run.font.name = "Menlo"
        run.font.size = Pt(9)
    doc.add_paragraph()


def bullet(doc, text, bold_prefix=None):
    para = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        para.add_run(bold_prefix).bold = True
    para.add_run(text)
    return para


def note(doc, text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.italic = True
    run.font.color.rgb = MUTED
    run.font.size = Pt(10)
    return para


def table_of(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.size = Pt(9.5)
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = ""
            run = cells[index].paragraphs[0].add_run(str(value))
            run.font.size = Pt(9)
            if index == 0:
                run.font.name = "Menlo"
    if widths:
        for row in table.rows:
            for index, width in enumerate(widths):
                row.cells[index].width = Inches(width)
    doc.add_paragraph()
    return table


# --- document ---------------------------------------------------------------

def build():
    installed, skipped = collect_skills()
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    for level, size in ((1, 20), (2, 15), (3, 12)):
        style = doc.styles[f"Heading {level}"]
        style.font.color.rgb = ACCENT if level == 1 else RGBColor(0x33, 0x30, 0x2E)
        style.font.size = Pt(size)
        style.font.bold = True

    # Title page ------------------------------------------------------------
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Claude Code Skills")
    run.bold = True
    run.font.size = Pt(32)
    run.font.color.rgb = ACCENT

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Setup and Portability Guide")
    run.font.size = Pt(16)
    run.font.color.rgb = MUTED

    blurb = doc.add_paragraph()
    blurb.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = blurb.add_run(
        f"How to install, verify and carry a complete Claude Code setup across machines, "
        f"projects and accounts.\n"
        f"Covers the {len(installed)} installed skills, plus global instructions, "
        f"settings and custom commands."
    )
    run.font.size = Pt(10.5)
    run.font.color.rgb = MUTED

    doc.add_page_break()

    # 1 --------------------------------------------------------------------
    doc.add_heading("1. What a skill is, and when Claude actually uses one", 1)
    doc.add_paragraph(
        "A skill is a folder containing a SKILL.md file. That file holds instructions "
        "Claude should follow for a particular kind of task — a debugging method, a code "
        "style, a deployment checklist. It can sit alongside supporting files: scripts, "
        "reference documents, templates, examples."
    )
    doc.add_paragraph("The part that matters most is how a skill gets chosen:")
    bullet(doc, "At the start of every session, Claude Code scans its skill directories "
                "and loads the name and description of each skill it finds. Only those two "
                "fields — not the body.")
    bullet(doc, "The body of SKILL.md is read only when the skill is actually invoked. "
                "This is why a 300 KB skill costs almost nothing until it is needed.")
    bullet(doc, "Claude picks a skill by matching the task against those descriptions. "
                "The description is therefore not documentation — it is the trigger.")
    doc.add_paragraph(
        "Two practical consequences follow. A skill with a vague description ('helps with "
        "React') will rarely fire, because nothing in a real request matches it. And a "
        "skill in a folder Claude does not scan will never fire at all, no matter how good "
        "it is — which is the single most common reason a skill library appears to do nothing."
    )
    note(doc, "Rule of thumb: write the description as the situation, not the subject. "
              "'Use when encountering any bug, test failure, or unexpected behavior, before "
              "proposing fixes' triggers reliably. 'Debugging guide' does not.")

    # 2 --------------------------------------------------------------------
    doc.add_heading("2. Where skills must live", 1)
    doc.add_paragraph(
        "Claude Code only discovers skills in these locations. Anywhere else is invisible."
    )
    table_of(
        doc,
        ["Location", "Scope", "Use it for"],
        [
            ["~/.claude/skills/", "Personal — every project, every session",
             "Your own working style: debugging method, testing discipline, language and "
             "framework practices. This is the main one."],
            ["<project>/.claude/skills/", "That project only",
             "Conventions specific to one codebase: its deploy steps, its architecture "
             "rules, its review checklist. Commit these so the team shares them."],
            ["Plugin marketplaces", "Whatever the plugin installs",
             "Skills distributed by others, installed through the plugin system rather "
             "than managed by hand."],
        ],
        widths=[1.9, 1.6, 3.0],
    )
    doc.add_paragraph(
        "The claude-setup repository is an ordinary directory. Claude will not read it "
        "during a session. It is the source of truth and the backup — but the files have "
        "to be installed into one of the locations above before they take effect. That "
        "installation is what install.sh does."
    )
    note(doc, "~/.claude/ itself is created by Claude Code on first launch. There is no "
              "need to make it by hand; the installer creates any missing subdirectories.")

    # 3 --------------------------------------------------------------------
    doc.add_heading("3. Anatomy of a skill", 1)
    doc.add_paragraph("The minimum viable skill is one file:")
    code_block(doc, [
        "systematic-debugging/",
        "└── SKILL.md",
    ])
    doc.add_paragraph("A larger one keeps its supporting material beside it:")
    code_block(doc, [
        "systematic-debugging/",
        "├── SKILL.md                       ← required, the entry point",
        "├── root-cause-tracing.md          ← referenced from SKILL.md",
        "├── condition-based-waiting.md",
        "└── find-polluter.sh               ← a script the skill can run",
    ])
    doc.add_paragraph("SKILL.md must open with a YAML frontmatter block:")
    code_block(doc, [
        "---",
        "name: systematic-debugging",
        "description: Use when encountering any bug, test failure, or",
        "  unexpected behavior, before proposing fixes",
        "---",
        "",
        "# Systematic Debugging",
        "",
        "## Overview",
        "...instructions for Claude, in markdown...",
    ])

    doc.add_heading("The name field must match the folder name", 3)
    doc.add_paragraph(
        "This trips people up. The name in the frontmatter is the skill's registered "
        "identity. If the folder is called react-native-skills but the frontmatter says "
        "vercel-react-native-skills, the two disagree and the skill may fail to register "
        "or appear under a name you did not expect. Third-party skills are frequently "
        "published this way."
    )
    doc.add_paragraph(
        "Every folder in this repository already matches its SKILL.md name, so nothing "
        "needs reconciling today. install.sh still checks on every run and installs a "
        "skill under its frontmatter name if the two ever diverge — which protects any "
        "skill added later from a third party, where the mismatch is common."
    )

    # 4 --------------------------------------------------------------------
    doc.add_heading("4. Setting up on a new machine or a new account", 1)
    doc.add_paragraph(
        "This is the procedure to follow when moving to a different laptop, a different "
        "employer, or a different Claude Code login. It assumes nothing but a fresh "
        "Claude Code install."
    )

    doc.add_heading("The short version", 3)
    code_block(doc, [
        "git clone <your-private-repo> ~/claude-setup",
        "cd ~/claude-setup",
        "./install.sh",
    ])
    doc.add_paragraph("Then restart Claude Code. The rest of this section is detail.")

    doc.add_heading("Step 1 — Install Claude Code and sign in", 3)
    doc.add_paragraph(
        "Launch it once before anything else. This is what creates ~/.claude/ along with "
        "its internal folders. Do not create that directory by hand."
    )
    note(doc, "The ~ in these paths means your home folder. On a new laptop the username "
              "will differ, so always type ~/.claude/... and never a hardcoded /Users/<name>/ "
              "path. install.sh is written this way, which is why it is portable.")

    doc.add_heading("Step 2 — Get this repository onto the machine", 3)
    doc.add_paragraph(
        "It carries install.sh with it, so the installer travels alongside the files and "
        "needs no separate setup."
    )
    code_block(doc, [
        "git clone <your-private-repo> ~/claude-setup",
        "",
        "# or, from a cloud-drive copy, download the folder and then:",
        "#   cloud drives do not preserve the executable bit, so use 'bash'",
        "bash install.sh",
    ])

    doc.add_heading("Step 3 — Preview, then install", 3)
    doc.add_paragraph(
        "The dry run changes nothing and prints exactly what would happen. Read it before "
        "committing, particularly on a machine that already has skills installed."
    )
    code_block(doc, [
        "cd ~/claude-setup",
        "chmod +x install.sh          # not needed after a git clone",
        "",
        "./install.sh --dry-run       # preview, writes nothing",
        "./install.sh                 # install",
    ])
    doc.add_paragraph(
        "This installs the skills and restores your personal configuration in one step:"
    )
    table_of(
        doc,
        ["From the repo", "Installed to", "What it is"],
        [
            ["skills/", "~/.claude/skills/",
             "Every skill, available in all projects on the machine"],
            ["home/CLAUDE.md", "~/.claude/CLAUDE.md",
             "Global instructions applied to every session"],
            ["home/settings.json", "~/.claude/settings.json",
             "Model, theme, effort level"],
            ["home/commands/", "~/.claude/commands/",
             "Custom slash commands"],
        ],
        widths=[1.5, 1.9, 3.1],
    )
    doc.add_paragraph("The installer's options:")
    table_of(
        doc,
        ["Option", "Effect"],
        [
            ["(none)", "Copy skills into ~/.claude/skills/ and restore the config files"],
            ["--dry-run", "Print the plan and exit without writing anything"],
            ["--symlink", "Symlink the skills instead of copying them"],
            ["--skills-only", "Install skills, leave the ~/.claude config files alone"],
            ["--target DIR", "Install skills elsewhere (implies --skills-only)"],
            ["--help", "Show usage"],
        ],
        widths=[1.7, 4.8],
    )
    note(doc, "Safe to re-run at any time. A config file that would be overwritten is "
              "copied to ~/.claude/backups/setup-<timestamp>/ first, so nothing is lost.")

    doc.add_heading("Copy or symlink?", 3)
    table_of(
        doc,
        ["", "Copy (default)", "Symlink (--symlink)"],
        [
            ["Source of truth", "Duplicated; edits need a re-run to take effect",
             "Stays in the repo; edits apply on the next session"],
            ["If the repo folder moves or is deleted", "Skills keep working",
             "Skills break"],
            ["Best for", "Any machine — and the only sensible choice for a cloud-drive "
             "copy or a --target install",
             "Actively writing or tuning skills, where the re-run is friction"],
        ],
        widths=[1.5, 2.6, 2.6],
    )

    doc.add_heading("Step 4 — Project-scoped skills (optional)", 3)
    doc.add_paragraph(
        "Only for conventions that belong to one codebase rather than to you. Install into "
        "the project and commit the result so the whole team gets them:"
    )
    code_block(doc, [
        "./install.sh --target /path/to/project/.claude/skills",
    ])
    note(doc, "This always copies. A symlink pointing into your home directory is "
              "meaningless on a teammate's machine.")

    doc.add_heading("Step 5 — Restart Claude Code", 3)
    doc.add_paragraph(
        "Skills and configuration are read when a session starts. A session that was "
        "already running will not see them until it is restarted."
    )

    # 5 --------------------------------------------------------------------
    doc.add_heading("5. Verifying it worked", 1)
    doc.add_paragraph("On disk:")
    code_block(doc, [
        "ls ~/.claude/skills/ | wc -l        # one entry per installed skill",
        "ls ~/.claude/CLAUDE.md ~/.claude/settings.json ~/.claude/commands/",
        "",
        "# --symlink installs only: list broken links, should print nothing",
        "find ~/.claude/skills/ -maxdepth 1 -type l ! -exec test -e {} \\; -print",
    ])
    doc.add_paragraph("In Claude Code, after restarting — ask directly:")
    code_block(doc, [
        '"list your available skills"',
    ])
    doc.add_paragraph(
        "The installed skills should appear by name. If one you expect is missing, work "
        "through the next section."
    )

    # 6 --------------------------------------------------------------------
    doc.add_heading("6. Troubleshooting", 1)
    table_of(
        doc,
        ["Symptom", "Cause and fix"],
        [
            ["A skill does not appear at all",
             "Most often the session was not restarted. Otherwise: the skill is not in a "
             "scanned directory, SKILL.md is missing, or the frontmatter is malformed "
             "(the --- delimiters must be the very first line and must close)."],
            ["It appears under an unexpected name",
             "The frontmatter name differs from the folder name. The name field wins. "
             "Re-run install.sh, which reconciles the two."],
            ["It appears but never triggers",
             "The description does not match how the task gets phrased. Rewrite it as a "
             "situation with concrete trigger words: 'Use when …, before …'. The "
             "skill-creator skill can help, and can measure trigger accuracy."],
            ["Two skills share a name",
             "Claude Code ships with built-in skills. A personal skill with the same name "
             "creates an ambiguity with no predictable winner. Either rename yours, or "
             "add the name to SKIP_SKILLS at the top of install.sh."],
            ["Skills broke after moving the repo",
             "Only affects --symlink installs, which point at absolute paths. Re-run "
             "install.sh from the repo's new location and every link is rebuilt."],
            ["Installer says BLOCKED for a skill",
             "A real directory exists at that name in the target and was not installed by "
             "this repo — possibly a hand-written skill that exists nowhere else. The "
             "installer refuses to delete it. Inspect it, then move or delete it before "
             "re-running."],
            ["A config file was overwritten",
             "The previous version is in ~/.claude/backups/setup-<timestamp>/. The "
             "installer backs up any config file it replaces."],
            ["Permission denied running the script",
             "chmod +x install.sh, or invoke it as: bash install.sh. Cloud-drive syncs "
             "drop the executable bit, so this is expected after a Drive download."],
        ],
        widths=[2.1, 4.4],
    )

    # 7 --------------------------------------------------------------------
    doc.add_heading("7. Maintaining the library", 1)
    bullet(doc, "Drop a folder containing a SKILL.md into skills/, re-run install.sh, and "
                "commit. It is safe to re-run at any time.", "Adding a skill.  ")
    bullet(doc, "Delete it from skills/ and from ~/.claude/skills/, then commit.",
           "Removing a skill.  ")
    bullet(doc, "Edit the file in skills/, re-run install.sh, and commit. With a --symlink "
                "install, skip the re-run — a session restart is enough.",
           "Editing a skill.  ")
    bullet(doc, "The repository is the source of truth and the backup. Commit and push "
                "after any change, so the history is there when a skill edit turns out to "
                "be wrong.", "Committing.  ")
    bullet(doc, "Use the skill-creator skill — it scaffolds the structure, and can "
                "evaluate how reliably a description triggers.", "Writing a new skill.  ")
    bullet(doc, "Regenerate this document after changing the library — the appendix is "
                "built by reading the SKILL.md files, so it stays accurate:",
           "Keeping this guide current.  ")
    code_block(doc, [
        "python3 -m pip install python-docx      # once",
        "python3 docs/build-setup-guide.py",
        "",
        "# if pip refuses with 'externally-managed-environment':",
        "python3 -m venv .venv && .venv/bin/pip install python-docx",
        ".venv/bin/python docs/build-setup-guide.py",
    ])

    # Appendix A -----------------------------------------------------------
    doc.add_page_break()
    doc.add_heading(f"Appendix A — The {len(installed)} installed skills", 1)
    doc.add_paragraph(
        "Names as registered with Claude Code. Where the source folder differs, it is "
        "shown in the second column."
    )
    rows = [
        [name, "" if name == folder else folder, summarize(desc)]
        for name, folder, desc in sorted(installed)
    ]
    table_of(doc, ["Skill", "Folder", "Purpose"], rows, widths=[1.9, 1.4, 3.2])

    # Appendix B -----------------------------------------------------------
    doc.add_heading("Appendix B — Deliberately not installed", 1)
    doc.add_paragraph(
        "These folders exist in _agents/skills/ but are skipped, because Claude Code "
        "already ships a built-in skill under each name. Installing them would create two "
        "skills with the same name and no predictable winner. To override a built-in with "
        "your own copy, remove its name from SKIP_SKILLS at the top of install-skills.sh."
    )
    table_of(
        doc,
        ["Skill", "Built-in already covers"],
        [[name, purpose] for name, purpose in sorted(SKIPPED.items())],
        widths=[1.9, 4.6],
    )

    doc.save(OUTPUT)
    return OUTPUT, len(installed), len(skipped)


if __name__ == "__main__":
    path, installed_count, skipped_count = build()
    print(f"wrote {path}")
    print(f"  {installed_count} skills documented, {skipped_count} listed as skipped")
