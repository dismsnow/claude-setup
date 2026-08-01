---
name: sorting-comparators
description: >-
  Correctness rules for ordering data in JavaScript/TypeScript and React Native — writing
  Array.sort comparators, sorting dates and numeric-looking strings, avoiding in-place
  mutation of props, state or query results, ordering at the data source instead of in JS,
  and picking a max/min without sorting. Use when writing or reviewing any .sort() call,
  comparator, localeCompare, "newest first" / "sort by" / list ordering logic, or code that
  takes the largest or most recent item out of an array.
license: MIT
metadata:
  author: marc
  version: '1.0.0'
---

# Sorting & Comparator Correctness

Sorting bugs are quiet. The list still renders, the app still runs, and the order is just
wrong — usually only for some data. These rules catch the cases that don't announce
themselves.

You almost never choose a sorting *algorithm* in JS. The engine already did: `Array.sort`
is required to be **stable** (ES2019+), and engines use an adaptive merge sort. The real
decisions are **what your comparator says**, **what array you sort**, and **where the
sorting happens**.

---

## Quick reference

| Rule | Short form |
|---|---|
| 1 | Never call bare `.sort()` — it compares as strings |
| 2 | A comparator returns a **number**, never a boolean |
| 3 | Copy before sorting anything you don't own |
| 4 | Don't sort just to find one item |
| 5 | Order at the data source when there is one |
| 6 | Dates: epoch numbers, or strictly ISO `YYYY-MM-DD` strings |
| 7 | Numeric-looking strings need `{ numeric: true }` |
| 8 | Multi-key: chain comparators with `\|\|` |
| 9 | Sort once, not on every render |

---

## 1. Never call bare `.sort()`

The default comparator converts every element to a string and compares UTF-16 code units.

```js
// Incorrect
[10, 9, 1].sort();            // → [1, 10, 9]

// Correct
[10, 9, 1].sort((a, b) => a - b);   // → [1, 9, 10]
```

This is the single most common sorting bug, and it hides until your data crosses a digit
boundary — nine items look fine, ten don't.

## 2. A comparator returns a number, never a boolean

The contract is: negative if `a` comes first, positive if `b` does, `0` if equal. A boolean
coerces to `0`/`1`, so "less than" is never expressed and the result is subtly wrong.

```js
// Incorrect — no way to say "a before b"
items.sort((a, b) => a.value > b.value);

// Correct
items.sort((a, b) => a.value - b.value);

// Correct for strings
items.sort((a, b) => a.name.localeCompare(b.name));
```

Keep comparators **consistent**: if `compare(a, b) < 0` then `compare(b, a)` must be `> 0`.
An inconsistent comparator produces an unspecified order, not an error.

## 3. Copy before sorting anything you don't own

`.sort()` mutates in place and returns the *same* array. Sorting something you were handed
mutates the caller's data.

```js
// Incorrect — mutates props / state / a query result
function newestFirst(records) {
  return records.sort((a, b) => b.createdAt - a.createdAt);
}

// Correct
function newestFirst(records) {
  return [...records].sort((a, b) => b.createdAt - a.createdAt);
}
```

Applies to: function parameters, props, values read from a store, and arrays returned by a
database or API client. In React this also causes bugs that look unrelated — mutating an
array in place doesn't change its identity, so a memoised child may not re-render at all.

**Sorting a freshly-built array is fine** and needs no copy, because nothing else holds a
reference to it:

```js
Object.keys(grouped).sort(...)          // fine
Array.from(map.values()).sort(...)      // fine
rows.filter(Boolean).map(toItem).sort(...)  // fine — .map() already made a new array
```

If your runtime supports ES2023, `toSorted()` returns a sorted copy directly. `[...arr].sort()`
is the portable equivalent and always safe.

## 4. Don't sort just to find one item

Sorting to read index `0` does far more work than needed, and (per rule 3) usually mutates
something on the way.

```js
// Incorrect — O(n log n), mutates, allocates
const newest = records.sort((a, b) => b.createdAt - a.createdAt)[0];

// Correct — O(n), no mutation, no allocation
const newest = records.reduce(
  (best, r) => (best === undefined || r.createdAt > best.createdAt ? r : best),
  undefined,
);
```

Same for "the largest", "the earliest", "the highest priority". Reach for `reduce`, or a
single pass, not a full ordering.

