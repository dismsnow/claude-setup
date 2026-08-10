# The Release Matrix and Version Management

Two things that look like configuration detail and are actually the release process: **which profile produces which artifact for which audience**, and **who owns the build number**.

## Part 1: The Release Matrix

One row per build profile, every column filled.

| Profile | `distribution` | `channel` | `environment` | Submit track | Trigger | Version bump |
|---|---|---|---|---|---|---|
| `development` | `internal` | — | `development` | never | manual | none |
| `uat` | `internal` | `uat` | `preview` | never | merge → `develop` | none |
| `uat-store` | `store` | `uat` | `preview` | `internal` | manual | `versionCode` / `buildNumber` |
| `live` | `store` | `production` | `production` | `production` (draft) | tag `v*` | `versionCode` / `buildNumber` |

**Read each row as one sentence.** A `live` build is store-distributed, listens on the `production` update channel, resolves `production` environment variables, submits to the production track as a draft, is triggered only by a version tag, and increments the native build number. If a row does not read as a coherent sentence, the profile is misconfigured — and that will show up as a release-day surprise, not a build failure.

### What each column means

| Column | Field | Values | Gets wrong |
|---|---|---|---|
| Distribution | `distribution` | `internal` \| `store` | `internal` produces installable artifacts for testers; `store` produces submittable ones |
| Channel | `channel` | any string | Which EAS Update channel the *binary* listens on. Set at build time, immutable afterwards. |
| Environment | `environment` | `development` \| `preview` \| `production` | Which set of EAS environment variables the build resolves. Only these three names are valid. |
| Track | `submit.<profile>.android.track` | `internal` \| `alpha` \| `beta` \| `production` | Where `eas submit` sends the artifact |
| Trigger | — | CI config | Who or what starts this build |
| Version bump | `autoIncrement` | see Part 2 | Whether two builds in a row can collide |

### The four mismatches worth checking first

**1. Channel and environment disagree.** A profile with `"channel": "uat"` and `"environment": "production"` builds an artifact that resolves production API URLs but listens for UAT updates. It will work in testing and then take a UAT JS bundle in production.

**2. A store profile with no `autoIncrement`.** Two store builds in a row produce the same build number, and the store rejects the second. The failure arrives at the worst possible moment — mid-release — and it looks like a credential problem.

**3. A "preview" profile quietly on Debug.** `ios.buildConfiguration` defaults are easy to get wrong when profiles are copy-pasted. A Debug artifact behaves nothing like the release one. (For the performance implications, `react-native-best-practices` → `prebuild-eas-build-profiles.md`.)

**4. Copy-paste drift between related profiles.** Use `extends` instead:

```json
{
  "uat": {
    "distribution": "internal",
    "channel": "uat",
    "environment": "preview",
    "env": { "ENVIRONMENT": "uat" },
    "android": { "buildType": "apk" },
    "ios": { "buildConfiguration": "Release" }
  },
  "uat-store": {
    "extends": "uat",
    "distribution": "store",
    "android": { "buildType": "app-bundle", "autoIncrement": "versionCode" },
    "ios": { "simulator": false, "autoIncrement": "buildNumber" }
  }
}
```

Without `extends`, a fix applied to `uat` silently fails to reach `uat-store`, and the divergence is invisible until a store build behaves differently from the internal one that was tested.

### Submit profile fields

Android:

| Field | Values |
|---|---|
| `track` | `production`, `beta`, `alpha`, `internal` |
| `releaseStatus` | `completed`, `draft`, `halted`, `inProgress` |
| `rollout` | fraction 0–1 for a staged release |
| `serviceAccountKeyPath` | path to the Play service account JSON |
| `changesNotSentForReview` | boolean |
| `applicationId` | for multi-flavour builds |

iOS: `appleId`, `ascAppId`, `appleTeamId`, `ascApiKeyPath`, `ascApiKeyIssuerId`, `ascApiKeyId`, `bundleIdentifier`, `sku`, `language`, `companyName`, `metadataPath`, `groups` (TestFlight internal groups).

`"releaseStatus": "draft"` is the right default: the artifact reaches the store but not users until someone promotes it. Make promotion a deliberate act.

**Omit a platform's submit block rather than filling it with placeholders.** A missing block fails immediately and clearly. `"ascAppId": "YOUR_ASC_APP_ID"` fails deep inside the submission with a confusing error — and placeholders have a habit of surviving into exactly the release that needed them.

---

## Part 2: Where build-time environment resolves

**This is the mapping that silently ruins releases**, and it deserves its own section because the failure is invisible until the store rejects the upload.

When `app.config.js` branches on an environment variable:

