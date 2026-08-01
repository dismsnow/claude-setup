# Authoring Config Plugins

**Impact: HIGH** — a non-idempotent or silently-failing plugin corrupts every subsequent build.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit a working plugin. Report the difference if asked; change nothing that already ships.

## Quick Pattern

**Incorrect (appends again on every prebuild):**

```js
module.exports = (config) =>
  withProjectBuildGradle(config, (cfg) => {
    cfg.modResults.contents = cfg.modResults.contents.replace(
      'mavenCentral()',
      "mavenCentral()\n    maven { url 'https://example.com/repo' }"
    );
    return cfg;
  });
```

**Correct (guarded by a marker, and fails loudly):**

```js
const { withProjectBuildGradle } = require('@expo/config-plugins');

const MARKER = 'https://example.com/repo';

module.exports = function withExampleRepo(config) {
  return withProjectBuildGradle(config, (cfg) => {
    if (cfg.modResults.contents.includes(MARKER)) return cfg; // already applied

    const anchor = 'mavenCentral()';
    if (!cfg.modResults.contents.includes(anchor)) {
      // A newer template moved the anchor. Fail now, not at runtime.
      throw new Error(`withExampleRepo: anchor "${anchor}" not found in build.gradle`);
    }

    cfg.modResults.contents = cfg.modResults.contents.replace(
      anchor,
      `${anchor}\n    maven { url '${MARKER}' }`
    );
    return cfg;
  });
};
```

## Step 1: Confirm you actually need a plugin

Most native changes have a declarative equivalent. Check in order: an app config field → an `expo-build-properties` property (`prebuild-build-properties.md`) → options on the library's own plugin. Write a plugin only when none of those can express the change. Every custom plugin is code you own across SDK upgrades.

## Step 2: Pick the right mod

| Mod | Edits | Use for |
|---|---|---|
| `withProjectBuildGradle` | `android/build.gradle` | Repositories, global Gradle config |
| `withAppBuildGradle` | `android/app/build.gradle` | App-module Gradle blocks |
| `withGradleProperties` | `gradle.properties` | Flags read by the build (prefer over string-patching Gradle) |
| `withAndroidManifest` | `AndroidManifest.xml` | Components, metadata, intent filters — via a parsed object, not string replace |
| `withStringsXml` / `withAndroidColors` | `res/values/*` | Android resources |
| `withInfoPlist` | `Info.plist` | iOS keys, permission strings — via a parsed object |
| `withEntitlementsPlist` | `*.entitlements` | iOS capabilities |
| `withXcodeProject` | `project.pbxproj` | Build phases, files, target settings |
| `withPodfile` / `withPodfileProperties` | `Podfile` | Pod-level config (prefer `extraPods` first) |
| `withDangerousMod` | Arbitrary filesystem | Last resort — no safety, runs raw |

Prefer a mod that gives you a **parsed object** (`withAndroidManifest`, `withInfoPlist`) over one that gives you a **string** (`with*BuildGradle`). Object edits don't break when the template's formatting changes.

## Step 3: Make it idempotent, and make failure loud

Two rules, both non-negotiable:

1. **Guard with a marker.** Check for a distinctive substring you inject and return early if present. `prebuild` without `--clean` can run against already-modified files.
2. **Throw when an anchor is missing.** A `.replace()` on a string that isn't there is a silent no-op — you get a green prebuild and a broken app. An exception at prebuild time is far cheaper than a production bug.

## Deep Dive: what a plugin receives

The mod callback gets the config object with `modResults` (the file being edited) and `modRequest` (paths and platform context):

```js
cfg.modRequest.projectRoot        // absolute project root
cfg.modRequest.platformProjectRoot // e.g. <root>/android
cfg.modRequest.platform           // 'android' | 'ios'
cfg.modResults                    // string for gradle, parsed object for manifest/plist
```

Use `modRequest.projectRoot` to build paths — never hardcode an absolute path, and never assume the plugin's own `__dirname` relates to the project layout.

Plugins run **in array order**, and later plugins see earlier plugins' output. If two plugins target the same anchor, order decides the result. Keep a custom plugin that depends on another one after it in the `plugins` array.

## Common Pitfalls

- **No idempotency guard.** The classic symptom: a duplicated Gradle block after running prebuild twice, and a build failure that looks unrelated.
- **Silent `.replace()` no-ops.** Covered above — throw instead.
- **String-patching the Android manifest.** Use `withAndroidManifest` and mutate the parsed object; string edits break on formatting changes and produce invalid XML.
- **`withDangerousMod` as a first move.** It bypasses every safety net and runs before/after other mods in ways that are easy to get wrong. Exhaust the typed mods first.
- **Committing generated output as "proof" the plugin works.** In a CNG project that re-introduces the thing you're trying to avoid. Verify by regenerating instead — `prebuild-verify-native-changes.md`.
- **Forgetting the plugin is build-time code you own.** It executes on every developer machine and in CI. Treat it like any other reviewed source file (see the security skill on build-time code execution).

## Related

- `prebuild-build-properties.md` — check here before writing a plugin
- `prebuild-cng-workflow.md` — the full decision ladder
- `prebuild-verify-native-changes.md` — proving the plugin ran and produced what you expect

---
Verified against: `@expo/config-plugins` as shipped with Expo SDK 54, React Native 0.81 (Aug 2026).
Available mods change between SDK versions — check the installed `@expo/config-plugins` exports before relying on a specific mod.
