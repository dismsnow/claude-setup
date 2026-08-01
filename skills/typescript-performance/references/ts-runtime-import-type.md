# import type and Side-Effect Retention

**Impact: MEDIUM** — can pull an entire module into the bundle for a type you don't ship.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit imports wholesale. Fix a specific case only when bundle analysis shows a module you didn't expect.

## Quick Pattern

**Incorrect (may retain the module at runtime):**

```ts
import { HeavyClient, type HeavyConfig } from './heavy-client';
//       ^ value import — the module stays in the bundle

export function describe(config: HeavyConfig): string {
  return config.name; // HeavyClient is never actually used
}
```

**Correct (type-only, provably erased):**

```ts
import type { HeavyConfig } from './heavy-client';

export function describe(config: HeavyConfig): string {
  return config.name;
}
```

## Why this happens

The compiler erases imports it can prove are types only. That proof is not always available:

- Babel (and therefore Metro) compiles **one file at a time**. It cannot see into `./heavy-client` to determine whether `HeavyConfig` is a type or a value. A plain `import { HeavyConfig }` looks like a value import, so the module reference is kept.
- Even when the compiler *can* tell, a module with **top-level side effects** (registering something, mutating a global, running setup) must be retained if imported at all — bundlers won't drop a module that might do work on load.

`import type` removes the ambiguity: the statement is a compile-time-only declaration, and the emitted file has no reference to that module.

## Step 1: Make it explicit with a compiler flag

```json
{
  "compilerOptions": {
    "verbatimModuleSyntax": true,
    "isolatedModules": true
  }
}
```

- **`verbatimModuleSyntax`** — imports and exports are emitted exactly as written; anything type-only must say `type`. The compiler errors when you import a type without it, turning a silent bundle cost into a build-time message.
- **`isolatedModules`** — enforces that each file is independently compilable, which is what Babel/Metro actually do.

Together these make erasure predictable instead of inferred.

## Step 2: Prefer inline `type` for mixed imports

When you genuinely need both a value and a type from a module:

```ts
import { createClient, type ClientOptions } from './client';
```

The inline `type` keyword marks just that specifier. The module is still imported (you need `createClient`), but the type specifier contributes nothing.

## Deep Dive: interaction with barrel files

This compounds with barrel-export cost. Importing a type from a barrel:

```ts
import type { ButtonProps } from '../design-system'; // barrel index
```

is safe for the *type*, but if anything else in that file imports a **value** from the same barrel, the whole barrel — and every module it re-exports — enters the graph. `import type` protects the type import; it does not rescue a value import from a barrel.

Import values from their source module rather than a barrel. See `bundle-barrel-exports.md` in the `react-native-best-practices` skill.

## Common Pitfalls

- **Assuming all type imports are free.** They are free only when the compiler can prove it, which under Babel means saying `type` explicitly.
- **Enabling `verbatimModuleSyntax` mid-project and treating the errors as breakage.** Each error marks a real ambiguity. Still — that's a migration, not a quick fix; see the scope note.
- **Using `import type` for something used as a value.** `import type { Foo }` then `new Foo()` fails at build time. Types only.
- **Expecting `import type` to shrink a bundle on its own.** It removes a *potential* retention. Confirm with bundle analysis rather than assuming a win.
- **Re-exporting types without `export type`.** The same ambiguity applies on the way out: `export { type Foo }` or `export type { Foo }`.

## Related

- `ts-runtime-zero-cost-types.md` — the broader erasure model
- `ts-tooling-tsconfig-baseline.md` — where these flags go in a new project
- `bundle-barrel-exports.md` and `bundle-analyze-js.md` in `react-native-best-practices` — measuring the effect

---
Verified against: TypeScript 5.9, React Native 0.81 / Metro with Babel (Aug 2026).
`verbatimModuleSyntax` semantics are version-specific — check the TypeScript release notes for your version.
