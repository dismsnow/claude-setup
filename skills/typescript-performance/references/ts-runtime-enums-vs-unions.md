# Enums vs String Unions

**Impact: MEDIUM** — a few hundred bytes per enum, plus tree-shaking resistance.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit. A shipping app full of `enum` is not a defect; migration risk exceeds the bytes saved.

## Quick Pattern

**Incorrect (emits a runtime object):**

```ts
enum Role {
  Worker = 'worker',
  Supervisor = 'supervisor',
}

function greet(role: Role) {}
```

Compiles to roughly:

```js
var Role;
(function (Role) {
  Role['Worker'] = 'worker';
  Role['Supervisor'] = 'supervisor';
})(Role || (Role = {}));
```

**Correct (erased entirely):**

```ts
const ROLES = ['worker', 'supervisor'] as const;
type Role = (typeof ROLES)[number]; // 'worker' | 'supervisor'

function greet(role: Role) {}
```

The type disappears at compile time. `ROLES` only exists in the output if you actually use it at runtime — and when you do, it's a plain array rather than a bidirectional lookup object.

## Why unions are the better default

- **Zero runtime footprint** when you only need the type.
- **Structural, not nominal.** A plain `'worker'` string is assignable to `Role`; with an enum you must write `Role.Worker` everywhere, including in tests and API payload literals.
- **Serializes naturally.** Values arriving from JSON are already the union's members. Enum round-tripping needs mapping.
- **Narrows better.** Exhaustive `switch` checking works cleanly with a `never` fallthrough.

```ts
function label(role: Role): string {
  switch (role) {
    case 'worker': return 'Worker';
    case 'supervisor': return 'Supervisor';
    default: {
      const exhaustive: never = role; // compile error if a member is unhandled
      return exhaustive;
    }
  }
}
```

## Deep Dive: numeric enums and `const enum`

**Numeric enums** additionally emit a reverse mapping (`Role[0] === 'Worker'`), making them larger than string enums, and they accept arbitrary numbers in some positions — weaker typing *and* more code.

**`const enum`** was the traditional answer: fully inlined, no runtime object. It does not work in a React Native / Babel toolchain. Babel compiles one file at a time and cannot know a `const enum`'s members from another module, so `isolatedModules` — which matches how Metro actually compiles — rejects it. Treat `const enum` as unavailable and use a union.

## When an enum is the right call

Not every enum is a mistake:

- **A library's API requires one.** Pass what it expects.
- **You need a runtime-iterable, named set** and want the enum's own object as that value. A `const` array plus a derived union does this with less machinery, but an existing enum already works.
- **Cross-language codegen** (protobuf, OpenAPI generators) emits enums. Don't hand-edit generated output.

## Common Pitfalls

- **Reaching for `const enum` to avoid the runtime object.** It won't compile under `isolatedModules`.
- **Migrating a working codebase's enums for bundle size.** The saving is small; the churn touches every call site. Not worth it without a measured problem.
- **Losing exhaustiveness when moving to unions.** Add the `never` default case shown above, or the compiler stops telling you about unhandled members.
- **Declaring `as const` and forgetting `[number]`.** `typeof ROLES` is the tuple type, not the member union.

## Related

- `ts-runtime-zero-cost-types.md` — what else is free
- `ts-runtime-transpile-cost.md` — other constructs that emit code
- The `rn-prettier` skill's "prefer type unions over enums" style rule agrees with this guidance.

---
Verified against: TypeScript 5.9, React Native 0.81 / Metro with Babel (Aug 2026).
`const enum` behaviour is toolchain-dependent — re-check if the project stops using Babel.
