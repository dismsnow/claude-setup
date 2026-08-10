# New Expo Project: Day 1

**Goal: CI exists before the feature code does.** A new app should start at Level 2 of [ADOPTION.md](ADOPTION.md), not Level 0.

Every step below is cheap now and expensive later. Pinning Node takes thirty seconds on day one and half a day once three people have different versions installed. Configuring `runtimeVersion` takes one line on day one and forces a re-build of every installed client once the app has users.

Budget 30–45 minutes. Do the steps in order — several depend on the one before.

---

## 1. Create the app

```sh
npx create-expo-app@latest MyApp --template default
cd MyApp
```

## 2. Create the git remote — before writing any code

```sh
gh repo create <org>/MyApp --private --source . --push
```

Two things matter here:

- **Do this first**, so the first commit lands in CI's view of history and the workflow file is present from the beginning.
- **Never put a token in the remote URL.** Use `gh auth login` or SSH. A URL like `https://ghp_…@github.com/…` sits in plaintext in `.git/config`, gets copied with the repo, and is read by anything that inspects it.

Hosting on GitHub is what keeps EAS Workflows available as an option later — its git triggers are GitHub-only. GitLab and Bitbucket can still call `eas build` from their own CI, but you lose the built-in job types. Decide deliberately; see [cicd-runner-recipes.md](references/cicd-runner-recipes.md).

## 3. Pin the Node version

```sh
echo "24" > .nvmrc
```

```json
{
  "engines": { "node": ">=22" }
}
```

CI then reads `.nvmrc` via `node-version-file` rather than hardcoding a version in the workflow, so there is exactly one source of truth. Expo's own CI examples currently use Node 24; match the runtime you actually develop on and check your SDK's supported range.

## 4. Pick one package manager

Choose npm **or** yarn, and delete the other lockfile. Two lockfiles means CI and your laptop can resolve different dependency trees, and the resulting bug is invisible until it isn't.

If the project needs install flags, put them in `.npmrc`:

```
legacy-peer-deps=true
```

**Not** only in an `eas-build-pre-install` script. Those npm hooks (`eas-build-pre-install`, `eas-build-post-install`, `eas-build-on-success`, `eas-build-on-error`, `eas-build-on-cancel`, `eas-build-on-complete`) are executed by the **EAS Build worker**. A GitHub Actions or GitLab runner never runs them, so a project that depends on one for install flags will install correctly on EAS and fail on your PR gate. `.npmrc` is read by both.

## 5. Add the quality scripts

```json
{
  "scripts": {
    "typecheck": "tsc --noEmit",
    "lint": "eslint .",
    "test": "jest --ci --passWithNoTests",
    "doctor": "npx expo-doctor",
    "ci": "npm run typecheck && npm run lint && npm run test && npm run doctor"
  }
}
```

The single `ci` script means the workflow file has one command in it and you can run the exact same gate locally. `--passWithNoTests` keeps the gate green on day one and honest as tests arrive.

## 6. Configure lint and test

```sh
npx expo install --dev eslint eslint-config-expo jest-expo jest @types/jest
```

A working `jest` block for an Expo app — the `transformIgnorePatterns` is the part people get wrong:

```json
{
  "jest": {
    "preset": "jest-expo",
    "setupFilesAfterEach": ["<rootDir>/jest.setup.ts"],
    "transformIgnorePatterns": [
      "node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg))"
    ]
  }
}
```

## 7. Link the project to EAS

```sh
npx eas-cli@latest init
```

This writes a real `projectId` into `extra.eas.projectId`. Verify it took:

```sh
npx expo config --type public | grep projectId
```

A literal placeholder here means `eas build` cannot run at all — worth checking rather than assuming.

## 8. Write `eas.json`

```json
{
  "cli": {
    "version": ">= 16.15.0",
    "appVersionSource": "remote"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "environment": "development",
      "env": { "ENVIRONMENT": "dev" },
      "android": { "buildType": "apk" }
    },
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
    },
    "live": {
      "distribution": "store",
      "channel": "production",
      "environment": "production",
      "env": { "ENVIRONMENT": "live" },
      "android": { "buildType": "app-bundle", "autoIncrement": "versionCode" },
      "ios": { "buildConfiguration": "Release", "autoIncrement": "buildNumber" }
    }
  },
  "submit": {
    "uat": { "android": { "track": "internal", "releaseStatus": "draft" } },
    "live": { "android": { "track": "production", "releaseStatus": "draft" } }
  }
}
```

Four deliberate choices:

- **`appVersionSource: "remote"`** — EAS owns the build numbers, so CI never has to commit a version bump. Recommended by Expo from EAS CLI 12.0.0 onward.
- **`extends`** on `uat-store` — copy-pasted profiles drift. Inheriting means a fix to `uat` cannot silently fail to reach `uat-store`.
- **`autoIncrement` on both store profiles** — without it, two store builds in a row collide on the same build number and the second is rejected.
- **iOS `submit` blocks omitted, not filled with placeholders.** A missing block fails immediately and clearly. `"ascAppId": "YOUR_ASC_APP_ID"` fails deep in the submission with a confusing error. Add the block when you have the real values.

Profile names are yours to choose — `development` / `uat` / `uat-store` / `live` here. Expo's own examples use `development` / `preview` / `production`. Pick one convention and use it across every app you own; the cost of two conventions is paid every time you switch projects.

