# TangerineXiaoAiAssistant · 小爱电脑助手

通过小爱音箱控制 Windows 的轻量助手。当前是 **0.3.0 桌面便携测试版**：提供托盘、简单设置和可选开机自启，复用 VoxNode 的小米协议代码，通过固定规则打开网页、启动已登记应用、设置系统音量和请求锁屏。

**当前状态：代码与 Windows 本地测试已完成；小米二维码入口已连通；账号登录、具体音箱的对话读取和 TTS 尚待真机验收。不能据此宣称所有音箱可用。**

## 运行测试版（不需要 Python）

从 [GitHub Releases](https://github.com/Manamiiii/TangerineXiaoAiAssistant/releases) 下载 `TangerineXiaoAiAssistant-0.3.0-windows-x64.zip`，完整解压后进入 `TangerineXiaoAiAssistant` 文件夹。不要下载页面自动生成的 `Source code`，也不要在压缩包内直接运行程序。

这是 Windows x64 便携预发布测试版，不是安装程序；不需要安装 Python。到另一台电脑上使用时，在那台电脑重新扫码登录绑定目标音箱的小米账号，不要复制其他电脑的加密凭据。

在解压后的文件夹中（开发机对应 `dist/TangerineXiaoAiAssistant/`）：

1. 双击 **`TangerineXiaoAiAssistant-Desktop.exe`** 打开设置。在“连接与设置”点“扫码登录小米”，用米家 App 扫码并在手机上确认。
2. 选择音箱，点“保存设置”，再点“检查连接”。预期显示对话接口返回的记录数量。
3. 点“开始监听”，等“正在监听，可以说指令”，再说“小爱同学，让电脑打开 B 站”。预期默认浏览器打开 `https://www.bilibili.com` 一次。
4. 点“停止 / 取消”停止监听；关闭窗口会收起到托盘。要彻底退出，使用“退出助手”或托盘右键“退出”。

“语音命令”里可以添加网页、选择应用 EXE；更改后返回“连接与设置”保存。开机自启默认关闭，勾选后保存才会启用。完整说明见 [桌面版使用说明](docs/DESKTOP.md)。

旧的 `login.cmd`、`probe.cmd`、`run.cmd` 仍可使用（运行窗口按 Ctrl+C 停止）。桌面版和命令行共用单实例锁，使用这些脚本前先退出托盘程序。

也可在 PowerShell 进入上述目录后运行：

```powershell
.\TangerineXiaoAiAssistant.exe init
.\TangerineXiaoAiAssistant.exe login
.\TangerineXiaoAiAssistant.exe probe
.\TangerineXiaoAiAssistant.exe run
```

仅验证本地规则和浏览器，不需要小米登录：

```powershell
# 默认演练，无副作用
.\TangerineXiaoAiAssistant.exe test-command '小爱同学，让电脑打开 B 站'
# 实际请求默认浏览器打开配置中的网址
.\TangerineXiaoAiAssistant.exe test-command '小爱同学，让电脑打开 B 站' --execute
```

## 配置和隐私

**从旧版升级**：先退出旧程序，再完整解压新包并启动桌面版。默认读取原有登录、设备和命令，不覆盖设置。从 0.1.0 升级可在“语音命令”点“补入音量 / 锁屏”，再保存；也可以使用 `upgrade-config.cmd`。已启用自启且目录变化时，在新程序中重新保存自启设置。

**登记应用**：双击 `configure-app.cmd`，输入名称（如微信），再输入或拖入该电脑已安装应用的 `.exe` 文件。之后重启 `run.cmd`，即可说“让电脑打开微信”。同名应用再次登记会更新路径；应用更新后路径变化时可重新登记。不接受快捷方式、脚本、网络路径或附加命令行参数。

| 语音示例 | 行为 |
|---|---|
| 让电脑打开 B 站 | 打开配置中的固定网页 |
| 让电脑打开微信 | 启动事先登记的微信 EXE |
| 让电脑把音量调到 30 / 三十 / 百分之三十 | 将默认播放设备音量设为 30%，读回结果；保留原静音状态 |
| 让电脑锁屏 / 锁定电脑 | 向 Windows 请求锁屏，需要在已登录的桌面会话运行 |

音量范围为 0–100 的整数，不接受任意表达式。锁屏命令若使用 `test-command ... --execute` 会实际请求锁屏；默认不加 `--execute` 时只是演练。更多配置示例与实现边界见 [本地命令说明](docs/LOCAL_COMMANDS.md)。

默认数据目录：`%LOCALAPPDATA%\TangerineXiaoAiAssistant`。

| 文件 | 内容 |
|---|---|
| `config.json` | 触发词、设备 ID、白名单命令，不放密码或 Token |
| `xiaomi.dpapi` | 使用当前 Windows 用户 DPAPI 加密的小米会话令牌 |
| `assistant.log` | 连接状态、执行结果类型；轮转保留最多约 1.5 MB |
| `assistant.lock` | 单实例锁；进程结束后锁自动释放，文件保留正常 |

桌面版二维码只在内存中显示；CLI 扫码图片临时保存，用后删除。账号密码登录是可选后备方式：`login --password`，密码和验证码在本机隐藏输入，不保存密码。退出桌面版后运行 `logout` 可删除本机令牌缓存。加密凭据不能通过复制到另一 Windows 用户来迁移；请重新登录。

界面更改需保存并重新开始监听；外部编辑 JSON 后请重新打开桌面版。示例见 [config.example.json](config.example.json)。`phrases` 写触发词之后的完整短语，忽略大小写、空白、首尾常见标点；不做任意子串匹配。可以为固定网址添加多条别名，例如 `打开B站`、`打开哔哩哔哩`。语音不能直接提供网址、可执行文件路径或 Shell 命令。

可使用 `--data-dir PATH` 和 `--config PATH`，参数放在子命令之前。正常使用保持默认即可。

## 已实现与边界

- 小米扫码登录、可选密码/OTP 登录、设备列表和编号选择（协议已实现，账号/设备待实测）。
- 复用 MiNA `nlp_result_get` 读取对话；TTS 结果播报可通过 `tts_reply` 关闭。
- 固定触发词、网页和应用白名单、0–100 音量、锁屏；无需大模型。多条规则同时命中时拒绝执行。
- 初始快照不执行；重复记录去重；超过默认 30 秒的语音不执行；异常未来时间戳不执行。
- 网络异常按 6、12、24、48、60 秒退避重试；401 最多刷新一次业务令牌；登录失效会给出重新登录指引。
- 播报失败不重做电脑动作；只反馈“请求打开”，不把浏览器启动请求等同于网页加载成功。
- 不开 HTTP 服务、不监听局域网端口、不包含 GUI 自动操作。
- Windows 托盘、扫码/设备选择窗口、命令管理、脱敏日志；可选当前用户开机自启。没有安装器或自动更新。

初次启动同步时发出的语音可能作为初始快照被忽略，请等提示后再说。断线超过时效窗口会丢弃旧指令，这是防止延迟误操作的取舍。尚未测试多种音箱固件、Windows 10 或长时间休眠恢复；本版本不保证恰好一次投递或零丢失。

## 开发

固定目录为 `D:\IdeaProjects\TangerineXiaoAiAssistant`，直接在 `main` 开发。

```powershell
cd D:\IdeaProjects\TangerineXiaoAiAssistant
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m xiaoai_pc init
.\.venv\Scripts\python.exe -m xiaoai_pc test-command '让电脑打开B站'
.\.venv\Scripts\python.exe -m xiaoai_pc desktop
.\.venv\Scripts\python.exe scripts/build.py
.\.venv\Scripts\python.exe scripts/smoke_exe.py
```

开发需要 Python 3.11+，当前验证使用 Windows / Python 3.12 x64。运行依赖包括 `requests`、`pycaw`、`comtypes`、托盘 `pystray`、图像 `Pillow` 及传递依赖；窗口使用 Python 自带 Tk。不实现系统监控。PyInstaller 仅用于构建。两个 requirements lock 文件固定本次验证版本。构建会下载并核验对应版本的 pystray 源码；完整许可和重建方式见 [桌面说明](docs/DESKTOP.md#依赖源码和重建)。

## 研究与后续

- [源码研究、复用范围、架构与阶段计划](docs/RESEARCH.md)
- [验证记录与真机验收步骤](docs/VALIDATION.md)
- [WorkBuddy 接口研究](docs/WORKBUDDY.md)
- [第三方代码与许可](THIRD_PARTY_NOTICES.md)

0.3.0 已补齐托盘、设置界面与可选自启。WorkBuddy 暂为独立接口与显式 Mock，未接入语音主循环，未调用真实任务接口；真实音箱验收、WorkBuddy 授权集成和安装器仍待完成。

这是独立第三方工具，与小米或腾讯没有从属关系。
