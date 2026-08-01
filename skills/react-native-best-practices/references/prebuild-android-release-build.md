# Android Release Build Performance (Prebuild)

**Impact: HIGH** — the largest available Android size and startup wins, all declarative.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit a shipping release config. Report the difference if asked; change nothing that already ships.

This is the CNG counterpart to `bundle-r8-android.md` and `bundle-hermes-mmap.md`. Those describe the same settings as edits to `android/` files, which is correct for bare React Native and discarded in a CNG project.

## Quick Config

```js
// app.config.js
plugins: [
  [
    'expo-build-properties',
    {
      android: {
        // Code shrinking + obfuscation. Biggest single size win.
        enableProguardInReleaseBuilds: true,
        // Strips unused resources. Requires the flag above.
        enableShrinkResourcesInReleaseBuilds: true,
        // Keep-rules for anything reached by reflection.
        extraProguardRules: `
-keep class com.example.model.** { *; }
        `,
        // Leave OFF: compressing the JS bundle blocks Hermes mmap and slows startup.
        // enableBundleCompression: false  // already the default
      },
    },
  ],
],
```

## The four levers, in order of payoff

| Lever | Property | Effect | Risk |
|---|---|---|---|
| Code shrinking (R8) | `enableProguardInReleaseBuilds` | Large APK/AAB size reduction; also obfuscates | Reflection breaks without keep-rules |
| Resource shrinking | `enableShrinkResourcesInReleaseBuilds` | Removes unreferenced resources | Dynamically-named resources need keep-rules |
| JS bundle compression | `enableBundleCompression` | **Leave off.** On trades startup speed for APK size | Regresses TTI |
| Native lib packaging | `useLegacyPackaging`, `packagingOptions` | Download vs install size; drops duplicate `.so` | Wrong `pickFirst` can ship the wrong lib |

Ship an **AAB** for Play Store distribution so Google generates per-device splits — that removes unused ABIs and densities without any config on your side. Use APKs only for internal distribution and local testing.

## Step-by-step: turning on shrinking safely

1. Record a baseline. Build a release artifact and note its size (`bundle-analyze-app.md`).
2. Enable `enableProguardInReleaseBuilds` alone. Build. **Smoke-test the release build on a device** — not a debug build.
3. Exercise reflection-heavy paths: JSON deserialization into model classes, native module bridging, anything referenced by string name. These fail only at runtime.
4. Add `extraProguardRules` keep-rules for what broke. Keep them narrow — a blanket `-keep class **` cancels the optimization.
5. Add `enableShrinkResourcesInReleaseBuilds`. Rebuild, re-test, especially dynamically-referenced drawables.
6. Re-measure size and startup, and confirm both moved the way you expect.

Skipping step 3 is how shrinking ships a crash that never appears in development.

## Deep Dive: why bundle compression is off by default

React Native can memory-map an uncompressed Hermes bytecode bundle straight from the APK instead of decompressing it into memory at launch. Compressing the bundle defeats mmap: you save download size and pay for it on every cold start. Expo therefore defaults `enableBundleCompression` to `false`.

Practical consequence: on a modern Expo project **there is usually nothing to do here** — the fast path is already the default. Verify rather than "fix":

```bash
# After prebuild, confirm nothing turned compression on
grep -rn "enableBundleCompression\|expo.android.enableBundleCompression" android/gradle.properties app.config.js
```

Only if a project explicitly enabled it — and doesn't need the size saving — is turning it off an improvement. Measure TTI both ways (`native-measure-tti.md`) rather than assuming.

## Common Pitfalls

- **Enabling resource shrinking without code shrinking.** It needs R8's reachability data; alone it does nothing.
- **Testing shrinking against a debug build.** These properties only apply to release builds. A passing debug build proves nothing.
- **Over-broad keep-rules.** `-keep class **` makes the build succeed and the optimization pointless. Keep rules should name packages, not wildcards over everything.
- **Editing `proguard-rules.pro` directly.** Use `extraProguardRules` so it survives regeneration.
- **Comparing an APK against an AAB.** Different artifacts, not comparable sizes. Compare like to like across builds.
- **Assuming obfuscation is a security control.** R8 renames symbols; it does not protect secrets. See the security skill.

## Related

- `prebuild-build-properties.md` — the full property reference
- `prebuild-verify-native-changes.md` — confirm the generated Gradle actually changed
- `bundle-analyze-app.md` — measuring the size delta
- `native-measure-tti.md` — measuring the startup delta
- `native-android-16kb-alignment.md` — separate Play requirement, also native
- `bundle-r8-android.md` — the bare React Native form of these settings

---
Verified against: expo-build-properties 0.14.8, Expo SDK 54, React Native 0.81 (Aug 2026).
Defaults (notably `enableBundleCompression: false`) are version-specific — re-check the installed `pluginConfig.d.ts`.
