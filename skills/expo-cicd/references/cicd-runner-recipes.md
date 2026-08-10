# CI Runner Recipes: EAS Workflows, GitHub Actions, GitLab CI

Three dialects of the same four steps. The lesson of this file is the **sameness** — once the release matrix is filled in, the runner is an implementation detail you can change later.

```
checkout → install Node + deps → run the gate → call eas
```

## Choosing a platform

Start with where the repo lives, not with tooling preference.

| Repo host | EAS Workflows | GitHub Actions + `eas-cli` | GitLab CI + `eas-cli` |
|---|---|---|---|
| GitHub | ✅ full git triggers | ✅ | — |
| GitLab | ❌ no git triggers | — | ✅ |
| Bitbucket / other | ❌ no git triggers | — | ✅ (same shape) |

**EAS Workflows git triggers are GitHub-only.** On any other host you can still run EAS Workflows manually with `eas workflow:run`, but push and pull-request triggers will not fire — so in practice non-GitHub repos drive `eas-cli` from their own CI.

| | EAS Workflows | Generic CI + `eas-cli` |
|---|---|---|
| Build/submit/update as first-class job types | ✅ | you script it |
| Fingerprint-gated build-vs-update built in | ✅ (`fingerprint` + `get-build`) | you script it |
| Arbitrary steps (deploy a backend, run a linter on a monorepo sibling) | limited | ✅ anything |
| Works on any VCS host | ❌ | ✅ |
| Where the minutes are billed | EAS | your CI provider |

**They compose well, and that is usually the right answer:** run the free PR gate on your existing CI, and let EAS Workflows own the build/submit/update jobs where its built-in job types do real work.

---

## EAS Workflows

Files live in `.eas/workflows/*.yml`, next to `eas.json`. Validate before committing:

```sh
eas workflow:validate .eas/workflows/production.yml
eas workflow:run .eas/workflows/production.yml          # manual run
eas workflow:run .eas/workflows/production.yml --wait   # block until done
```

### Built-in job types

| Type | Key params |
|---|---|
| `build` | `platform`, `profile` |
| `submit` | `build_id` |
| `update` | `branch` or `channel`, `platform` |
| `fingerprint` | `environment` (job-level, not under `params`) |
| `get-build` | `fingerprint_hash`, `profile` |
| `update-rollout` | `update_group_id` |
| `testflight` | `build_id` |
| `require-approval` | — |
| `slack` | `webhook_url` |
| `github-comment` | — |
| `maestro` / `maestro-cloud` | `build_id`, `flow_path` |
| `deploy`, `get-build`, `branch-delete`, `repack`, `doc`, `apple-device-registration-request` | see docs |

Custom jobs use `steps:` instead of `type:`, with built-in functions in the `eas/` namespace: `eas/checkout`, `eas/install_node_modules`, `eas/prebuild`, `eas/download_build`, `eas/upload_artifact`, `eas/download_artifact`, `eas/restore_cache`, `eas/save_cache`, `eas/use_npm_token`, `eas/send_slack_message`.

### PR gate

```yaml
name: PR checks

on:
  pull_request:
    branches: [main, develop]

jobs:
  check:
    name: Typecheck, lint, test
    steps:
      - uses: eas/checkout
      - uses: eas/install_node_modules
      - name: Typecheck
        run: npm run typecheck
      - name: Lint
        run: npm run lint
      - name: Test
        run: npm run test
      - name: Doctor
        run: npx expo-doctor
```

### UAT build on merge

```yaml
name: UAT build

on:
  push:
    branches: [develop]

jobs:
  build_android:
    name: Build Android UAT
    type: build
    params:
      platform: android
      profile: uat
  build_ios:
    name: Build iOS UAT
    type: build
    params:
      platform: ios
      profile: uat
  notify:
    name: Notify testers
    needs: [build_android, build_ios]
    type: slack
    params:
      webhook_url: ${{ env.SLACK_WEBHOOK_URL }}
      message: 'New UAT build available'
```

