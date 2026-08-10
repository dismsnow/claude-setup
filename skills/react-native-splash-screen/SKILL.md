---
name: react-native-splash-screen
description: Splash screen / launch screen best practices for React Native and Expo. Covers whether to hand-edit native code (almost always no), the expo-splash-screen config plugin, Android 12+ SplashScreen API geometry and icon masking, iOS launch storyboards, when to hide the splash, animated splash handoff to a JS overlay, react-native-bootsplash for bare RN, and why the splash is never where cold-start time is actually lost. Use when adding or fixing a splash screen, seeing a white flash or double splash on launch, a logo clipped into a circle on Android, a splash that never dismisses, or when deciding between the config plugin, a custom config plugin, and native edits.
license: MIT
metadata:
  tags: react-native, expo, splash-screen, launch-screen, startup, tti, android-12, cng
---

# React Native / Expo Splash Screens

## The short answer to "should we touch native code?"

**No — and it would not make anything faster.**

The native splash is drawn by the OS from a **static theme resource** (Android) or a
**storyboard** (iOS) *before* your process is warm, before the React Native runtime
initialises, before Hermes loads the bundle, before a single line of JS runs. There is no
work happening there to optimise. It is already the cheapest frame your app will ever draw.

Three concrete reasons to stay out of the native directories:

1. **It gets deleted.** In an Expo project using Continuous Native Generation, `android/`
   and `ios/` are generated artefacts. `expo prebuild --clean` discards hand edits. Check
   before you touch anything: `grep -nE '^/?(ios|android)/?$' .gitignore` — a match means generated.
2. **Google explicitly says don't.** Since Android 12 the system owns the splash window. Apps
   that disable it and draw their own splash Activity get a *double* splash — the system one,
   then yours — which is the single most common cause of the "flicker / white flash" bug reports.
