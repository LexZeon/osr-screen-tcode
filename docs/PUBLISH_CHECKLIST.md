# Publish Checklist

Product: **SR6/OSR6 Realtime Screen TCode High Hardware Compatibility**.
Approved BETA prerelease: **2.0.0-test.3**, not stable 2.0.0.

1. Work in the Git clone on `2.0.0-High-Hardware-Compatibility-BETA`. Never force-push, merge into main or replace a stable tag without approval.
2. Update README, bilingual manuals, changelog, UI and acknowledgements. Keep **“电话机”** unchanged in both languages.
3. Run automated tests and syntax checks. Build the current clone, not a sibling editable install, with `SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility.spec`.
4. Prepare Windows and source folders/ZIPs using `tools/build_release.py`. Include Start.cmd, README, docs, changelog, licenses and third-party notices. Windows includes the exe, CPU dependencies and installer tooling.
5. Reject trained models, optional GPU runtimes, .git, .venv, caches, logs, local settings and private paths. Source must contain no compiled executables or build intermediates. Do not bundle CUDA/cuDNN/NVIDIA/DirectML downloads.
6. Extract the actual Windows ZIP to a fresh temporary folder and verify Start.cmd opens the app without exiting. Test without driving hardware. Verify frozen in-app GPU installation in a disposable user profile.
7. Commit source/docs/tests, push the BETA branch normally, and tag `v2.0.0-test.3`. Create a draft prerelease, upload both ZIPs plus SHA256SUMS.txt, verify asset sizes, then publish with prerelease=true and make_latest=false.

## Asset Names

- `SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility-v2.0.0-test.3-Windows.zip`
- `SR6-OSR6-Realtime-Screen-TCode-High-Hardware-Compatibility-v2.0.0-test.3-Source.zip`
- `SHA256SUMS.txt`

Release body: `GitHub发布页文案.md`. Highlight experimental hardware, unverified physical compatibility, unsigned exe, adults-only restriction and conservative testing.

Contact: aivnailedeng@gmail.com