Environment variables are interpolated as `${{ env.NAME }}`; set `SLACK_WEBHOOK_URL` with `eas env:set`. The `slack` job requires both `webhook_url` and `message`.

### The fingerprint-gated release

This is the pattern the whole skill points at: **check whether a build with this fingerprint already exists; if it does, ship an update instead of building.** Adapted from Expo's own "deploy to production" example.

```yaml
name: Deploy to production

on:
  push:
    branches: [main]

jobs:
  fingerprint:
    name: Fingerprint
    type: fingerprint
    environment: production

  get_android_build:
    name: Check for existing Android build
    needs: [fingerprint]
    type: get-build
    params:
      fingerprint_hash: ${{ needs.fingerprint.outputs.android_fingerprint_hash }}
      profile: live

  build_android:
    name: Build Android
    needs: [get_android_build]
    if: ${{ !needs.get_android_build.outputs.build_id }}
    type: build
    params:
      platform: android
      profile: live

  approve_submit:
    name: Approve store submission
    needs: [build_android]
    type: require-approval

  submit_android:
    name: Submit Android
    needs: [approve_submit, build_android]
    type: submit
    params:
      build_id: ${{ needs.build_android.outputs.build_id }}

  publish_android_update:
    name: Publish Android update
    needs: [get_android_build]
    if: ${{ needs.get_android_build.outputs.build_id }}
    type: update
    params:
      branch: production
      platform: android
```

Read the control flow: no existing build for this fingerprint → build it, get a human's approval, submit. An existing build → the native runtime is unchanged, so publish an OTA update instead. Duplicate the three build/submit jobs for iOS. The `require-approval` job is the human gate — remove it only if you are certain you want unattended store submissions.

---

## GitHub Actions

### PR gate

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

No secrets, no EAS, free minutes. `node-version-file: .nvmrc` keeps one source of truth for the Node version.

### EAS build

```yaml
name: EAS Build
on:
  workflow_dispatch:
    inputs:
      profile:
        description: Build profile
        type: choice
        options: [uat, uat-store, live]
        default: uat
  push:
    branches: [develop]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-node@v6
        with:
          node-version-file: .nvmrc
          cache: npm
      - uses: expo/expo-github-action@v8
        with:
          eas-version: latest
          token: ${{ secrets.EXPO_TOKEN }}
      - run: npm ci
      - name: Build on EAS
        run: |
          eas build --platform all \
            --profile ${{ inputs.profile || 'uat' }} \
            --non-interactive --no-wait
```

`--no-wait` returns as soon as the build is queued — you are not billed CI minutes while EAS builds. **The trade-off: the job goes green even if the build later fails.** If you need the job's status to reflect the build result, drop `--no-wait` and accept the minutes, or add a follow-up job that polls.

For a release, chain submission onto the build instead of a separate job:

```sh
eas build --platform all --profile live --non-interactive --auto-submit-with-profile live
```

### Notes

- `expo/expo-github-action@v8` accepts `eas-version`, `token`, `packager` (default `yarn` — set `npm` if that is your manager), `eas-cache`, `patch-watchers`.
- Pin `eas-version` to a known-good version rather than `latest` if reproducibility matters more than currency.
- For simulator/emulator *test* artifacts and `gh run download` retrieval, see the `github-actions` skill — but note its composite actions target bare RN CLI and need an `expo prebuild` step in a CNG project.

---

## GitLab CI

`.gitlab-ci.yml` — the same four steps.

```yaml
stages: [check, build]

default:
  image: node:24
  cache:
    key:
      files: [package-lock.json]
    paths: [.npm/]
  before_script:
    - npm ci --cache .npm --prefer-offline

check:
  stage: check
  script:
    - npm run ci
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"

build_uat:
  stage: build
  script:
    - npx eas-cli build --platform all --profile uat --non-interactive --no-wait
  rules:
    - if: $CI_COMMIT_BRANCH == "develop"

build_live:
  stage: build
  script:
    - npx eas-cli build --platform all --profile live --non-interactive --no-wait
  rules:
    - if: $CI_COMMIT_TAG =~ /^v/
      when: manual
```

