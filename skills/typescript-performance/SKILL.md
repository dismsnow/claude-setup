---
name: typescript-performance
description: TypeScript performance guidance covering two distinct problems - what TypeScript costs the shipped app (enums emitting runtime objects, import type and side-effect imports, decorator and class-field transpilation, zero-cost type constructs) and what it costs the developer (slow tsc, slow editor, incremental builds, skipLibCheck, project references, pathological type inference). Use when choosing between enum and union types, adding a tsconfig flag, deciding where runtime validation belongs, or when someone says type-checking is slow, the editor lags, VS Code is unresponsive in a large codebase, or type errors reached production despite TypeScript.
license: MIT
metadata:
  tags: typescript, performance, tsconfig, bundle-size, type-checking, react-native
---

# TypeScript Performance

TypeScript performance is two unrelated problems that get conflated:

1. **Runtime and bundle cost** (`ts-runtime-*`) — most TypeScript disappears at compile time, but a few constructs emit real JavaScript that ships to users. Knowing which is a small, finite list.
2. **Toolchain speed** (`ts-tooling-*`) — `tsc` and the editor's language server doing too much work. Affects developers, never users.

A request to "make TypeScript faster" is almost always the second one. Confirm which before optimizing.

## Scope

**Applies to:** new projects (adopt at setup) and new code (follow while writing).

**Existing working code:** do not retrofit. A shipping app full of `enum` is not a bug to fix — the migration risk exceeds the few hundred bytes saved. Report the difference if asked and let the owner decide. The exception is a *measured* problem: if type-checking genuinely takes minutes, that is worth fixing in existing code.

## Priority-Ordered Guidelines

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Type errors reaching production | CRITICAL | `ts-tooling-*` |
| 2 | Toolchain speed (tsc, editor) | HIGH | `ts-tooling-*` |
| 3 | Runtime/bundle cost | MEDIUM | `ts-runtime-*` |
| 4 | Validation boundaries | MEDIUM | `ts-runtime-*` |

Runtime cost ranks below toolchain speed deliberately: the wins are real but small (kilobytes), while a slow type-check taxes every developer on every change, and an unchecked build ships bugs.

## The one thing that is actually critical

**Metro and Babel strip TypeScript types without checking them.** A React Native app bundles successfully with type errors in it. Types only get verified when something runs `tsc`, so a project without `tsc --noEmit` in CI or a pre-commit hook has type safety in the editor and none in the pipeline.

```bash
npx tsc --noEmit    # the check that actually gates anything
```

See `ts-tooling-ci-and-editor.md`.

## Quick Reference

### What emits runtime JavaScript

| Construct | Emits? | Prefer |
|---|---|---|
| `interface`, `type`, generics, `satisfies`, `as` | **No** — erased entirely | Use freely |
| `enum` | **Yes** — a runtime object | String union + `as const` |
| `const enum` | Yes/unusable under Babel | String union |
| `namespace` | **Yes** — an IIFE | ES modules |
| Parameter properties (`constructor(private x)`) | **Yes** — assignment code | Explicit fields |
| Decorators | **Yes** — helper calls | Keep when a library requires them |
| `import` of a type without `type` keyword | **Maybe** — may retain the module | `import type` |

### Toolchain flags worth setting in a new project

| Flag | Value | Why |
|---|---|---|
| `strict` | `true` | Catches real bugs; no runtime cost |
| `skipLibCheck` | `true` | Large win; skips checking `.d.ts` in dependencies |
| `incremental` | `true` | Reuses prior work between runs |
| `isolatedModules` | `true` | Matches how Babel/Metro actually compile, file by file |
| `verbatimModuleSyntax` | `true` | Makes type-only imports explicit and erasure predictable |

## References

### Runtime & bundle cost (`ts-runtime-*`)

| File | Impact | Description |
|------|--------|-------------|
| [ts-runtime-enums-vs-unions.md][enums] | MEDIUM | `enum` emits objects; unions don't |
| [ts-runtime-import-type.md][import-type] | MEDIUM | Type-only imports and side-effect retention |
| [ts-runtime-transpile-cost.md][transpile] | MEDIUM | Decorators, namespaces, parameter properties, `target` |
| [ts-runtime-zero-cost-types.md][zero-cost] | LOW | What is free, and the traps that add cost anyway |
| [ts-runtime-validation-boundaries.md][validation] | MEDIUM | Types vanish at runtime; validate untrusted input once |

### Toolchain speed (`ts-tooling-*`)

| File | Impact | Description |
|------|--------|-------------|
| [ts-tooling-ci-and-editor.md][ci] | CRITICAL | Metro doesn't type-check; where `tsc` must run |
| [ts-tooling-tsconfig-baseline.md][tsconfig] | HIGH | A sane baseline for a new project |
| [ts-tooling-typecheck-speed.md][speed] | HIGH | Diagnosing slow `tsc` with real data |
| [ts-tooling-slow-types.md][slow-types] | MEDIUM | Type patterns that blow up checking time |

## Problem → Reference Mapping

| Problem | Start With |
|---------|-----------|
| Type errors reached production | [ts-tooling-ci-and-editor.md][ci] |
| `tsc` takes minutes | [ts-tooling-typecheck-speed.md][speed] → [ts-tooling-slow-types.md][slow-types] |
| Editor/IntelliSense lags | [ts-tooling-slow-types.md][slow-types] |
| Starting a new project's tsconfig | [ts-tooling-tsconfig-baseline.md][tsconfig] |
| `enum` or union type? | [ts-runtime-enums-vs-unions.md][enums] |
| Does TypeScript add to my bundle? | [ts-runtime-zero-cost-types.md][zero-cost] → [ts-runtime-transpile-cost.md][transpile] |
| Unused module still in the bundle | [ts-runtime-import-type.md][import-type] |
| API response shape is wrong at runtime | [ts-runtime-validation-boundaries.md][validation] |
| Monorepo type-checking is slow | [ts-tooling-ci-and-editor.md][ci] |

## Related Skills

- **`react-native-best-practices`** — bundle analysis and barrel-import cost, which interacts with `import type`
- **`rn-prettier`** — code-style rules for React Native TypeScript files. This skill covers performance only and does not override its style choices.

[enums]: references/ts-runtime-enums-vs-unions.md
[import-type]: references/ts-runtime-import-type.md
[transpile]: references/ts-runtime-transpile-cost.md
[zero-cost]: references/ts-runtime-zero-cost-types.md
[validation]: references/ts-runtime-validation-boundaries.md
[tsconfig]: references/ts-tooling-tsconfig-baseline.md
[speed]: references/ts-tooling-typecheck-speed.md
[slow-types]: references/ts-tooling-slow-types.md
[ci]: references/ts-tooling-ci-and-editor.md
