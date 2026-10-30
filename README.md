# TangerineXiaoAiAssistant · 小爱电脑助手

通过小爱音箱控制 Windows 的轻量助手。当前是 **0.1.0 控制台 MVP**：复用 VoxNode 的小米协议代码，实现“小爱音箱 → 对话轮询 → 固定规则 → 默认浏览器打开 B 站”。

**当前状态：代码与 Windows 本地测试已完成；小米二维码入口已连通；账号登录、具体音箱的对话读取和 TTS 尚待真机验收。不能据此宣称所有音箱可用。**

## 运行测试版（不需要 Python）

在本机 `dist/TangerineXiaoAiAssistant/` 中：

1. 双击 `login.cmd`，用米家 App 扫描弹出的二维码并在手机上确认。多个音箱时按编号选择。
2. 双击 `probe.cmd`，预期显示设备可访问、对话接口返回记录数量。
3. 双击 `run.cmd`，等出现“音箱记录已同步”，再说“小爱同学，让电脑打开 B 站”。预期默认浏览器打开 `https://www.bilibili.com`。
4. 在运行窗口按 `Ctrl+C` 停止。当前还没有托盘、开机自启或安装程序。

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

默认数据目录：`%LOCALAPPDATA%\TangerineXiaoAiAssistant`。

| 文件 | 内容 |
|---|---|
| `config.json` | 触发词、设备 ID、白名单命令，不放密码或 Token |
| `xiaomi.dpapi` | 使用当前 Windows 用户 DPAPI 加密的小米会话令牌 |
| `assistant.log` | 连接状态、执行结果类型；轮转保留最多约 1.5 MB |
| `assistant.lock` | 单实例锁；进程结束后锁自动释放，文件保留正常 |

扫码图片只临时保存，用后删除。账号密码登录是可选后备方式：`login --password`，密码和验证码在本机隐藏输入，不保存密码。`logout` 删除本机令牌缓存。加密凭据不能通过复制到另一 Windows 用户来迁移；请重新登录。

编辑配置后重启程序。示例见 [config.example.json](config.example.json)。`phrases` 写触发词之后的完整短语，忽略大小写、空白、首尾常见标点；不做任意子串匹配。可以为固定网址添加多条别名，例如 `打开B站`、`打开哔哩哔哩`。语音不能直接提供网址、可执行文件路径或 Shell 命令。

可使用 `--data-dir PATH` 和 `--config PATH`，参数放在子命令之前。正常使用保持默认即可。

## 已实现与边界

- 小米扫码登录、可选密码/OTP 登录、设备列表和编号选择（协议已实现，账号/设备待实测）。
- 复用 MiNA `nlp_result_get` 读取对话；TTS 结果播报可通过 `tts_reply` 关闭。
- 固定触发词、白名单网页命令及别名；无需大模型。
- 初始快照不执行；重复记录去重；超过默认 30 秒的语音不执行；异常未来时间戳不执行。
- 网络异常按 6、12、24、48、60 秒退避重试；401 最多刷新一次业务令牌；登录失效会给出重新登录指引。
- 播报失败不重做电脑动作；只反馈“请求打开”，不把浏览器启动请求等同于网页加载成功。
- 不开 HTTP 服务、不监听局域网端口、不包含 GUI 自动操作。

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
.\.venv\Scripts\python.exe scripts/build.py
.\.venv\Scripts\python.exe scripts/smoke_exe.py
```

开发需要 Python 3.11+，当前验证使用 Windows / Python 3.12 x64。运行依赖只有 `requests` 及其传递依赖；PyInstaller 仅用于构建。`requirements-runtime.lock` / `requirements-build.lock` 固定本次验证的版本。

## 研究与后续

- [源码研究、复用范围、架构与阶段计划](docs/RESEARCH.md)
- [验证记录与真机验收步骤](docs/VALIDATION.md)
- [WorkBuddy 接口研究](docs/WORKBUDDY.md)
- [第三方代码与许可](THIRD_PARTY_NOTICES.md)

第二阶段范围仅为网页控制。应用启动、精确系统音量、锁屏是后续本地命令增量；WorkBuddy 暂为独立接口与显式 Mock，未接入语音主循环，未调用真实任务接口；托盘、自启和安装器待基础链路通过真机验收后再做。

这是独立第三方工具，与小米或腾讯没有从属关系。
