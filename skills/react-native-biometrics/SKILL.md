---
name: react-native-biometrics
description: >-
  Best practices and copy-paste patterns for adding biometric authentication to
  a React Native app — Face ID, Touch ID, and Android fingerprint/face — for
  both app-unlock ("app lock", "protect this screen", "biometric login") and
  cryptographic server-verified flows ("sign this transaction", "step-up auth",
  "device key", WebAuthn-style challenge signing). Use this whenever the user
  mentions biometrics, Face ID, Touch ID, fingerprint, "unlock with biometrics",
  "require Face ID", biometric login/gate, or signing something with the user's
  fingerprint — even if they don't name a library. Routing rule baked in: for
  Expo apps prioritize expo-local-authentication (boolean gate) paired with
  expo-secure-store; for bare React Native, or ANY app that needs key/signature
  crypto, use @sbaiahmed1/react-native-biometrics (maintained TurboModule fork,
  EC256/RSA2048 keys). Covers install + EAS/config-plugin setup, the boolean-vs-
  signature security distinction, secure-store gating, key lifecycle and
  enrollment-change invalidation, device-integrity checks (fintech), error
  codes, simulator/emulator testing, and Android vendor fragmentation.
---

# React Native Biometrics — Implementation Skill

Biometric auth in a mobile app does one of two jobs, and picking the wrong one
is the most common mistake:

1. **Gate access** — "prove a human with an enrolled face/finger is holding the
   phone right now, then let them into the app / this screen." A local yes/no.
2. **Prove identity to a server** — "the user authorized *this specific action*
   (a login, a payment) with a key that only unlocks after biometrics, and the
   server can verify it cryptographically."

These need different tools. Job 1 is a boolean. Job 2 is a signature. Do not try
to make a boolean do job 2.

> **Related:** `react-native-security` → `references/security-token-storage.md`
> covers what belongs in secure store vs AsyncStorage, and independently
> classifies biometric gate state as *bypassable if tamperable* — the same point
> as the rule below, from the storage side. Defer to it for token-at-rest
> questions rather than re-deciding them here.

---

## The one rule that matters most

**A biometric `success: true` returned to JavaScript is not a security
boundary.** It is a UI signal. On a rooted/jailbroken device or under a hooked
runtime, that boolean can be forged, and a `verifyKeySignature` call can be
skipped entirely.

So for anything that actually protects value:

- **Gate a *secret*, not a screen.** Don't branch your UI on `success`; use the
  biometric to *unlock a stored secret* (a session token, an encryption key)
  that you literally cannot proceed without. On Expo that's
  `expo-secure-store` with `requireAuthentication`; on bare RN it's a
  Keystore/Keychain-backed key.
- **For server-facing auth, verify a signature server-side.** The device signs a
  server-issued challenge with a hardware-backed, biometric-bound private key;
  the server checks it against the public key it stored at enrollment. The phone
  never gets to *say* "trust me, they authenticated."

Everything below is in service of this rule.

---

## Pick the right library

Check the project first:

```bash
node -p "require('./package.json').dependencies.expo ? 'expo' : 'bare'"
node -p "require('./package.json').dependencies['react-native']"
ls -d ios android 2>/dev/null   # present => bare, or already prebuilt
```

| Situation | Use | New Arch | Adds a `.so`? |
|---|---|---|---|
| Expo app, just need to **unlock the app / gate a screen** | `expo-local-authentication` + `expo-secure-store` | ✅ | **No** |
| **Bare React Native**, any biometric need | `@sbaiahmed1/react-native-biometrics` | ✅ Fabric **and** Paper | **No** |
| **Any** app (Expo or bare) needing **signature / key crypto** — server-verified login, transaction signing, device identity, WebAuthn | `@sbaiahmed1/react-native-biometrics` | ✅ Fabric **and** Paper | **No** |
| ❌ Avoid | `react-native-biometrics` (SelfLender) | ❌ none | — |

Why each column matters:

- **New Arch** — the New Architecture has been the default since RN 0.76. A
  library without Fabric support is a hard failure, not a deprecation warning.
- **Adds a `.so`** — Google Play's 16 KB page-size requirement is **enforced**
  (both deadlines have passed), so any new native binary needs an alignment
  check. None of the recommended packages here ship one:
  `@sbaiahmed1/react-native-biometrics` is Swift + Kotlin with no C++/NDK code,
  and the Expo modules ride `expo-modules-core`, which is already present. See
  `react-native-best-practices` → `native-android-16kb-alignment.md`.

