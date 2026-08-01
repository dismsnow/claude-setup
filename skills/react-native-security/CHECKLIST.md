# Pre-Release Security Checklist

A scannable pass over the references in this skill. Each item names where to look and what evidence to produce.

**How to use this on an existing app:** this is an **audit**, not a work order. Produce findings with evidence and let the owner decide what to fix and when. Items marked **[SHIP-BLOCKING]** are live vulnerabilities worth escalating; the rest are *adopt going forward* and should not trigger a retrofit of working code.

For a new project, work top to bottom before the first release.

---

## 1. Secrets — `security-secrets-and-config.md`

- [ ] **[SHIP-BLOCKING]** No third-party API secret, signing key, or service credential in the app bundle.
      ```bash
      npx expo config --type public | grep -iE "secret|key|token|password|api[-_]?key"
      grep -rniE "(api[-_]?key|secret|password|bearer|private[-_]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}" src/ app/
      ```
- [ ] Every value in `extra` / `EXPO_PUBLIC_*` is an **identifier**, not a secret.
- [ ] `.env*` is gitignored; a valueless `.env.example` is committed.
- [ ] Build-only credentials live in EAS secrets / CI, never in app config.

## 2. OTA updates — `security-ota-code-signing.md`

- [ ] **[SHIP-BLOCKING]** If the app ships OTA updates, code signing is configured.
      ```bash
      npx expo config --type public | grep -A6 '"updates"'   # expect codeSigningCertificate
      ```
- [ ] The signing **private key** is not in the repo (`git log --all -- '*keys*'` and check `.gitignore`).
- [ ] Certificate expiry date is recorded and has an owner.
- [ ] `channel` matches the release stage for each build profile.
- [ ] `runtimeVersion` policy prevents a JS update reaching an incompatible binary.
- [ ] Rollback path has been exercised at least once.

## 3. Token storage — `security-token-storage.md`

- [ ] **[SHIP-BLOCKING]** Auth and refresh tokens are in `expo-secure-store`, not AsyncStorage or the local DB.
      ```bash
      grep -rniE "AsyncStorage\.(set|get)Item\(['\"].*(token|jwt|refresh|credential|password)" src/ app/
      ```
- [ ] Local database contents reviewed: does any cached table hold data belonging to someone other than the signed-in user?
- [ ] Regulated PII cached offline is either encrypted or not cached.
- [ ] Cache is scoped and cleared on **user switch** — but *not* on ordinary session expiry, so unsynced offline work survives.
- [ ] A secure-store read failure is handled as "not logged in", not a crash.

## 4. Deep links & push — `security-deep-links.md`

- [ ] Every link/push parameter is validated for type and shape at the entry point.
- [ ] **[SHIP-BLOCKING]** No route performs a privileged or destructive action from link params alone.
- [ ] The server authorizes every action independently of the link.
- [ ] Sensitive routes use verified App Links / Universal Links, not a bare custom scheme.
- [ ] OAuth redirects do not rely on a hijackable custom scheme.
- [ ] Params used in paths or URLs are allow-listed.
- [ ] No sensitive content in push notification bodies (lock-screen visible).
- [ ] No Android component is exported beyond what's needed as an entry point.

## 5. WebView — `security-webview.md`

Skip if the app has no WebView.

- [ ] `originWhitelist` is an explicit list — never `['*']`.
- [ ] **[SHIP-BLOCKING]** `allowFileAccess`, `allowFileAccessFromFileURLs`, `allowUniversalAccessFromFileURLs` are all `false`.
- [ ] `onShouldStartLoadWithRequest` enforces an allow-list per navigation.
- [ ] `onMessage` validates every message; no generic "call any native method" handler.
- [ ] No token in the WebView URL or `injectedJavaScript`.
- [ ] `javaScriptEnabled={false}` wherever the content doesn't need it.
- [ ] External/untrusted URLs open in an in-app browser, not a privileged WebView.

## 6. Transport — `security-network-tls.md`

- [ ] **[SHIP-BLOCKING]** `usesCleartextTraffic` is not `true`; no app-wide iOS ATS exception.
      ```bash
      grep -rn "usesCleartextTraffic" app.config.* app.json
      grep -rn "NSAllowsArbitraryLoads" app.config.* app.json ios/
      ```
- [ ] All production endpoints are HTTPS (including image/asset CDNs).
- [ ] Any cleartext exception is domain-scoped and non-production only.
- [ ] If pinning is used: public key (not leaf cert), a backup pin, a documented rotation runbook, and the update channel is not pinned without recovery.

## 7. Logs & telemetry — `security-logging-leaks.md`

- [ ] `console.*` is stripped from production builds (`transform-remove-console` in the production Babel env).
- [ ] **[SHIP-BLOCKING]** No token or password reaches a crash/analytics service.
- [ ] Crash SDK capture settings are configured explicitly, not left at defaults.
- [ ] A `beforeSend`-style redaction hook is in place for headers and context.
- [ ] No tokens in URLs or query strings.
- [ ] No state-snapshot middleware serializing tokens held in state.
- [ ] Verbose network interceptors are disabled in release builds.

## 8. Supply chain — `security-supply-chain.md`

- [ ] `npm audit --production` reviewed; findings triaged.
- [ ] Lockfile committed; CI uses `npm ci` (not `npm install`).
- [ ] Every config plugin has been read — each runs code at build time with access to CI secrets.
- [ ] Every native patch has an owner and a recorded reason, re-verified after the last SDK upgrade.
- [ ] **[SHIP-BLOCKING]** No credential committed to the repo, and no token in the git remote URL.
      ```bash
      git config --get remote.origin.url    # must not contain a token
      ```
- [ ] No hand-rolled cryptography.

## 9. Permissions & declarations — `security-permissions.md`

- [ ] Only permissions the app actually uses are present.
      ```bash
      npx expo config --type prebuild | grep -iA20 "permissions"
      ```
- [ ] Every permission string is specific and in the app's language.
- [ ] Permissions are requested at point of use, not at launch.
- [ ] Denial is handled gracefully everywhere.
- [ ] Background location (if used) has an in-app disclosure before the system prompt.
- [ ] **[SHIP-BLOCKING for release]** Store data declarations match reality, including data collected by third-party SDKs.

---

## Reporting findings

For each finding, give the owner what they need to decide:

1. **What** — the issue in one sentence.
2. **Where** — file and line, or the config key.
3. **Impact** — what an attacker actually gets. Be concrete; avoid "could be exploited".
4. **Classification** — ship-blocking, or adopt-going-forward.
5. **Options** — the fix, plus its rollout risk (a token-storage change logs users out; a key rotation can break production; enabling code signing affects which clients accept updates).

Sequencing is the owner's call. Do not apply security changes to working code unprompted — the fix's blast radius is often larger than the finding's.
