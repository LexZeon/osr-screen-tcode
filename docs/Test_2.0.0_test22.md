# 2.0.0-test.22：固定主体参考、独立客体与假定客体

双击根目录 [Start.cmd](../Start.cmd)，确认标题 **2.0.0-test.22**。操作说明见 [Start.md](../Start.md)。本轮只更新测试源码。

## 针对的反馈

test.21 的橙点／三轴反复出现和消失，而且参考点没有持续标注同一位置。用户要求先标注主体，有客体则标注客体，没有客体则根据主体往复假定客体。本轮调整 v2 的跟踪、恢复及融合交接底层，保留已有界面、采集调度与最终输出链路。

主体跟踪适用于 v2 及其全／半行程模式；完整的客体／假定客体输出流程使用 **v2 L0 参考 → 融合参考（默认）**。产品的保存／默认逻辑无变化，无新增设置键；本机测试中发生的个人配置覆盖另见下文，不能视为旧设置已保留。直接 Pose 和混合 v1 未改。

## 本机验证中的配置事故

本轮修改实时测试的收尾代码时，误将关闭窗口放进延后执行的清理回调。回调执行时，屏蔽设置写入的模拟已经结束，因此测试用偏好意外写进了本机测试版个人配置。这是开发检查造成的错误，不是用户操作，也不是正常更新所需的配置迁移。

已修正为在写入屏蔽仍有效时关闭窗口，并新增 `tests/run_tests.py`：在加载界面与运行时模块之前，把设置、预览与运行时路径指向独立临时目录，测试结束核对原个人配置的指纹。后续完整检查使用 `python tests/run_tests.py -v`。

用户确认没有修改前的窗口或配置备份；查找也未取得可确认的原配置。已在系统临时目录保留事故文件的副本，再将本机测试配置设为项目默认值，并使用 **混合分析 v2、45 FPS、Log only**。这不是恢复原设置；若需原来的连接信息、个人行程或其他偏好，需要重新设置。该事故副本不是原配置备份。用户随后说明，每次测试运行前都会点击“恢复默认”；后续复测以恢复默认后的效果为基准，本轮功能不依赖旧个人参数。正式仓库、正式 Python 环境和旧发布包没有修改，配置及事故副本均未加入源码。

## 主体 A

`subject_tracking.py` 保存主体上的固定参考点 **A**。三轴以 A 为原点，不再每帧取变化的特征包围框中心。主体变换负责搬运参考点，附近同一图像特征负责校正漂移；初始外观因缩放而变化时，近期同位置的纹理、对比度和多数分布式点只能补充确认暂停；恢复运动仍需固定锚点验证，防止变形误配被累计为运动。更换参考或切镜头重新建立身份。黄框仍表示本帧实际采样区域，不把采样框中心画成另一个主体原点。

短暂失败时，缓存最近可靠画面的主体／背景分布式特征，最多跨 **0.25 秒**重新匹配。两组各自通过真实图像、稳健变换、空间分布、误差与背景外推验证，才恢复观测。首次与主路径不一致的运动暂保持，后续恢复优先于普通相邻帧跟踪，补齐可靠旧画面到当前画面的整个位移，避免漏算中间失效帧。不会把位置外推当成测量，也不会把较长位移重复累计。

旧区域内新露出的背景，不能再直接证明“主体静止”。主体自己的像素匹配成功且相对背景没有运动，才可确认这条恢复路径上的暂停。普通跟踪与恢复一致过滤低于拟合分辨率的尺度噪声，减少纯上下运动被误认为带有缩放。真实尺度运动仍作为画面代理量，不是真实深度。

恢复保留实际点对应供旋转分析使用。开始阶段仍先完成原有区域／背景确认；切镜头、长间隔和过期缓存会清除旧身份，明确无证据时仍保持或重新建立参考。

## 客体 T? 与假定客体 V?

- **橙色 T?：独立客体候选。** 继续沿主体运动朝向选择另一个物体的可达边界，并使用该客体自己的点、外观和变换。新增独立图像缓存；主运动／运镜对应暂缺时，客体自身仍能从最近可靠画面匹配，就保留同一身份及真实位置。无法验证则标为保持，不更新到达比例；未知且无法配准的旧坐标仍隐藏。恢复中的尺度与距离范围在同一图像基准下更新，避免运镜缩放被乘算两次。
- **浅黄色 V?：假定客体。** 没有可靠客体时，从已经确认的主体往复中心、主方向、幅度和远近方向推定一个端点。它表示当前主体往复的假定终点，不是检测到的物体，不人为拉到更远，也不显示实测到达百分比。主体相位继续驱动 L0；不会对中心 C 取绝对距离而产生倍频。方向不明时保留稳定方向并提示待确认。
- **暂缺测的 V?：** 可显示保持的假定参考，但明确标注暂缺测；这个标记不能恢复观测置信度、证明接触或自行启动规律。主体尚未形成有效往复时，不凭空创建一个输出目标。

