---
name: react-native-image-ux
description: >-
  Image loading UX in React Native — placeholders, transitions, caching and
  prefetching with expo-image so images never pop in, shift the layout, or leave
  grey boxes. Use when adding images to a list, feed, grid, avatar or detail
  screen; when images flash, pop in, or push content around as they load; when a
  recycled list row briefly shows the previous item's image; or when choosing an
  image component or caching library. Trigger on "image placeholder", "blurhash",
  "thumbhash", "image loading", "images pop in", "layout shift", "image cache",
  "prefetch images", "avatar", "product grid", "photo list", "fast-image",
  "expo-image", or any FlatList/FlashList whose rows contain remote images.
---

# React Native Image UX

Images are usually the largest, slowest thing on a screen and the most common
source of visible jank. Almost all of it comes from one omission.

---

## The one rule that matters most

**Reserve the image's box before the bytes arrive.**

An image with no known height occupies zero space until it loads, then suddenly
occupies hundreds of pixels — shoving everything below it down the screen. This
is mobile's version of Cumulative Layout Shift, and it is the same failure the
skeleton skill exists to prevent: *the placeholder's dimensions must equal the
real content's dimensions.*

```tsx
// Wrong — height is unknown until load, so the layout jumps
<Image source={{ uri }} />
```

```tsx
// Right — the box exists from first paint
<Image source={{ uri }} style={{ width: '100%', aspectRatio: 16 / 9 }} />
```

Use `aspectRatio` when the shape is known but the width is fluid; use fixed
`width`/`height` for avatars and thumbnails. Either way the space is claimed
before the network is touched. Everything else here improves what the user sees
*inside* that reserved box.

---

## Stack selection

| Project | Package | Fabric | Adds a `.so`? |
| --- | --- | --- | --- |
| **Expo** (recommended) | `expo-image` | ✅ | **No** |
| **Bare RN** (recommended) | `npx install-expo-modules` → `expo-image` | ✅ | **No** |
| Bare RN, Expo-free | `react-native-turbo-image` (Nuke/Coil) | ✅ | **Yes** — check 16 KB |
| Bare RN, Expo-free | `@d11/react-native-fast-image` (maintained fork) | ✅ | **Yes** — check 16 KB |
| ❌ Avoid | `react-native-fast-image` (original) | ❌ | — |

> [!WARNING]
> The original `react-native-fast-image` is unmaintained and **does not support
> the New Architecture**. Do not add it to a new project. If a project already
> has it, migrating to `expo-image` is mostly mechanical.

`expo-image` is a Kotlin/Swift module over Glide (Android) and SDWebImage (iOS).
It rides `expo-modules-core` and **adds no new native binary**, so it does not
change your Android 16 KB alignment surface. The Expo-free alternatives both ship
native code and therefore do require a fresh alignment check — see
`react-native-best-practices` → `native-android-16kb-alignment.md`.

Using `expo-image` in a bare app is officially supported:

```bash
npx install-expo-modules       # adds the small `expo` package
npx expo install expo-image
npx pod-install
```

Also remove any legacy placeholder library — `react-native-image-placeholder`
and similar wrappers are entirely superseded by the `placeholder` prop below.

---

## The props that matter

```tsx
import { Image } from 'expo-image';

<Image
  source={{ uri }}
  placeholder={{ thumbhash }}       // instant preview
  placeholderContentFit="cover"
  contentFit="cover"
  transition={200}                  // cross-fade, not a pop
  cachePolicy="memory-disk"
  priority="high"
  style={{ width: '100%', aspectRatio: 16 / 9 }}
/>
```

| Prop | Why it matters |
| --- | --- |
| `placeholder` | Blurhash/thumbhash preview shown instantly. The main perceived-speed win |
| `placeholderContentFit` | How the placeholder fills the box (default `scale-down`) — mismatching `contentFit` causes a visible jolt |
| `transition` | Cross-fade in ms. Without it images *pop* |
| `cachePolicy` | `none` \| `disk` (default) \| `memory` \| `memory-disk` |
| `priority` | `low` \| `normal` \| `high` — ordering when many load at once |
| `recyclingKey` | **Essential in virtualized lists** — see below |
| `allowDownscaling` | Downscale to the view size; keeps memory down on large images |
| `contentFit` | `cover` \| `contain` \| `fill` \| `none` \| `scale-down` |

