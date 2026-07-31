---
description: How to trigger EAS builds for this project
---

This project uses EAS Build (`eas.json` is configured).

### Building with EAS

1. To build for iOS (ensure you specify the correct EAS profile):
   // turbo
   ```bash
   eas build --platform ios --profile <profile_name>
   ```

2. To build for Android:
   // turbo
   ```bash
   eas build --platform android --profile <profile_name>
   ```

*Make sure you are logged in using `eas login` if you encounter authentication issues.*
