# iOS Release Build Performance (Prebuild)

**Impact: MEDIUM-HIGH** — fewer levers than Android, but `useFrameworks` and `ccacheEnabled` matter.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit a shipping release config. Report the difference if asked; change nothing that already ships.

## Quick Config

```js
// app.config.js
plugins: [
  [
    'expo-build-properties',
    {
      ios: {
        // Local build-speed win. No effect on the shipped app.
        ccacheEnabled: true,
        // Set only when a dependency requires it — see below.
        // useFrameworks: 'static',
        // Raise only when a dependency demands it; it drops older-OS users.
        // deploymentTarget: '15.1',
      },
    },
  ],
],
```

iOS has no R8 equivalent. App size is governed mostly by assets and native dependencies, and App Store thinning already strips unused architectures and resources per device.

## The levers

| Property | What it changes | When to set it |
|---|---|---|
| `ccacheEnabled` | Caches C++ compilation between builds | Local iteration and self-hosted CI. Pure developer-time win. |
| `useFrameworks` | `'static'` or `'dynamic'` pod linkage | Only when a dependency requires a specific mode. |
| `deploymentTarget` | Minimum iOS version | Only when a dependency demands a higher floor. |
| `extraPods` | Extra CocoaPods entries | A native dep with no config plugin. |
| `privacyManifestAggregationEnabled` | Merges pod privacy manifests | App Store compliance, not performance. |

## Deep Dive: useFrameworks is a compatibility switch, not a speed dial

The two modes trade launch time against compatibility:

- **`'static'`** — pods link into the app binary. Faster launch (no dynamic loading per framework), larger binary, and some pods that expect dynamic frameworks break.
- **`'dynamic'`** — pods build as separate dynamic frameworks. Each adds launch-time load cost, but Swift pods requiring dynamic linkage work.

Do not set this speculatively. Leave it unset unless a dependency's install instructions demand a mode or the pod install fails without one. Changing it flips linkage for *every* pod in the project, so it is a high-blast-radius setting — a broken `pod install` is the common outcome of setting it "for performance".

If you do change it, run a clean regenerate and a full pod install, then measure launch time (`native-measure-tti.md`) rather than assuming a direction.

## Deep Dive: where iOS size actually goes

Before reaching for build settings, look at what dominates:

1. **Assets** — uncompressed images and bundled media usually outweigh code. See `bundle-native-assets.md`.
2. **Native dependencies** — each pod carries its own code. See `bundle-library-size.md`.
3. **The JS bundle** — see `bundle-analyze-js.md`.
4. **dSYMs** — debug symbols are uploaded for symbolication, not shipped to users; they don't inflate the download.

Measure with `bundle-analyze-app.md` before changing build settings. The answer is usually assets.

## Common Pitfalls

- **Setting `useFrameworks` to make the app faster.** It's a compatibility switch; the usual result is a pod install failure. Measure, don't guess.
- **Raising `deploymentTarget` to "modernize".** It silently drops users on older iOS versions for no measured benefit. Raise only under dependency pressure.
- **Expecting `ccacheEnabled` to change app performance.** It only speeds up your builds.
- **Editing the `Podfile` by hand in a CNG project.** Use `extraPods` or a plugin; direct edits are discarded (`prebuild-cng-workflow.md`).
- **Chasing binary size before profiling assets.** Nearly always the wrong first move.

## Related

- `prebuild-build-properties.md` — the full property reference
- `prebuild-verify-native-changes.md` — confirming the Podfile actually changed
- `bundle-native-assets.md` / `bundle-library-size.md` / `bundle-analyze-app.md` — where iOS size really goes
- `native-measure-tti.md` — measuring launch impact

---
Verified against: expo-build-properties 0.14.8, Expo SDK 54, React Native 0.81 (Aug 2026).
Re-check property names and accepted values against the installed `pluginConfig.d.ts`.
