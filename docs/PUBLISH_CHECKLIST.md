# Windows and Source Release Checklist — 2.0.0

Release name: **SR6/OSR6 Realtime Screen TCode 2.0.0**. Source version: `2.0.0`; Python package version: `2.0.0`. Publication branch: `2.0.0-beta`. Matching Windows/source archives are required; no broad hardware compatibility is asserted.

## Scope

- Publish **2.0.0** as the official release, retaining test.25's analysis/output behavior and the reviewed portable-packaging support. Keep the earlier test.25 tag intact; the provisional test.26 name is not a separate release.
- Mark the GitHub release as a **normal release**, with prerelease disabled. Use tag `v2.0.0` and the [bilingual release text](Release_2.0.0.md).
- GitHub creates automatic source ZIP/tar archives. Do not describe these as a portable application or a Windows binary package.
- Build the Windows onedir package with the repository spec and `tools/build_release.py`; use isolated output/cache directories and read-only existing dependencies. Preserve older releases and assets; never relabel an old binary or overwrite an earlier version.
- Retain both complete archives, matching source-commit manifests, release notes and SHA-256 checksums in a separate directory for each version. Incomplete development snapshots must be explicitly separate, never presented as complete releases.
- Keep the previous development branch/history intact when publishing from `2.0.0-beta`; do not force-push or silently change the default branch.

## Review the exact publication

- Review all staged modifications, additions and intentional deletions against the current source. Do not blindly stage a dirty working directory.
- Remove obsolete hardware-compatibility branding from current product names, UI, launcher text, packaging metadata and active publishing instructions. Preserve attribution, licenses and accurate historical records.
- Exclude local models, downloadable GPU runtimes, virtual environments, caches, logs, generated outputs, private media, personal settings and machine-specific paths. Inspect the actual staged file list and contents as well as ignore rules.
- Preserve `LICENSE`, `THIRD_PARTY_NOTICES.md` and necessary upstream credits, including the simulator. Document borrowed ideas accurately without claiming upstream code was bundled when it was not.
- Keep startup instructions separate: the complete Windows ZIP includes Python; source startup requires Python 3.10+ and may create a local `.venv`. A compatible shared environment can be reused read-only. The separately attached Start.cmd is only a spare launcher for the complete Windows folder.
- Describe existing SR6/OSR6 TCode transport separately from unverified robot-arm mapping, inverse kinematics, collisions and feedback. Keep image-scale proxies and estimated targets distinct from real depth/contact.

## Validation

- Use the isolated main-suite entry point `tests/run_tests.py`; protect real settings through startup and GUI checks. Run main GUI/capture checks sequentially.
- Rerun tests appropriate to publication edits, both language startup checks and the independent Lab startup when affected. Do not substitute old binary tests for current source verification.
- Check the actual built exe and a freshly extracted ZIP, including both languages, independent Lab, mandatory dependency resources, CPU/model inference and Log-only capture without external Python. Keep source-test and frozen-test results distinct in [the 2.0.0 report](Validation_2.0.0.md).
- Record any publication-time checks and remaining limitations honestly. Software and synthetic checks do not verify physical hardware; do not connect hardware automatically.
- Verify the pushed branch/tag resolve to the reviewed commit, confirm `v2.0.0` is a normal release with prerelease disabled, and check public links and downloadable source after publishing.

This checklist is a workflow, not proof that each publication step has completed. The actual Git commit, remote state and release page establish publication status.
