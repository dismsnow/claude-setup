# Token and Local Data Storage

**Impact: HIGH** — determines what an attacker with device or backup access can take.

**Classification:** ADOPT GOING FORWARD for new code. An auth token in plain `AsyncStorage` in a shipping app is **SHIP-BLOCKING** — report it. Do not migrate token storage unprompted: a botched migration logs every user out, and offline-first apps may lose queued local work.

## Quick Pattern

**Incorrect (plain, unencrypted key-value storage):**

```ts
import AsyncStorage from '@react-native-async-storage/async-storage';
await AsyncStorage.setItem('authToken', token); // readable on a compromised device
```

**Correct (OS-backed secure storage):**

```ts
import * as SecureStore from 'expo-secure-store';

await SecureStore.setItemAsync('authToken', token);
const token = await SecureStore.getItemAsync('authToken');
```

`expo-secure-store` uses the iOS Keychain and Android Keystore — hardware-backed where available, encrypted at rest, and excluded from ordinary backups.

## What goes where

| Data | Storage | Why |
|---|---|---|
| Auth / refresh tokens, session keys | **Secure store** | Directly grants access as the user |
| Biometric or PIN gate state | **Secure store** | Bypassable if tamperable |
| Encryption keys | **Secure store** | Defeats the encryption if leaked |
| Theme, locale, onboarding-seen flags | AsyncStorage | Harmless |
| Non-sensitive cache, feature flags | AsyncStorage | Harmless |
| Business records for offline use | Local DB — see below | Depends on sensitivity |
| Anything you'd call PII | Local DB **and** consider encryption | Regulatory exposure |

## Deep Dive: local databases are plaintext by default

SQLite — and the local-database libraries built on it — write **unencrypted files** into the app's data directory. This is easy to forget because the data arrives via a typed model layer that feels like a server.

The practical exposure:

- On a rooted/jailbroken device, the file is readable directly.
- On a debug build, it's readable over the development tooling.
- It may be captured by device backups depending on platform and configuration.
- Anyone with physical device access and the right tooling can extract it.

That is often **acceptable** — an offline-first app caching records the logged-in user is already authorized to see puts nothing new at risk. The exposure is the *device holder* reading data the *device holder* could already see in the app.

It stops being acceptable when:

- The cache contains **other people's** data (multi-user devices, or a supervisor role caching a whole team's records).
- It contains regulated personal data with retention or encryption obligations.
- It contains anything that functions as a credential.

**Never put tokens in the local database** — that's what secure store is for, regardless of how convenient the model layer is.

For genuinely sensitive local data, options are an encrypted SQLite build with the key held in secure store, encrypting sensitive columns at the application layer, or simply not caching those fields offline. All three cost something; the third is often the right answer.

## Deep Dive: shared devices

If one physical device is used by multiple people — a common field-work pattern — local caches become a cross-user leak. Two rules:

1. **Scope cached data to its owner** and clear it when the user changes, so the next user cannot read the previous user's records.
2. **Be careful what triggers the clear.** Wiping on every logout-shaped event (including token expiry or an automatic sign-out) can destroy unsynced offline work. Distinguish "a different user is signing in" from "the session ended". The first must wipe; the second must not.

Getting this backwards causes either a privacy leak or data loss, so it deserves explicit design rather than a convenient hook.

## Step-by-step for a new project

1. Tokens and keys → `expo-secure-store`, from the first commit.
2. Preferences → AsyncStorage.
3. For each entity cached offline, ask: could this contain data belonging to someone other than the signed-in user? If yes, scope and clear on user change.
4. If any cached field is regulated PII, decide encryption before shipping, not after.
5. Handle secure-store read failures — hardware state and OS upgrades can make a read fail. Treat it as "not logged in", not a crash.

## Common Pitfalls

- **Tokens in AsyncStorage** because it's the storage already wired up.
- **Assuming a typed model layer implies encryption.** It's a plaintext file.
- **Storing large blobs in secure store.** It's for small secrets; keychain/keystore have size limits. Encrypt a file and keep the *key* in secure store.
- **Wiping local data on every logout path**, destroying unsynced offline work.
- **Not clearing on user switch**, leaking the previous user's records.
- **Treating a secure-store read failure as fatal**, bricking the app after an OS upgrade.
- **Migrating token storage in a "cleanup" pass.** It logs everyone out. Plan it.

## Related

- `security-secrets-and-config.md` — build-time secrets, a different problem
- `security-logging-leaks.md` — tokens escaping through logs after correct storage
- `CHECKLIST.md` — the pre-release pass

---
Verified against: Expo SDK 54, `expo-secure-store` as shipped with it (Aug 2026).
Platform backup and hardware-backing behaviour varies by OS version — verify against current Expo and platform docs for compliance claims.
