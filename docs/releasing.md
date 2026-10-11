# Releasing GiPU

`.github/workflows/release.yml` builds the downloadable apps:

| File | What it is |
| --- | --- |
| `GiPU-<version>-macos-arm64.dmg` | Mac app for Apple silicon, with the image worker inside. The model (about 1 GB) downloads from **Contribute** on first use. |
| `GiPU-<version>-android-arm64.apk` | Android app for 64-bit ARM phones (nearly all current phones). |
| `SHA256SUMS.txt` | Checksums for both. |

iPhone is not built here; it installs from source through Xcode (see the README).

## Make a release

1. Merge everything for the release into `main`.
2. Tag and push:

   ```bash
   git tag v0.2.0 && git push origin v0.2.0
   ```

3. The workflow builds both apps (about 30–45 minutes, mostly the Mac worker) and creates a **draft** release with generated notes.
4. Open the draft on GitHub, check the notes and files, then publish it.

The tag must look like `v1.2.3`; it becomes the app version. To build without publishing, run the workflow from **Actions → Release → Run workflow**. Files then stay attached to that run as artifacts. A pull request that changes the workflow also builds both apps without publishing.

## One-time setup

**Default grid address.** Set the repository variable `GIPU_DEFAULT_GRID` (Settings → Secrets and variables → Actions → Variables) to the hosted grid's `https://` address. New installs then suggest it on the join screen. Without it, people type the address themselves. Release Android builds only connect to `https://` grids.

**Android signing.** Android only installs updates signed with the same key, so create it once and keep it safe:

```bash
./scripts/android-release-key.sh
```

It writes the key and its passwords to `~/.gipu-release/` (owner-only permissions) and prints the two `gh secret set` commands that store them as repository secrets: `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`. Back up that folder privately; losing it means existing installs cannot be updated.

Until those secrets exist, the workflow publishes a **debug-signed** APK named `...-debug.apk` and shows a warning. It installs, but it allows plain-http grids and is debuggable, so treat it as a test build. Release-signed and debug-signed APKs cannot update each other; uninstall first when switching.

## What people see when installing

- **Mac:** the app is not signed with an Apple Developer ID or notarized. After dragging it to Applications, macOS blocks the first launch. Open **System Settings → Privacy & Security** and choose **Open Anyway**, or Control-click the app and choose **Open**. Signing and notarization need an Apple Developer account and can be added to the workflow later.
- **Android:** sideloading needs **Install unknown apps** allowed for the browser or file manager used to open the APK. The app does not need Google Play.

## Verification record

See the V1 progress log for which parts of this workflow have actually run, locally or on GitHub.
