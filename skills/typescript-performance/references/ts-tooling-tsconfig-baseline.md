# tsconfig Baseline for a New Project

**Impact: HIGH** — sets type-check speed and safety for the life of the project.

**Applies to:** New projects — adopt at setup.
**Existing working code:** Do not change a working `tsconfig.json` to match this. Flipping `strict` or `verbatimModuleSyntax` on an existing codebase produces a large error backlog — that is a planned migration, not a cleanup. Report the difference and let the owner decide.

## Quick Config

For a new Expo / React Native project:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "skipLibCheck": true,
    "incremental": true,
    "tsBuildInfoFile": "node_modules/.cache/tsconfig.tsbuildinfo",
    "isolatedModules": true,
    "verbatimModuleSyntax": true,
    "noUncheckedIndexedAccess": true
  }
}
```

**Extend the framework's base config.** It already sets `target`, `lib`, `jsx`, `moduleResolution`, and path behaviour to match what Metro does. Overriding those is how projects acquire subtle mismatches — see `ts-runtime-transpile-cost.md`.

## What each flag buys

| Flag | Effect |
|---|---|
| `strict` | Enables the family of strict checks. Catches real bugs, costs nothing at runtime. Non-negotiable for a new project. |
| `skipLibCheck` | Skips type-checking `.d.ts` files in dependencies. **Usually the single biggest speed win.** |
| `incremental` | Writes a build-info file so subsequent runs reuse prior work. |
| `tsBuildInfoFile` | Puts that file somewhere gitignored. Without this it lands next to your config. |
| `isolatedModules` | Enforces that each file compiles independently — matching Babel/Metro's actual model. |
| `verbatimModuleSyntax` | Requires explicit `import type`, making erasure predictable (`ts-runtime-import-type.md`). |
| `noUncheckedIndexedAccess` | `arr[0]` is `T \| undefined`. Catches a genuinely common class of bug. Adds friction — see below. |

## Deep Dive: why `skipLibCheck: true` is right, not lazy

It sounds like disabling safety. It isn't, for practical purposes:

- It skips checking the **internal consistency of dependencies' type declarations** — not your usage of them. Your calls into a library are still fully checked against its types.
- A React Native app pulls in a large dependency tree. Cross-checking every `.d.ts` is a large fraction of total check time.
- Errors it would surface are almost always in code you cannot fix — two libraries with incompatible internal type assumptions. You'd suppress them anyway.

Leave it on. This is standard practice, and the framework base configs generally set it already.

## Deep Dive: flags to consider, with honest tradeoffs

**`noUncheckedIndexedAccess`** — makes indexed access return `T | undefined`. Catches real bugs (indexing past the end of an array, missing map keys), but adds non-null assertions or guards at every index. Genuinely valuable in a new project where you absorb the cost as you write. Painful to enable later.

**`exactOptionalPropertyTypes`** — distinguishes "absent" from "explicitly `undefined`". Correct, and often noisy against third-party types. Reasonable to skip.

**`noImplicitOverride`**, **`noFallthroughCasesInSwitch`** — cheap, low-noise, worth adding.

**`allowJs`** — needed only if the project actually contains `.js` source. It expands what the compiler processes, so don't enable it speculatively.

**Do not set** `target`, `lib`, `module`, `moduleResolution`, or `jsx` unless you have a specific reason. The base config handles them.

## Common Pitfalls

- **Not extending the framework base config**, then hand-rolling `target`/`lib`/`jsx` slightly wrong.
- **`incremental` without `tsBuildInfoFile`**, leaving a build artifact in the project root and often in git. Add it to `.gitignore` either way.
- **Setting `strict: false` to reduce errors.** That's turning off the tool, not configuring it.
- **Turning `skipLibCheck` off "for thoroughness."** Large slowdown, errors you can't act on.
- **Enabling `noUncheckedIndexedAccess` on an existing codebase** and generating hundreds of errors. New projects only.
- **Assuming `tsconfig.json` controls the bundle.** Metro/Babel does the transform; this file drives type-checking (`ts-tooling-ci-and-editor.md`).

## Related

- `ts-tooling-ci-and-editor.md` — where the check actually runs
- `ts-tooling-typecheck-speed.md` — diagnosing a slow check
- `ts-runtime-import-type.md` — what `verbatimModuleSyntax` enforces

---
Verified against: TypeScript 5.9, Expo SDK 54 (`expo/tsconfig.base`), React Native 0.81 (Aug 2026).
Base config contents change per SDK — read the installed `expo/tsconfig.base` before overriding anything.
