# Type Patterns That Slow the Compiler

**Impact: MEDIUM** — compile-time only, but one bad type can dominate a project's check time.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not refactor types speculatively. Fix what a trace actually implicates (`ts-tooling-typecheck-speed.md`); complex types that aren't slow are fine as they are.

## The mental model

These patterns cost **zero at runtime** — they're erased like all types (`ts-runtime-zero-cost-types.md`). The cost is the compiler doing combinatorial work, paid at every instantiation site. A slow type imported by 200 files is paid 200 times, which is why one definition can dominate a whole project.

## Pattern 1: Large unions multiplied together

```ts
// Incorrect — cross product: 50 × 20 × 4 = 4,000 members
type IconName = 'add' | 'remove' | /* ...50 names... */;
type Color = 'red' | 'blue' | /* ...20 colors... */;
type Size = 'sm' | 'md' | 'lg' | 'xl';
type IconKey = `${IconName}-${Color}-${Size}`;
```

Template literal types over unions multiply. A few hundred members is fine; tens of thousands makes every use expensive and error messages unreadable.

```ts
// Correct — keep the axes separate
interface IconProps { name: IconName; color: Color; size: Size }
```

## Pattern 2: Deep recursive conditional types

```ts
// Expensive — recurses through every nested property
type DeepPartial<T> = T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T;
```

Applied to a deeply nested type, this instantiates at every level, at every use site. If you need it, apply it at the outermost boundary once and export the *result*:

```ts
// Compute once; downstream code imports a concrete type
export type PartialConfig = DeepPartial<Config>;
```

Cheaper than every consumer re-instantiating `DeepPartial<Config>` themselves.

## Pattern 3: Large inferred object literals

```ts
// The compiler infers a distinct type for a 500-key object,
// then re-checks structurally at each use
export const translations = { /* 500 keys */ };
```

Annotate or constrain it so inference has less to do:

```ts
export const translations: Record<TranslationKey, string> = { /* ... */ };
```

Use `satisfies` when you need to keep literal types (`ts-runtime-zero-cost-types.md`) — but be aware that on a very large literal, `satisfies` still checks every member. For a truly huge table, an explicit `Record<...>` is faster.

## Pattern 4: `any` cascades

```ts
const data: any = await res.json();
const items = data.items.map((x) => x.value); // every downstream type is any
```

`any` doesn't slow the compiler — it stops it working. Errors go undetected and IntelliSense dies in that subtree. Use `unknown` and narrow (`ts-runtime-validation-boundaries.md`). Listed here because "TypeScript isn't helping" often traces back to one `any` upstream.

## Pattern 5: Inference-heavy generic chains

Long chains of generic helpers where each infers from the last — common in builder APIs and some form libraries — make the compiler solve a large constraint system per call site.

If a specific call site is slow, annotate the generic explicitly instead of letting it infer:

```ts
const form = useForm<LoginFields>();   // explicit, no inference work
```

## Step-by-step: fixing an implicated type

1. Get the file and position from `analyze-trace` (`ts-tooling-typecheck-speed.md`).
2. Identify which of the patterns above it matches.
3. Apply the narrowest fix — usually: compute a complex type once and export the result, split multiplied unions into separate axes, or add an explicit annotation where inference is doing the work.
4. **Re-measure.** If check time didn't move, revert — you traded readability for nothing.

## Common Pitfalls

- **Refactoring complex types that aren't slow.** Complexity is not the problem; measured cost is.
- **Assuming these cost runtime performance.** They don't. Wrong reference — see `ts-runtime-*`.
- **Replacing a slow type with `any`.** Fast and useless.
- **Instantiating an expensive utility type at every use site** rather than computing it once and exporting the result.
- **Not re-measuring after a type refactor**, so nobody knows whether it helped.

## Related

- `ts-tooling-typecheck-speed.md` — measuring first, and finding the implicated file
- `ts-runtime-zero-cost-types.md` — why none of this affects runtime
- `ts-runtime-validation-boundaries.md` — replacing `any` with real narrowing

---
Verified against: TypeScript 5.9 (Aug 2026). Compiler performance characteristics change between releases — re-measure after a TypeScript upgrade rather than trusting an old trace.
