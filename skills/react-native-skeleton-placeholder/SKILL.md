---
name: react-native-skeleton-placeholder
description: >-
  Best practices and copy-paste patterns for building loading skeletons in
  React Native with react-native-skeleton-placeholder (v5). Use this whenever
  implementing loading/placeholder states, "content loading" UX, shimmer
  effects, or perceived-performance work for lists, cards, feeds, profiles, or
  detail screens — including fintech (transaction lists, balance cards),
  e-commerce (product grids, product detail), and social (feeds, profiles).
  Trigger even when the user only says "add a loading state", "make loading feel
  faster", "skeleton", "placeholder", or "shimmer" without naming the library.
  Covers install/EAS setup, dark-mode theming, anti-flicker timing,
  accessibility/reduced-motion, list performance, and per-genre layouts.
---

# React Native Skeleton Placeholder — Implementation Skill

A skeleton is a low-fidelity preview of a screen's real layout, shown while data
loads. Done right it makes an app feel *fast* (the user sees structure
immediately instead of a blank screen or a lonely spinner) and eliminates the
content "jump" that happens when data pops in. Done wrong it flickers, shifts the
layout, ignores dark mode, and janks long lists.

This skill assumes `react-native-skeleton-placeholder` v5 and TypeScript.

---

## The one rule that matters most

