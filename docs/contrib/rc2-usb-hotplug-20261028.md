# RC2：ECHO-B 热插拔、USB 音频与睡眠实测（2026-10-28）

贡献与实机验证：[@Rivarise](https://github.com/Rivarise)。排查、实现和文档由 AI 工具辅助，物理拔插和试听由贡献者完成。

## 版本与范围

实测系统为 `v1.0.0-rc.2` 的 Android 16 构建 `1792913333`，设备为 MateBook E Go / `gaokun3` / SC8280XP。
原内核 EFI 载荷 SHA256 以 `7636022f` 开头，来自本仓的 Linux 7.2.9 + buildbot 19 个提交 + RC2 内核补丁配方。
本次内核修复在相同配方上构建，未替换原 DTB、ramdisk 或启动参数。

本文记录三件彼此独立的事：耳机未枚举、枚举后播放噼啪、息屏却不挂起。补丁 `0113` 处理第一件。
USB 音频写入路径处理第二件；睡眠属性检查处理第三件。不要把“声卡出现”当成“音频已干净”，也不要把“屏幕灭了”当成“整机已挂起”。

当前 `dev` 已迁移到 Android 17（整理本文时基于 `fcf069b`），其内核补丁配方与本次 RC2 的内核配方一致。
**没有刷入或验收整套 A17 ROM**。下文的音频源码变更仅适用于 A16，不能直接应用到 A17。

## 症状、端口与复现

电脑 ADB 使用靠近电源键的 port0；待测设备使用远离电源键的 port1。
port1 路径为 `a8f8800.usb / a800000.usb / xhci-hcd.0.auto`，combo PHY 为 `8903000.phy`。
不要对承载 ADB 的 `a600000.usb` 做手动解绑或复位。

外设：

| 外设 | 身份 | 实测用途 |
|---|---|---|
| MOONDROP ECHO-B | VID `35d8` / PID `149b`，USB HS 480 Mb/s | 枚举、ALSA、正反插、声音、暂停恢复 |
| WD_BLACK P40 | VID `1058` / PID `266f`，UAS | 两种插头方向的 USB 3 连接和有界读取 |

原始故障的复现步骤：

1. port1 留空开机，待安卓启动后插入 ECHO-B。
2. 如偶尔识别，拔出，等待约 5 秒，翻转**插在机身上的那一端**后重新插入。
3. 观察新 USB 枚举、HID 注册和 `/proc/asound/cards`；故障时声卡真的消失。
4. 故障后换回曾成功的方向也可能无效，需重启才能恢复。

声音是否正常需要另外试听。用同一段内容播放，暂停数秒后恢复；仅有 HID 或声卡记录不能证明没有噼啪。

## 对照与修复

单独在 Type-C 回调期间保护 PIPE 的 V1 内核，已确认保护分支运行，但仍会空口开机首次插入失败；带设备开机后也会在再次翻转时失效。
同一 V1 空口开机下，用有时限的临时模块保住公共输入，记录到四次新 ECHO-B HID 注册，贡献者确认两种方向、再次拔插和暂停恢复正常。
临时模块仅用于对照，最终 V2 未加载它。

这一对照支持“重新配置期间保留公共输入”的修复方向；**未独立确定是哪一路时钟或电源，也未证明具体硅片勘误**。

`0113` 的资源保留条件是 `huawei,gaokun3`、设备名 `8903000.phy` 且已经初始化。
在该 PHY 的强制重新配置期间，保留原来持有的 regulator、公共时钟和 PIPE，继续执行复位与方向／模式编程；普通消费者的初始化／退出仍按原生命周期取得和释放资源。
不会再常驻增加引用，也没有把端口降为 USB 2 或删除 DP 模式。

同时修正共用代码中的失败路径：

- USB power-on 超时时不多释放由 common init/exit 拥有的 PIPE。
- switch/mux 回调返回实际失败，恢复缓存的请求值，并记录“硬件重配未完成”状态，使同值请求能重试。
- dirty 状态下 DP 正在使用时返回 `-EBUSY`，避免新增的失败恢复流程碰到显示链路。

资源保留有本机条件；回调失败处理和 PIPE 所有权修正在共用驱动中。其他板卡没有实物验证。

## 实测结果与证据边界

| 测试 | 证据 | 结论 |
|---|---|---|
| V2 独立启动、port1 空口 | 实际运行内核 notes/build ID；未加载临时模块 | 确认测到的是 V2 |
| ECHO-B 首次插入、翻转 | 新 HID 分别在开机后约 86.21、102.18 秒注册；声卡出现，用户试听正常 | 两种方向通过 |
| 分开确认拔出和插入 | 323.44 秒断开；351.87 秒重新注册 HID，试听正常 | 一轮明确重新枚举通过 |
| P40 两种方向 | 两次 `SuperSpeed Plus Gen 2x1`、`speed=10000`、UAS；各读 64 MiB 到 `/dev/null` 成功 | USB 3 保留；不等于持续速度基准 |
| 硬盘换回耳机 | P40 安全卸载后拔出；ECHO-B 新 HID 注册，暂停恢复正常 | 外设类型切换通过 |
| V2 休眠唤醒后 | 新 ECHO-B HID 注册，正反插及暂停恢复试听正常 | 本轮唤醒后音频通过 |
| 正常 gk3boot 空口启动 | 最终 dev2 HID 128.28 秒、翻转 dev3 HID 137.50 秒，当前 ALSA ECHO-B 在线 | 正式入口下再次通过 |

曾有一次“反复拔插三次均正常”的口头反馈，但日志没有新枚举，**没有计入重复测试证据**；随后改用分开确认拔出与插入来验证。
被拔出打断、未完成 HID 注册的尝试也没有计入成功次数。

最终内核 GNU build ID 为 `6149f132bb264ef89754352b198505585c268eda`，kernel notes SHA256 为
`387f608ad101dbe67a4d66e86d3dd86c3d1ac175f82f803acc2d8a354261678f`。
同一个 V2 载荷通过独立测试入口及正常 gk3boot 启动；root 可用，SELinux Enforcing，最终没有诊断模块，跟踪已关闭。
Type-C 重配后四路原生输入时钟引用保持为 1，没有额外常驻 hold。

本次没有显示器可测 **DP 输出**；没有开展长期待机功耗、其他 DAC、大量外设兼容性或其他板卡回归。

## 可重复的软件检查

`scripts/tests/` 的两个脚本从指定内核源码中提取实际函数体，编译后用外围 API doubles 检查资源引用及回调状态；它们不接触设备或 MMIO。
需要 Python 3 与支持 GNU C 的主机 GCC。每次运行使用自己的临时目录。

```sh
python3 scripts/tests/test_qmp_combo_common_inputs.py /path/to/linux/drivers/phy/qualcomm/phy-qcom-qmp-combo.c
python3 scripts/tests/test_qmp_combo_reconfigure_callbacks.py /path/to/linux/drivers/phy/qualcomm/phy-qcom-qmp-combo.c
```

分别覆盖 20 项 common/USB 生命周期及失败场景、35 项 switch/mux 模式、错误、同值重试及 DP 占用场景。
配方重放应使用 `scripts/kernel-apply-patches.sh ... --verify`；只在已经叠满补丁的树上跑 `--check` 有脚本已注明的盲区。
实际 ARM64 W=1 对象编译和完整 RC2 测试内核构建均通过。主机 doubles 不能替代其他硬件回归。

提交前另从保留的原始 7.2.9 tar 重建所有补丁涉及的文件，加上 19 个 buildbot 补丁作为基线，
再用本仓 `--verify` 重放 79 个项目内核补丁：74 个涉及文件全部一致，0 fuzz、0 应用失败。
比对副本中仅把实测 PHY 源码的 Windows CRLF 统一为 LF，实际构建树未改动；不相关内核文件未复制进此验证夹具。
撤掉 `0113` 的负对照会在实际资源引用断言失败，补丁后的 55 项通过。

## RC2 播放噼啪：独立的 A16 音频问题

ECHO-B 枚举成功后，原 RC2 仍有轻微噼啪。部分较大音频试验让噼啪加重，已撤回；回到原版 HAL、调整到 48 kHz/16 bit 仍有轻微噼啪。
最终复用本仓 A16 补丁 `0069` 已存在的直接 ALSA 播放路径，仅让 `StreamOutUsb` 选择它，试听、暂停恢复和重新插入均干净。
实机部署的是与该一行源码变更等价的、校验原版指纹后应用的最小 HAL 修补模块，未在本次重编整套 A16 HAL。

A16 的源码语义为：在 `hardware/interfaces/audio/aidl/default/include/core-impl/StreamUsb.h` 的 `StreamOutUsb` 中加入：

```cpp
bool writesPlaybackDirectly() const override { return true; }
```

它依赖 A16 版 `0069` 对 `StreamAlsa` 的扩展。当前 A17 已把 `StreamAlsa` 与 `StreamAlsaMonoPipe` 拆开，USB 原生使用直写的 `StreamAlsa`；本仓 `0069` 的 A17 说明已经记录这点。
因此本贡献把 RC2 修复作为版本限定的实测记录，**不向当前 A17 代码重复添加该开关，也不宣称已验收 A17 的 ECHO-B 播放**。
耳机麦克风录音和所有格式／采样率组合未测试。

## 睡眠与启动通知的排查记录

夜间约 9 小时 41 分钟息屏掉电 68–69 个百分点时，两个原有 `allow_suspend` 属性都是 0，
`gaokun3_nosuspend`、`gaokun3_usbrole` 从开机一直持有，SystemSuspend 的尝试数为 0。
恢复项目已有的睡眠设置后，第一次测试仍接着电源线，系统一直认为供电在线、USB 保护锁未释放，**这轮不算休眠通过**。

两个 USB-C 口完全拔空后，约 10 分 5 秒新增拔线时间内，realtime 与 uptime 的差值增加约 9 分 8 秒；
休眠成功数 0→8，另有 5 次在冻结进程阶段中止。boot_id 未变，电源键唤醒正常，之后 ECHO-B 试听也正常。
CX／DDR 深度省电计数仍为 0，**这不代表长期掉电已经修好**。开关为何被关闭未确定，也不把夜间耗电直接归因于本次 PHY 修复。

睡眠属性及 USB 保护锁的原有设计见 [`init.gaokun3.rc`](../../device/huawei/gaokun3/init.gaokun3.rc) 和 [`usbrole.rc`](../../device/huawei/gaokun3/etc/usbrole.rc)。
测待机需要拔掉电脑数据线；连接电脑时系统会保留 USB 保护锁。

独立直连测试内核启动时，“绕过启动入口”通知符合该测试方式的行为。
相同载荷通过正常 `gk3boot-android-a.conf` 启动后，`via=gk3boot`、`bypassed=0`、`notify` 为空。
这是恢复正常启动路径的验证，没有为隐藏通知修改 Parts 或 boot_control。
本机的启动镜像备份和一次性安装事务不纳入此上游补丁；正常入口与回滚设计见 [`boot-entry-design.md`](../boot-entry-design.md)。

## 后续验证

- 真实 DP 显示器、其他 USB DAC 和 USB 3 外设兼容性。
- 更长的反复热插拔及睡眠／唤醒压力测试。
- 完全拔线的长期待机耗电与 CX／DDR 省电状态。
- A17 ROM 下完整音频与 USB 回归；本次报告不能替代它。
