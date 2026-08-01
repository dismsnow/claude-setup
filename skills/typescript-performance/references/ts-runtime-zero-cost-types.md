# Zero-Cost Type Constructs

**Impact: LOW** (informational) — prevents the false economy of avoiding types "for performance".

**Applies to:** New projects and new code — use these freely.
**Existing working code:** Nothing to change. This reference exists to stop unnecessary rewrites.

## Quick Reference: free at runtime

Every one of these is erased completely. None adds a byte to the bundle:

| Construct | Example |
|---|---|
| `interface` / `type` | `interface User { id: string }` |
| Generics | `function first<T>(xs: T[]): T \| undefined` |
| `satisfies` | `const config = { retries: 3 } satisfies Config` |
| Type assertions | `value as User` |
| Type predicates | `function isUser(v: unknown): v is User` |
| `keyof`, `typeof`, indexed access | `type Id = User['id']` |
| Mapped & conditional types | `type Partial<T> = { [K in keyof T]?: T[K] }` |
| Branded types | `type UserId = string & { readonly __brand: unique symbol }` |
| `readonly`, `as const` (type position) | `readonly string[]` |
| Function overload signatures | multiple declarations, one implementation |
| Non-null assertion | `value!` |

Complex types cost **compile time**, never runtime — that's `ts-tooling-slow-types.md`, a different problem with different symptoms.

## Prefer `satisfies` over an annotation

```ts
// Annotation — widens the type; `theme.colors.primary` is just `string`
const theme: Theme = { colors: { primary: '#1BAA9B' } };

// satisfies — validates against Theme AND keeps the literal type
const theme = { colors: { primary: '#1BAA9B' } } satisfies Theme;
// theme.colors.primary is '#1BAA9B'
```

`satisfies` checks conformance without discarding literal types. Both compile to the same JavaScript; the second gives you better inference downstream. There is no runtime tradeoff to weigh.

## Deep Dive: branded types instead of runtime wrappers

A common way to accidentally add runtime cost is wrapping primitives in classes to distinguish them:

```ts
// Costs a class, an allocation per value, and .value everywhere
class UserId {
  constructor(readonly value: string) {}
}

// Free — the brand exists only in the type system
type UserId = string & { readonly __brand: unique symbol };
const asUserId = (s: string) => s as UserId;
```

The branded version prevents passing a raw `string` where a `UserId` is required, with zero allocations. The values are plain strings at runtime, so they serialize, compare, and index normally.

## Deep Dive: where type work *should* become runtime work

Types are erased, so they cannot validate data crossing a trust boundary. The failure mode is asserting instead of checking:

```ts
// A lie. No validation happens; a malformed response propagates silently.
const user = (await res.json()) as User;
```

That is not a performance problem — it's a correctness one, and the fix genuinely does add runtime code. Add it deliberately at boundaries only, never as a blanket habit. See `ts-runtime-validation-boundaries.md`.

## Common Pitfalls

- **Avoiding generics or utility types for "performance".** They're free at runtime. If they're slow, that's the type-checker, not the app.
- **Wrapping primitives in classes for type safety.** Use a brand.
- **Using `as` where a type predicate belongs.** `as` silences the compiler without checking; a predicate function actually narrows and can validate.
- **Believing `readonly` costs something.** It's compile-time only — unlike `Object.freeze()`, which is a real runtime call.
- **Reading "types are free" as "casts are safe".** Erasure is exactly why an unchecked cast is dangerous.

## Related

- `ts-runtime-validation-boundaries.md` — where runtime checking is warranted
- `ts-runtime-enums-vs-unions.md` / `ts-runtime-transpile-cost.md` — the constructs that aren't free
- `ts-tooling-slow-types.md` — when complex types cost compile time

---
Verified against: TypeScript 5.9 (Aug 2026).
