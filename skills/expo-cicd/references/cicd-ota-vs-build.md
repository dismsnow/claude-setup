# OTA Update or New Native Build?

The recurring release decision, and the one with the worst failure mode. Getting it wrong ships a JavaScript bundle that calls a native module the installed binary does not contain — the app crashes on launch, for every user who received the update, and the fix is a store release.

**So do not decide this by judgement. The fingerprint decides.**

---

## Part 0: The precondition gate

Before "update or build?" is even a live question, OTA has to actually work. Three checks. Projects fail these far more often than you would expect, because `expo-updates` can be installed, listed as a plugin, and have channels configured in `eas.json` while updates are disabled in the shipped binary. In that state `eas update` publishes successfully and reaches nobody.

```sh
npx expo config --type public | grep -A 6 '"updates"'
npx expo config --type public | grep -A 3 runtimeVersion
```

| # | Check | Looking for | If missing |
|---|---|---|---|
| 1 | `updates.url` is set | `https://u.expo.dev/<project-id>` | `eas update:configure` |
| 2 | `runtimeVersion` is set | a policy or an explicit string | add one — see below |
| 3 | Updates enabled in the **binary** | `updates.enabled` not `false`; native config not disabling it | rebuild after fixing 1 and 2 |

Check 3 is the one that hides. In a CNG project the generated native config is gitignored, so the evidence lives in `android/app/src/main/AndroidManifest.xml` (`expo.modules.updates.ENABLED`) and `ios/<App>/Supporting/Expo.plist` (`EXUpdatesEnabled`) after a local prebuild — or, more reliably, in the behaviour of a real build. `updates.enabled` defaults to `true`; if it is explicitly `false` anywhere in the config chain, nothing else in this file applies.

**A published update never reaches a binary that was built before OTA was configured.** Fixing checks 1–3 means the *next* build is the first one that can receive updates. Every already-installed client needs that store release first. This is why [NEW-PROJECT-DAY-1.md](../NEW-PROJECT-DAY-1.md) sets `updates.url` and `runtimeVersion` on day one, when the cost is two lines.

---

## Part 1: `runtimeVersion` — the compatibility contract

`runtimeVersion` is the promise that a given JS bundle can run against a given native binary. An update is only delivered to a binary whose runtime version matches.

| Policy | Changes when | Use for |
|---|---|---|
| `fingerprint` | anything affecting the native runtime changes — dependencies, config plugins, SDK version, native code | **CNG projects — the right default** |
| `appVersion` | you change `version` in the app config | projects with custom native code that bump `version` every public release |
| `nativeVersion` | `version` or the build number changes | rarely; **incompatible with `appVersionSource: "remote"`** |
| an explicit string | you change it by hand | you want total manual control and accept the risk |

```json
{ "expo": { "runtimeVersion": { "policy": "fingerprint" } } }
```

`fingerprint` hashes everything that affects the native runtime, so the runtime version changes exactly when a new binary is genuinely required — no more, no less. That is what makes the build-vs-update decision mechanical rather than a judgement call.

If you use `appVersionSource: "remote"` (recommended — see [cicd-release-matrix.md](cicd-release-matrix.md)), the `nativeVersion` policy is not supported. Use `fingerprint`, or `appVersion`.

---

## Part 2: The decision

```
Did the fingerprint change?
├── No  → an OTA update is safe
└── Yes → a new native build is required. No exceptions.
```

```sh
eas fingerprint:generate                        # current fingerprint
eas fingerprint:compare --build-id <BUILD_ID>   # local tree vs a build
eas fingerprint:compare --build-id <A> --build-id <B>
eas fingerprint:compare --update-id <UPDATE_ID>
```

Rules of thumb for what moves a fingerprint — useful for intuition, but **never a substitute for running the command**:

| Change | Fingerprint |
|---|---|
| JS/TS logic, styles, copy, images in the bundle | unchanged → update |
| Adding a dependency with native code | changed → build |
| Config plugin added, removed, or reconfigured | changed → build |
| `app.config` native fields — permissions, bundle id, plugins | changed → build |
| Expo SDK upgrade | changed → build |
| A JS-only dependency | usually unchanged — verify |

That last row is why the command matters: "JS-only" packages sometimes pull native dependencies transitively, and the diff is not visible in your own source.

