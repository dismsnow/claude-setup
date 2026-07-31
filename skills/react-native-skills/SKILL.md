---
name: react-native-skills
description: React Native and Expo best practices for building performant mobile apps. Use when building React Native components, optimizing list performance, implementing animations with Reanimated, working with navigation, styling, or native platform APIs. Auto-applies when writing or reviewing any .tsx screen or component file.
license: MIT
metadata:
  author: vercel (adapted for Claude Code)
  version: '1.0.0'
---

# React Native Skills

Comprehensive best practices for React Native and Expo applications. Contains
rules across multiple categories covering performance, animations, UI patterns,
and platform-specific optimizations.

## When to Apply

Reference these guidelines when:

- Building or reviewing any React Native / Expo screen or component
- Optimizing list and scroll performance
- Implementing animations with Reanimated or gestures
- Working with images and media
- Handling safe areas, modals, and navigation
- Writing state management logic
- Configuring native modules or fonts

## Rule Categories by Priority

| Priority | Category         | Impact   | Prefix               |
| -------- | ---------------- | -------- | -------------------- |
| 1        | Core Rendering   | CRITICAL | `rendering-`         |
| 2        | List Performance | HIGH     | `list-performance-`  |
| 3        | Animation        | HIGH     | `animation-`         |
| 4        | Scroll           | HIGH     | `scroll-`            |
| 5        | Navigation       | HIGH     | `navigation-`        |
| 6        | UI Patterns      | HIGH     | `ui-`                |
| 7        | State Management | MEDIUM   | `react-state-`, `state-` |
| 8        | React Compiler   | MEDIUM   | `react-compiler-`    |
| 9        | Design System    | MEDIUM   | `design-system-`     |
| 10       | Monorepo         | LOW      | `monorepo-`          |
| 11       | Configuration    | LOW      | `fonts-`, `imports-`, `js-` |

---

## Quick Reference

### 1. Core Rendering (CRITICAL — prevents crashes)

- **`rendering-text-in-text-component`** — Always wrap strings in `<Text>`. RN crashes if a string is a direct child of `<View>`.
- **`rendering-no-falsy-and`** — Never use `{value && <Component />}` when value could be `0` or `""`. Use ternary or `!!value`.

### 2. List Performance (HIGH)

- **`list-performance-virtualize`** — Use FlashList or LegendList instead of ScrollView with mapped children, even for short lists.
- **`list-performance-item-memo`** — Pass only primitive props to list items so `memo()` shallow comparison works correctly.
- **`list-performance-callbacks`** — Hoist callbacks to the root of the list; items call it with an ID, not an inline function.
- **`list-performance-inline-objects`** — Never create new objects inside `renderItem`. Pass primitives or pass `item` directly.
- **`list-performance-function-references`** — Don't map/filter data before passing to lists. Keep stable object references.
- **`list-performance-images`** — Use compressed, appropriately-sized images (2× display size). Use CDN resize params.
- **`list-performance-item-expensive`** — Keep list items lightweight: no queries, no context, no expensive hooks.
- **`list-performance-item-types`** — Use `getItemType` for heterogeneous lists (different item layouts). Separate recycling pools.

### 3. Animation (HIGH)

- **`animation-gpu-properties`** — Animate only `transform` and `opacity`. Never animate `width`, `height`, `top`, `left`, `margin`, `padding`.
- **`animation-derived-value`** — Use `useDerivedValue` (not `useAnimatedReaction`) for deriving one shared value from another.
- **`animation-gesture-detector-press`** — For animated press states, use `GestureDetector` + `Gesture.Tap()`. Store press state (0/1), derive scale via `interpolate`.

### 4. Scroll (HIGH)

- **`scroll-position-no-state`** — Never store scroll position in `useState`. Use Reanimated `useSharedValue` for animations, `useRef` for tracking.

### 5. Navigation (HIGH)

- **`navigation-native-navigators`** — Always use `@react-navigation/native-stack` (not `@react-navigation/stack`). For tabs, use native bottom tabs. Prefer native header options over custom header components.

### 6. UI Patterns (HIGH/MEDIUM)

