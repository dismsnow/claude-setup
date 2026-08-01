# Validation at Trust Boundaries

**Impact: MEDIUM** — the one place where adding runtime code is correct, and where over-applying it costs real bundle size.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit validation across an existing codebase. Add it where a real shape mismatch has caused a bug, or at a new boundary you're writing.

## Quick Pattern

**Incorrect (a cast is not a check):**

```ts
async function loadUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  return (await res.json()) as User; // asserts, verifies nothing
}
```

If the server returns `{ error: 'not found' }`, this "succeeds" and the mismatch surfaces later as an unrelated crash — often deep in a render, far from the fetch.

**Correct (validate once, at the edge):**

```ts
function parseUser(raw: unknown): User {
  if (
    typeof raw !== 'object' || raw === null ||
    typeof (raw as any).id !== 'string' ||
    typeof (raw as any).name !== 'string'
  ) {
    throw new Error('Malformed user response');
  }
  return raw as User; // now the assertion is backed by a check
}

async function loadUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  return parseUser(await res.json());
}
```

## Where the boundaries are

Validate where data enters your program from somewhere you don't control:

| Boundary | Trusted? |
|---|---|
| HTTP/API responses | **No** — validate |
| Deep links / URL params | **No** — validate (also a security boundary) |
| Push notification payloads | **No** — validate |
| Persisted storage written by an older app version | **No** — shapes drift across releases |
| Native module return values | Usually — but check when the contract is loose |
| Your own function calls | Yes — the compiler already checked |

Data read back from local storage is the boundary people miss. A record written by version 1.2 and read by 2.0 is untrusted input, because the shape may have changed.

## Deep Dive: hand-written guards vs. a validation library

Both are legitimate; the tradeoff is bundle size against ergonomics.

**Hand-written guards** — zero dependency cost, verbose, and easy to get subtly wrong (forgetting a nested field, not handling arrays). Good when you have a handful of boundaries.

**A schema library** (zod, valibot, and similar) — declarative, derives the TypeScript type from the schema so they cannot drift, and handles nesting and unions correctly. Costs bundle size, and this is a real consideration in a mobile app.

If you adopt one:

- Check the library's actual bundle contribution with `bundle-analyze-js.md` rather than trusting a README claim.
- Prefer libraries with a modular API so unused validators can be tree-shaken.
- Derive the type from the schema (`type User = z.infer<typeof userSchema>`) so there is a single source of truth.
- Validate at the boundary only. Re-validating already-validated data on every render is pure cost.

**Do not validate everywhere.** Once data has passed the boundary it is typed, and re-checking it inside components is bundle size and CPU spent to re-prove something known.

## Step-by-step for a new API layer

1. Define the type or schema for the response.
2. Parse at the fetch site — one function per endpoint.
3. On failure, fail loudly and specifically ("malformed user response"), not with a generic error. A vague message costs debugging time later.
4. Everything downstream consumes the validated type and does not re-check.
5. When the server contract changes, the parse function is the single place to update.

## Common Pitfalls

- **`as` on `res.json()`.** The most common way type safety is lost. The compiler is satisfied; nothing was verified.
- **`any` on a response**, which then propagates untyped through the app and disables checking wherever it lands.
- **Validating in components rather than at the boundary.** Repeated cost, scattered logic.
- **Adding a schema library for one endpoint.** Weigh the bundle cost against a ten-line guard.
- **Trusting locally-persisted data.** Cross-version shape drift is real; treat old records as untrusted.
- **Silent fallbacks** (`?? {}`) that mask a malformed response and produce a confusing empty UI instead of an error.

## Related

- `ts-runtime-zero-cost-types.md` — why erasure makes this necessary
- `bundle-library-size.md` and `bundle-analyze-js.md` in `react-native-best-practices` — measuring a validator's cost
- The `react-native-security` skill on deep links — untrusted link parameters are a security boundary too

---
Verified against: TypeScript 5.9 (Aug 2026). Library-specific bundle figures change per release — measure rather than quoting a number.