只有主体原点 A 与独立客体 T? 都有可靠位置时，才计算到达比例。远离目标 L0 大，接近 L0 小，原点与目标重合对应估计 100% 到达／倍率前底部。仍按三轴原点判断，不改为物体前缘或屏幕边缘。

T? 仍是几何候选，并非语义接触检测。对于两个实际接触物体都不在画面的新镜头，可见主体的往复可建立 V? 并输出，不能推断不可见接触的真实位置。

## 修复反复交接锁住 L0

已复现目标逐帧交替有效／失效时，旧融合逻辑每帧重启当前位置偏移，301 个样本的输出行程为 **0**。现在目标丢失后先跟随主体，重新接入要求同一目标持续有效至少 **0.3 秒**，且距失效至少 **0.4 秒**。确认期间可以显示候选，但不会反复接管脚本。重新接入从当前输出连续过渡。

主体也缺测时，只沿用此前已经确认的稳定往复，仍最多 **2 秒**，最后 **0.5 秒**减慢停住。明确暂停、切镜头、重设参考清除旧规律；预测不能冒充真实观测。

普通 v2、全／半行程及可选 RTM 2D 旋转辅助共用此逻辑。1/4、半、全行程仍保留离散峰值与余弦形状；五档、总行程、轴倍率、联动、反向、限位、末端减速、导出和模拟器继续使用原最终指令。预览中的分析 L0 不等于乘算后的实际设备行程。

## 改动文件

- `src/osr_screen_tcode/subject_tracking.py`：主体锚点、图像验证、有限时间的实测恢复。
- `camera_motion.py`：主体参考生命周期、完整位移恢复、暂停证据与尺度分辨率。
- `reach_target.py`：独立客体图像缓存、身份接续及一致的距离基准。
- `point_l0.py`、`fused_l0.py`、`visual_pipeline.py`：稳定原点、假定客体、目标交接及共用输出。
- `motion_reference.py`：A／T?／V? 标注和中英文状态；短暂保持与实测明确区分。
- `tests/test_subject_tracking.py`、`test_reach_target.py`、`test_camera_motion.py`、`test_fused_l0.py`、`test_target_reference.py`、`test_realtime_integration.py`、`test_output_failures.py`、`ui_smoke.py`：位置漂移、间歇模糊、脚本锁定、身份恢复、实时启停及显示回归；`tests/run_tests.py` 隔离测试配置与生成文件。
- 版本元数据、README、Start.md、AI 接手说明和两份日志同步。

## 验证记录

- 最终主程序完整 **285 项通过，520.900 秒**。使用 `python tests/run_tests.py -v`，正常 OpenCV 线程配置，独立临时设置目录；结束后真实个人配置指纹一致。这只证明修正后的这轮运行未再改动配置，不能抵消或掩盖上面的配置事故。
- 新增主体／目标回归覆盖：逐帧交替有效／失效不锁住脚本；151 帧主体参考位置稳定；每三帧一次明显模糊后仍可恢复并生成超过 70% 的分析 L0 行程；主运动失败但客体像素有效时身份保留；目标恢复不重复计算运镜缩放。均为受控合成画面，不是用户原片的保证。
- 开发中针对主体、往复中心、重复帧的 **6 项回归通过**（51.8 秒）。重复帧不增加位移，初始化确认不会被重复显示绕过；最终生产代码又由下述 17 项复验，完整结果以最终隔离运行记录为准。
- 独立预览 **28 项通过**，模拟器最终指令 JavaScript 检查通过。
- 主程序 `Start.cmd --smoke --language zh/en` 和独立预览 `Start.cmd --smoke` 通过；新主程序标题为 **2.0.0-test.22**。
- 已检查中文主体＋独立客体、英文间歇模糊＋假定客体保持、中文全／半行程＋RTM 旋转辅助三种窗口图像，并在最后恢复调整后再次检查中文主体＋假定客体。标记与说明可见，假定／保持不冒充实际到达。图像仅在系统临时目录。
- 实际读屏 Log only **235 次统计更新**，正常停止，工作线程退出，无采集错误或界面回调错误；未连接硬件或保存个人设置。检查工具请求 120 FPS，末次统计约 95 FPS 采集／73 FPS 分析、输入帧龄 6.8 毫秒，仅代表此次桌面内容，不改变默认设置。该启停检查在最后恢复确认细节之前运行。最终代码单独复测 **253 次统计更新**，正常停止，线程退出，无采集或界面回调错误（10.43 秒含初始化与收尾）；正常程序线程配置保持不变。
- **102 个 Python 文件**语法检查通过；本轮改动文件的空白与个人路径检查通过。全工作区检查另报告了原有 `CONTRIBUTING.md` 与 `OPEN_SOURCE_NOTICE.md` 文件末尾空行，未为本任务改写这些已有内容。两份日志的 test.22 条目一致，原有 test.5 历史措辞差异保留。未跟踪文件检查没有模型、运行库、视频、运行日志、缓存、压缩包或个人配置，窗口截图仍在临时目录。

