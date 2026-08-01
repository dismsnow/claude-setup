# New Architecture (Prebuild)

**Impact: HIGH** — determines whether Fabric, TurboModules, and bridgeless are actually in play.

**Applies to:** New projects — adopt at setup (it is the default). | New code — write TurboModule-compatible native code.
**Existing working code:** Do not flip this on a shipping app as a "quick win". It changes every native module's execution path. Report the state if asked; migrate only as deliberate, tested work.

## Quick Config

```js
// app.config.js — the app config ROOT, not inside a plugin
export default {
  expo: {
    newArchEnabled: true,
  },
};
```

**Do not use `expo-build-properties`' `android.newArchEnabled` / `ios.newArchEnabled` — both are deprecated.** They still type-check, which makes the mistake easy to miss.

## What it actually enables

| Piece | Replaces | Why it matters for performance |
|---|---|---|
| **Fabric** | Legacy UIManager | Renderer with synchronous layout access; enables view flattening (`native-view-flattening.md`) |
| **TurboModules** | Legacy native modules | Lazy module init and direct JSI calls instead of serialized bridge traffic |
| **Bridgeless** | The asynchronous bridge | Removes the JSON-serialized bridge entirely |
| **Codegen** | Hand-written bindings | Typed native interfaces generated from JS specs |

The practical payoff is the removal of serialization overhead on the hot path — most visible in native module call volume and in list/layout work.

## Step 1: Find out what the project is actually running

Enabling the flag and having it take effect are different things. Verify at runtime:

```js
// Diagnostic only — these are React Native internals, not public API.
// Do not branch product logic on them.
console.log('Fabric:', global.nativeFabricUIManager != null);
console.log('Bridgeless:', global.RN$Bridgeless === true);
```

And confirm the generated native config after prebuild:

```bash
npx expo prebuild -p android --clean --no-install
grep -n "newArchEnabled" android/gradle.properties
```

If the flag is set in app config but the generated property disagrees, a plugin or a stale native directory is overriding it.

## Step 2: Triage incompatible dependencies

The interop layer lets many legacy modules run under the New Architecture, but it costs the very overhead the migration removes — and not every module works. Before assuming a dependency blocks you:

1. Check the library's current version for New Architecture support; it may already be supported in a newer release.
2. Check whether it works *through interop* — many do. Correct-but-slower is a valid interim state.
3. Look for a maintained replacement. Prefer libraries with a TurboModule implementation (`native-sdks-over-polyfills.md`).
4. If it is genuinely blocking and unmaintained, that dependency — not the architecture — is the thing to fix.

A single legacy module running via interop does not negate the benefit for the rest of the app.

## Deep Dive: version context

The New Architecture is the default for new projects on current Expo SDKs, and Expo has been phasing out legacy-architecture support across SDK releases. Because that timeline moves every release, **check the release notes for the SDK you are actually on** rather than trusting a remembered cutoff — the answer to "can I still opt out?" changes per SDK.

For a **new project**: leave it on. It is the default, and starting on the legacy architecture means planning a migration you could have avoided.

For an **existing app**: treat enabling it as a project with testing, not a config tweak. The flag changes how every native module executes.

## Common Pitfalls

- **Setting the deprecated plugin property** instead of the app config root, then concluding the New Architecture "doesn't work".
- **Branching product logic on `global.nativeFabricUIManager`.** Internal and unstable; use it for diagnostics only.
- **Flipping it on in an existing app to fix a performance problem.** Profile first (`js-measure-fps.md`, `native-profiling.md`). It is an architecture migration, not a targeted fix.
- **Assuming it's on because the flag is in app config.** A stale native directory or a plugin can override it. Verify (`prebuild-verify-native-changes.md`).
- **Writing new native modules against the legacy API.** New native code should be a TurboModule — see `native-turbo-modules.md`.

## Related

- `native-turbo-modules.md` — writing modules for this architecture
- `native-view-flattening.md` — Fabric-era view hierarchy work
- `native-threading-model.md` — threading under TurboModules
- `prebuild-verify-native-changes.md` — confirming the flag reached the build

---
Verified against: Expo SDK 54, React Native 0.81 (Aug 2026). `newArchEnabled` confirmed as an app config root key in `@expo/config-types`; the `expo-build-properties` platform variants are marked deprecated in 0.14.8.
Legacy-architecture support timelines change per SDK — check the release notes for your SDK version.
