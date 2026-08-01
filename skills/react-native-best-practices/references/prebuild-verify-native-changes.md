# Verifying Native Changes Landed

**Impact: MEDIUM** — closes the Measure → Optimize → Re-measure loop for native config, where silent failure is the norm.

**Applies to:** New projects — adopt at setup. | New code — follow while writing.
**Existing working code:** Read-only. These are inspection commands; none of them modify project source.

## Why this exists

Native config changes fail *quietly*. A plugin whose anchor moved, a property name that's subtly wrong, a stale `android/` directory — all produce a green prebuild and a build that ignores your change. JavaScript changes fail loudly; native config changes do not. Verify explicitly.

## Quick Commands

```bash
# 1. What does the resolved config actually say?
npx expo config --type prebuild

# 2. Regenerate from scratch without touching node_modules, then inspect.
npx expo prebuild -p android --clean --no-install
grep -n "minifyEnabled\|shrinkResources" android/app/build.gradle
grep -n "enableBundleCompression\|newArchEnabled" android/gradle.properties

# 3. iOS equivalent
npx expo prebuild -p ios --clean --no-install
grep -n "use_frameworks\|IPHONEOS_DEPLOYMENT_TARGET" ios/Podfile
```

`--clean` is what makes this trustworthy: it deletes the native directories first, so you are reading generated output rather than leftovers. `--no-install` skips the dependency install step to keep the loop fast.

## Step-by-step

1. **Read the resolved config first.** `npx expo config --type prebuild` applies your plugins and prints the result. If your property isn't there, the problem is in app config — stop, no need to build.
2. **Regenerate clean.** `npx expo prebuild -p <platform> --clean --no-install`.
3. **Grep the generated file for the concrete setting**, not for your plugin's name. You want evidence of the *effect*.
4. **Run prebuild twice** and diff, to catch non-idempotent plugins:
   ```bash
   npx expo prebuild -p android --clean --no-install
   cp android/build.gradle /tmp/first.gradle
   npx expo prebuild -p android --no-install     # note: no --clean
   diff /tmp/first.gradle android/build.gradle   # must be empty
   ```
   Any output means a plugin applied itself twice — see `prebuild-config-plugin-authoring.md`.
5. **Confirm in the built artifact** for release-only settings, since shrinking flags only take effect in release builds (`bundle-analyze-app.md`).

## Deep Dive: what to grep for

| Change | Generated file | Grep for |
|---|---|---|
| R8 / code shrinking | `android/app/build.gradle` | `minifyEnabled` |
| Resource shrinking | `android/app/build.gradle` | `shrinkResources` |
| Custom shrinker rules | `android/app/proguard-rules.pro` | your rule text |
| JS bundle compression | `android/gradle.properties` | `enableBundleCompression` |
| New Architecture | `android/gradle.properties` | `newArchEnabled` |
| Maven repositories | `android/build.gradle` | the repository URL |
| SDK / tool versions | `android/build.gradle` | `compileSdkVersion`, `targetSdkVersion` |
| iOS deployment target | `ios/Podfile` | `platform :ios` |
| Pod linkage | `ios/Podfile` | `use_frameworks!` |
| Extra pods | `ios/Podfile` | the pod name |
| Permissions / components | `AndroidManifest.xml`, `Info.plist` | the key or component name |

## Common Pitfalls

- **Verifying without `--clean`.** You may be reading a leftover file that your change didn't produce. This is the mistake that makes a hand-edit look like it worked.
- **Grepping for the plugin name instead of the effect.** A plugin can run and still no-op.
- **Skipping the run-twice idempotency check.** Duplication surfaces later as a confusing build failure.
- **Checking a debug build for release-only settings.** Shrinking flags are absent from debug by design.
- **Committing the generated directories to "lock in" the verified state.** That abandons CNG (`prebuild-cng-workflow.md`). Regenerate instead.
- **Forgetting the regenerate is destructive to local native edits.** `--clean` deletes `android/`+`ios/`. In a CNG project that is exactly the point; if the project has *committed* native directories, check `git status` before running it.

## Related

- `prebuild-cng-workflow.md` — the workflow this verifies
- `prebuild-config-plugin-authoring.md` — fixing a plugin that no-ops or double-applies
- `prebuild-android-release-build.md` / `prebuild-ios-release-build.md` — the settings being verified
- `bundle-analyze-app.md` — verifying the size effect in the artifact

---
Verified against: Expo SDK 54, React Native 0.81 (Aug 2026).
CLI flags change between versions — check `npx expo prebuild --help` on your installed CLI.