```js
const ENV = process.env.ENVIRONMENT ?? 'dev';
export default { expo: {
  name: ENV === 'live' ? 'MyApp' : `MyApp (${ENV})`,
  ios: { bundleIdentifier: ENV === 'live' ? 'com.acme.app' : `com.acme.app.${ENV}` },
}};
```

…the value is resolved **at config-evaluation time**, and there are three separate places it can come from:

| Source | Set where | Available when |
|---|---|---|
| `env` in the `eas.json` build profile | committed to the repo, per profile | during an EAS build |
| EAS environment variables | `eas env:set`, per environment | during an EAS build, per the profile's `environment` field |
| The CI job's own environment | workflow YAML | in your CI runner, **not** on the EAS build worker |
| A local `.env` file | your machine | locally only |

A CI job that exports `ENVIRONMENT=live` in its own YAML and then calls `eas build` does **not** pass that variable to the EAS build worker. The worker resolves the config itself, from `eas.json` `env` and the profile's EAS environment. If those disagree with what you assumed, you get a correctly-signed, correctly-versioned build with the wrong bundle identifier.

**The check, run on the runner and not just locally:**

```sh
npx expo config --type public | grep -E 'bundleIdentifier|package|name|scheme'
```

Put it in the pipeline as a step before the build, at least until you trust the mapping. It costs nothing and it is the only thing that catches this class of bug before the store does.

---

## Part 3: Version management

Three numbers, commonly confused:

| Number | Field | Who sees it | Must increase |
|---|---|---|---|
| Marketing version | `version` | users, store listing | per release you want users to notice |
| Android build number | `android.versionCode` | Play only | **every** store upload |
| iOS build number | `ios.buildNumber` | App Store Connect only | **every** store upload |

Most release pain comes from the build numbers, because they must be unique per upload and nothing local enforces that.

### `appVersionSource`: remote or local

```json
{ "cli": { "appVersionSource": "remote" } }
```

| | `remote` | `local` |
|---|---|---|
| Who owns build numbers | EAS servers | your `app.json` / native project |
| CI must commit a version bump | no | **yes, every build** |
| Two machines building concurrently | safe | collides |
| Building a release in Xcode / Android Studio | needs `build:version:sync` first | works directly |

**Use `remote` unless you genuinely build releases locally.** Expo has recommended it since EAS CLI 12.0.0, and the reason is CI: with `local` and `autoIncrement`, the bump only persists if something commits it, which means your pipeline is pushing commits to your release branch. That is a whole category of failure — merge conflicts, loops, protected-branch rejections — that `remote` simply does not have.

One documented incompatibility: **`remote` is not supported with `runtimeVersion: { policy: "nativeVersion" }`**, because that policy reads the native build number which is no longer locally authoritative. Use the `appVersion` or `fingerprint` policy instead.

### `autoIncrement`

| Platform | Allowed values |
|---|---|
| Android | `"version"`, `"versionCode"`, `false` |
| iOS | `"version"`, `"buildNumber"`, `false` |

Put `autoIncrement` on **every store profile**. Leave it off internal profiles — bumping a number nobody reads just adds noise.

`"version"` bumps the marketing version's patch number. Most teams don't want that automated; the marketing version is a decision, not a counter.

### Commands

```sh
eas build:version:get -p android -e live      # what the next build will use
eas build:version:set -p android -e live      # seed remote from a shipped version
eas build:version:sync -p all -e live         # pull remote values into local files
```

`build:version:set` is the migration command: if an app already has version 105 in the Play Store and you are switching to `remote`, run this so remote tracking continues from there rather than starting at 1.

### Migrating an existing app from `local` to `remote`

For an app with hand-edited version numbers already in the stores:

1. Record the current shipped values — Play Console `versionCode`, App Store Connect build number.
2. Change `cli.appVersionSource` to `"remote"` in `eas.json`.
3. `eas build:version:set -p android -e live` and `-p ios -e live`, entering those shipped values.
4. `eas build:version:get -p all -e live` and confirm the numbers match.
5. Add `autoIncrement` to the store profiles.
6. Leave the local `version` in the app config as the marketing version; the local `versionCode` / `buildNumber` become ignored seeds. Say so in a comment, or someone will "fix" them later.

Do this **before** automating store submission, not during. A version collision discovered mid-release is much harder to reason about than one discovered on a quiet afternoon.

---

## Related

- [cicd-ota-vs-build.md](cicd-ota-vs-build.md) — `runtimeVersion` policy, which interacts with `appVersionSource`
- [cicd-secrets-in-ci.md](cicd-secrets-in-ci.md) — where the credentials referenced by `submit` profiles live
- [cicd-runner-recipes.md](cicd-runner-recipes.md) — turning this matrix into workflow YAML
- `react-native-best-practices` → `prebuild-eas-build-profiles.md` — which profile to *benchmark*. That file owns measurement; this one owns release lifecycle.