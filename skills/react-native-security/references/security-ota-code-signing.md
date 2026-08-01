# OTA Updates and Code Signing

**Impact: CRITICAL** — an unsigned update channel is a path to running arbitrary code in your app.

**Classification:** ADOPT GOING FORWARD for new code. An app shipping OTA updates with no code signing is **SHIP-BLOCKING** — report it. Note that enabling signing affects which clients can accept updates, so rollout must be sequenced by the owner.

## Why this is critical

`expo-updates` downloads a new JavaScript bundle at runtime and executes it. That is a deliberate, useful feature — and it means the update channel is a **remote code execution channel by design**. Its security rests entirely on the client only accepting bundles you actually published.

Without code signing, that trust reduces to "whatever the update server said". Anyone who can compromise the update endpoint, or interpose on the connection in a way that defeats TLS, can ship code into every installed copy of your app.

Code signing moves trust from the transport to a cryptographic signature the client verifies against a certificate embedded in the binary.

## Quick Config

```bash
# Generate a signing key pair and certificate
npx expo-updates codesigning:generate \
  --key-output-directory keys \
  --certificate-output-directory certs \
  --certificate-validity-duration-years 10 \
  --certificate-common-name "Your Organization"

# Embed the certificate in the app config
npx expo-updates codesigning:configure \
  --certificate-input-directory certs \
  --key-input-directory keys
```

This results in app config along these lines:

```json
{
  "updates": {
    "url": "https://u.expo.dev/<project-id>",
    "codeSigningCertificate": "./certs/certificate.pem",
    "codeSigningMetadata": { "keyid": "main", "alg": "rsa-v1_5-sha256" }
  }
}
```

**The guarantee, per the field's own definition:** when `codeSigningCertificate` is provided, *all* updates downloaded by `expo-updates` must be signed. An unsigned or wrongly-signed update is rejected by the client rather than executed.

Verify what shipped:

```bash
npx expo config --type public | grep -A6 '"updates"'
```

## Key handling

The private key signs your updates. If it leaks, an attacker can sign updates your app will accept — the same power as compromising the update server.

- **Never commit the private key.** Add the key directory to `.gitignore`.
- Store it where release credentials live (a secrets manager or the CI secret store), not in the repo.
- The **certificate** is public and belongs in the app config; the **key** does not.
- Note the certificate's validity duration — an expired certificate breaks the update path, so record the expiry somewhere with an owner.

## Channels and runtime version

Two settings decide *which* update a build accepts, and getting them wrong causes crashes that look like code bugs:

- **`channel`** — which stream of updates a build listens to. Keep it aligned with the release stage (a production build must not listen on a preview channel).
- **`runtimeVersion`** — declares native compatibility. A JS bundle expecting a native module that isn't in the installed binary will crash at runtime.

**The rule: any change to native code or native dependencies requires a new build, not an OTA update.** OTA ships JavaScript. If a JS update calls into a native module the installed binary lacks, it fails on the device. Use runtime-version policies so incompatible updates are never offered to an incompatible binary.

## Operational safety

- **Test on the channel you'll publish to**, using a release-configuration build (`prebuild-eas-build-profiles.md`).
- **Know the rollback path before you need it.** Republishing a previous known-good update is the usual mechanism; confirm it works while nothing is on fire.
- **An OTA update is a production deploy.** Apply the same review as a store release — it reaches users faster and with less review than one.
- **Consider what happens offline.** A client that can't reach the update server should run the embedded bundle, not fail.

## Common Pitfalls

- **No code signing**, treating TLS as sufficient. TLS protects the pipe; signing proves the payload is yours.
- **Committing the private key.** Rotating it means shipping a new binary to every user.
- **A production build on a non-production channel**, silently receiving preview code.
- **Shipping native changes via OTA.** They aren't in the update; the app crashes.
- **No rollback rehearsal**, discovering the process during an incident.
- **An expired signing certificate** with no owner watching the date.
- **Publishing from a developer machine** with no review, because it's one command.

## Related

- `security-secrets-and-config.md` — private key handling as a build credential
- `security-supply-chain.md` — the update pipeline is part of your supply chain
- `prebuild-eas-build-profiles.md` in `react-native-best-practices` — channels and release-configuration builds

---
Verified against: Expo SDK 54, `expo-updates` as shipped with it (Aug 2026). `codeSigningCertificate` / `codeSigningMetadata` (`alg: rsa-v1_5-sha256`, `keyid`) confirmed in `@expo/config-types`.
CLI command names and flags change between versions — check `npx expo-updates --help` on the installed version.
