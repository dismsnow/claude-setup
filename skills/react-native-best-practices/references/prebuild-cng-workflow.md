# Prebuild / CNG Workflow

**Impact: CRITICAL** — a native performance change applied the wrong way is silently discarded.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Do not retrofit. Report the difference if asked; change nothing that already ships.

## Quick Pattern

**Incorrect (edit vanishes on the next prebuild):**

```groovy
// android/app/build.gradle — hand-edited in a CNG project
android {
    buildTypes { release { minifyEnabled true } } // gone after `expo prebuild --clean`
}
```

**Correct (declared in source, regenerated every time):**

```js
// app.config.js — survives prebuild because it *is* the input
plugins: [
  ['expo-build-properties', { android: { enableProguardInReleaseBuilds: true } }],
]
```

## The mental model

With Continuous Native Generation, `android/` and `ios/` are **build outputs**, not source. `npx expo prebuild` generates them from three inputs:

1. the app config (`app.json` / `app.config.js` / `app.config.ts`)
2. config plugins listed in that config
3. the installed packages' own autolinking + bundled plugins

Anything not expressed in those inputs does not survive regeneration. `--clean` deletes the directories first, which is why it exposes the problem that a plain `prebuild` can mask.

## Step 1: Detect which mode the project is in — before touching anything

```bash
# CNG project? Then native dirs are generated and gitignored.
grep -nE '^/?(ios|android)/?$' .gitignore

# Cross-check: are they tracked by git?
git ls-files --error-unmatch android/ >/dev/null 2>&1 && echo "tracked (committed native)" || echo "not tracked"
```

| Signal | Mode | Where native changes belong |
|---|---|---|
| `ios/`+`android/` gitignored, `app.config.*` present | **CNG** | App config → plugin. Never the generated files. |
| `ios/`+`android/` committed, `app.config.*` present | **Prebuild-once / hybrid** | Ambiguous — ask. Someone may hand-maintain these. |
| No `app.config.*`, native dirs committed | **Bare React Native** | Edit native files directly. The existing `bundle-*` refs apply as written. |

A project with no `android/` directory at all is unambiguously CNG — it hasn't been generated yet.

## Step 2: Choose the lowest rung that works

Work down this ladder and stop at the first rung that can express the change:

1. **App config field** — `newArchEnabled`, `android.permissions`, `scheme`, icons, splash. Cheapest, no plugin needed.
2. **`expo-build-properties`** — SDK/tool versions, release shrinking, packaging, Maven repos, iOS deployment target and frameworks. Covers most *performance* knobs. See `prebuild-build-properties.md`.
3. **A package's own config plugin** — most native libraries ship one; pass options rather than patching their generated output.
4. **A custom config plugin** — for changes no existing plugin covers. See `prebuild-config-plugin-authoring.md`.
5. **Patch-based tooling** (`patch-project`) — captures native edits as a patch reapplied after prebuild. A pragmatic escape hatch; patches break when the template changes on SDK upgrade, so treat each one as a maintenance debt with an owner.
6. **Commit the native directories** — abandons CNG. Now you own template upgrades by hand forever. Choose deliberately, not by accident.

Rungs 1–2 are declarative and essentially free. Rung 5 costs you on every SDK bump. Rung 6 costs you permanently.

## Common Pitfalls

- **Testing with `prebuild` instead of `prebuild --clean`.** A plain prebuild often leaves existing files in place, so a hand-edit appears to survive. It won't survive a fresh CI checkout. Always validate with `--clean`.
- **Assuming CI matches local.** EAS Build runs prebuild from a clean checkout. If a change only exists in your local `android/`, it is not in the build.
- **Editing `android/app/proguard-rules.pro` directly.** Use `extraProguardRules` — same effect, survives regeneration.
- **A plugin that isn't idempotent.** Running prebuild twice must not append the same block twice. See `prebuild-config-plugin-authoring.md`.
- **Concluding "prebuild is broken" when a plugin silently no-ops.** A plugin whose string-match anchor no longer exists in a newer template fails quietly. Verify the output — see `prebuild-verify-native-changes.md`.

## Related

- `prebuild-build-properties.md` — the declarative knobs available at rung 2
- `prebuild-verify-native-changes.md` — proving a change actually landed
- `prebuild-android-release-build.md` / `prebuild-ios-release-build.md` — release performance per platform
- `bundle-r8-android.md` / `bundle-hermes-mmap.md` — the bare-React-Native form of the same settings

---
Verified against: Expo SDK 54, React Native 0.81, expo-build-properties 0.14.8 (Aug 2026).
Re-check behaviour against the installed Expo CLI before relying on flag specifics.