Default for an Expo app: `expo-local-authentication`. Reach for
`@sbaiahmed1/react-native-biometrics` the moment "the server needs to trust it"
enters the picture — even inside an Expo project.

> Don't use the old `react-native-biometrics` (SelfLender). Its last release was
> v3.0.0 in September 2022 — roughly four years stale — and it has no New
> Architecture support. `@sbaiahmed1/...` is its maintained successor with a
> nearly identical mental model but a functional API.

---

# Part A — Expo: `expo-local-authentication`

The default for gating access in an Expo app.

## Install & setup

```bash
npx expo install expo-local-authentication expo-secure-store
```

Add the config plugin so the native permission strings are generated at prebuild
(don't hand-edit `Info.plist` / `AndroidManifest.xml` in a managed app):

```json
{
  "expo": {
    "plugins": [
      ["expo-local-authentication", {
        "faceIDPermission": "Allow $(PRODUCT_NAME) to use Face ID to unlock the app."
      }]
    ]
  }
}
```

The plugin sets `NSFaceIDUsageDescription` (iOS) and adds `USE_BIOMETRIC`
(Android). The module is present in Expo Go with a default Face ID string, but
to ship your own string you need a **dev build** — `eas build --profile
development` (or `npx expo prebuild && npx expo run:ios/android`). Rebuild once,
not per change.

## The precheck sequence (never skip it)

Always check hardware → enrollment → *then* authenticate. Skipping straight to
`authenticateAsync` produces confusing failures on devices with no sensor or no
enrolled biometric.

```ts
import * as LocalAuthentication from 'expo-local-authentication';

export async function biometricStatus() {
  const hasHardware = await LocalAuthentication.hasHardwareAsync();
  const isEnrolled  = await LocalAuthentication.isEnrolledAsync();
  const types       = await LocalAuthentication.supportedAuthenticationTypesAsync();
  // types: 1 = FINGERPRINT, 2 = FACIAL_RECOGNITION, 3 = IRIS
  const level       = await LocalAuthentication.getEnrolledLevelAsync();
  // level: NONE | SECRET (device PIN/pattern) | BIOMETRIC_WEAK | BIOMETRIC_STRONG
  return { hasHardware, isEnrolled, types, level };
}

export async function unlock(): Promise<boolean> {
  const { hasHardware, isEnrolled } = await biometricStatus();
  if (!hasHardware || !isEnrolled) return false; // fall back to your own PIN screen

  const res = await LocalAuthentication.authenticateAsync({
    promptMessage: 'Unlock MyApp',
    cancelLabel: 'Cancel',
    fallbackLabel: 'Use passcode',
    disableDeviceFallback: false,      // true = biometrics only, no device PIN
    requireConfirmation: false,        // Android: skip the extra "confirm" tap for face
    biometricsSecurityLevel: 'strong', // Android: require Class 3, reject weak face unlock
  });
  return res.success;
}
```

`biometricsSecurityLevel` is the Expo-side equivalent of the Class 2 vs Class 3
distinction discussed in Part B. Set it to `'strong'` for anything sensitive —
budget Android face unlock is Class 2 and should not gate real value.

`authenticateAsync` resolves to `{ success: true }` or
`{ success: false, error, warning? }`. Handle the error string rather than
treating every non-success the same:

```ts
const res = await LocalAuthentication.authenticateAsync({ promptMessage: 'Unlock' });
if (!res.success) {
  switch (res.error) {
    case 'user_cancel':
    case 'system_cancel':
    case 'app_cancel':        return; // silent — user backed out
    case 'user_fallback':     return showAppPinScreen();
    case 'not_available':
    case 'not_enrolled':
    case 'passcode_not_set':  return showEnrollBiometricsHint();
    case 'lockout':           return showTooManyAttempts();
    case 'timeout':
    case 'unable_to_process':
    case 'authentication_failed': return showGenericRetry();
    default:                  return showGenericRetry(); // no_space, invalid_context, unknown
  }
}
```

The documented error set is: `not_enrolled`, `user_cancel`, `app_cancel`,
`not_available`, `lockout`, `no_space`, `timeout`, `unable_to_process`,
`unknown`, `system_cancel`, `user_fallback`, `invalid_context`,
`passcode_not_set`, `authentication_failed`. Keep a `default:` branch — platform
builds have historically surfaced strings outside this list (a permanent-lockout
variant among them), and an unhandled one must not fall through silently.

## Making it a real boundary: pair with `expo-secure-store`

This is how you follow the one rule in Expo. Store the sensitive value with
`requireAuthentication: true` — the OS then demands biometrics/device credential
to *read it back*, so there's nothing to skip.

```ts
import * as SecureStore from 'expo-secure-store';

// Check support before writing — an item written with requireAuthentication on a
// device that can't satisfy it is unreadable later.
if (!SecureStore.canUseBiometricAuthentication()) return storeWithoutGate(token);

// At login, after your normal server auth:
await SecureStore.setItemAsync('session_token', token, {
  requireAuthentication: true,
  authenticationPrompt: 'Unlock MyApp',
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
});

// On app open — the biometric prompt is triggered by the read itself:
try {
  const token = await SecureStore.getItemAsync('session_token', {
    requireAuthentication: true,
    authenticationPrompt: 'Unlock MyApp',
  });
  if (!token) return goToLogin();
  resumeSession(token);
} catch {
  // Cancelled, biometrics failed, or the key was invalidated by an OS upgrade or
  // enrollment change. Treat as "not logged in" — never as a crash.
  return goToLogin();
}
```

Three caveats that decide whether this works:

- **On iOS the prompt fires on read/update, never on create.** That asymmetry is
  the point — the write is silent, the read is what costs a Face ID scan.
- **Enrollment changes invalidate the item.** Adding a fingerprint or re-enrolling
  a face makes the stored value unreadable by design. The user re-logs in; that
  is correct behaviour, not a bug to work around.
- **Not supported in Expo Go** when biometrics are available, because
  `NSFaceIDUsageDescription` is missing there. Test on a dev build or a release
  build, not in Expo Go.

The catch-all above matches `react-native-security`'s rule that a secure-store
read failure is "not logged in", not a crash — hardware state and OS upgrades
can both make a read fail.

## Expo limitation

`expo-local-authentication` is boolean-only: no keypairs, no signatures, no
server-verifiable proof. The moment you need "the server must trust this," even
in an Expo app, switch to Part B (it runs in Expo via prebuild + a dev build —
just not Expo Go).

---

# Part B — `@sbaiahmed1/react-native-biometrics`

For bare React Native, and for any app (Expo included) that needs signature/key
crypto. Version referenced here: **0.16.0**. Requirements: **React Native 0.68+
(0.75+ recommended)**, Android **minSdk 23** / targetSdk 34, iOS device with a
passcode set. Swift + Kotlin, TurboModule, works on both architectures.

## Install & setup

```bash
npm install @sbaiahmed1/react-native-biometrics
```

**Bare RN — iOS:** `cd ios && pod install`, and add to `Info.plist`:

```xml
<key>NSFaceIDUsageDescription</key>
<string>MyApp uses Face ID to secure your account.</string>
```

**Bare RN — Android:** in `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.USE_BIOMETRIC" />
<uses-permission android:name="android.permission.USE_FINGERPRINT" />
```

Ensure `minSdkVersion 23` in `android/app/build.gradle`, and if you use
ProGuard/R8:

```proguard
-keep class androidx.biometric.** { *; }
-keep class com.sbaiahmed1.reactnativebiometrics.** { *; }
```

**Expo:** don't touch native files — use the bundled config plugin, then a dev
build (not Expo Go):

```json
{
  "expo": {
    "plugins": [
      ["@sbaiahmed1/react-native-biometrics", {
        "faceIDPermission": "MyApp uses Face ID to secure your account."
      }]
    ]
  }
}
```

Then `npx expo prebuild` (or `eas build --profile development`). Pass
`"faceIDPermission": false` if you manage the plist string yourself.

## API shape

Functional, named exports (no class to instantiate). Grouped by job:

- **Availability:** `isSensorAvailable(options?)` → `{ available, biometryType,
  isDeviceSecure, error? }`.
- **Gate access (boolean):** `simplePrompt(message, options?)`,
  `authenticateWithOptions(options)`.
- **Keys:** `createKeys(...)`, `createKeysWithOptions(options)`,
  `getPublicKey(alias?)`, `keyExists(alias?)`, `getKeyAttributes(alias?)`,
  `deleteKeys(alias?)`, `getAllKeys()`, `configureKeyAlias(alias)` /
  `configure({ keyAlias })`, `getDefaultKeyAlias()`, `validateKeyIntegrity(alias?)`.
- **Signing:** `verifyKeySignature(...)` (biometric-gated), `signWithOptions(options)`
  (gated, advanced), `sign(options)` (prompt-free — gate-less keys only),
  `validateSignature(...)` (local check, testing only), `sha256(...)`.
- **Security / diagnostics:** `getDeviceIntegrityStatus()`, `getDiagnosticInfo()`,
  `runBiometricTest()`, `setDebugMode(bool)`.
- **Change detection:** `subscribeToBiometricChanges(cb)` /
  `unsubscribeFromBiometricChanges(sub)`, `startBiometricChangeDetection()` /
  `stopBiometricChangeDetection()`.

Enums: `BiometricStrength` (`Strong` = Android Class 3, `Weak` = Class 2),
`AuthType`, `InputEncoding` (`UTF8` | `Base64` — use Base64 for WebAuthn/binary
challenges), `SignatureAlgorithm` (`SHA256withRSA`, `SHA512withRSA`,
`SHA256withECDSA`, `SHA512withECDSA`). Enums import cleanly on web/non-native via
`@sbaiahmed1/react-native-biometrics/types`.

## Pattern 1 — Simple app unlock (boolean)

Same job as Part A, for a bare-RN app. Still pair with a gated secret for real
protection.

```ts
import { isSensorAvailable, authenticateWithOptions } from '@sbaiahmed1/react-native-biometrics';

const info = await isSensorAvailable();
if (!info.available) {
  // info.biometryType: 'FaceID' | 'TouchID' | 'Biometrics' | 'None' | 'Unknown'
  return showAppPinScreen();
}

const res = await authenticateWithOptions({
  title: 'Unlock MyApp',
  subtitle: 'Confirm it’s you',   // Android
  cancelLabel: 'Cancel',
  fallbackLabel: 'Use passcode',
  allowDeviceCredentials: true,        // let device PIN/pattern satisfy it too
});
if (res.success) unlockApp();
```

If the PIN fallback is your own screen rather than the device credential, see
`react-native-keyboard-ux` for the numeric-entry form details.

## Pattern 2 — Server-verified login / step-up (the important one)

This is job 2 done correctly. Two phases.

**Enrollment (once, e.g. after normal login):**

```ts
import { createKeys, getPublicKey, BiometricStrength } from '@sbaiahmed1/react-native-biometrics';

// Silent — NO biometric prompt fires here. The auth requirement is attached to
// *using* the key later, not creating it.
const { publicKey } = await createKeys('myapp-auth', 'ec256', BiometricStrength.Strong);

// Capture publicKey NOW. On iOS a biometric-gated key can refuse a later
// non-interactive getPublicKey (KEY_REQUIRES_AUTHENTICATION); Android is fine.
await api.registerDeviceKey({ userId, publicKey }); // server stores it, bound to the user
```

**Login / step-up (every time):**

```ts
import { verifyKeySignature } from '@sbaiahmed1/react-native-biometrics';

const { challenge } = await api.getAuthChallenge(userId); // fresh server nonce, single-use

const res = await verifyKeySignature(
  'myapp-auth',
  challenge,              // sign the server's exact bytes
  'Sign in',              // prompt title
  'Confirm it’s you',     // subtitle (Android)
  'Cancel',
);

if (res.success && res.signature) {
  // Server verifies res.signature over `challenge` using the stored public key.
  const { ok, token } = await api.verifyAuth({ userId, challenge, signature: res.signature });
  if (ok) resumeSession(token);
}
```

Server side: `getPublicKey` (and the `publicKey` from `createKeys`) is
base64-encoded X.509 SubjectPublicKeyInfo DER, consumable by standard tooling
(`openssl pkey -pubin -inform DER`, Node `crypto.verify`, etc.). Verify the
signature over the raw challenge bytes with the matching algorithm (ECDSA-SHA256
for `ec256`). The challenge must be server-generated, single-use, and
short-lived — that's what stops replay.

## Pattern 3 — Transaction signing (high security)

Biometrics only, no PIN fallback, strong sensor — for authorizing a payment or
other money-moving action. Sign a canonical representation of the action so the
server verifies *what* was approved.

```ts
import { signWithOptions, BiometricStrength, InputEncoding } from '@sbaiahmed1/react-native-biometrics';

const payload = JSON.stringify({ amount: 1000, currency: 'MYR', to: 'acct_123', nonce });

const res = await signWithOptions({
  keyAlias: 'myapp-tx',
  data: payload,
  promptTitle: 'Authorize payment',
  promptSubtitle: 'RM1,000 to acct_123',
  biometricStrength: BiometricStrength.Strong,
  disableDeviceFallback: true,           // fail rather than accept a PIN
  // inputEncoding: InputEncoding.Base64, // if `data` is already binary (WebAuthn)
});

if (res.success) {
  await api.submitSignedTransaction({ payload, signature: res.signature });
} else if (res.errorCode === 'BIOMETRIC_NOT_AVAILABLE') {
  showEnrollStrongBiometricHint();
}
```

## Pattern 4 — Prompt-free device key

A Keystore/Keychain-backed key that signs *without* a prompt — for silent
request signing / device identity (a modern `react-native-rsa-native`
replacement). The private key is still non-exportable.

```ts
import { createKeysWithOptions, sign, SignatureAlgorithm } from '@sbaiahmed1/react-native-biometrics';

await createKeysWithOptions({
  keyAlias: 'device-id',
  keyType: 'rsa2048',
  requireAuthentication: false,   // <- the whole point: no biometric to use it
});

const res = await sign({
  keyAlias: 'device-id',
  data: requestBody,
  algorithm: SignatureAlgorithm.SHA256withRSA, // must match key type
});
```

`sign` only works on `requireAuthentication: false` keys. Call it on a gated key
and it resolves `{ success: false, errorCode: 'KEY_REQUIRES_AUTHENTICATION' }` —
use `verifyKeySignature` / `signWithOptions` for those.

## Key lifecycle & enrollment-change invalidation

Auth-bound keys are deliberately fragile — that's a feature. When the user
adds/removes a fingerprint or re-enrolls a face, an `ec256` key created with
`BiometricStrength.Strong` (iOS `.biometryCurrentSet`) is invalidated, and
Android auth-bound keys behave similarly. Detect it and re-enroll instead of
leaving the user stuck:

```ts
import {
  startBiometricChangeDetection, subscribeToBiometricChanges,
} from '@sbaiahmed1/react-native-biometrics';

await startBiometricChangeDetection();
const sub = subscribeToBiometricChanges((e) => {
  if (e.changeType === 'ENROLLMENT_CHANGED') {
    dropLocalSession();      // stop trusting the old key
    promptReEnrollment();    // deleteKeys + createKeys + re-register public key
  }
});
// cleanup: sub.remove(); stopBiometricChangeDetection();
```

Android note: creating an auth-bound key requires a **strong (Class 3)**
biometric enrolled, else it rejects with `CREATE_KEYS_ERROR: "At least one
biometric must be enrolled"`. Devices whose only biometric is weak (budget
camera face unlock) must use `allowDeviceCredentials: true` (API 30+), which
lets the device PIN/pattern unlock the key.

## Error handling

Both boolean and signature calls resolve with `success` + an `errorCode` (they
generally don't throw for user-cancel). Branch on the code:

```ts
function explain(errorCode?: string) {
  switch (errorCode) {
    case 'BIOMETRIC_NOT_AVAILABLE':     return 'No biometrics available on this device.';
    case 'BIOMETRIC_DISABLED':          return 'Biometrics are turned off — enable them in Settings.';
    case 'KEY_REQUIRES_AUTHENTICATION': return 'That key needs biometric signing — wrong sign() path.';
    case 'KEY_NOT_FOUND':               return 'No key for this alias — re-enroll.';
    case 'KEY_ALREADY_EXISTS':          return 'Key already exists (failIfExists was set).';
    case 'UNSUPPORTED_ALGORITHM':       return 'SHA-512 unsupported for this key (old/StrongBox) — use SHA-256.';
    case 'INVALID_ALGORITHM':           return 'Algorithm doesn’t match key type (RSA vs EC).';
    case 'CREATE_KEYS_ERROR':           return 'Enroll a strong biometric, or allow device credentials.';
    default:                            return 'Authentication failed — try again.';
  }
}
```

## Device integrity (useful for fintech)

`getDeviceIntegrityStatus()` reports root/jailbreak, secure-hardware presence,
and best-effort runtime-hook (Frida/Xposed) detection with a `riskLevel`.

```ts
const s = await getDeviceIntegrityStatus();
if (s.isCompromised || s.riskLevel === 'HIGH') {
  restrictSensitiveFeatures();
}
```

Treat it as *defense in depth, not proof*. A negative result isn't a guarantee —
an attacker controlling the runtime can defeat the check. For signals the server
can trust, pair it with **Play Integrity** (Android) and **App Attest** (iOS).
The Android Frida port probe also needs the app to hold `INTERNET` permission
(RN apps normally do).

---

## Gotchas & testing

- **Simulators need enrollment.** iOS Simulator: *Features ▸ Face ID ▸ Enrolled*,
  then *Matching/Non-matching Face* to drive a prompt. Android emulator: add a
  fingerprint in Settings, then simulate a touch with
  `adb -e emu finger touch 1`.
- **No Mac?** Iterate iOS through an EAS dev build
  (`eas build --profile development --platform ios`). It's a slow loop — build
  once, test many. `runBiometricTest()` and `getDiagnosticInfo()` are your
  remote-debug lifeline when you can't attach a debugger.
- **Android vendor fragmentation is real.** Budget face unlock is Class 2 (Weak)
  and can't back an auth-bound key. Test on an actual mid-range Android (a
  Samsung is a good representative device), not just a flagship or emulator.
- **32-bit release crash.** If a release build crashes on startup on
  `armeabi-v7a` devices with a backtrace through
  `JavaTurboModule::setEventEmitterCallback`, that is an **upstream React Native
  core bug** — the library labels it as such — triggered by the
  `onBiometricChange` event emitter rather than caused by this library. See
  issue #89 on the repo. If you don't use change detection and hit it, that's
  the lead to follow.
- **Never persist an "isAuthenticated" flag** in AsyncStorage as your gate — see
  the one rule. Re-authenticate on app foreground for sensitive screens rather
  than keeping a long-lived unlocked state.

---

## Pre-ship checklist

- [ ] No UI branches on a raw biometric `success` boolean for anything that
      protects value — a **secret** is gated, not a screen.
- [ ] Expo gating uses `expo-secure-store` with `requireAuthentication`, and
      `canUseBiometricAuthentication()` is checked **before** writing the item.
- [ ] Secure-store read failure is handled as "not logged in", never as a crash.
- [ ] Precheck sequence runs hardware → enrollment → authenticate.
- [ ] `authenticateAsync` error handling has a `default:` branch.
- [ ] `biometricsSecurityLevel: 'strong'` (Expo) / `BiometricStrength.Strong`
      (Part B) on anything sensitive — weak Class 2 face unlock does not gate value.
- [ ] Server-facing auth verifies a **signature** over a fresh, single-use,
      short-lived server challenge — not a client-reported boolean.
- [ ] Public key captured at `createKeys` time and registered server-side; iOS
      may refuse a later non-interactive `getPublicKey`.
- [ ] Transaction signing covers a canonical payload of the action, not just a
      nonce, so the server verifies *what* was approved.
- [ ] Enrollment-change detection wired to re-enrollment, so an invalidated key
      doesn't strand the user.
- [ ] No `isAuthenticated` flag persisted; sensitive screens re-authenticate on
      foreground.
- [ ] Device integrity treated as defence-in-depth, paired with Play Integrity /
      App Attest where the server must trust the signal.
- [ ] Built as a **dev build**, not Expo Go, wherever `requireAuthentication` or
      Part B is used.
- [ ] Tested on a real mid-range Android, not only a flagship or emulator.

---

## TL;DR

- Expo, gating access → `expo-local-authentication`, and gate a secret via
  `expo-secure-store` (`requireAuthentication`), don't branch on the boolean.
- Bare RN, or any server-trust / signing need (Expo included) →
  `@sbaiahmed1/react-native-biometrics`: `createKeys` → server stores public key
  → `verifyKeySignature` over a server challenge → server verifies.
- The boolean is UI; the signature is security. Prechecks and enrollment-change
  handling are not optional.
