---
name: token-efficiency
description: "Reduce token spend — both in Claude Code sessions (making quota last longer) and in code that calls the Claude API. Use when the user says tokens run out too fast, sessions cost too much, asks to 'implement prompt caching', asks why the cache isn't hitting, worries that saving tokens will weaken the model, or is adding cache_control to API calls. Covers what is already automatic, effort tuning, cache invalidation, session hygiene, and cache_control placement."
---

# Token Efficiency

Two separate problems that get confused with each other. Establish which one first.

| Symptom | Problem | Section |
|---|---|---|
| "My Claude Code quota runs out too fast" | Session spend | § A |
| "Add prompt caching to my API integration" | `cache_control` placement | § B |

**Check before advising.** If the project has no Anthropic SDK dependency, it is § A — there is no call site to add caching to, and saying otherwise sends the user hunting for one:

```sh
grep -rlE "@anthropic-ai|from anthropic|import anthropic" \
  --include="*.ts" --include="*.tsx" --include="*.py" --include="package.json" . \
  2>/dev/null | grep -v node_modules
```

---

## § A — Claude Code session spend

### Lead with this: caching is already on, and it is free

Three things the user almost always has backwards. Correct them **before** discussing any lever, because they change what the user is even asking for:

1. **There is nothing to enable.** Claude Code marks its own cache breakpoints. No `cache_control`, no setting, no install. The honest answer to "how do I implement prompt caching?" is "you already have it" — let the user believe a switch exists and they will waste time hunting for it.
2. **The first turn cannot hit cache.** Turn 1 has nothing to read, so it *writes* (1.25× input). Turn 2 onward *reads* at ~0.1×. That entry fee is inherent, not a misconfiguration. Sessions run a **1-hour TTL**, so the prefix survives long gaps — it does not silently lapse between messages.
3. **Caching costs zero model quality.** It changes how identical tokens are billed, not what the model does with them. Same model, same reasoning, byte-identical output. Users often resist token-saving because they assume it means a weaker model — say plainly that this one is free, so their caution lands on the levers that actually trade something.

Which levers *do* trade quality:

| Lever | Saves | Costs quality |
|---|---|---|
| Prompt caching | A lot | **No — none** |
| `effortLevel` | A lot | Yes — real |
| Smaller model | A lot | Yes — real |
| Narrow reads, fewer subagents | Meaningful | No, done sensibly |

**Input is rarely the problem — output is.** The prefix is re-read at ~0.1×, but output is never cached and costs 5× input (Opus 5: $5/MTok in, $25/MTok out). Every lever below targets output.

### Lever 1 — `effortLevel` (largest by a wide margin)

`~/.claude/settings.json`. Controls thinking depth and generation per turn.

| Setting | Use for |
|---|---|
| `low` | Subagents, mechanical edits, simple lookups |
| `medium` | Cost-sensitive routine work |
| `high` | Balanced default — the sweet spot for quality vs. efficiency |
| `xhigh` | Hard coding and agentic work — **Claude Code's own default** |
| `max` | Correctness matters more than cost; genuinely hard one-offs |

**`max` is not "the strongest setting" — it is "spend without a ceiling."** Frame it that way, because users set it believing it is a quality floor. Above `xhigh` returns diminish, and on routine tasks `max` overthinks: it costs more *and* reads worse. Moving `max` → `xhigh` is often a large saving at **no** quality loss on ordinary work.

It is a per-task setting, not a standing one. Recommend `high`/`xhigh` as the default and `/config` to raise it for a specific hard problem.

### Lever 2 — a CLAUDE.md that mandates verbose thinking

A global `CLAUDE.md` instructing "think comprehensively / extensively / at length on every interaction" applies that cost to **every turn**, including "what's in this file". It inflates output tokens — the expensive kind — on exactly the trivial turns where it buys nothing.

The file itself sits in the cached prefix and is nearly free to *read*. The damage is what it makes the model *write*.

If the user wants reasoning depth, `effortLevel` already delivers it **and scales it to task complexity**. A prose mandate cannot scale; it fires flat on everything. Prefer the setting over the instruction, and flag the redundancy when both exist.

### Lever 3 — what invalidates the session cache

The prefix is a byte-exact match; any change invalidates everything after it:

| Action | Cost |
|---|---|
| Switching model mid-session (`/model`) | **Full rebuild** — caches are model-scoped |
| Adding/removing an MCP server | Full rebuild — tool schemas render at position 0 |
| Editing `CLAUDE.md` / `MEMORY.md` mid-session | Rebuilds everything after it |
| `/clear` | Intentional reset — that is the point |

Batch these at session boundaries, not mid-task. Switching model twice in a long session pays for the conversation three times.

### Lever 4 — subagents and workflows

Each subagent re-establishes context, explores, and reports back; the parent then re-reads the report. Several multiples of doing the work inline.

