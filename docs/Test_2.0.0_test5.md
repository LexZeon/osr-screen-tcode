# 2.0.0-test.5

## 范围 / Scope

本地源码测试，用于视觉分析与机械臂模拟实验。尚未验证具体机械臂。现有 SR6/OSR6 TCode 串口/BLE 路径保留；本轮不改轴算法、倍率、限位或设备运动行为。

Local visual-analysis and robot-arm simulation experiment. Existing SR6/OSR6 TCode transport is retained, but physical robot-arm compatibility is unverified. No axis mapping or motion tuning is introduced.

## 改动 / Changes

- 新增“独立骨架预览 / Independent Pose Preview”按钮，启动 Pose Preview Lab 0.2.1-test。该窗口不读写主程序输出状态，独立保存预览设置。
- 移除其他商业设备的品牌选择、外部服务扫描、功能绑定和适配实现。
- 旧外部设备配置迁移为 Log only；无效绑定字段在下次保存时删除。迁移不主动连接设备。
- 更新文档和界面措辞；旧发布包和远程仓库不变。
- The standalone preview uses its own process and settings; no model/region/control data is passed from the host. Other commercial-device integrations are removed, including saved bindings. Old external profiles default to Log only.

## 验证 / Verification

运行根目录 Start.cmd，先用 Log only。点击“独立骨架预览”，检查独立窗口能打开、重复点击不重复启动。主程序和预览分别关闭。
若窗口未打开，查看 logs/preview-lab.log。预览模型和操作见 ../Pose-Preview-Lab/Start.md。

Use Start.cmd, select Log only, and open Independent Pose Preview. Repeated clicks should not create duplicate windows. Startup diagnostics are written to logs/preview-lab.log. No hardware is required for these checks.

独立预览额外占用 CPU；它的处理分辨率不改变主程序的采集/分析设置。画面尺度不等于真实深度。两处画面分别采集，不承诺帧级同步。

The extra window consumes additional CPU and captures independently. Its resolution does not alter the host analysis pipeline, and image scale is not physical depth.

本版本仅源码，没有 exe/ZIP，没有推送。任何真实机械臂测试需要另外验证关节映射、碰撞风险、硬件限位和独立急停。参考预览不是传感器反馈。

Source-only: no exe/ZIP or push. Real robot-arm testing requires separate validation of kinematics, collisions, limits and independent emergency stopping. The reference preview is not feedback.