Set `EXPO_TOKEN` as a **masked, protected** CI/CD variable in project settings. `when: manual` on the release job is GitLab's version of the human gate.

Bitbucket Pipelines and CircleCI follow the identical shape: an image with the right Node, a cached install, then `npx eas-cli build …`. Only the trigger syntax differs.

---

## Repo readiness — what actually breaks the first run

Nearly every first-CI failure is one of these, and none of them are pipeline bugs.

| Blocker | Symptom | Fix |
|---|---|---|
| **Two lockfiles** | CI resolves a different dependency tree than your laptop | Pick one manager, delete the other lockfile |
| **Node unpinned** | Works locally, fails on the runner with a syntax or engine error | `.nvmrc` + `engines.node`; CI reads `node-version-file` |
| **Install flags only in `eas-build-pre-install`** | EAS builds fine, the PR gate fails at `npm ci` | Move flags to `.npmrc` — see below |
| **Placeholder `projectId`** | `eas build` cannot resolve the project | `eas init`; verify with `npx expo config --type public \| grep projectId` |
| **No `.easignore`, or a naive one** | Slow uploads, or secrets uploaded | Copy `.gitignore` into it first — it **replaces** `.gitignore`, it does not extend it |
| **Tracked cruft** — `app.json.backup`, a second app config elsewhere in the tree | CI picks up the wrong config | Delete or move it out of the project root |
| **`postinstall` patches not surviving CI install** | Native code differs between local and CI builds | Ensure `patch-package` / `patch-project` run in the CI install step too |

### `eas-build-pre-install` is not a CI hook

These npm lifecycle hooks are executed by the **EAS Build worker**:

`eas-build-pre-install`, `eas-build-post-install`, `eas-build-on-success`, `eas-build-on-error`, `eas-build-on-cancel`, `eas-build-on-complete`

A GitHub Actions or GitLab runner never runs them. A project that puts `npm config set legacy-peer-deps true` in `eas-build-pre-install` will build correctly on EAS and fail on its own PR gate. Put install configuration in `.npmrc`, which both read. `EAS_BUILD_PLATFORM` (`android` / `ios`) is available inside these hooks if you need to fork behaviour.

### CNG in CI

EAS Build runs `prebuild` from a **clean checkout**. Consequences:

- A local `android/` or `ios/` directory is never part of an EAS build. Hand-edits there do not ship — they belong in a config plugin or `expo-build-properties`. (`react-native-best-practices` covers this.)
- Anything the native build needs must be reachable from the uploaded archive: config plugins, patch files, vendored libraries. If it is gitignored *and* not negated in `.easignore`, it is not there.
- `expo prebuild` must run with the same environment your config expects. `ENVIRONMENT=uat expo prebuild --clean` and a bare `expo prebuild --clean` produce different native projects when `app.config.js` branches on that variable — a `--clean` pass without the variable set silently regenerates the *default* environment's native code.

### Caching

Cache the package manager store, not `node_modules`:

- GitHub Actions: `cache: npm` (or `yarn`) on `actions/setup-node`
- GitLab: cache `.npm/` keyed on the lockfile, install with `--cache .npm --prefer-offline`
- EAS Workflows: `eas/restore_cache` / `eas/save_cache`

---

## Verifying a pipeline

```sh
eas workflow:validate .eas/workflows/production.yml   # EAS Workflows syntax
npx expo-doctor                                        # project health
npx eas-cli build:version:get -p android               # what CI will use next
npx expo config --type public                          # what the config resolves to
```

Run that last command **on the runner**, not just locally. It is the only way to catch a build-time environment variable resolving differently in CI — the failure that ships a UAT bundle identifier to production.