- Delegate only for genuinely independent, parallel work (wide multi-file sweeps).
- Never delegate what a couple of `read`/`grep` calls would finish.
- Never delegate verification — it belongs in the main loop.
- Run subagents at `low`/`medium` effort.
- Workflows can spawn dozens of agents. They are opt-in for a reason; never reach for one unasked.

### Lever 5 — read narrowly

- `Read` with `offset`/`limit` on large files instead of pulling 2000 lines for one function.
- `Grep` to locate, then read the hit — don't read in order to search.
- Delegate broad fan-out to `Explore`, which returns conclusions rather than file dumps.
- Never `cat` a large file through `Bash` — the whole thing lands in context, unnumbered.

### Lever 6 — memory hygiene

`MEMORY.md` loads every session and grows monotonically. Every line is permanent rent.

- One line per memory; never content in the index.
- Delete superseded memories — a fixed bug's note is dead weight once the fix ships.
- Watch for one lesson split across several files.

### Diagnostic order

Asked "why is this costing so much", check in descending impact:

1. `effortLevel` in `~/.claude/settings.json`
2. Global + project `CLAUDE.md` for verbose-thinking mandates
3. MCP servers configured but unused (schemas load regardless)
4. `MEMORY.md` size and staleness
5. Habits — mid-session model switches, wide reads, reflexive subagents

Report bytes and estimated tokens (`bytes / 4`) so relative weight is visible instead of a vague "it's big".

---

## § B — `cache_control` in API code

Only when the project actually calls the Claude API. Full reference is the `claude-api` skill (`shared/prompt-caching.md`) — **read it before writing cache code**; model minimums in particular shift per release.

### The invariant

Caching is a **prefix match**. The key is the exact bytes up to each breakpoint. One byte changes at position N → everything from N on is invalidated.

Render order is fixed: `tools` → `system` → `messages`. Stable content first, volatile last. Get ordering right and most caching works without markers; get it wrong and no marker placement rescues it.

### Placement

```python
# Simplest — auto-marks the last cacheable block
client.messages.create(
    model="claude-opus-5",
    max_tokens=16000,
    cache_control={"type": "ephemeral"},
    system=LARGE_SHARED_PROMPT,
    messages=[{"role": "user", "content": question}],
)

# Manual, when the boundary matters
system=[{"type": "text", "text": PROMPT,
         "cache_control": {"type": "ephemeral"}}]   # + "ttl": "1h"
```

| Situation | Breakpoint on |
|---|---|
| Large shared system prompt | Last system block (caches tools + system together) |
| Multi-turn conversation | Last content block of the newest turn |
| Shared preamble + varying question | End of the **shared** part, not end of prompt |
| Prefix differs every request | Don't cache — pure write premium, zero reads |

Max 4 breakpoints per request.

### Minimum cacheable prefix

Below the minimum it silently does not cache — no error, `cache_creation_input_tokens: 0`. **Not monotonic across generations**, so check per model rather than assuming newer means lower:

- 512 — Opus 5, Fable 5
- 1024 — Opus 4.8, Sonnet 5, Sonnet 4.6/4.5
- 2048 — Opus 4.7
- 4096 — Opus 4.6/4.5, Haiku 4.5

### Verify

```python
r.usage.cache_read_input_tokens      # served from cache (~0.1×)
r.usage.cache_creation_input_tokens  # written (1.25× at 5min, 2× at 1h)
r.usage.input_tokens                 # uncached remainder ONLY
```

Total prompt size is the sum of all three. If `cache_read_input_tokens` stays 0 across repeated same-prefix requests, something is invalidating it.

### Silent invalidators

Grep the prefix-building path:

- `datetime.now()` / `Date.now()` in the system prompt
- `uuid4()` or request IDs interpolated early
- `json.dumps(d)` without `sort_keys=True`; iterating a `set`
- Session or user ID inside the system prompt (kills cross-user sharing)
- Conditional system sections — each flag combination is a distinct prefix
- A tool list that varies per user (tools render at position 0)

Fix by moving the dynamic part after the last breakpoint, or making serialization deterministic.

### Two habits worth more than marker placement

1. **Freeze the system prompt.** Inject dates, modes, user names as a later message. On Opus 5 / Opus 4.8 / Fable 5, append `{"role": "system", "content": "..."}` to `messages[]` — operator authority, cached prefix intact, no beta header.
2. **Don't change tools or model mid-conversation.** Both force a full rebuild.

### Break-even

Reads ~0.1× base input; writes 1.25× (5-min TTL) or 2× (1-hour). Two requests to break even on 5-minute, three on 1-hour. The 1-hour TTL only pays off for bursty traffic with gaps over 5 minutes — continuous traffic keeps a 5-minute cache warm on its own.
