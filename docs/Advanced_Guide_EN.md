# Advanced Test Notes

**Test.26:** extract the complete **Windows.zip** and run its `Start.cmd` or EXE; no separate Python is needed. Source startup requires Python 3.10+. See the [portable guide](../tools/README-Portable.md) and [test.26 report](Test_2.0.0_test26.md).

**当前 test.26：** 完整解压 **Windows.zip** 后双击包内 `Start.cmd` 或 exe，无需另装 Python；源码启动仍需 Python 3.10+。见 [便携包说明](../tools/README-Portable.md) 和 [test.26 记录](Test_2.0.0_test26.md)。

See the [current startup/preview guide](../Start.md) and [retained test.25 analysis limitations](Test_2.0.0_test25.md). Compare the same source clip and resolution when measuring latency. Processing time is not end-to-end delay; image scale is not physical depth. The [test.10 report](Test_2.0.0_test10.md) remains a historical feature record.

Do not infer robot-arm compatibility from the retained SR6/OSR6 transport. Existing limits are not a substitute for validated mechanical limits, feedback and independent emergency stopping.
