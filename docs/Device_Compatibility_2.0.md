# 接口范围 / Interface Scope

**2.0.0:** extract the complete **Windows.zip** and run its `Start.cmd` or EXE; no separate Python is needed. Source startup requires Python 3.10+. Analysis/output behavior remains that of test.25. See the [portable guide](../tools/README-Portable.md) and [2.0.0 report](Validation_2.0.0.md).

**当前 2.0.0：** 完整解压 **Windows.zip** 后双击包内 `Start.cmd` 或 exe，无需另装 Python；源码启动仍需 Python 3.10+。分析／输出行为沿用 test.25。见 [便携包说明](../tools/README-Portable.md) 和 [2.0.0 记录](Validation_2.0.0.md)。

当前 2.0.0 只保留现有 SR6/OSR6 TCode 串口和 BLE UART 接口，以及 Log only。其他商业设备适配已移除；旧绑定不再恢复。机械臂关节定义、逆运动学、碰撞检测与实机反馈未实现或验证。

SR6/OSR6 是沿用的设备/接口名称，不意味着任意机械臂可以直接连接。不要将原有回中位置等同于机械臂的安全姿态。先在主程序选择 Log only 验证分析预览。

Current 2.0.0 retains existing SR6/OSR6 TCode serial/BLE transport and Log only. Other commercial-device integrations have been removed. Robot-arm kinematics, collision handling and feedback are not verified. A legacy center position is not a validated robot-arm safe pose.

See the [release validation](Validation_2.0.0.md), [retained analysis behavior](Test_2.0.0_test25.md) and [README](../README.md).
