# 接口范围 / Interface Scope

**Test.26:** extract the complete **Windows.zip** and run its `Start.cmd` or EXE; no separate Python is needed. Source startup requires Python 3.10+. Analysis/output behavior remains that of test.25. See the [portable guide](../tools/README-Portable.md) and [test.26 report](Test_2.0.0_test26.md).

**当前 test.26：** 完整解压 **Windows.zip** 后双击包内 `Start.cmd` 或 exe，无需另装 Python；源码启动仍需 Python 3.10+。分析／输出行为沿用 test.25。见 [便携包说明](../tools/README-Portable.md) 和 [test.26 记录](Test_2.0.0_test26.md)。

当前 test.26 只保留现有 SR6/OSR6 TCode 串口和 BLE UART 接口，以及 Log only。其他商业设备适配已移除；旧绑定不再恢复。机械臂关节定义、逆运动学、碰撞检测与实机反馈未实现或验证。

SR6/OSR6 是沿用的设备/接口名称，不意味着任意机械臂可以直接连接。不要将原有回中位置等同于机械臂的安全姿态。先在主程序选择 Log only 验证分析预览。

Current test.26 retains existing SR6/OSR6 TCode serial/BLE transport and Log only. Other commercial-device integrations have been removed. Robot-arm kinematics, collision handling and feedback are not verified. A legacy center position is not a validated robot-arm safe pose.

See the [current test guide](Test_2.0.0_test26.md), [retained analysis behavior](Test_2.0.0_test25.md) and [README](../README.md).