## 9. Configure the app config for environments and updates

```ts
// app.config.ts
const ENV = process.env.ENVIRONMENT ?? 'dev';
const isLive = ENV === 'live';

export default {
  expo: {
    name: isLive ? 'MyApp' : `MyApp (${ENV})`,
    slug: 'myapp',
    version: '1.0.0',
    scheme: isLive ? 'myapp' : `myapp-${ENV}`,
    ios: { bundleIdentifier: isLive ? 'com.acme.myapp' : `com.acme.myapp.${ENV}` },
    android: { package: isLive ? 'com.acme.myapp' : `com.acme.myapp.${ENV}` },
    updates: { url: 'https://u.expo.dev/<your-project-id>' },
    runtimeVersion: { policy: 'fingerprint' },
    extra: { environment: ENV, eas: { projectId: '<your-project-id>' } },
  },
};
```

**Set `updates.url` and `runtimeVersion` now, even if you have no plans for OTA.** Adding them later to an app with users means the next build is a new runtime, and every installed client needs a store update before OTA can reach them. Today it is two lines.

`fingerprint` is the right policy for a CNG project — it hashes everything that affects the native runtime, so it changes exactly when a new binary is genuinely required. Note that `appVersionSource: "remote"` is **not** compatible with the `nativeVersion` policy; use `fingerprint` or `appVersion`.

Per-environment bundle identifiers let UAT and production coexist on one device, which is worth having from the start.

## 10. Write `.easignore`

Start it as a **copy of your entire `.gitignore`**, then add build-only exclusions:

```bash
# ... everything from .gitignore ...

/android
/ios
/docs
/coverage
*.md
```

`.easignore` **replaces** `.gitignore` for the upload archive rather than adding to it — the EAS CLI prioritises it. A three-line `.easignore` therefore starts uploading `node_modules` and anything else `.gitignore` was covering. `!` negation is supported, and is the right way to include a gitignored file the build genuinely needs.

## 11. Put secrets in EAS, not in the repo

```sh
# A value the build needs, hidden from logs
eas env:set --name GOOGLE_MAPS_API_KEY --value "…" \
  --environment preview --environment production --visibility sensitive

# A file the build needs
eas env:set --name GOOGLE_SERVICES_JSON --type file --value ./google-services.json \
  --environment production --visibility secret
```

File-type variables are made available to the build as a **path** on the runner, not as inline content. That is what lets `google-services.json` stay out of the repo entirely.

Before adding any variable, check whether it belongs in the app at all — anything shipped in the bundle is readable by anyone with the app, and `EXPO_PUBLIC_*` values are inlined into the JS bundle by design. That classification question is `react-native-security`'s; routing is [cicd-secrets-in-ci.md](references/cicd-secrets-in-ci.md).

## 12. Add exactly one CI secret

```sh
gh secret set EXPO_TOKEN
```

Create the token at **expo.dev → Account settings → Access tokens**. For anything shared or long-lived, use a Robot user under an Organization rather than a personal token — a personal token can act on everything you own.

`EXPO_TOKEN` should be the only secret your CI provider holds. Keystores, App Store Connect keys and Play service accounts live in EAS.

## 13. Commit the PR gate in the first commit

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v6
        with:
          node-version-file: .nvmrc
          cache: npm
      - run: npm ci
      - run: npm run ci
```

No secrets, no EAS, free minutes. GitLab and EAS Workflows equivalents: [cicd-runner-recipes.md](references/cicd-runner-recipes.md).

## 14. Write `RELEASE.md`

Ten lines. This is the document that Levels 3 and 4 automate, and the fallback when automation breaks.

```markdown
# Release

| Environment | Profile | Channel | Command | Who |
|---|---|---|---|---|
| Dev client | `development` | — | `eas build -p android --profile development` | anyone |
| UAT | `uat` | `uat` | automatic on merge to `develop` | CI |
| Production | `live` | `production` | tag `v1.2.3`, then approve the submit job | maintainer |

Secrets live in EAS (`eas env:list`). CI holds only `EXPO_TOKEN`.
Rollback: see references/cicd-ota-vs-build.md
```

---

## Verify before you write a feature

```sh
npm run ci                                   # the gate passes locally
npx expo config --type public | grep -E 'projectId|runtimeVersion|url'
npx eas-cli build -p android --profile uat   # one real build, end to end
git push                                     # the gate runs in CI and passes
```

That last step matters: **run one real build before wiring more automation.** It initialises credentials and confirms the project is genuinely buildable. Automating a build that has never succeeded manually just moves the failure somewhere harder to read.

---

## Day-1 checklist

- [ ] Git remote created, no token in the URL
- [ ] `.nvmrc` + `engines.node`
- [ ] One lockfile, committed
- [ ] `typecheck` / `lint` / `test` / `doctor` / `ci` scripts
- [ ] Real `projectId` (not a placeholder)
- [ ] `eas.json` — every profile fills every column of the release matrix
- [ ] `updates.url` + `runtimeVersion` policy set
- [ ] `.easignore` starts as a copy of `.gitignore`
- [ ] Secrets in EAS; `EXPO_TOKEN` the only CI secret
- [ ] `ci.yml` committed
- [ ] `RELEASE.md` written
- [ ] One successful manual `eas build`