开发中的失败也有记录：第一轮完整 284 项检查有 6 项失败，包含旧标注预期、中心／重复帧恢复、紧凑英文接触说明，以及旧启停计时在界面初始化阶段就耗尽。修正显示含义、恢复确认状态和检查计时后重新验证；实时检查仍验证原有输出数量、非阻塞停止和线程退出。试验“首次失败立即恢复”反而缩短了模糊场景行程，已采用等待下一帧再次确认的路径，相关 6 项复验通过。第二轮完整 285 项有 2 项失败：并行负载下超时的输出失败界面限时检查，以及主体变形行程缩短。前者从实际启动后计时，后者收紧为“近期外观只能补充确认暂停”；随后相关 **17 项通过**（107.1 秒，这一针对性运行将 OpenCV 固定为一个线程，未改变程序默认线程配置）。并行负载下额外读屏检查产生 219 次更新，但未在停止后一秒退出，记为收尾超时而非通过。较早失败结果没有记为通过。

第三轮完整检查因发现上述配置写入事故主动停止，未计为完成或通过。修正测试清理后，最终完整检查改用独立临时目录，并保留程序正常的 OpenCV 线程配置；不与其他界面／读屏检查并行。

## 实片复测重点与限制

按照用户的复测习惯，先点“恢复默认”，使用 Log only；默认分析为混合 v2、L0 参考为融合参考。打开分析预览，观察 A 是否保持在主体同一部位、T? 是否属于另一个物体；没有客体时应显示 V?，而不是不断等待橙点出现。暂缺测时查看保持／预测状态及脚本是否连续，再试全／半行程。

固定局部外观与多点几何仍可能因大幅变形、转身、强模糊、重复纹理、长期遮挡或主体／背景运动不可区分而失败。短时缓存不是长期身份识别，也没有增加语义目标检测模型。假定客体在纯尺度或未知远近方向下尤其不能代表真实接触位置。两秒延续仅适用于此前已确认的节奏。

高并行负载下曾出现停止后一秒线程仍未退出；单独复测通过，退出延迟仍需关注，停止后的工作线程指令仍受原 stop_event 检查拦截。真实用户片段和设备仍需复测，不能保证所有闪烁已经消失；无机械臂关节映射、逆运动学、碰撞检测或反馈验证。没有安装依赖、加入模型／素材／缓存／日志／个人设置，没有修改正式仓库或旧发布包，没有打包、提交或推送。

## English

Test.22 first maintains a persistent subject anchor **A**, then independently tracks object candidate **T?**. If no reliable object exists, **V?** explicitly marks an assumed endpoint inferred from confirmed subject reciprocation. It never claims observed contact or an actual reach percentage.

Actual subject and background pixels can be re-matched from the last verified frame, up to 0.25 s back, recovering the complete missing displacement rather than only the final adjacent-frame step. Exposed background no longer proves a paused subject. Scale below fit resolution is filtered consistently. Independent object pixels can preserve identity across missing source pairs; only verified source and target positions produce reach.

After a target dropout, fusion follows subject motion until the same target stays ready for 0.3 s and at least 0.4 s has passed. This prevents repeated transition offsets from pinning L0. Known-rhythm continuation remains capped at 2 s with braking in the last 0.5 s. Cuts and pauses clear old rhythm. Cycle/optional RTM rotation variants share the changes; final output processing and the product's save/default logic remain unchanged.

During development, an incorrectly timed test cleanup accidentally overwrote this machine's test preferences. No verified original backup was found, and the user confirmed there was no earlier open window or backup. The accidental file was copied to a temporary location, then test preferences were reset to factory defaults with Hybrid v2, 45 FPS and Log only. This is not recovery of the original settings; former personal preferences would need re-entry if wanted. The user subsequently confirmed they click Restore Defaults before every trial, so this is the acceptance baseline. Cleanup now runs inside the save mock, and `python tests/run_tests.py -v` isolates test storage before GUI imports and checks the real configuration fingerprint afterward.

Strong deformation, blur, occlusion, ambiguous texture and semantic contact remain limitations. This is a source-only test update without hardware validation. Use [Start.cmd](../Start.cmd) and see [Start.md](../Start.md).

Final isolated main suite: **285 tests passed in 520.900 s**, with the normal OpenCV thread configuration and an unchanged personal-configuration fingerprint. Standalone preview: **28 passed**. Simulator command checks and bilingual launch checks passed. The final separate Log-only screen check delivered 253 statistics updates and stopped cleanly. These checks do not establish real-video or hardware compatibility; earlier failures and the local settings incident remain documented above.
