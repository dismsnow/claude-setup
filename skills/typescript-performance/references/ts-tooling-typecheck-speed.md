# Diagnosing Slow Type-Checking

**Impact: HIGH** — a slow `tsc` taxes every developer on every change.

**Applies to:** Any project with a measured problem — this is diagnosis, and the commands are read-only.
**Existing working code:** Measuring is always safe. Act on what the data shows; don't refactor types speculatively.

## Quick Commands

```bash
# 1. Where is the time going?
npx tsc --noEmit --extendedDiagnostics

# 2. Is incremental actually helping? (run twice; compare)
npx tsc --noEmit --incremental

# 3. Per-file/per-type detail for a genuinely slow project
npx tsc --noEmit --generateTrace .trace
npx analyze-trace .trace     # from the @typescript/analyze-trace package
```

## Step-by-step

1. **Get a baseline.** Time a cold run and a warm run:
   ```bash
   time npx tsc --noEmit
   ```
   A cold run of tens of seconds on a large app is normal. Minutes is not.

2. **Read `--extendedDiagnostics`.** The numbers that matter:

   | Metric | Meaning |
   |---|---|
   | `Files` | How many files the compiler pulled in. Surprisingly large? Check `include`/`exclude` and `allowJs`. |
   | `Check time` | Type-checking proper. Dominant → suspect complex types (`ts-tooling-slow-types.md`). |
   | `Parse time` | Reading files. Dominant → too many files, or huge generated files. |
   | `Program time` | Module resolution. Dominant → path/resolution config or a very wide dependency graph. |
   | `Memory used` | Near the limit causes GC thrash and superlinear slowdown. |

3. **Check the cheap wins first**, in this order — they resolve most cases:
   - `skipLibCheck: true` (see `ts-tooling-tsconfig-baseline.md`)
   - `incremental: true` with `tsBuildInfoFile` set
   - Narrow `include` / widen `exclude` so the compiler isn't checking build output, coverage reports, or generated fixtures

4. **Confirm the file count is sane.** If `Files` is far larger than your source tree, something is dragging in extra input:
   ```bash
   npx tsc --noEmit --listFilesOnly | wc -l
   npx tsc --noEmit --listFilesOnly | grep -v node_modules | head -50
   ```

5. **Only then generate a trace.** `--generateTrace` plus `analyze-trace` reports the specific files and type instantiations consuming time. Use it when the cheap wins are exhausted — it produces a lot of output and needs interpretation.

## Deep Dive: reading a trace

`analyze-trace` reports hot spots as file/position pairs with durations. Two patterns dominate:

- **One file taking a large share.** Usually a big union, a deeply generic helper, or a huge inferred object literal. Look at what that file exports and how it's typed.
- **Time spread across many files that all import one type.** The expensive type is in the imported module; the cost is paid at each instantiation site. Fixing the one definition fixes all of them.

The second pattern is why a seemingly innocuous shared type can dominate a whole project's check time. See `ts-tooling-slow-types.md`.

## Deep Dive: the editor is a separate measurement

`tsc` speed and editor responsiveness are related but distinct. The language server does incremental, in-memory work scoped to open files and their dependencies. A project where `tsc` is fine but typing feels laggy usually has a specific expensive type in the file being edited, not a global problem.

To separate them: if the editor lags only in certain files, it's local — inspect the types in those files. If it lags everywhere, it's project-wide, and the same fixes as `tsc` apply.

## Common Pitfalls

- **Optimizing without measuring.** Refactoring types on a hunch usually changes nothing. Run `--extendedDiagnostics` first.
- **Reaching for `--generateTrace` before checking `skipLibCheck`.** The cheap flag often wins outright.
- **Measuring only cold runs** and concluding `incremental` doesn't help. Compare a second run.
- **`incremental` with no `tsBuildInfoFile`**, so the cache lands somewhere unexpected or gets cleaned.
- **Blaming `tsc` for a slow bundler.** Metro slowness is a different problem — `tsc` doesn't run during bundling at all.
- **Checking build output.** A stale `dist/` or generated directory inside `include` can double the work.

## Related

- `ts-tooling-tsconfig-baseline.md` — the flags to try first
- `ts-tooling-slow-types.md` — fixing the types a trace implicates
- `ts-tooling-ci-and-editor.md` — where the check runs

---
Verified against: TypeScript 5.9 (Aug 2026). `@typescript/analyze-trace` is a separate package — install it on demand rather than assuming it's present.
