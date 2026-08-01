# Transport Security

**Impact: HIGH** — but mostly satisfied by defaults, which is the useful thing to know.

**Classification:** ADOPT GOING FORWARD for new code. `usesCleartextTraffic: true` in a shipping app is **SHIP-BLOCKING** — report it.

## Quick Config

The correct configuration is usually **none**. Both platforms block cleartext HTTP by default, and Expo's `usesCleartextTraffic` defaults to `false`. Verify rather than change:

```bash
grep -rn "usesCleartextTraffic" app.config.* app.json
grep -rn "NSAllowsArbitraryLoads\|NSExceptionAllowsInsecureHTTPLoads" app.config.* app.json ios/
grep -rniE "http://(?!localhost|127\.0\.0\.1)" src/ app/    # non-local plain HTTP
```

No results is the desired outcome for the first two.

## The one rule

**Every production endpoint is HTTPS.** No exceptions for "internal" APIs, staging environments reachable from devices, or image CDNs. Cleartext traffic on a mobile network can be read and modified by anyone on the path.

## When someone asks for a cleartext exception

The request usually comes from local development against an HTTP dev server, or an internal service without a certificate.

- **Local development** — the platforms already permit localhost, and a development build is not a production build. This does not require a config change.
- **An internal service without TLS** — the fix is a certificate on that service, not an exception in the app. Certificates are free.
- **If an exception is genuinely unavoidable**, scope it to the specific domain and to non-production builds only. A blanket `usesCleartextTraffic: true` or `NSAllowsArbitraryLoads` disables the protection app-wide, for every user, permanently.

An app-wide exception added for one dev convenience is the most common way this protection is lost.

## Dev-only tooling in release builds

Network inspection tooling is for development. In an Expo project the `networkInspector` build property maps to a dev-client flag, so it is scoped to development clients rather than production — but the general rule holds: verify that no debugging proxy, logging interceptor, or inspection hook is active in a release build. See `security-logging-leaks.md`.

## Deep Dive: certificate pinning, honestly

Pinning makes the app reject a TLS connection unless the server presents an expected certificate or public key. It defends against a compromised or fraudulently-issued CA certificate, and against casual interception by proxy tools.

**It is not free, and it is not usually the highest-value thing to do.**

The costs:

- **Rotation risk.** When your certificate rotates and the pin doesn't, every installed app loses connectivity. This is an outage you cannot fix with an OTA update if the update channel itself is pinned — the app can't reach the server to get the fix. Recovery requires a store release.
- **Operational coupling.** Your app release cycle becomes coupled to your TLS certificate lifecycle, including automated renewals.
- **Limited threat coverage.** It does not protect against a compromised device, a malicious app, or anything covered by the other references here.

If you pin:

- **Pin the public key, not the leaf certificate.** Keys survive certificate renewal; leaf certificates don't.
- **Pin a backup key** as well, so rotation is possible without a release.
- **Set an expiry/failure policy** — decide deliberately whether an unrecognized pin fails closed (secure, risks outage) or falls back (available, weaker).
- **Never pin the update channel** without a tested recovery path.
- **Document the rotation runbook with an owner** before shipping it.

For most apps, ordinary HTTPS with modern TLS is the right level. Reach for pinning when a specific threat model or compliance requirement calls for it — and note that under prebuild it needs a config plugin or a library, since it touches native networking config (`prebuild-config-plugin-authoring.md`).

## Common Pitfalls

- **App-wide cleartext for local development.** Ships the exception to production.
- **Assuming HTTPS validates the endpoint's identity beyond the certificate.** It proves you reached that domain, nothing about the response's trustworthiness — see `ts-runtime-validation-boundaries.md`.
- **Pinning a leaf certificate**, guaranteeing an outage at renewal.
- **Pinning with no backup key and no runbook.**
- **Pinning the update endpoint**, removing your ability to ship the fix.
- **Treating pinning as a substitute for the rest of this skill.** It addresses one narrow threat.

## Related

- `security-logging-leaks.md` — dev tooling and interceptors in release builds
- `security-webview.md` — `mixedContentMode` and page-level transport
- `security-ota-code-signing.md` — why the update channel needs signing, not just TLS
- `prebuild-build-properties.md` in `react-native-best-practices` — where `usesCleartextTraffic` lives

---
Verified against: Expo SDK 54, expo-build-properties 0.14.8 (`usesCleartextTraffic` defaults to `false`), React Native 0.81 (Aug 2026).
Platform transport-security defaults change with OS versions — verify against current platform docs for compliance claims.
