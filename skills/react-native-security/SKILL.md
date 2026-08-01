---
name: react-native-security
description: Security best practices for React Native and Expo mobile apps. Covers where secrets can and cannot live (app config extra and EXPO_PUBLIC_ vars ship readable inside the bundle), storing auth tokens in the OS keystore rather than AsyncStorage, validating deep link and push payload parameters, hardening WebViews, expo-updates code signing, TLS and cleartext traffic, permission minimization, keeping tokens and PII out of logs and crash reports, and dependency supply chain. Use when reviewing a mobile app for security, deciding where to put an API key or token, adding a WebView or deep link, configuring OTA updates, or preparing a release.
license: MIT
metadata:
  tags: react-native, expo, security, mobile, secrets, owasp
---

# React Native / Expo Security

Practical security guidance for React Native and Expo apps. Organized around a single premise: **anything shipped in the app binary is readable by anyone who has the app.** A mobile app is client software distributed to untrusted devices, not a trusted environment.

## Scope and how to act on findings

**Applies to:** new projects (adopt at setup) and new code (follow while writing).

**Existing working code — read this before changing anything.** Each item below is tagged:

- **ADOPT GOING FORWARD** — a pattern for new code. Do **not** retrofit working code. Note the difference if asked; leave shipping code alone.
- **SHIP-BLOCKING** — a live vulnerability in code that already runs. **Report it with evidence and let the owner decide.** Do not silently "fix" security issues in working code: a token-storage migration can lock users out, and rotating a leaked key can break production. The owner needs to sequence it.

The correct output for a ship-blocking finding is a clear report: what the issue is, where, what an attacker gets, and the options. Not a commit.

## The premise, concretely

Anyone can extract your app's contents. `.apk`/`.ipa` files can be unzipped; the JS bundle is readable text after trivial processing. Therefore:

| Shipped in the app | Safe for secrets? |
|---|---|
| App config `extra` | **No** — readable in the bundle |
| `EXPO_PUBLIC_*` env vars | **No** — public by name and by design |
| Hardcoded string in a `.ts` file | **No** |
| A `.env` file bundled into the app | **No** |
| Obfuscated / minified code | **No** — R8 renames symbols, it does not hide strings |
| OS keystore at runtime (Keychain / Keystore) | **Yes**, for data obtained at runtime |
| Your server | **Yes** — the only place a real secret belongs |

## Priority-Ordered Guidelines

| Priority | Category | Impact | Reference |
|----------|----------|--------|-----------|
| 1 | Secrets in the bundle | CRITICAL | [security-secrets-and-config.md][secrets] |
| 2 | Unsigned OTA updates | CRITICAL | [security-ota-code-signing.md][ota] |
| 3 | Auth token storage | HIGH | [security-token-storage.md][tokens] |
| 4 | Untrusted input from links | HIGH | [security-deep-links.md][links] |
| 5 | WebView privileges | HIGH | [security-webview.md][webview] |
| 6 | Transport security | HIGH | [security-network-tls.md][tls] |
| 7 | Logs and crash reports | MEDIUM-HIGH | [security-logging-leaks.md][logging] |
| 8 | Dependency supply chain | MEDIUM-HIGH | [security-supply-chain.md][supply] |
| 9 | Permission scope | MEDIUM | [security-permissions.md][permissions] |

Items 1 and 2 are first because both give an attacker something durable: a working credential, or the ability to run their code in your app.

## Quick Reference

### The five checks worth running on any app

```bash
# 1. Secrets in the resolved app config (everything here ships)
npx expo config --type public | grep -iE "secret|key|token|password|api[-_]?key"

# 2. Secrets hardcoded in source
grep -rniE "(api[-_]?key|secret|password|bearer|private[-_]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}" src/ app/

# 3. Auth tokens in plain (non-secure) storage
grep -rniE "AsyncStorage\.(set|get)Item\(['\"].*(token|jwt|refresh|credential|password)" src/ app/

# 4. Is the update channel signed?
npx expo config --type public | grep -A5 '"updates"'   # look for codeSigningCertificate

# 5. Cleartext traffic allowed?
grep -rn "usesCleartextTraffic" app.config.* app.json
```

Findings from these are **reports**, not edits. See the scope note above.

## References

| File | Impact | Description |
|------|--------|-------------|
| [security-secrets-and-config.md][secrets] | CRITICAL | What ships in the bundle; where secrets actually belong |
| [security-ota-code-signing.md][ota] | CRITICAL | Signing updates so only your code can run |
| [security-token-storage.md][tokens] | HIGH | Keystore vs AsyncStorage vs local database |
| [security-deep-links.md][links] | HIGH | Links and push payloads are untrusted input |
| [security-webview.md][webview] | HIGH | Containing a WebView's privileges |
| [security-network-tls.md][tls] | HIGH | TLS, cleartext, and pinning's real cost |
| [security-logging-leaks.md][logging] | MEDIUM-HIGH | Tokens and PII in logs and crash reports |
| [security-supply-chain.md][supply] | MEDIUM-HIGH | Dependencies and build-time code execution |
| [security-permissions.md][permissions] | MEDIUM | Requesting the minimum, and store declarations |

**[CHECKLIST.md][checklist]** — a scannable pre-release pass over all of the above.

## Problem → Reference Mapping

| Question | Start With |
|---|---|
| Where do I put this API key? | [security-secrets-and-config.md][secrets] |
| Where do I store the auth token? | [security-token-storage.md][tokens] |
| Is it safe to cache this offline? | [security-token-storage.md][tokens] |
| I'm adding a deep link | [security-deep-links.md][links] |
| I'm adding a WebView | [security-webview.md][webview] |
| I'm setting up OTA updates | [security-ota-code-signing.md][ota] |
| Should I add certificate pinning? | [security-network-tls.md][tls] |
| Are my logs leaking anything? | [security-logging-leaks.md][logging] |
| Is this dependency safe to add? | [security-supply-chain.md][supply] |
| Preparing a release | [CHECKLIST.md][checklist] |

## Related Skills

- **`react-native-best-practices`** — `prebuild-*` references cover the config plugins and build properties several items here depend on
- **`typescript-performance`** — validation at trust boundaries overlaps with deep-link and API input validation
- The built-in `/security-review` command reviews a concrete diff. This skill provides the mobile-specific knowledge to apply during one.

[secrets]: references/security-secrets-and-config.md
[tokens]: references/security-token-storage.md
[links]: references/security-deep-links.md
[webview]: references/security-webview.md
[ota]: references/security-ota-code-signing.md
[tls]: references/security-network-tls.md
[permissions]: references/security-permissions.md
[logging]: references/security-logging-leaks.md
[supply]: references/security-supply-chain.md
[checklist]: CHECKLIST.md
