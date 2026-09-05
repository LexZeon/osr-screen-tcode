# Advanced Guide

> **SR6/OSR6 Realtime Screen TCode High Hardware Compatibility v2.0.0-test.3:** BETA prerelease with Windows portable and source ZIPs. Extract the entire Windows folder and run `Start.cmd`; Python is not required for the portable build. Models and optional GPU runtimes are downloaded in-app, not bundled. Device measurement/sweep instructions concern native TCode hardware; new experimental hardware and custom bindings are described in [Device Compatibility](Device_Compatibility_2.0.md). For optional GPU installation and current changes, see the [main README](../README.md).


**Adults only: this project is intended for adults. Minors are prohibited.**

Use this when tuning latency, stability, six-axis behavior and release settings.

- Keep the capture region tight for lower latency.
- Use the recommended hybrid analysis mode first.
- Enable pose only when the frame contains enough of the full body for skeleton motion to be meaningful.
- Use audio-only mode for rhythm-heavy material where the visual motion is unreliable.
- Save safe L0 limits before increasing travel multipliers.
- Six-axis sensitivity should usually be lower than L0 sensitivity; raise it only after L0 feels stable.
- Watch the output curve for sticking at hard limits, noisy jitter or excessive delay.

The release package is meant to be honest and direct: a realtime OSR6 screen-reading TCode output tool, built by vibe coding and tested iteratively on real hardware.


Contact: aivnailedeng@gmail.com
Discord community: https://discord.gg/E7RY3rdKw


Discord note: if you join the community, follow the adults-only restriction. The server/relevant channels should be configured as age-restricted so minors cannot access adult content.