**`cachePolicy="memory-disk"`** is the right default for anything the user will
see more than once — avatars, list thumbnails, anything on a screen they return
to. It makes repeat renders instant. Use plain `disk` for large one-off images
where holding them in memory isn't worth it.

Set `placeholderContentFit` to the **same value** as `contentFit`. If the
placeholder is `scale-down` and the image is `cover`, the preview visibly
re-frames at the moment of swap.

---

## `recyclingKey` — the virtualized-list bug

In `FlashList` or `FlatList`, row components are **recycled**: the same mounted
component is reused for a different item as you scroll. Without a recycling key,
the view keeps showing the *previous* item's image until the new one loads.

The result is a list that briefly shows the wrong photo next to the right text.
It looks like a data bug and gets debugged as one.

```tsx
// Wrong — recycled rows show the previous row's image for a frame
<Image source={{ uri: item.photoUrl }} style={styles.thumb} />
```

```tsx
// Right — resets to the placeholder the moment the row is reused
<Image
  source={{ uri: item.photoUrl }}
  recyclingKey={item.id}
  placeholder={{ thumbhash: item.thumbhash }}
  transition={150}
  style={styles.thumb}
/>
```

Any `expo-image` inside a virtualized list needs `recyclingKey`. Use the item's
stable id — the same value you return from `keyExtractor`.

---

## Placeholders: thumbhash over blurhash

Both encode a tiny preview into a short string you store alongside the image URL,
so a recognisable blur appears **instantly** — no network round-trip.

**Prefer ThumbHash.** Compared to BlurHash it encodes more detail in the same
space, carries the aspect ratio, reproduces colour more accurately, and supports
alpha. BlurHash remains fine where it's already in use — a 28-character blurhash
decodes in well under a millisecond.

```tsx
<Image source={{ uri }} placeholder={{ thumbhash: item.thumbhash }} />
<Image source={{ uri }} placeholder={{ blurhash: item.blurhash }} />
```

### Where the hash comes from

The hash must be computed **server-side or at build time** and stored next to the
URL — usually one short text column. Computing it on the device requires
downloading the image first, which defeats the entire purpose.

If your backend can't produce one yet, don't fall back to a grey box. Store a
single dominant colour (cheap to compute, one column) and use it as the
placeholder:

```tsx
<Image
  source={{ uri }}
  placeholder={item.dominantColor ?? '#E1E9EE'}
  transition={200}
/>
```

A tinted box that roughly matches the incoming image is much less jarring than
grey, and it costs one column.

### Placeholder vs. skeleton

They solve different halves of the same problem and compose well:

- **Skeleton** — the row's *structure* before you have any data at all.
- **Image placeholder** — the image's *content* once you have the URL but not
  the bytes.

A list typically shows a skeleton first, then real rows whose images are
thumbhash placeholders resolving into photos. See the
`react-native-skeleton-placeholder` skill for the structure half.

---

## Prefetching: make the next screen instant

The cheapest perceived-performance win available. When the user is looking at a
list, you already know which detail image they may open next.

```tsx
import { Image } from 'expo-image';

// Warm the cache before navigation
Image.prefetch(visibleItems.map(i => i.heroUrl), { cachePolicy: 'memory-disk' });
```

Practical guidance:

- Prefetch **on the previous screen**, not on mount of the current one.
- Prefetch what is **likely**, not everything — a handful of visible rows, not
  the whole list. Over-prefetching wastes the user's data.
- Prefetch heroes and above-the-fold images only.
- On a metered connection, or when the user has Low Data Mode on, skip it.

`useImage` is available when you need the loaded instance itself (dimensions,
manual control) rather than a rendered view.

---

## Sizing and memory

- **Request the size you display.** A 4000 px image in a 120 px thumbnail wastes
  bandwidth, decode time and memory. Use CDN resize parameters where available.
- **Roughly 2× the display size** covers high-density screens; beyond that is
  waste.
- **`allowDownscaling`** (default on) keeps decoded bitmaps proportional to the
  view. Leave it on unless you're zooming.
