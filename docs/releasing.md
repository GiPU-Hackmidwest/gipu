# Releasing GiPU locally

Build on your own computer, then upload the installers manually. No GitHub Actions, paid runners or repository signing secrets are needed. iPhone installs through Xcode; see the README. An optional manual GitHub build is described at the end.

## Mac installer

On an Apple silicon Mac, follow the README prerequisites, then run from the repository root:

```bash
export VITE_DEFAULT_COORDINATOR=https://66-228-53-243.ip.linodeusercontent.com
npm --prefix apps/web ci
./scripts/build-desktop-app.sh --config '{"version":"0.2.0"}'
mkdir -p dist
stage="$(mktemp -d)"
ditto apps/web/src-tauri/target/release/bundle/macos/GiPU.app "$stage/GiPU.app"
ln -s /Applications "$stage/Applications"
hdiutil create -volname GiPU -srcfolder "$stage" -ov -format UDZO dist/GiPU-0.2.0-macos-arm64.dmg
hdiutil verify dist/GiPU-0.2.0-macos-arm64.dmg
```

The app includes its worker; the model downloads only after the user asks. These paths assume the default Cargo target directory; if you set `CARGO_TARGET_DIR`, use the bundle path printed by the build instead. The temporary staging directory can be removed after verification.

## Android installer

For team testing, use the README's debug APK instructions. To make a release APK, install the Android prerequisites and JDK 17, then create a signing key once:

```bash
./scripts/android-release-key.sh
```

This keeps the key and a backup of its settings in `~/.gipu-release/` with owner-only permissions, and writes the gitignored `apps/web/src-tauri/gen/android/keystore.properties`. It refuses to overwrite existing signing files and uploads nothing. Back up the key privately: Android updates require the same key.

```bash
export VITE_DEFAULT_COORDINATOR=https://66-228-53-243.ip.linodeusercontent.com
cd apps/web
npm ci
npm run tauri android build -- --target aarch64 --apk --config '{"version":"0.2.0"}'
```

Use the APK path printed by Tauri. Copy it to the repository's `dist/` as `GiPU-0.2.0-android-arm64.apk`. Without local signing settings, a release APK is unsigned and cannot be installed. Debug APKs are for testing; they are debuggable and allow HTTP. Debug and release APKs use different keys and cannot update each other.

## Share a release

Test both installers first. Keep signing keys, settings and user data out of the upload. Generate checksums for the files you intend to share:

```bash
cd dist
shasum -a 256 GiPU-0.2.0-macos-arm64.dmg GiPU-0.2.0-android-arm64.apk > SHA256SUMS.txt
```

On the repository's **Releases → Draft a new release** page, select the reviewed main commit, create a version tag such as `v0.2.0`, and attach the DMG, APK and checksum file. Save as a draft, review, then publish when the team is ready. Creating a tag does not start a build.

The repository is private, so downloads are available to people with repository access. For a team demo, installers can also be shared directly.

## Installation limits

- Mac builds use a final **ad-hoc signature** after worker deduplication; they are not Developer ID signed or notarized. The build fails if `codesign --verify --deep --strict` rejects the completed app. Ad-hoc signing seals the bundle against accidental modification but does not establish an Apple-verified developer identity. Users may still need **System Settings → Privacy & Security → Open Anyway**. See [Apple's first-launch guidance](https://support.apple.com/en-us/102445).
- A valid DMG checksum does not prove the app inside is valid. Before sharing, mount the packaged DMG and run `codesign --verify --deep --strict --verbose=2 /Volumes/GiPU/GiPU.app`, then copy it out and test launch on a compatible Apple-silicon Mac. If it says **damaged**, check the signature and download again; do not advise disabling Gatekeeper or removing quarantine as a fix for a defective package.
- The current wrapper refuses a configured Developer ID identity rather than silently replacing it with an ad-hoc signature. A future Developer ID build must sign after all resource changes and then notarize; that pipeline needs an Apple Developer account.
- Android sideloading requires allowing installation from the app used to open the APK. Google Play is not required.
- Release Android builds require an HTTPS grid address. Use a compatible deployed coordinator; building installers does not deploy it.

Actual build and device evidence is recorded in [v1-progress.md](v1-progress.md).

## Optional: build on GitHub (manual only)

`.github/workflows/release.yml` builds the same installers on GitHub runners, but only when someone starts it: **Actions → Release → Run workflow**. It never runs on pushes, tags or pull requests.

- **Version:** stamped into both apps, for example `0.2.0`.
- **Platforms:** `android` (Linux runner, cheap), `macos` or `both`. In this private repository, macOS minutes cost 10× Linux minutes; a Mac build uses roughly 300 included minutes.
- **Draft release:** when ticked, the files and `SHA256SUMS.txt` go to a **draft** release `v<version>`, created at the run's commit or added to an existing draft. A published release is never changed. Publishing stays a manual step on the Releases page.

Files are always kept as workflow artifacts on the run. The repository variable `GIPU_DEFAULT_GRID` sets the suggested grid address.

Android signing on GitHub needs the local key from `scripts/android-release-key.sh`, stored as repository secrets. Run this from the repository after creating the key; nothing is printed:

```bash
base64 -i ~/.gipu-release/gipu-release.jks | gh secret set ANDROID_KEYSTORE_BASE64
grep '^storePassword=' ~/.gipu-release/keystore.properties | cut -d= -f2- | gh secret set ANDROID_KEYSTORE_PASSWORD
gh secret set ANDROID_KEY_ALIAS --body gipu
grep '^keyPassword=' ~/.gipu-release/keystore.properties | cut -d= -f2- | gh secret set ANDROID_KEY_PASSWORD
```

Without those secrets the run produces a debug-signed `...-debug.apk` for testing and shows a warning. The runner deletes the decoded key after the build.

After this workflow first lands on `main`, enable it once: it was switched off when the earlier automatic version was removed.

```bash
gh workflow enable Release
```

