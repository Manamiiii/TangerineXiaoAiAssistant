# 橘子小爱电脑助手

**用小爱音箱的固定口令，打开 Windows 上的网页和应用、调音量、锁屏。**

想离开键鼠时也能操作电脑？对音箱说一句：

> 小爱同学，让电脑打开 B 站。

适合已有小爱音箱和 Windows 电脑、愿意参与早期测试的用户。简单命令由本地规则执行，无需大模型或自建服务器。

**[下载与版本](#下载与版本)** · [快速开始](#快速开始) · [使用与排错](docs/QUICKSTART.md) · [反馈问题](https://github.com/Manamiiii/TangerineXiaoAiAssistant/issues/new?template=bug_report.md)

> **测试阶段：真实音箱的登录、语音读取和播报尚未完成验收，目前没有已验证机型清单。** Windows 本地程序已有测试；请先用现有设备验证，不要为此专门购买音箱。

## 可以做什么

| 对音箱说 | 电脑执行 |
|---|---|
| 让电脑打开 B 站 | 用默认浏览器打开配置好的固定网址 |
| 让电脑打开微信 | 启动事先登记的微信 EXE，需要先安装并添加应用 |
| 让电脑把音量调到三十 | 将默认播放设备音量设为 30%，保留原静音状态 |
| 让电脑锁屏 | 向 Windows 发出锁屏请求 |

支持添加网页、应用和语音别名；只匹配配置中的口令，语音不能直接运行任意 Shell 命令。程序可收起到托盘，开机自启默认关闭，由你选择开启。

<details>
<summary>查看真实界面预览（0.3.1.dev0 开发版，尚无 Release 包）</summary>

<img src="docs/images/commands-preview.jpg" alt="橘子小爱电脑助手命令页：锁屏规则演练匹配成功，未执行动作、未连接音箱" width="640">

这是开发版的**本地规则演练**，不是音箱联动演示。公开的 0.3.0 尚无“演练所选”按钮，保存按钮也位于“连接与设置”页。

</details>

## 下载与版本

| 版本 | 状态 | 获取方式 |
|---|---|---|
| **0.3.0** | 已发布的 Windows x64 便携测试版 | [打开 Releases 下载页](https://github.com/Manamiiii/TangerineXiaoAiAssistant/releases/tag/v0.3.0) |
| **0.4.0** | main 分支安装版源码 | 可构建 Windows x64 Setup 和 Portable；尚未发布下载包，[安装与构建说明](docs/INSTALLER.md) |

**旧包 0.3.0 尚未包含开发版的图像依赖安全更新和配置保存防护，建议等待修复版后再尝试。** [查看更新背景与安全边界](docs/PRIVACY.md#分发与依赖)。

如果仍要测试现有版本：在下载页展开 **Assets**，选择 **`TangerineXiaoAiAssistant-0.3.0-windows-x64.zip`**（约 40 MB）。也可[直接下载该 ZIP](https://github.com/Manamiiii/TangerineXiaoAiAssistant/releases/download/v0.3.0/TangerineXiaoAiAssistant-0.3.0-windows-x64.zip)。

- 这是解压即运行的便携包，**没有安装向导，不需要安装 Python**。
- GitHub 代码目录没有 `dist`；`Code → Download ZIP` 和 `Source code` 都是源码，不是运行包。
- 测试包未签名。下载页附有 `SHA256SUMS.txt` 可核对文件一致性，不要关闭 Windows 防护或忽略检测结果。

## 快速开始

当前 Releases 的 0.3.0 仍按下列便携版步骤使用。0.4.0 Setup 安装后可从开始菜单或桌面“安装版”快捷方式启动，升级/卸载默认保留本机数据，详见 [安装版说明](docs/INSTALLER.md)。

准备好 **Windows 10/11 x64 电脑、小爱音箱、绑定音箱的小米账号和米家 App**。电脑与音箱需要联网；电脑需已开机、登录桌面并保持助手运行。不需要管理员权限。目前只在 Windows 11 上验证过本地程序。

1. **完整解压 ZIP**，进入文件夹，双击 **`TangerineXiaoAiAssistant-Desktop.exe`**。不要直接在压缩包中运行；不带 `-Desktop` 的 EXE 是命令行工具。
2. **扫码登录**：点击“扫码登录小米”，用米家 App 扫码并在手机确认。
3. **选择并保存音箱**：在下拉框中选音箱，点击“保存设置”。0.3.0 的保存按钮在“连接与设置”页。
4. **检查连接**：点击“检查连接”，预期显示对话接口返回的记录数量。返回 0 条不一定是错误，但也不证明能收到之后的口令。
5. **开始监听**：等“正在监听，可以说指令”，再说“让电脑打开 B 站”。预期网页打开一次，等待 10 秒不重复打开；这一步仍需你的实际设备验证。

“停止 / 取消”可停止监听。**关闭窗口会收起到托盘，完全退出请用“退出助手”或托盘右键“退出”。**

第一次尝试遇到问题，按 [现象与处理方法](docs/QUICKSTART.md#根据现象排错) 排查。添加应用、升级、配置恢复和卸载也在同一份说明中。

## 使用边界与隐私

- **需要小米云端服务**：语音识别由音箱和小米服务完成，助手读取对话记录后在本地匹配规则；同一局域网不意味着离线可用。
- **固定口令，不是自由对话**：应用需先登记，不支持随口提供网址或复杂任务。WorkBuddy 真实任务尚未接入；不能唤醒关机或休眠电脑。
- **设备兼容性待验证**：没有全型号、海外地区或共享设备兼容保证；长时间运行、休眠恢复、Windows 10 和真实开机自启仍待验证。
- **口令不验证说话人**：音箱附近其他人也可能触发已配置操作，不需要的规则可以移除。
- **凭据在本机加密保存**：默认数据目录是 `%LOCALAPPDATA%\TangerineXiaoAiAssistant`。不加入遥测，不开放远程控制端口；日志不记录语音全文或 Token。[隐私与安全说明](docs/PRIVACY.md)

## 帮助与反馈

[首次使用与排错](docs/QUICKSTART.md) · [配置示例](config.example.json) · [实际验证记录](docs/VALIDATION.md)

反馈问题时请提供**程序版本、Windows 版本、音箱型号、失败步骤和界面固定提示**，并说明“检查连接”是否通过。不要发送二维码、密码、Token 或整个数据目录。[提交使用问题](https://github.com/Manamiiii/TangerineXiaoAiAssistant/issues/new?template=bug_report.md)

## 开发与致谢

项目名为 `TangerineXiaoAiAssistant`，使用 Python，窄范围复用 [VoxNode](https://github.com/Almmor/VoxNode) 的小米通信代码，保留上游许可与修改记录。

[源码运行与构建](docs/DEVELOPMENT.md) · [Windows 安装版](docs/INSTALLER.md) · [复用研究与架构](docs/RESEARCH.md) · [WorkBuddy 接入进度](docs/WORKBUDDY.md)

## License

本项目用于开源分享，除另有声明的第三方代码外，采用 **GNU GPL v3（GPL-3.0-only）**。你可以按许可证使用、修改和再分发；软件不提供担保。完整条款见 [LICENSE](LICENSE)。

VoxNode 复用代码及其他依赖保留各自的版权和许可证，详见 [第三方许可与源码说明](THIRD_PARTY_NOTICES.md)。当前源码包含此许可证；此前发布的 0.3.0 ZIP 尚未更新许可材料。

这是独立第三方个人工具，与小米或腾讯没有从属关系。
