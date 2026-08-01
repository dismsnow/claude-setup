# Permissions and Data Declarations

**Impact: MEDIUM** — over-requesting causes store rejections and erodes user trust.

**Classification:** ADOPT GOING FORWARD for new code. An undeclared or misdeclared data collection practice is **SHIP-BLOCKING for release** (it blocks or retroactively breaches store review) — report it.

## The principle

Request the **minimum** permission, at the **latest** moment, with a **specific** reason. Every permission is attack surface, a store-review question, and a data-handling obligation.

A permission granted for a feature the user hasn't reached yet is all cost and no benefit.

## Quick Config

Declare permissions through the library's config plugin rather than by editing generated native files, so they survive `expo prebuild --clean`:

```js
// app.config.js
plugins: [
  [
    'expo-location',
    {
      // Specific and honest. "This app needs location" gets rejected.
      locationWhenInUsePermission:
        'We use your location to show nearby service points while you are using the app.',
    },
  ],
  [
    'expo-camera',
    {
      cameraPermission: 'We use the camera to scan item barcodes.',
      recordAudioAndroid: false, // don't request what you don't use
    },
  ],
],
```

Verify what actually ships:

```bash
npx expo config --type prebuild | grep -iA20 "permissions"
```

## Writing permission strings

iOS shows these strings verbatim in the system prompt, and App Review reads them. A vague string is a common rejection cause.

| Bad | Good |
|---|---|
| "This app needs camera access." | "We use the camera to scan item barcodes." |
| "Required for the app to work." | "We access photos so you can attach one to a report." |
| "For location services." | "We record your route while you are on shift so your supervisor can confirm coverage." |

State **what** you access and **why the user benefits**. Write them in the app's language, matching the rest of the UI.

## Deep Dive: background permissions get extra scrutiny

Background location is the most heavily reviewed permission on both stores. Requesting it requires that the core feature genuinely cannot work otherwise, and Google requires a prominent in-app disclosure before the system prompt, explaining what is collected and why.

If you request it:

- Confirm the feature genuinely needs **background** rather than while-in-use.
- Add the in-app disclosure screen before the system prompt.
- Explain retention: how long the data is kept and who sees it.
- Expect to justify it in review, and to re-justify it on updates.
- Consider whether a foreground service with a visible notification is the more honest design.

The same care applies to any always-on collection: microphone, contacts, health data, precise location.

## Deep Dive: store data declarations

Both stores require you to declare what data the app collects and how it's used — Play's Data Safety form and Apple's privacy questions plus `PrivacyInfo.xcprivacy`. These are legally meaningful statements, and they must match reality.

Two things people get wrong:

1. **Third-party SDKs collect data too.** An analytics, crash-reporting, or ads SDK collecting device identifiers is *your* declaration to make. Audit what your dependencies collect, not just your own code (`security-supply-chain.md`).
2. **Declarations drift.** Adding an SDK changes what you collect. Re-check the declaration whenever dependencies change.

On iOS, pods ship their own privacy manifests; the `privacyManifestAggregationEnabled` build property merges them into one file rather than leaving you to aggregate by hand. Enable it if you're managing manifests manually today.

Keep declarations consistent with `security-logging-leaks.md` — if telemetry sends user identifiers to a third party, that is collection and must be declared.

## Step-by-step for a new permission

1. Confirm the feature cannot work without it.
2. Choose the narrowest variant (while-in-use over always; coarse over precise; read-only over read-write).
3. Declare it via the library's config plugin, with a specific string.
4. Request it **at the point of use**, not at app launch.
5. Handle denial gracefully — the app must remain usable, with a clear explanation and a path to settings.
6. Update the store data declarations.
7. Verify with `npx expo config --type prebuild` that only the intended permissions are present.

## Common Pitfalls

- **Requesting everything at launch.** Users deny prompts they don't understand, and denial is often permanent.
- **Vague permission strings**, causing review rejection.
- **A library adding permissions you didn't intend.** Check the generated manifest — some plugins add more than you expect.
- **Requesting background location** when while-in-use suffices.
- **Crashing or dead-ending on denial** instead of degrading.
- **Editing the manifest or `Info.plist` directly** in a CNG project, where it's discarded (`prebuild-cng-workflow.md`).
- **Stale data declarations** after adding an SDK.

## Related

- `security-logging-leaks.md` — what you send to third parties is collection
- `security-supply-chain.md` — auditing what dependencies collect
- `security-deep-links.md` — Android component exposure in the manifest
- `prebuild-config-plugin-authoring.md` in `react-native-best-practices` — editing the manifest correctly

---
Verified against: Expo SDK 54, expo-build-properties 0.14.8 (`privacyManifestAggregationEnabled`), React Native 0.81 (Aug 2026).
Store policies and required declarations change frequently — verify against current Play and App Store policy before a release.