## 5. Order at the data source when there is one

If the rows come from a database or an API, ordering there is almost always better: it can
use an index, it happens outside JS, and it can be combined with a limit so you transfer
fewer rows.

```js
// Incorrect — fetch everything, order in JS, throw most of it away
const all = await db.query(where('userId', id)).fetch();
const newest = [...all].sort((a, b) => b.createdAt - a.createdAt)[0];

// Correct — let the source order and limit
const [newest] = await db.query(where('userId', id), orderBy('createdAt', 'desc'), limit(1)).fetch();
```

Check your specific client's API for the exact operators. The principle holds for SQL,
ORMs, and most query builders.

## 6. Dates: epoch numbers, or strictly ISO `YYYY-MM-DD`

Comparing date **strings** only works when the format is fixed-width, zero-padded, and
big-endian — i.e. ISO-8601. Every other common format sorts wrongly.

```js
// Incorrect — "12/01/2024" sorts before "9/03/2024"
rows.sort((a, b) => a.date.localeCompare(b.date));   // date is "DD/MM/YYYY"

// Correct — ISO strings do sort lexicographically
rows.sort((a, b) => a.isoDate.localeCompare(b.isoDate));  // "2024-03-09" < "2024-12-01"

// Most robust — precompute epoch ms once, then compare numbers
const withMs = rows.map(r => ({ ...r, dateMs: new Date(r.date).getTime() }));
withMs.sort((a, b) => b.dateMs - a.dateMs);
```

Precomputing the timestamp once when the data is built also avoids re-parsing the date on
every comparison — `sort` calls the comparator O(n log n) times.

If you rely on ISO string ordering, say so where the field is defined, so a later change to
the format doesn't silently break the order.

## 7. Numeric-looking strings need `{ numeric: true }`

Reference numbers, invoice IDs and codes are strings, so `"10"` sorts before `"9"`.

```js
// Incorrect
codes.sort((a, b) => a.localeCompare(b));            // "CHIT-10" before "CHIT-9"

// Correct — natural / human ordering
codes.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
```

Note: this depends on the runtime having full `Intl` support. If yours doesn't, the options
argument is ignored silently — verify on-device rather than in Node, and fall back to
extracting the numeric part and comparing it as a number.

## 8. Multi-key: chain comparators with `||`

Each comparator returns `0` for a tie, which is falsy, so `||` falls through to the next key.

```js
items.sort((a, b) =>
  b.groupDate - a.groupDate ||
  b.createdAt - a.createdAt ||
  a.name.localeCompare(b.name)
);
```

Because `Array.sort` is **stable**, you can also sort by the secondary key first and then by
the primary — equal elements keep their relative order. Chaining is usually clearer, but
stability is what makes "sort by date, preserving the existing name order" work at all.

## 9. Sort once, not on every render

A sorted array built in a component body is rebuilt on every render, and the new identity
defeats `memo()` on anything you pass it to — so you pay twice.

```jsx
// Incorrect — new array every render
function List({ items }) {
  const sorted = [...items].sort(byDate);
  return <Rows data={sorted} />;
}

// Correct
function List({ items }) {
  const sorted = useMemo(() => [...items].sort(byDate), [items]);
  return <Rows data={sorted} />;
}
```

Better still, sort once where the data is derived — in a selector or the data layer — so
every screen reads the same already-ordered array. See `react-native-skills` for the wider
list-performance rules.

---

## When complexity actually matters

Asymptotic analysis is a poor cost model for app code, because it counts operations while
apps are billed in **frames, boundary crossings and allocations**. Sorting 30 rows is free
no matter what the notation says; awaiting one database call per row in a loop is slow even
though it is technically linear with indexed lookups.

So don't reach for Big-O. Ask instead: *how often does this run, does it cross into SQLite /
the bridge / the network, and does it allocate on every render?*

The one complexity rule that pays for itself:

```js
// Incorrect — O(n × m), a full scan of `used` for every item
const available = items.filter(i => !used.includes(i.id));

// Correct — build the index once, then O(1) per item
const usedIds = new Set(used);
const available = items.filter(i => !usedIds.has(i.id));
```

Apply it when **both** sides can grow. At a handful of items the array version is clearer
and you should leave it alone.