3. **The perf win isn't there.** Cold start is lost in the JS bundle, blocking update checks,
   and font/asset loading — see [What actually costs startup time](#what-actually-costs-startup-time).

**The one legitimate reason to reach lower** is a capability the `expo-splash-screen` plugin
doesn't expose (an animated Android 12 icon, a custom exit animation). Even then the answer is
a **config plugin**, not a hand edit — see [When you genuinely need more](#when-you-genuinely-need-more).

---

## Mental model: three phases, three owners

A cold launch has three visually distinct phases. Most splash bugs are a mismatch at a seam.

| Phase | Owner | Duration | You control |
|-------|-------|----------|-------------|
| 1. System splash | OS (theme / storyboard) | ~launch → first RN frame | Colour + icon only, declaratively |
| 2. Held splash | `expo-splash-screen` | Until you call `hide()` | *How long* — this is the lever |
| 3. JS gate (optional) | Your React tree | Until app is ready | Everything, incl. animation |

Phase 1 is free and uncontrollable. Phase 2 is where you decide when the app is "ready".
Phase 3 exists only if you want animation or branding the system splash can't express.

**The seams are where flicker comes from.** A white flash between 1→2 or 2→3 means the
background colours don't match, or you hid the splash before the first real frame was ready.

---

## Expo: the declarative setup

Configure via the **config plugin**, not the legacy `splash` key.

```js
// app.config.js
plugins: [
  [
    'expo-splash-screen',
    {
      image: './assets/images/splash-mark.png',
      imageWidth: 200,
      resizeMode: 'contain',
      backgroundColor: '#ffffff',
      dark: {
        image: './assets/images/splash-mark-dark.png',
        backgroundColor: '#000000',
      },
      // Per-platform overrides — useful because Android masks and iOS doesn't
      ios: { imageWidth: 300 },
      android: { imageWidth: 200 },
    },
  ],
],
```

### Plugin props

| Prop | Default | Notes |
|------|---------|-------|
| `backgroundColor` | `#ffffff` | Must be opaque. Android requires a single solid colour. |
| `image` | — | PNG only. 1024×1024, transparent background. |
| `imageWidth` | `100` | Drawn width in **dp/pt**, not pixels. |
| `resizeMode` | — | `contain` \| `cover` \| `native` |
| `dark` | — | `{ image, backgroundColor }` overrides |
| `ios` / `android` | — | Per-platform override objects |
| `enableFullScreenImage_legacy` | `false` | **iOS only**, deprecated. Avoid. |

### The legacy `splash` key is on its way out

```js
// ❌ Legacy — deprecated since SDK 52, still shimmed, will be removed
splash: { image: './assets/splash.png', resizeMode: 'cover', backgroundColor: '#fff' }
```

Expo currently auto-maps this to the plugin, so it "works". But a top-level `splash` key
combined with a plugin entry produces conflicting output, and `resizeMode: 'cover'` encodes
a pre-Android-12 full-screen assumption that no longer holds. Migrate to the plugin and
delete the `splash` key entirely.

---

## Android 12+: the icon is masked, and this is what breaks logos

This is the single most surprising constraint, and the reason full-screen splash images are
gone on Android. The system draws your image on a fixed canvas and **masks it to a circle**.

```
Without windowSplashScreenIconBackgroundColor:
  canvas 288×288 dp   →   visible circle 192 dp diameter
With an icon background colour:
  canvas 240×240 dp   →   visible circle 160 dp diameter
Branding image (bottom):  200×80 dp   (Android's own design guidance says don't)
```

Everything outside that circle is invisible. A wide wordmark **will be clipped**.

### Sizing formula

`imageWidth` is the drawn width of your whole PNG. If the visible mark occupies fraction
`f` of the PNG's width, the mark renders at `imageWidth × f` dp.

- **Square-bounded artwork** must fit *inscribed* in the 192 dp circle → max side ≈ `192 / √2` ≈ **136 dp**
- **Circular artwork** can use the full **192 dp**
- Android's own guidance: keep content within the **inner two-thirds** of the canvas

Worked example: a 1024×1024 PNG where the mark occupies ~52% of the width, at
`imageWidth: 260` → mark renders at ~135 dp, corners ~95 dp from centre against the 96 dp
radius limit. Fits, barely.

**Practical consequence:** ship the *mark only* to the Android splash. If you need the full
lockup with wordmark, render it in the phase-3 JS gate, which has no mask. iOS has no mask
either, so `ios.image` can carry the full lockup.

### There is no full-screen splash image on Android anymore

If you're migrating from `resizeMode: 'cover'` with a full-bleed background image, that
design is not expressible on Android 12+. Replace it with background colour + centred mark.
Trying to reproduce it with a custom Activity reintroduces the double-splash bug.

---

## iOS: a generated storyboard

The plugin generates `SplashScreen.storyboard` — background colour with the image centred at
`imageWidth` points. No mask, so wider artwork is fine.

**iOS caches launch storyboards aggressively.** After changing splash config, a stale splash
on device is expected, not a bug. To clear it: delete the app from the device/simulator, or
rebuild with `--no-build-cache`.

---

## When to hide it

Call `preventAutoHideAsync()` at **module scope**, never inside a component or hook — from a
hook it can run after auto-hide has already fired, and the call silently does nothing.

```tsx
// app/_layout.tsx  (Expo Router)
import * as SplashScreen from 'expo-splash-screen';

SplashScreen.preventAutoHideAsync();
SplashScreen.setOptions({ duration: 400, fade: true });

export default function RootLayout() {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    (async () => {
      await loadFontsAndCriticalState();   // fast, local, bounded
      setIsReady(true);
    })();
  }, []);

  useEffect(() => {
    if (isReady) SplashScreen.hide();
  }, [isReady]);

  if (!isReady) return null;
  return <Stack />;
}
```

`setOptions({ fade })` is **iOS-only** — confirmed in the package's own type definitions
(`@platform ios`). Blog posts and even parts of the docs imply it's cross-platform. On Android
the splash always cuts. Don't build a design that depends on a synchronised cross-platform fade.

### Rules for the hide call

- **Hide as early as the first real frame is stable.** Both Google's guidance and Expo's docs
  say the same thing: the goal is to hide it as soon as possible.
- **Never `setTimeout` a minimum splash duration for branding.** It's a deliberate regression
  in the metric users actually feel, and Android's own guidance is against it.
- **Never block the hide on a network request.** Anything remote belongs behind a rendered
  skeleton, not behind the splash. If the network hangs, your app looks frozen at launch.
- **Guard against never hiding.** A `preventAutoHideAsync()` with a code path where `isReady`
  never flips is an app that never launches. If initialisation can fail, hide in a `finally`.

With Expo Router, the splash **auto-hides** once the app directory renders unless you called
`preventAutoHideAsync()` at module scope. If your splash vanishes early under Router, that's
the cause.

---

## What actually costs startup time

The splash is not where cold start is lost. In rough order of impact:

1. **`expo-updates` blocking the launch.** A non-zero `fallbackToCacheTimeout` blocks startup
   on an update check — this is the number-one cause of "white screen after the splash". Keep
   it at `0` (the default) so updates download in the background, or set `checkOnLaunch` to
   `NEVER` / `ERROR_RECOVERY_ONLY`.
2. **JS bundle size and parse time.** See the `react-native-best-practices` skill —
   `bundle-analyze-js`, `bundle-hermes-mmap` (disabling Android bundle compression enables
   Hermes mmap, a direct TTI win), `bundle-barrel-exports`.
3. **Work you put behind the splash.** Every `await` before `hide()` is time on the splash.
   Fonts and a cached auth token: fine. A remote config fetch or a DB migration: not fine.
4. **Asset decode.** A full-bleed splash bitmap has to be decoded at launch. The Android 12
   icon path avoids this by design; on iOS, `enableFullScreenImage_legacy` reintroduces it.

Measure rather than guess:

```bash
# Android cold-start timing (TotalTime is the number you care about)
adb shell am force-stop com.your.pkg
adb shell am start -W -n com.your.pkg/.MainActivity
```

Only measure **cold** starts, and only on a **release/preview** build — a dev build's timings
are meaningless.

---

## Animated splash: the phase-2 → phase-3 handoff

You cannot animate the native splash on Expo. The supported pattern is: let the native splash
hand off to a JS overlay that starts out **pixel-identical** to it, then animate the overlay.

```tsx
// Overlay must match the native splash exactly at t=0, or you get a visible jump.
const [splashDone, setSplashDone] = useState(false);
const opacity = useSharedValue(1);

// Same backgroundColor, same image, same width in dp, same centring as the plugin config.
{!splashDone && (
  <Animated.View style={[StyleSheet.absoluteFill, styles.matchesNativeSplash, animatedStyle]}
                 pointerEvents="none" />
)}
```

Getting the seam invisible:

- **Identical background colour** to `backgroundColor` in the plugin config.
- **Identical image geometry** — same asset, same dp width, centred.
- **Mind the insets.** Edge-to-edge is enforced on Android 15+ / SDK 54+. The native splash is
  drawn full-screen *behind* the system bars. If your overlay is inside a `SafeAreaView`, the
  logo shifts at the handoff. Position the overlay against the full window, not the safe area.
- **Mount the overlay before calling `hide()`**, not after — otherwise there's a frame where
  neither is on screen. That frame is the white flash.

Cost: this runs on the JS/UI thread while the app is booting, i.e. at the worst possible
moment. Keep it to opacity/transform on the UI thread (Reanimated worklets), never a JS-driven
`Animated` timing without `useNativeDriver`.

---

## Bare React Native: react-native-bootsplash

For non-Expo projects, `react-native-bootsplash` (zoontek) is the current standard. It
generates the Android 12 theme attributes and iOS storyboard for you, provides
`useHideAnimation` for a proper animated handoff, and exposes `statusBarTranslucent` /
`navigationBarTranslucent` specifically to kill the native→JS shift described above.

Two things to know before adopting it:

- It **ships an Expo config plugin**, so it's a legitimate alternative to `expo-splash-screen`
  in a prebuild project — mainly worth it if you want its animation API. Don't run both.
- **Brand assets and dark-mode generation require a paid licence key.** The logo path is free.
  Budget for this before designing around a brand image.

Hide it from React Navigation's `onReady` so the splash lifts exactly when the navigator has
mounted its first screen.

`react-native-splash-screen` (crazycodeboy) is the older library that predates the Android 12
API. Don't start new work on it.

---

## When you genuinely need more

These are real capabilities the `expo-splash-screen` plugin does not expose. All of them are
reachable from a **config plugin** — a file in your repo that patches the generated native
project on every prebuild, so it survives `--clean`. See `prebuild-config-plugin-authoring`
in the `react-native-best-practices` skill.

| Want | Native mechanism | Route |
|------|------------------|-------|
| Animated Android 12 icon | `windowSplashScreenAnimatedIcon` (AnimatedVectorDrawable, ≤1000 ms) + `windowSplashScreenAnimationDuration` | `withAndroidStyles` config plugin |
| Coloured disc behind the icon | `windowSplashScreenIconBackgroundColor` (shrinks safe area to 160 dp) | `withAndroidStyles` config plugin |
| Custom Android dismiss animation | `splashScreen.setOnExitAnimationListener { … }` | `withMainActivity` config plugin |
| Force icon on Android 13+ | `windowSplashScreenBehavior: icon_preferred` | `withAndroidStyles` config plugin |

Note the AVD constraint: Android's animated icon accepts **AnimatedVectorDrawable XML only** —
no Lottie, no GIF, no video. Anything richer than that has to live in the phase-3 JS overlay.

Config plugins must be **idempotent** — a plugin that appends on every run duplicates the block
after the second prebuild.

---

## Testing

**Do not evaluate a splash screen in Expo Go or a development build.** Since SDK 52, Expo Go
shows your *app icon* instead of your splash, and dev builds cannot fully replicate the native
splash. Expo's docs state this outright. Every "my splash config isn't applying" report that
turns out to be a non-issue is this.

```bash
eas build --profile preview --platform android   # or ios
```

- **iOS:** delete the app between builds, or `--no-build-cache`, to defeat storyboard caching.
- **Android:** test on API 31+ (masking) *and* an older device if you still support one.
- Test **light and dark** if you configured a `dark` variant.
- Test with the app **fully killed**, not backgrounded — a warm start shows no splash at all.

---

## Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Logo clipped into a circle on Android | Android 12+ 192 dp mask | Ship mark-only; reduce `imageWidth`; full lockup in the JS gate |
| App icon shows instead of splash | Testing in Expo Go | Build a preview/production build |
| White flash after splash | `expo-updates` blocking, or hiding before first frame | `fallbackToCacheTimeout: 0`; hide when content is mounted |
| Double splash / flicker | Custom splash Activity fighting the system splash | Delete it; use the system API |
| Splash never dismisses | `preventAutoHideAsync()` with a path where ready never flips | Hide in a `finally`; add a failure path |
| Splash hides instantly under Expo Router | Router auto-hides without `preventAutoHideAsync()` | Call it at module scope |
| Visible jump into the JS overlay | Colour/geometry mismatch, or safe-area insets | Match exactly; position against the full window |
| Fade works on iOS, cuts on Android | `setOptions({ fade })` is iOS-only | Don't design around a cross-platform fade |
| Config changes don't apply on iOS | Launch storyboard cached | Delete app / `--no-build-cache` |
| Splash config vanished after prebuild | Hand-edited a generated native file | Move it into a config plugin |
| Old splash returns after SDK upgrade | Legacy `splash` key still present alongside the plugin | Delete the `splash` key |

---

## Checklist

- [ ] Configured via the `expo-splash-screen` plugin; no legacy `splash` key anywhere
- [ ] Source image is a 1024×1024 transparent PNG
- [ ] Android artwork fits the 192 dp visible circle (≈136 dp for square-bounded marks)
- [ ] `backgroundColor` is opaque and matches the app's first screen
- [ ] `dark` variant set if the app supports dark mode
- [ ] `preventAutoHideAsync()` at module scope, not in a component
- [ ] Nothing network-dependent gated behind the splash
- [ ] A guaranteed hide path even when initialisation fails
- [ ] `expo-updates` `fallbackToCacheTimeout` is `0`
- [ ] No artificial minimum splash duration
- [ ] Any JS overlay matches the native splash pixel-for-pixel at t=0, ignoring safe-area insets
- [ ] Verified on a **release/preview** build, cold-started, both platforms
- [ ] No hand edits in `android/` or `ios/` if the project uses CNG

## Related skills

- **`react-native-best-practices`** — `native-measure-tti`, `bundle-hermes-mmap`,
  `prebuild-cng-workflow`, `prebuild-config-plugin-authoring`
- **`upgrading-react-native`** — splash config migrations across SDK bumps