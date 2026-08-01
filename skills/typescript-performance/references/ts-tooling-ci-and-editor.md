# Where Type-Checking Actually Runs

**Impact: CRITICAL** — without this, TypeScript catches nothing outside your editor.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Adding a CI type-check to an existing project may surface a backlog of errors. That is information, not breakage — report the count and let the owner decide whether to fix, ratchet, or defer. Do not "fix" a hundred type errors uninvited.

## The core fact

**Metro and Babel strip TypeScript types without checking them.** Babel's TypeScript transform deletes type annotations and moves on; it never runs the type-checker. So:

- `npx expo start` succeeds with type errors in your code.
- An EAS build succeeds with type errors in your code.
- The app ships with type errors in your code.

Types are checked in exactly two places: your editor's language server, and an explicit `tsc` run. The editor checks only files you have open. If nothing runs `tsc`, TypeScript is a linting hint, not a guarantee.

## Quick Command

```bash
npx tsc --noEmit
```

`--noEmit` type-checks without producing output — Metro handles the actual transform. This is the command that gates anything.

## Step 1: Add a script

```json
{
  "scripts": {
    "typecheck": "tsc --noEmit"
  }
}
```

## Step 2: Run it in CI, before the build

```yaml
# Run this as its own step, ahead of the build step.
- run: npm ci
- run: npm run typecheck
- run: # build...
```

Ordering matters: a type-check takes seconds to a couple of minutes, while a native build takes many. Failing fast on types saves build minutes.

## Step 3: Optionally gate commits

A pre-commit hook gives faster feedback than CI. Note that `tsc` is **whole-project** — it cannot check "only staged files" meaningfully, because a change in one file can break another. Either run the full project check (with `incremental` on, this is usually fast enough) or leave it to CI.

Do not try to type-check individual files by passing paths to `tsc`; that ignores `tsconfig.json` and produces misleading results.

## Deep Dive: making the editor and CLI agree

A frequent confusion is the editor reporting different errors than `tsc`:

- **Different TypeScript versions.** The editor may use its own bundled version rather than the project's. Configure the editor to use the workspace TypeScript so both use the same compiler.
- **The editor checks open files; `tsc` checks everything.** A file nobody has opened can be broken for weeks.
- **Stale editor state.** Restarting the TypeScript server resolves phantom errors after dependency changes.

Keep `typescript` pinned in `devDependencies` and point the editor at it. Version drift between editor and CI produces "works on my machine" type errors.

## Deep Dive: monorepos and project references

In a monorepo, a single `tsc` run over everything re-checks unchanged packages. Project references let TypeScript build packages independently and reuse results:

```json
{
  "compilerOptions": { "composite": true, "declaration": true },
  "references": [{ "path": "../shared" }]
}
```

Then `tsc --build` checks only what changed downstream of a change. This is worth setting up for a new monorepo. Retrofitting it into an existing one is a real migration — `composite` requires `declaration`, which surfaces errors in types that were previously only used internally. Don't start there; start with `incremental` and `skipLibCheck`, which are far cheaper wins.

## Common Pitfalls

- **Assuming a green Metro bundle means types pass.** It does not, and this is the single most important item in this skill.
- **Assuming EAS Build type-checks.** It runs the bundler, not `tsc`.
- **Only trusting the editor.** It checks open files.
- **Running `typecheck` after the native build in CI.** Wastes build minutes on a run that was already doomed.
- **Passing file paths to `tsc`**, which silently ignores `tsconfig.json`.
- **Editor and CI on different TypeScript versions**, producing errors one sees and the other doesn't.

## Related

- `ts-tooling-tsconfig-baseline.md` — the flags that make this run fast
- `ts-tooling-typecheck-speed.md` — when the check itself is too slow

---
Verified against: TypeScript 5.9, Expo SDK 54, React Native 0.81 / Metro with Babel (Aug 2026).