- **`priority="low"`** for below-the-fold images so heroes win the queue.
- Large image grids are where memory pressure shows first — combine correct
  sizing with `recyclingKey` and list virtualization.

For the list-performance side of this, see `react-native-skills` →
`list-performance-images`.

---

## Local and offline images

Locally-stored photos have no network delay, but the other rules still apply.

- **Store file paths, not base64.** Base64 in a database row is the classic cause
  of Android `CursorWindow` crashes, and it bloats memory. Keep the bytes on disk
  and the path in the row.
- Point `source` at the `file://` URI directly — `expo-image` renders it without
  a network fetch.
- **Still reserve the box.** Decoding a large local photo is not instant, so
  layout shift is still possible.
- `cachePolicy` is irrelevant for local files; `transition` still is not — a
  short fade avoids a hard flash on decode.
- Bundled assets (`require('./logo.png')`) are already local; note that on
  release Android an `expo-asset` `localUri` is a drawable resource name, not a
  filesystem path — if you need the bytes for a PDF or HTML export, embed base64
  at that point rather than reading the path.

---

## A wrapper so the library is named once

Like the other skills here, keep the choice in one file. This also gives you a
single place to enforce the defaults that are easy to forget.

```tsx
// components/AppImage.tsx
import { Image, type ImageProps } from 'expo-image';

type Props = ImageProps & { thumbhash?: string; id?: string };

export function AppImage({ thumbhash, id, ...rest }: Props) {
  return (
    <Image
      placeholder={thumbhash ? { thumbhash } : '#E1E9EE'}
      placeholderContentFit={rest.contentFit ?? 'cover'}
      contentFit="cover"
      transition={200}
      cachePolicy="memory-disk"
      recyclingKey={id}
      {...rest}
    />
  );
}
```

If you later move to `react-native-turbo-image`, only this file changes. The
prop names differ between libraries, but the concepts — placeholder, transition,
cache policy, priority — exist in all of them.

---

## Accessibility

- Meaningful images need `accessibilityLabel` describing **what they show**, not
  "image".
- Decorative images should be hidden: `accessible={false}` /
  `accessibilityElementsHidden`. A screen reader announcing every decorative
  divider is worse than silence.
- Never put text only inside an image — it can't be read, scaled, or translated.
- If an image is the sole content of a tappable row, the row needs its own label.

---

## Common pitfalls

- **No reserved box.** The top rule. Everything below is secondary.
- **Missing `recyclingKey` in a list** — recycled rows show the previous image.
  Reads as a data bug.
- **No `placeholder`** — a grey box, then a pop.
- **No `transition`** — images snap in harshly.
- **`placeholderContentFit` mismatching `contentFit`** — the preview re-frames on swap.
- **Computing a blurhash on-device** — requires the download first; pointless.
- **Full-resolution images in thumbnails** — bandwidth, memory, decode time.
- **Prefetching an entire list** — burns the user's data allowance.
- **`cachePolicy="none"`** on repeatedly-viewed images — refetches every time.
- **Base64 image data in the database** — `CursorWindow` crashes on Android.
- **Adding `react-native-fast-image`** (original) to a New Architecture app.
- **Keeping a legacy placeholder wrapper** alongside `expo-image`, which already
  does it natively.

---

## Pre-ship checklist

- [ ] Every image has a **reserved box** — fixed dimensions or `aspectRatio`.
- [ ] Every image in a virtualized list has **`recyclingKey`**.
- [ ] `placeholder` set — thumbhash preferred, blurhash acceptable, dominant
      colour as the fallback. Never a bare grey box.
- [ ] `placeholderContentFit` matches `contentFit`.
- [ ] `transition` set (~150–250 ms).
- [ ] `cachePolicy="memory-disk"` for anything seen more than once.
- [ ] Hashes generated **server-side or at build time**, stored with the URL.
- [ ] Images requested at roughly display size, not full resolution.
- [ ] Next-screen heroes prefetched; prefetching bounded and skipped on metered
      connections.
- [ ] Local photos stored as **file paths**, never base64 in a row.
- [ ] Meaningful images labelled; decorative images hidden from screen readers.
- [ ] No unmaintained image library on a New Architecture app; any native
      alternative has passed a **16 KB alignment** check.