### Wiring it into CI

Let the pipeline apply the rule. EAS Workflows has this built in via `fingerprint` + `get-build`:

```yaml
jobs:
  fingerprint:
    type: fingerprint
    environment: production
  get_android_build:
    needs: [fingerprint]
    type: get-build
    params:
      fingerprint_hash: ${{ needs.fingerprint.outputs.android_fingerprint_hash }}
      profile: live
  build_android:
    needs: [get_android_build]
    if: ${{ !needs.get_android_build.outputs.build_id }}
    type: build
    params: { platform: android, profile: live }
  publish_android_update:
    needs: [get_android_build]
    if: ${{ needs.get_android_build.outputs.build_id }}
    type: update
    params: { branch: production, platform: android }
```

No build exists for this fingerprint → build. One does → the native runtime is unchanged, so publish an update. Full workflow in [cicd-runner-recipes.md](cicd-runner-recipes.md).

On other CI providers, run `eas fingerprint:compare --json` and branch on the result.

---

## Part 3: Channels and branches

Two separate concepts that are easy to conflate:

- **Channel** — set on the *binary* at build time via the `channel` field in `eas.json`. Immutable once built.
- **Branch** — a stream of updates you publish to. Mutable.

A channel points at a branch. That indirection is the useful part: you can repoint the `production` channel at a different branch without rebuilding anything, which is how promotion and rollback work.

```sh
eas update --branch production --message "Fix login alignment"
eas update --auto                            # branch + message from git
eas update --channel production -m "…"       # publish via the channel's branch
eas channel:list
eas channel:view production
```

`--auto` uses the current git branch name and latest commit message — convenient in CI, as long as your branch names match your update branches.

---

## Part 4: Staged rollout

Do not send an update to 100% of users immediately. There is no faster way to break every install simultaneously.

```sh
eas update --branch production --message "…" --rollout-percentage 10
eas update:edit --rollout-percentage 50      # widen
eas update:revert-update-rollout             # pull it back
```

Branch-level rollout, for shifting a channel between branches gradually:

```sh
eas channel:rollout production --action create --branch hotfix --percent 10
eas channel:rollout production --action edit --percent 50
eas channel:rollout production --action end --outcome republish-and-revert
```

A workable default: 10% → watch crash rates for an hour → 50% → watch → 100%. Automate the first step; keep the widening manual until you trust your monitoring.

---

## Part 5: Rollback

**Rehearse this before you need it.** An untested rollback path is not a rollback path.

| Situation | Command |
|---|---|
| A previous update was good | `eas update:republish --group <GROUP_ID>` |
| Everything published is bad; return to the bundle shipped in the binary | `eas update:roll-back-to-embedded` |
| Undo a specific update group | `eas update:rollback <GROUP_ID>` |
| Pull back a staged rollout | `eas update:revert-update-rollout` |

```sh
eas update:list --branch production     # find the group id to go back to
```

`roll-back-to-embedded` is the panic button: it tells clients to use the JS that shipped inside their binary, which is by definition compatible. It is the right first move when you are not sure which update broke things.

**What rollback cannot fix:** an update that shipped against a mismatched runtime and crashes on launch. If the app crashes before `expo-updates` can check for a new update, no published update can reach it — recovery is a store release. That is the entire reason Part 2 is mechanical.

---

## Part 6: What OTA must never carry

| Change | Why not |
|---|---|
| Anything that changes the fingerprint | It will not be delivered, or it will crash |
| Anything a store must review | Reviewers approve binaries; using OTA to route around review violates store policy |
| Native permissions | They are declared in the binary's manifest |
| Emergency security fixes to native code | Not reachable by OTA at all |

Code signing is a hard precondition for production OTA — an unsigned update channel is a code-execution path into your app. That is `react-native-security`'s territory: see its `security-ota-code-signing.md`. Do not automate publishing before it is configured.

---

## Related

- [cicd-runner-recipes.md](cicd-runner-recipes.md) — the full fingerprint-gated workflow
- [cicd-release-matrix.md](cicd-release-matrix.md) — `channel` per profile, and the `appVersionSource` / `nativeVersion` incompatibility
- [ADOPTION.md](../ADOPTION.md) — Level 4-OTA and its preconditions
- `react-native-security` → `security-ota-code-signing.md` — signing keys and certificate handling