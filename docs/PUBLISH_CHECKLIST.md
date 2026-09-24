# Source Prerelease Checklist — 2.0.0-test.25

Release name: **SR6/OSR6 Realtime Screen TCode 2.0.0-test.25**. Source version: `2.0.0-test.25`; Python package version: `2.0.0.dev25`. Publication branch: `2.0.0-beta`. This is a source prerelease; it does not assert broad hardware compatibility.

## Scope

- Publish the reviewed cumulative source through test.25, including integrated analysis/preview, final-command simulator, v2 subject tracking, multi-display capture fixes and bounded missing-observation continuity.
- Mark the GitHub release as a **prerelease**. Use the matching version tag and [bilingual release text](GitHub发布页文案.md).
- GitHub creates automatic source ZIP/tar archives. Do not describe these as a portable application or a Windows binary package.
- Do not build/upload a new exe or custom Windows ZIP for this source-only release. Preserve older releases, their original assets and remote history; never relabel an old binary with this version.
- Keep the previous development branch/history intact when publishing from `2.0.0-beta`; do not force-push or silently change the default branch.

## Review the exact publication

- Review all staged modifications, additions and intentional deletions against the current source. Do not blindly stage a dirty working directory.
- Remove obsolete hardware-compatibility branding from current product names, UI, launcher text, packaging metadata and active publishing instructions. Preserve attribution, licenses and accurate historical records.
- Exclude local models, downloadable GPU runtimes, virtual environments, caches, logs, generated outputs, private media, personal settings and machine-specific paths. Inspect the actual staged file list and contents as well as ignore rules.
- Preserve `LICENSE`, `THIRD_PARTY_NOTICES.md` and necessary upstream credits, including the simulator. Document borrowed ideas accurately without claiming upstream code was bundled when it was not.
- Keep the startup instructions accurate: Python 3.10+ is required; fresh source startup creates a local `.venv`. A compatible shared environment can be reused read-only, without installing into it.
- Describe existing SR6/OSR6 TCode transport separately from unverified robot-arm mapping, inverse kinematics, collisions and feedback. Keep image-scale proxies and estimated targets distinct from real depth/contact.

## Validation

- Use the isolated main-suite entry point `tests/run_tests.py`; protect real settings through startup and GUI checks. Run main GUI/capture checks sequentially.
- Rerun tests appropriate to publication edits, both language startup checks and the independent Lab startup when affected. Do not substitute old binary tests for current source verification.
- Keep the recorded test.25 baseline separate from publication-time checks: **392 main tests**, **38 Lab tests**, bilingual root startup, Lab startup, final-command simulator and Log-only capture checks passed for the completed test.25 source. Details and earlier failed attempts are in [the test.25 report](Test_2.0.0_test25.md).
- Record any publication-time checks and remaining limitations honestly. Software and synthetic checks do not verify physical hardware; do not connect hardware automatically.
- Verify the pushed branch/tag resolve to the reviewed commit, confirm the release is marked prerelease, and check public links and downloadable source after publishing.

This checklist is a workflow, not proof that each publication step has completed. The actual Git commit, remote state and release page establish publication status.