- **`ui-expo-image`** — Use `expo-image` instead of RN's `Image`. Better caching, blurhash placeholders, progressive loading.
- **`ui-pressable`** — Use `Pressable` instead of `TouchableOpacity` or `TouchableHighlight`.
- **`ui-safe-area-scroll`** — Use `contentInsetAdjustmentBehavior="automatic"` on root ScrollView instead of SafeAreaView wrapper.
- **`ui-scrollview-content-inset`** — Use `contentInset` (not padding) for dynamic spacing that changes (keyboard, toolbars).
- **`ui-menus`** — Use native menus (zeego) instead of custom JS dropdown/context menus.
- **`ui-native-modals`** — Use native `<Modal presentationStyle="formSheet">` or RN7 form sheet instead of JS bottom sheet libraries.
- **`ui-measure-views`** — Use `useLayoutEffect` + `onLayout` for view measurement. Use setState updater to avoid unnecessary re-renders.
- **`ui-image-gallery`** — Use `@nandorojo/galeria` for image lightboxes/galleries.
- **`ui-styling`** — Use `borderCurve: 'continuous'` with borderRadius. Use `gap` not margin for spacing. Use CSS `boxShadow` string syntax.

### 7. State Management (MEDIUM)

- **`react-state-minimize`** — Minimize state. Derive values during render instead of storing redundant state.
- **`react-state-dispatcher`** — When next state depends on current state, use updater `setState(prev => ...)` to avoid stale closures.
- **`react-state-fallback`** — Use `undefined` as initial state + `??` for fallback. State = user intent only.
- **`state-ground-truth`** — State should store ground truth (e.g. `pressed: 0|1`), not derived visual values (e.g. `scale`). Derive visuals via `interpolate`.

### 8. React Compiler (MEDIUM)

- **`react-compiler-destructure-functions`** — Destructure functions from hooks at top of render (`const { push } = useRouter()`). Never dot into objects in callbacks.
- **`react-compiler-reanimated-shared-values`** — Use `.get()` / `.set()` instead of `.value` on Reanimated shared values when React Compiler is enabled.

### 9. Design System (MEDIUM)

- **`design-system-compound-components`** — Use compound components (`Button`, `ButtonText`, `ButtonIcon`) instead of polymorphic children.

### 10. Monorepo (LOW)

- **`monorepo-native-deps-in-app`** — In a monorepo, native deps must be installed in the app package (autolinking only scans app's `node_modules`).
- **`monorepo-single-dependency-versions`** — Use a single exact version of each dep across all packages. Use `pnpm.overrides` or `resolutions`.

### 11. Configuration (LOW)

- **`fonts-config-plugin`** — Use `expo-font` config plugin to embed fonts at build time. Avoid `useFonts` / `Font.loadAsync`.
- **`imports-design-system-folder`** — Re-export all dependencies from a design system folder. App code imports from there, never directly from packages.
- **`js-hoist-intl`** — Hoist `Intl.DateTimeFormat`, `Intl.NumberFormat`, etc. to module scope. Never create them inside render or loops.

---

## How to Use

Each rule file in `rules/` contains:
- Why it matters
- Incorrect code example
- Correct code example
- Additional context

```bash
# Reference a specific rule
rules/list-performance-virtualize.md
rules/animation-gpu-properties.md
rules/rendering-no-falsy-and.md
```

## Problem → Rule Mapping

| Problem | Rule |
|---------|------|
| App crashes with text error | `rendering-text-in-text-component` |
| App crashes with 0 or "" rendering | `rendering-no-falsy-and` |
| Slow/janky list scrolling | `list-performance-virtualize` → `list-performance-function-references` |
| List items re-render too much | `list-performance-item-memo` → `list-performance-inline-objects` |
| Scroll position causes jank | `scroll-position-no-state` |
| Animation not smooth / drops frames | `animation-gpu-properties` → `animation-gesture-detector-press` |
| Press animation goes through JS bridge | `animation-gesture-detector-press` |
| Deriving animated values | `animation-derived-value` |
| Navigation feels slow | `navigation-native-navigators` |
| Image loading slow in lists | `list-performance-images` → `ui-expo-image` |
| Bottom sheet / modal feels janky | `ui-native-modals` |
| Safe area layout issues | `ui-safe-area-scroll` |
| Stale state in callbacks | `react-state-dispatcher` |
| Too many state variables | `react-state-minimize` |
| Shared value breaks with React Compiler | `react-compiler-reanimated-shared-values` |
| Font loading causes flash | `fonts-config-plugin` |
