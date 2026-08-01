# Transpilation Cost: Decorators, Namespaces, Class Fields

**Impact: MEDIUM** — the remaining TypeScript constructs that emit real JavaScript.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit. In particular, **a decorator a library requires is not a defect** — see below.

## Quick Reference

| Construct | Emitted output | Prefer in new code |
|---|---|---|
| `namespace Foo {}` | An IIFE plus a merged object | ES modules |
| `constructor(private x: T)` | Generated field assignments | Explicit field declarations |
| Decorators | `__decorate` helper calls per decorated member | Keep when required; avoid otherwise |
| Class fields with `useDefineForClassFields` | `Object.defineProperty` semantics | Match the project's existing setting |
| Low `target` | Downlevel helpers for modern syntax | A target Hermes already supports |

## Namespaces

```ts
// Incorrect — emits an IIFE and a runtime object
namespace Validators {
  export function isEmail(v: string) { return v.includes('@'); }
}

// Correct — plain module, tree-shakeable
export function isEmail(v: string) { return v.includes('@'); }
```

`namespace` predates ES modules. It produces a runtime object that bundlers struggle to tree-shake, because members are properties assigned inside a closure rather than statically-analyzable exports. There is no reason to write a new one. `declare namespace` in a `.d.ts` is different — that's type-only and free.

## Parameter properties

```ts
// Emits assignments in the constructor body
class Repo {
  constructor(private db: Database, private logger: Logger) {}
}

// Explicit — same cost roughly, but clearer and works without decorator metadata
class Repo {
  private db: Database;
  private logger: Logger;
  constructor(db: Database, logger: Logger) {
    this.db = db;
    this.logger = logger;
  }
}
```

The cost here is small and the shorthand is readable. This is a low-priority concern — mentioned for completeness, not worth a rule.

## Deep Dive: decorators

Decorators emit helper calls (`__decorate`, and metadata helpers when `emitDecoratorMetadata` is on) around every decorated member. `emitDecoratorMetadata` in particular emits type information as runtime data — which is the one place TypeScript deliberately *doesn't* erase types.

**When decorators are required, keep them.** Several widely-used libraries — ORMs and local-database layers in particular — are built on decorator-based models. A project with `experimentalDecorators: true` in its `tsconfig.json` almost certainly needs it. Removing decorators from such models breaks the library.

Practical guidance:

- **New code in a project that already uses decorators for its models** — follow the existing pattern. Consistency beats micro-optimization.
- **New code that doesn't need them** — don't introduce decorators for convenience (logging wrappers, memoization). A plain higher-order function costs less and is easier to follow.
- **`emitDecoratorMetadata`** — enable only if a library documents that it needs it. It measurably increases output size.
- Note that TC39 standard decorators and TypeScript's legacy `experimentalDecorators` are different features with different emit. Don't mix guidance between them; match what the project's libraries expect.

## Deep Dive: target and downlevelling

Setting `target` lower than the runtime supports makes the compiler emit helper functions for syntax the engine already implements natively — async/await state machines, spread helpers, class field shims. That's dead weight in both size and speed.

Hermes supports modern JavaScript. The Expo/React Native base tsconfig already sets an appropriate `target`, so the correct action is usually **none**: extend the framework's base config and don't override `target`. Lowering it "for compatibility" is a common self-inflicted cost.

Note that `target` in `tsconfig.json` primarily affects `tsc` output. In a React Native app Metro/Babel does the actual transform, driven by the Babel preset — so a mismatched `target` mostly misleads readers rather than changing the bundle. Keep them consistent to avoid confusion.

## Common Pitfalls

- **Stripping decorators from library-required model classes** to "reduce bundle size". This breaks the library. Check what depends on them first.
- **Enabling `emitDecoratorMetadata` speculatively.** It adds runtime type data for no benefit unless a library reads it.
- **Lowering `target` for safety.** Adds downlevel helpers Hermes doesn't need.
- **Writing new `namespace` blocks** — usually copied from old examples or `.d.ts` patterns.
- **Assuming `tsconfig` `target` controls the shipped bundle** in React Native. Babel does.

## Related

- `ts-runtime-zero-cost-types.md` — what costs nothing
- `ts-runtime-enums-vs-unions.md` — the other common emitter
- `ts-tooling-tsconfig-baseline.md` — extending the framework base config instead of overriding it

---
Verified against: TypeScript 5.9, React Native 0.81 / Hermes, Expo SDK 54 base tsconfig (Aug 2026).
Decorator semantics differ between legacy and standard decorators and change across TypeScript versions — verify against your configured mode.
