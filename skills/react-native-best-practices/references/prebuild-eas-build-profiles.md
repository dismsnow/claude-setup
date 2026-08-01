# EAS Build Profiles & Performance Measurement

**Impact: MEDIUM** — mostly about not measuring the wrong artifact.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not restructure working build profiles. Report the difference if asked; change nothing that already ships.

## Quick Config

```json
{
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "android": { "buildType": "apk" }
    },
    "preview": {
      "distribution": "internal",
      "android": { "buildType": "apk" },
      "ios": { "buildConfiguration": "Release" }
    },
    "production": {
      "distribution": "store",
      "android": { "buildType": "app-bundle" },
      "ios": { "buildConfiguration": "Release" }
    }
  }
}
```

## The rule that matters most

**Never benchmark a development build.** A dev-client or debug build carries the dev bundle, no minification, no shrinking, and development-only warnings. Startup and frame timings from it are meaningless — they routinely differ from release by a factor of several.

Every measurement in this skill — TTI, FPS, bundle size, app size — must come from a **release-configuration** build. That means `buildConfiguration: "Release"` on iOS and a release build type on Android, with `developmentClient` absent.

A `preview`-style internal profile using release configuration is the right target: release-realistic, but installable without store distribution.

## Profile settings that affect what you measure

| Setting | Values | Effect |
|---|---|---|
| `android.buildType` | `apk` \| `app-bundle` | `apk` for direct install/testing; `app-bundle` for Play (per-device splits, smaller downloads) |
| `ios.buildConfiguration` | `Debug` \| `Release` | Must be `Release` for any performance measurement |
| `developmentClient` | boolean | `true` loads JS from a dev server — never for measurement |
| `distribution` | `internal` \| `store` | Internal for device testing; store for submission |
| `channel` | string | Which update channel the build listens on — keep aligned with release stage |
| `android.gradleCommand` | e.g. `:app:assembleRelease` | Overrides the default task; set deliberately |

`appVersionSource` in the top-level `cli` block controls whether version numbers come from remote state or local config. Not a performance setting, but a common source of confusing "which build am I testing?" moments.

## Deep Dive: comparing artifacts honestly

An APK and an AAB are not comparable sizes. The AAB is a publishing format; Play generates per-device APKs from it, so the number users download is smaller than the AAB and different from a universal APK.

When tracking size across changes:

- Compare **the same artifact type** built from **the same profile** before and after.
- For the number users actually download, read Play Console's per-device download size rather than measuring the AAB.
- Record the profile name alongside every measurement.

The same discipline applies to channels: a build on the `production` channel can pull a different update than one on `preview`, so an unexplained behaviour difference between two builds is often a channel difference, not a code difference.

## Common Pitfalls

- **Profiling a development build** and optimizing an artifact you never ship. The single most common measurement error.
- **Comparing an AAB against an APK** and reporting a size "regression" that is an artifact-type difference.
- **A `preview` profile that quietly uses Debug configuration.** It then behaves nothing like production. Check `buildConfiguration` explicitly.
- **Assuming EAS uses your local `android/`.** EAS Build runs prebuild from a clean checkout — a local-only native edit is not in the build (`prebuild-cng-workflow.md`).
- **Mismatched channel and release stage**, producing builds that load unexpected updates.

## Related

- `prebuild-cng-workflow.md` — why CI regenerates native code
- `native-measure-tti.md` / `js-measure-fps.md` — what to measure, once you have the right build
- `bundle-analyze-app.md` — artifact size analysis
- `prebuild-android-release-build.md` — the release settings these profiles exercise

---
Verified against: Expo SDK 54, EAS Build schema as of Aug 2026.
`eas.json` fields change over time — check current EAS Build docs before relying on a specific field.