**The skeleton's dimensions must equal the real content's dimensions.** If a row
is 64px tall with a 40px avatar, the skeleton row must be 64px tall with a 40px
circle. Otherwise the layout shifts when data arrives — the single most jarring
loading bug (mobile's version of Cumulative Layout Shift).

The reliable way to guarantee this: **drive the skeleton and the real component
from the same layout constants.** Everything else in this document is secondary
to this.

```tsx
// layout.ts — imported by BOTH the skeleton and the real row
export const TX_ROW = { height: 64, px: 16, icon: 40, gap: 12 } as const;
```

---

## When to use a skeleton (and when not to)

Use a skeleton when **all** of these hold:

- The layout shape is **known in advance** (lists, cards, feeds, profiles, detail
  screens). You can only mirror a layout you can predict.
- The load typically takes **longer than ~300ms**. Below that, a skeleton flashes
  and feels worse than nothing.
- It's an **initial load** of a region, not a background refetch.

Prefer a **spinner** instead when the result shape is unknown, the wait is
indeterminate (uploads, submits), or the region is tiny. Prefer an **inline
indicator** (not a skeleton) for pull-to-refresh and pagination — see
[Refetch vs. initial load](#refetch-vs-initial-load).

---

## Installation & setup

The library needs two native peer dependencies:

```bash
# peer deps first
npm install @react-native-masked-view/masked-view react-native-linear-gradient
# then the library
npm install react-native-skeleton-placeholder
```

Because both peers ship native code, this **will not run in Expo Go**. You need a
config-plugin dev build:

- **Expo + EAS (recommended):** add the packages, then `eas build` a dev client
  (or `npx expo prebuild && npx expo run:ios/android`). Once, not per change.
- **Bare React Native:** `cd ios && pod install` after installing.

> Note for Expo users: this library depends specifically on
> `react-native-linear-gradient`, **not** `expo-linear-gradient`. Install the
> one above even if you already use Expo's gradient elsewhere.

---

## Core API

`SkeletonPlaceholder` is the animated container. `SkeletonPlaceholder.Item` is a
flexbox `View` whose dimensions define one shape in the skeleton.

**`<SkeletonPlaceholder>` props (v5):**

| Prop              | Type              | Default   | Notes |
| ----------------- | ----------------- | --------- | ----- |
| `backgroundColor` | `string`          | `#E1E9EE` | Base shape color |
| `highlightColor`  | `string`          | `#F2F8FC` | Shimmer color |
| `speed`           | `number` (ms)     | `800`     | **`0` disables the animation** (use for reduced motion) |
| `direction`       | `"left"\|"right"` | `"right"` | Shimmer sweep direction |
| `enabled`         | `boolean`         | `true`    | `false` renders children as-is (no shapes) |
| `borderRadius`    | `number`          | —         | Default radius for all items |

`SkeletonPlaceholder.Item` accepts standard flexbox/View style props as *props*
(not a `style` object): `width`, `height`, `flex`, `flexDirection`,
`alignItems`, `justifyContent`, `alignSelf`, `borderRadius`, and all
`margin*` / `padding*`.

> Percentage widths (`width="100%"`) work only when the parent has a bounded
> width. Inside a full-width container they're fine; when unsure, use fixed
> numbers or `flex: 1`.

---

## Reusable architecture

Don't scatter raw `<SkeletonPlaceholder>` blocks across screens. Build three
small pieces once and compose them.

### 1. A theme-aware wrapper + re-exported Item

Centralize colors so every skeleton adapts to dark mode automatically.

```tsx
// skeleton/Skeleton.tsx
import React from 'react';
import { useColorScheme } from 'react-native';
import SkeletonPlaceholder from 'react-native-skeleton-placeholder';
import { useReduceMotion } from './useReduceMotion';

const THEME = {
  light: { background: '#E1E9EE', highlight: '#F2F8FC' },
  dark:  { background: '#2A2E37', highlight: '#3A3F4B' },
};

type Props = React.ComponentProps<typeof SkeletonPlaceholder>;

export function Skeleton({ children, ...rest }: Props) {
  const scheme = useColorScheme() ?? 'light';
  const reduceMotion = useReduceMotion();
  const c = THEME[scheme];
  return (
    <SkeletonPlaceholder
      backgroundColor={c.background}
      highlightColor={c.highlight}
      borderRadius={6}
      speed={reduceMotion ? 0 : 1000} // 1000ms is a calmer shimmer than the 800 default
      {...rest} // callers can still override any of the above
    >
      {children}
    </SkeletonPlaceholder>
  );
}

// Re-export so screens import both from one place.
export const SkeletonItem = SkeletonPlaceholder.Item;
```

### 2. Readable primitives

These make skeleton layouts scan like a wireframe instead of a wall of props.

```tsx
// skeleton/primitives.tsx
import React from 'react';
import type { DimensionValue } from 'react-native';
import { SkeletonItem } from './Skeleton';

export const Line = ({ w, h = 12, mt }: { w: DimensionValue; h?: number; mt?: number }) => (
  <SkeletonItem width={w} height={h} marginTop={mt} />
);

export const Circle = ({ size }: { size: number }) => (
  <SkeletonItem width={size} height={size} borderRadius={size / 2} />
);

export const Box = ({ w, h, r = 8 }: { w: DimensionValue; h: number; r?: number }) => (
  <SkeletonItem width={w} height={h} borderRadius={r} />
);
```

### 3. A loading boundary (with built-in anti-flicker + a11y)

One component decides skeleton vs. content and handles the timing/accessibility
so screens stay clean.

```tsx
// skeleton/LoadingBoundary.tsx
import React from 'react';
import { View } from 'react-native';
import { useDelayedLoading } from './useDelayedLoading';

type Props = {
  loading: boolean;
  skeleton: React.ReactNode;
  children: React.ReactNode;
};

export function LoadingBoundary({ loading, skeleton, children }: Props) {
  const showSkeleton = useDelayedLoading(loading);
  if (showSkeleton) {
    return (
      <View
        accessible
        accessibilityRole="progressbar"
        accessibilityLabel="Loading content"
        importantForAccessibility="yes"
      >
        {skeleton}
      </View>
    );
  }
  if (loading) return null; // brief pre-delay window: blank, never a flash
  return <>{children}</>;
}
```

Screens then read declaratively:

```tsx
function TransactionsScreen() {
  const { data, isLoading } = useTransactions();
  return (
    <LoadingBoundary loading={isLoading} skeleton={<TransactionListSkeleton count={8} />}>
      <FlatList data={data} renderItem={({ item }) => <TransactionRow tx={item} />} />
    </LoadingBoundary>
  );
}
```

---

## Timing: kill the flicker

Two failure modes: (a) data loads in 50ms and the skeleton flashes for a frame;
(b) data loads at 480ms so the skeleton appears then vanishes instantly. Fix both
with one hook — **delay before showing, and enforce a minimum on-screen time.**

```tsx
// skeleton/useDelayedLoading.ts
import { useEffect, useRef, useState } from 'react';

/**
 * - Waits `delay` ms before showing (fast loads never render a skeleton).
 * - Once shown, keeps it visible at least `minDuration` ms (no blink-out).
 */
export function useDelayedLoading(
  isLoading: boolean,
  { delay = 300, minDuration = 500 } = {},
) {
  const [visible, setVisible] = useState(false);
  const shownAt = useRef<number | null>(null);

  useEffect(() => {
    if (isLoading && !visible) {
      const t = setTimeout(() => {
        shownAt.current = Date.now();
        setVisible(true);
      }, delay);
      return () => clearTimeout(t);
    }
    if (!isLoading && visible) {
      const elapsed = shownAt.current ? Date.now() - shownAt.current : minDuration;
      const t = setTimeout(() => {
        shownAt.current = null;
        setVisible(false);
      }, Math.max(minDuration - elapsed, 0));
      return () => clearTimeout(t);
    }
  }, [isLoading, visible, delay, minDuration]);

  return visible;
}
```

---

## Accessibility & reduced motion

Two things, both cheap:

1. **Announce loading, hide the noise.** The `LoadingBoundary` above sets
   `accessibilityRole="progressbar"` and `accessibilityLabel="Loading content"`
   so screen readers say "loading" instead of reading dozens of empty shapes.
2. **Respect reduced motion.** Users who enable it get motion sickness from
   shimmer. The `Skeleton` wrapper passes `speed={0}` (static shapes, no
   animation) when this hook reports true.

```tsx
// skeleton/useReduceMotion.ts
import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

export function useReduceMotion() {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduce);
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => sub.remove();
  }, []);
  return reduce;
}
```

---

## Performance: one placeholder, not N

**Wrap a whole list of skeleton items in a single `<SkeletonPlaceholder>`, not
one per row.** Each `<SkeletonPlaceholder>` runs its own animation loop; a screen
of 10 independent placeholders is 10 concurrent animations and will jank on lower
end Android. One wrapper animating many `Item` shapes is smooth.

Also:

- **Render only enough rows to fill the viewport** (≈ 6–10), not one per real
  record. The user can't see row 40.
- **`memo` the skeleton** so it doesn't re-render on unrelated parent updates.
- **Keep the shape tree shallow.** Fewer `Item`s = less to measure and mask.

---

## Refetch vs. initial load

Show the full skeleton **only on the first load of a region.** Swapping the whole
screen to a skeleton on every pull-to-refresh feels broken.

- **Pull-to-refresh:** keep the current content, use `FlatList`'s
  `refreshControl`.
- **Pagination:** keep the content, use `ListFooterComponent` with a small
  spinner (or one or two skeleton rows appended at the bottom).
- **Initial load:** full skeleton via `LoadingBoundary`.

A simple guard: `const isInitialLoad = isLoading && !data?.length;` and only feed
*that* to the boundary.

---

## Make the skeleton match *your* UI

This is the priority the genre examples serve, not the other way around. A
skeleton's entire job is to preview the *real* screen, so its geometry must come
from the components your project actually renders. If it doesn't, the placeholder
looks like a different app for ~400ms and then snaps into the real UI — the exact
thing a skeleton is supposed to prevent. Every number in the playbooks below
(`height={14}`, `width={140}`…) is a **stand-in for your component's real
measurement**, not a value to ship.

There are two reliable ways to guarantee the match. Pick per component; mix
freely.

### Strategy 1 — Hand-draw shapes from shared tokens

Build a separate skeleton, but source every dimension from the **same design
tokens / layout constants the real component uses** — never magic numbers. A text
line's height is the real text's `lineHeight`; a card's radius is `radius.card`;
gaps are `spacing.md`. Change a token and both the UI and its skeleton move
together.

```tsx
// theme.ts — the project's existing design system (you likely already have some of this)
export const spacing = { xs: 4, sm: 8, md: 12, lg: 16 };
export const radius  = { card: 12, pill: 999 };
export const type    = {
  title:   { fontSize: 16, lineHeight: 20 },
  body:    { fontSize: 14, lineHeight: 18 },
  caption: { fontSize: 11, lineHeight: 14 },
};
```

```tsx
// Skeleton leaf heights EQUAL the real text line-heights → no vertical shift.
import { spacing, radius, type } from '@/theme';

<SkeletonItem width="60%" height={type.body.lineHeight} />
<SkeletonItem marginTop={spacing.xs} width={90} height={type.caption.lineHeight} />
<SkeletonItem marginTop={spacing.md} width="100%" height={180} borderRadius={radius.card} />
```

Same idea as the shared-`TX_ROW` example near the top, generalized: whatever the
component reads for spacing/size, the skeleton reads too. Best when you want tight
control and minimal render cost.

### Strategy 2 — Mask the real component (impossible to drift)

`SkeletonPlaceholder` can turn *any* `View`/`Text`/`Image` children into
shimmering boxes sized exactly like those elements — that's what `enabled` is for.
So instead of maintaining a parallel skeleton, feed the **actual component** in
and flip `enabled`:

```tsx
// One representative row's worth of dummy data, so masked box widths look real.
const PLACEHOLDER_ROWS: Transaction[] = Array.from({ length: 8 }, (_, i) => ({
  id: `sk-${i}`,
  icon: undefined,
  merchant: 'Merchant name',   // medium-length → representative box width
  date: '12 Aug 2026',
  amount: 'RM 000.00',
}));

function TransactionsList({ data, loading }: { data: Transaction[]; loading: boolean }) {
  const rows = loading ? PLACEHOLDER_ROWS : data;
  return (
    <Skeleton enabled={loading}>
      <View>
        {rows.map((tx) => <TransactionRow key={tx.id} tx={tx} />)}
      </View>
    </Skeleton>
  );
}
```

When `enabled` is `true`, every leaf of the *real* `TransactionRow` renders as a
box — the skeleton **is** the UI, masked, so it cannot look different. When
`loading` flips to `false`, the identical tree renders real data with zero layout
change. Because the whole list sits under one `<Skeleton>`, it's still a single
animation.

Trade-offs to know:

- The component must render with data absent — feed **representative dummy data**
  (as above) so box widths match typical content. Variable-length text follows the
  dummy values, so pick realistic lengths or let the component truncate.
- Every leaf becomes a box, including any you'd have styled differently. Usually
  fine; occasionally you special-case one node.
- To also avoid flicker, gate the dummy tree behind the delay:
  `const show = useDelayedLoading(loading); if (loading && !show) return null;`
  then use `enabled={show}` with `rows = show ? PLACEHOLDER_ROWS : data`.

### Which to use

- **Simple, stable rows/cards, or you want max performance** → Strategy 1.
- **Complex layout that's painful to re-draw, or a component that changes often** →
  Strategy 2 (it tracks the component automatically).

---

# Genre playbooks

Treat every layout below as a **template to adapt, not numbers to ship** — swap
the dimensions for your component's real tokens (Strategy 1) or mask the real
component instead (Strategy 2). Each is written as **shapes only** (a set of
`SkeletonItem`s, no wrapper) so you can drop it into a single `<Skeleton>`. The
fintech section shows the full architecture end-to-end; the others are more
compact.

## Fintech

Dense rows and precise numbers — layout-shift is especially ugly here because the
eye tracks the right-aligned amount column.

### Transaction row — the canonical shared-constants example

```tsx
// layout.ts
export const TX_ROW = { height: 64, px: 16, icon: 40, gap: 12 } as const;
```

```tsx
// TransactionRow.skeleton.tsx  — shapes only
import React from 'react';
import { SkeletonItem } from '../skeleton/Skeleton';
import { Circle } from '../skeleton/primitives';
import { TX_ROW } from './layout';

export function TransactionRowShapes() {
  return (
    <SkeletonItem
      flexDirection="row"
      alignItems="center"
      height={TX_ROW.height}
      paddingHorizontal={TX_ROW.px}
    >
      <Circle size={TX_ROW.icon} />
      <SkeletonItem flex={1} marginLeft={TX_ROW.gap}>
        <SkeletonItem width={140} height={14} />
        <SkeletonItem marginTop={6} width={90} height={11} />
      </SkeletonItem>
      <SkeletonItem width={70} height={16} />
    </SkeletonItem>
  );
}
```

```tsx
// TransactionRow.tsx — the REAL row, same TX_ROW constants → zero layout shift
import React from 'react';
import { View, Text, Image } from 'react-native';
import { TX_ROW } from './layout';

export function TransactionRow({ tx }: { tx: Transaction }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', height: TX_ROW.height, paddingHorizontal: TX_ROW.px }}>
      <Image source={tx.icon} style={{ width: TX_ROW.icon, height: TX_ROW.icon, borderRadius: TX_ROW.icon / 2 }} />
      <View style={{ flex: 1, marginLeft: TX_ROW.gap }}>
        <Text style={{ fontSize: 14 }}>{tx.merchant}</Text>
        <Text style={{ fontSize: 11, marginTop: 4, color: '#888' }}>{tx.date}</Text>
      </View>
      <Text style={{ fontSize: 15 }}>{tx.amount}</Text>
    </View>
  );
}
```

```tsx
// TransactionListSkeleton.tsx — ONE <Skeleton>, memoized, viewport-sized
import React, { memo } from 'react';
import { Skeleton } from '../skeleton/Skeleton';
import { TransactionRowShapes } from './TransactionRow.skeleton';

export const TransactionListSkeleton = memo(function TransactionListSkeleton({
  count = 8,
}: { count?: number }) {
  return (
    <Skeleton>
      {Array.from({ length: count }).map((_, i) => (
        <TransactionRowShapes key={i} />
      ))}
    </Skeleton>
  );
});
```

### Balance / account card

```tsx
export function BalanceCardShapes() {
  return (
    <SkeletonItem padding={20} borderRadius={16}>
      <SkeletonItem width={90} height={12} />              {/* "Total balance" */}
      <SkeletonItem marginTop={12} width={180} height={32} /> {/* the big number */}
      <SkeletonItem marginTop={16} flexDirection="row" alignItems="center">
        <SkeletonItem width={60} height={14} />            {/* +2.4% */}
        <SkeletonItem marginLeft={8} width={80} height={14} />
      </SkeletonItem>
    </SkeletonItem>
  );
}
```

## E-commerce

Image-led cards in a grid, plus a media-heavy detail screen.

### Product grid (2 columns)

```tsx
import React from 'react';
import { Skeleton, SkeletonItem } from '../skeleton/Skeleton';

const CARD = { w: 168, image: 168 };

function ProductCardShapes() {
  return (
    <SkeletonItem width={CARD.w} marginBottom={16}>
      <SkeletonItem width={CARD.w} height={CARD.image} borderRadius={12} /> {/* photo */}
      <SkeletonItem marginTop={10} width={CARD.w} height={14} />            {/* title l1 */}
      <SkeletonItem marginTop={6} width={CARD.w * 0.6} height={14} />       {/* title l2 */}
      <SkeletonItem marginTop={10} width={70} height={18} />               {/* price */}
    </SkeletonItem>
  );
}

export function ProductGridSkeleton({ count = 6 }: { count?: number }) {
  const rows = Math.ceil(count / 2);
  return (
    <Skeleton>
      {Array.from({ length: rows }).map((_, r) => (
        <SkeletonItem key={r} flexDirection="row" justifyContent="space-between">
          <ProductCardShapes />
          <ProductCardShapes />
        </SkeletonItem>
      ))}
    </Skeleton>
  );
}
```

> Real grids compute card width from `Dimensions`/`useWindowDimensions` and gutter
> — use the same computed value in both the card and its skeleton.

### Product detail

```tsx
export function ProductDetailShapes() {
  return (
    <SkeletonItem>
      <SkeletonItem width="100%" height={320} />                   {/* hero image */}
      <SkeletonItem padding={16}>
        <SkeletonItem width="80%" height={22} />                   {/* title */}
        <SkeletonItem marginTop={12} width={100} height={26} />    {/* price */}
        <SkeletonItem marginTop={20} width="100%" height={12} />   {/* description */}
        <SkeletonItem marginTop={8} width="100%" height={12} />
        <SkeletonItem marginTop={8} width="65%" height={12} />
        <SkeletonItem marginTop={24} width="100%" height={48} borderRadius={12} /> {/* Add to cart */}
      </SkeletonItem>
    </SkeletonItem>
  );
}
```

## Social media

Feeds and profiles — the highest-frequency skeleton in most apps, so the
one-placeholder-per-list rule matters most here.

### Feed post

```tsx
import React from 'react';
import { SkeletonItem } from '../skeleton/Skeleton';
import { Circle } from '../skeleton/primitives';

export function FeedPostShapes() {
  return (
    <SkeletonItem paddingHorizontal={16} paddingVertical={12}>
      {/* header: avatar + name + timestamp */}
      <SkeletonItem flexDirection="row" alignItems="center">
        <Circle size={40} />
        <SkeletonItem marginLeft={12}>
          <SkeletonItem width={120} height={13} />
          <SkeletonItem marginTop={6} width={80} height={10} />
        </SkeletonItem>
      </SkeletonItem>
      {/* body text — vary widths so it reads like a paragraph */}
      <SkeletonItem marginTop={12} width="100%" height={12} />
      <SkeletonItem marginTop={6} width="92%" height={12} />
      <SkeletonItem marginTop={6} width="60%" height={12} />
      {/* media */}
      <SkeletonItem marginTop={12} width="100%" height={200} borderRadius={12} />
      {/* action row: like / comment / share */}
      <SkeletonItem flexDirection="row" marginTop={12}>
        <SkeletonItem width={56} height={20} borderRadius={10} />
        <SkeletonItem marginLeft={16} width={56} height={20} borderRadius={10} />
        <SkeletonItem marginLeft={16} width={56} height={20} borderRadius={10} />
      </SkeletonItem>
    </SkeletonItem>
  );
}
```

> Tip: varying the text-line widths (100% / 92% / 60%) reads as a real paragraph.
> Three identical full-width bars read as "obviously fake."

### Profile header

```tsx
export function ProfileHeaderShapes() {
  return (
    <SkeletonItem>
      <SkeletonItem width="100%" height={120} borderRadius={0} /> {/* cover */}
      <SkeletonItem alignItems="center" marginTop={-40}>          {/* avatar overlaps cover */}
        <Circle size={80} />
        <SkeletonItem marginTop={10} width={140} height={16} />   {/* display name */}
        <SkeletonItem marginTop={8} width={200} height={11} />    {/* bio */}
        <SkeletonItem flexDirection="row" marginTop={16}>         {/* posts / followers / following */}
          {[0, 1, 2].map((i) => (
            <SkeletonItem key={i} marginHorizontal={16} alignItems="center">
              <SkeletonItem width={40} height={16} />
              <SkeletonItem marginTop={6} width={50} height={10} />
            </SkeletonItem>
          ))}
        </SkeletonItem>
      </SkeletonItem>
    </SkeletonItem>
  );
}
```

---

## Common pitfalls

- **Layout shift on load** — skeleton and content have different sizes. Fix:
  shared layout constants (the [top rule](#the-one-rule-that-matters-most)).
- **One `<SkeletonPlaceholder>` per row** — N animation loops, jank. Fix: one
  wrapper around all items.
- **Rendering a skeleton per data record** — 200 offscreen skeletons. Fix: cap at
  viewport size (6–10).
- **Skeleton on every refetch** — screen flashes on pull-to-refresh. Fix: gate on
  initial load only.
- **Light-gray shapes on a dark background** — looks broken in dark mode. Fix:
  theme-aware colors in the wrapper.
- **Flicker on fast loads** — shows for one frame. Fix: `useDelayedLoading`.
- **Ignoring reduced motion** — motion sickness. Fix: `speed={0}` when enabled.
- **Passing a `style` object to `Item`** — `Item` takes style props *directly*
  (`<SkeletonItem width={40} />`), not `style={{ width: 40 }}`.

---

## Alternatives (know when to switch)

`react-native-skeleton-placeholder` is a great default: simple flexbox API, tiny,
battle-tested. Consider switching when:

- **`moti/skeleton`** — Reanimated-based, so the shimmer runs on the UI thread
  (smoothest on heavy lists) and there's no linear-gradient native dep. Good if
  you already use Moti/Reanimated.
- **`react-content-loader` / `react-native-content-loader`** — SVG-based; reach
  for it when you need non-rectangular shapes (custom logos, curves) that flexbox
  boxes can't express.

---

## Pre-ship checklist

- [ ] Skeleton mirrors the **project's real component** — shared tokens/constants
      (Strategy 1) or a masked real component (Strategy 2), never the example's
      placeholder numbers (no layout shift, no "different app" look).
- [ ] The whole list sits in **one** `<SkeletonPlaceholder>`.
- [ ] Only **viewport-sized** count of skeleton items rendered, and `memo`'d.
- [ ] Colors are **theme-aware** (checked in light *and* dark mode).
- [ ] **Anti-flicker** timing applied (delay + minimum duration).
- [ ] Full skeleton shows on **initial load only**; refetch/pagination use inline
      indicators.
- [ ] **Reduced motion** respected (`speed={0}`).
- [ ] Loading region has an **accessibility label** ("Loading content").
- [ ] Built via **dev client / EAS** (not Expo Go) — native peers are linked.
