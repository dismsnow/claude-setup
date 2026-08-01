# expo-build-properties: Declarative Native Config

**Impact: HIGH** — the correct place for nearly every native performance knob in a CNG project.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit. Report the difference if asked; change nothing that already ships.

## Quick Config

```bash
npx expo install expo-build-properties
```

```js
// app.config.js
plugins: [
  [
    'expo-build-properties',
    {
      android: {
        enableProguardInReleaseBuilds: true,
        enableShrinkResourcesInReleaseBuilds: true,
      },
      ios: {
        ccacheEnabled: true,
      },
    },
  ],
],
```

The plugin writes these into the generated Gradle/Podfile on every prebuild, so the settings are reproducible from source.

## Android properties

| Property | Default | Performance relevance |
|---|---|---|
| `enableProguardInReleaseBuilds` | `false` | **HIGH** — R8 code shrinking + obfuscation. The single biggest Android size win. |
| `enableShrinkResourcesInReleaseBuilds` | `false` | **HIGH** — strips unused resources. Requires the ProGuard flag above to be on. |
| `extraProguardRules` | — | Keep-rules needed once shrinking is on. Appended to `proguard-rules.pro`. |
| `enablePngCrunchInReleaseBuilds` | `true` | Already on. Can *inflate* already-optimized PNGs — disable only if you optimize them yourself. |
| `enableBundleCompression` | `false` | **Leave off for startup speed.** On = smaller APK, slower startup (blocks Hermes mmap). Already the fast default. |
| `useLegacyPackaging` | `false` | On = compressed native libs: smaller download, more install size and slower load. Off is the modern default. |
| `packagingOptions` | — | `pickFirst` / `exclude` / `merge` / `doNotStrip` for duplicate or symbol-heavy `.so` files. |
| `buildFromSource` | `false` | **Leave off.** Builds React Native from source and significantly increases build times. |
| `minSdkVersion` / `compileSdkVersion` / `targetSdkVersion` | SDK default | Raise deliberately; store policy drives `targetSdkVersion`. |
| `buildToolsVersion` / `kotlinVersion` | SDK default | Override only to resolve a concrete conflict. |
| `extraMavenRepos` | — | Extra Gradle repositories. Replaces a hand-written Gradle-patching plugin. |
| `manifestQueries` | — | Android package visibility (`package` / `intent` / `provider`). |
| `usesCleartextTraffic` | `false` | **Security** — keep `false`. See the security skill. |
| `useDayNightTheme` | — | DayNight theme variant for correct dark-mode support. |
| `networkInspector` | `true` | Dev-client network inspection (`EX_DEV_CLIENT_NETWORK_INSPECTOR`). |

**Do not set `android.newArchEnabled` here — it is deprecated.** Use the app config root instead; see `prebuild-new-architecture.md`.

## iOS properties

| Property | Default | Performance relevance |
|---|---|---|
| `ccacheEnabled` | `false` | **Build speed** — caches C++ compilation across builds. Big local-iteration win, no runtime effect. |
| `useFrameworks` | — | `'static'` or `'dynamic'`. Affects launch time and pod compatibility — see `prebuild-ios-release-build.md`. |
| `deploymentTarget` | SDK default | Raising it drops old-OS users; only raise when a dependency demands it. |
| `extraPods` | — | Extra CocoaPods entries (`name`, `version`, `configurations`, `git`/`tag`, `modular_headers`, …). |
| `privacyManifestAggregationEnabled` | — | Merges pod `PrivacyInfo.xcprivacy` files. Compliance, not performance. |
| `networkInspector` | `true` | Dev-client network inspection. |

Same rule as Android: `ios.newArchEnabled` is deprecated — use the app config root.

## Deep Dive: extraMavenRepos instead of a custom Gradle plugin

Adding a Maven repository is the most common reason people hand-write a Gradle-patching config plugin. It is a supported property, so prefer it:

```js
android: {
  extraMavenRepos: [
    'https://example.com/maven-releases',
    {
      url: 'https://example.com/private',
      // Read secrets from the environment — never hardcode them in app config,
      // which is committed and also readable in the shipped bundle.
      credentials: { username: "System.getenv('MAVEN_USER')", password: "System.getenv('MAVEN_PASS')" },
      authentication: 'basic',
    },
  ],
}
```

A plain string is shorthand for `{ url }`. Only drop to a custom plugin when the change genuinely has no property (see `prebuild-config-plugin-authoring.md`).

## Common Pitfalls

- **Enabling `enableShrinkResourcesInReleaseBuilds` without `enableProguardInReleaseBuilds`.** Resource shrinking depends on code shrinking; alone it does nothing useful. Set both.
- **Turning on shrinking without keep-rules, then shipping.** Reflection-based libraries break at runtime, not build time. Always smoke-test a real release build — see `prebuild-android-release-build.md`.
- **Enabling `enableBundleCompression` to "reduce app size" and regressing startup.** It is off by default precisely because startup matters more for most apps. Measure TTI before and after (`native-measure-tti.md`).
- **Setting `newArchEnabled` in the plugin.** Deprecated and easy to miss because it still type-checks.
- **Assuming a property exists.** Verify against `node_modules/expo-build-properties/build/pluginConfig.d.ts` in the installed version. Invented keys fail validation at prebuild time.

## Related

- `prebuild-cng-workflow.md` — when to reach for this vs. a custom plugin
- `prebuild-android-release-build.md` / `prebuild-ios-release-build.md` — applying these per platform
- `prebuild-verify-native-changes.md` — confirming the generated output changed

---
Verified against: expo-build-properties 0.14.8 (`build/pluginConfig.d.ts`), Expo SDK 54, React Native 0.81 (Aug 2026).
Property names and defaults change between versions — re-read the installed `pluginConfig.d.ts` before relying on them.
