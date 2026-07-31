---
description: How to build and run the app on simulators / local devices
---

Use these commands to run the app natively on your local environment. Note that the `package.json` contains several prebuild configurations for environment targeting (UAT vs Live).

### Running Locally on iOS

1. Run on iOS (UAT environment):
   // turbo
   ```bash
   yarn ios:uat
   ```

2. Run on iOS (Live environment):
   // turbo
   ```bash
   yarn ios:live
   ```

### Running Locally on Android

1. Run on Android (UAT environment):
   // turbo
   ```bash
   yarn android:uat
   ```

2. Run on Android (Live environment):
   // turbo
   ```bash
   yarn android:live
   ```
