# Quick Start

**Test.26:** extract the complete **Windows.zip** and run its `Start.cmd` or EXE; no separate Python is needed. Source startup requires Python 3.10+. Keep the EXE with `_internal` and all supporting files. See the [portable guide](../tools/README-Portable.md) and [test.26 report](Test_2.0.0_test26.md).

**当前 test.26：** 完整解压 **Windows.zip** 后双击包内 `Start.cmd` 或 exe，无需另装 Python；源码启动仍需 Python 3.10+。保留 `_internal` 等完整配套文件。见 [便携包说明](../tools/README-Portable.md) 和 [test.26 记录](Test_2.0.0_test26.md)。

This test is for visual-analysis and robot-arm simulation experiments. Select Log only before starting analysis.

Use Analysis Preview for paired raw/processed comparison. Start with Log only; the same analysis feeds the selected output route. Existing SR6/OSR6 transport is retained; real robot-arm compatibility is unverified.

Output Monitor opens by default. Show Preview opens the 3D reference model using final output after all gains and constraints. Full/Half Travel is first in the analysis list, followed by RTM 2D, with Hybrid v2 still selected by default. Dance settings are saved separately.

See the [startup instructions](../Start.md); the [test.18 guide](Test_2.0.0_test18.md) records earlier feature changes. Older screenshots and device guides do not describe this version.
