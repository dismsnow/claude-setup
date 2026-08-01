# Secrets and App Config

**Impact: CRITICAL** — a bundled credential is a credential an attacker has.

**Classification:** ADOPT GOING FORWARD for new code. A hardcoded third-party secret in a shipping app is **SHIP-BLOCKING** — report it with evidence; rotation and release sequencing are the owner's call, because rotating a live key can break production.

## Quick Pattern

**Incorrect (ships to every user, readable):**

```js
// app.config.js
export default {
  expo: {
    extra: {
      stripeSecretKey: process.env.STRIPE_SECRET_KEY, // in the bundle, in plain text
    },
  },
};
```

```ts
// Also wrong — same outcome
const API_SECRET = 'sk_live_51H8xY2...';
const KEY = process.env.EXPO_PUBLIC_API_SECRET; // EXPO_PUBLIC_ means public
```

**Correct (the secret never leaves your server):**

```ts
// The app calls your backend; your backend holds the secret and calls the third party.
const res = await fetch(`${API_BASE}/payments/intent`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${await getUserToken()}` },
  body: JSON.stringify({ amount }),
});
```

The app authenticates *as the user*. Only your server holds credentials that act on behalf of the *application*.

## What actually ships

`app.config.js` is evaluated at **build time**, and its output is embedded in the app. Everything under `extra` is retrievable at runtime by your code — and therefore by anyone reading the bundle. The same is true of any `EXPO_PUBLIC_`-prefixed variable: the prefix is the framework telling you it is public.

```bash
# See exactly what ships
npx expo config --type public
```

Anything printed there is public. Treat that output as the definition of "in the bundle".

## The two kinds of value people conflate

| | Identifier | Secret |
|---|---|---|
| Examples | API base URL, project/app ID, analytics or push app ID, public client ID, Sentry DSN | Signing key, service-role key, DB password, third-party API secret, private key |
| Ships in app? | Yes, fine | Never |
| If exposed | Nothing an attacker can act on alone | Direct compromise |

Identifiers in `extra` are correct and normal — a push provider's app ID, for instance, is designed to be in the client. The mistake is treating a secret as an identifier because both are "config".

If a value grants the *holder* the ability to act, it's a secret. If it merely *names* something, it's an identifier.

## Build-time secrets vs. bundled secrets

There is a legitimate use for secret environment variables in a build: credentials the *build* needs, which never enter the app.

| Use | Mechanism | Ends up in app? |
|---|---|---|
| Private npm registry token, Maven credentials, signing credentials | EAS secrets / CI environment variables | **No** |
| Anything read via `extra` or `EXPO_PUBLIC_*` | App config | **Yes** |

For a private Maven repository, read credentials from the environment rather than hardcoding them — see `prebuild-build-properties.md` in `react-native-best-practices`, which supports `System.getenv(...)` for exactly this.

## Deep Dive: why obfuscation doesn't help

R8/ProGuard renames classes and methods. It does **not** encrypt string literals, and your key is a string literal. Neither minification nor Hermes bytecode compilation is a security boundary — bytecode is decompilable and strings are extractable.

Any scheme that ships a secret and hides it is obfuscation, not protection. It raises effort slightly and fails against anyone motivated. Design so that there is no secret in the app to find.

## Step-by-step for a new project

1. Decide, per value, whether it's an identifier or a secret.
2. Identifiers → app config `extra`, or an `EXPO_PUBLIC_` variable.
3. Secrets → your server. The app gets a short-lived, user-scoped token instead.
4. Build-only credentials → EAS secrets / CI environment.
5. Add `.env*` to `.gitignore`, and commit a `.env.example` with names but no values.
6. Before the first release, run `npx expo config --type public` and read the whole thing.

## Common Pitfalls

- **Assuming `extra` is private** because it isn't in the source tree. It's in the bundle.
- **Using `EXPO_PUBLIC_` for a secret** because it's the variable mechanism that "works" — it works by publishing.
- **Committing `.env` with real values.** Also see `security-supply-chain.md` on credentials in repo config.
- **Trusting obfuscation.** See above.
- **Calling a third-party API directly from the app** with an app-level key, because "there's no backend yet". That decision ships the key.
- **Rotating a discovered key immediately without coordination.** It's the right end state, but it can break production — report and sequence it.

## Related

- `security-token-storage.md` — where runtime-obtained tokens go
- `security-logging-leaks.md` — the other common way secrets escape
- `security-supply-chain.md` — build-time credential handling
- `prebuild-build-properties.md` in `react-native-best-practices` — environment-sourced Maven credentials

---
Verified against: Expo SDK 54, React Native 0.81 (Aug 2026).
`npx expo config --type public` is the authoritative check for what ships — prefer running it over reasoning about config files.
