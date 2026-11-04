# 源码运行与构建

普通用户请从 [README 的下载入口](../README.md#下载与版本) 获取便携包，无需安装开发环境。

## 版本与环境

本文对应 main 分支的 `0.4.1` 安装版源码。Releases 目前仍提供 0.3.0 便携测试包；0.4.1 尚无 Release 包。以下步骤以**含有本文档的工作树**为准，旧版本请按对应版本 README 操作。

开发需要 Windows、Python 3.11+（包含 Tcl/Tk）；目前使用 Python 3.12 x64 构建和验证。依赖由两个 requirements lock 文件固定。构建需要联网安装依赖并下载、核验 pystray 对应源码，不需要管理员权限。

在项目根目录的 PowerShell 中运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/check_public_files.py
```

## 本地运行

```powershell
# 使用隔离的数据目录，避免修改已有用户配置
.\.venv\Scripts\python.exe -m xiaoai_pc --data-dir build/dev-data desktop

# 先退出桌面版，再使用同一数据目录运行 CLI
.\.venv\Scripts\python.exe -m xiaoai_pc --data-dir build/dev-data init
.\.venv\Scripts\python.exe -m xiaoai_pc --data-dir build/dev-data test-command '让电脑打开B站'
```

`test-command` 默认只演练，不联网、不执行电脑动作。加 `--execute` 会真实执行，包括锁屏；不要把它用于无副作用测试。桌面版和 CLI 共用单实例锁。

测试不会代替真实账号和设备验收，也不应为开发机启用自启或实际锁屏。音量测试使用替身；可选成品音量检查只读。已有验证范围见 [VALIDATION.md](VALIDATION.md)。

## 构建便携包

需要 Setup 时使用 `python scripts/build.py --installer`，安装器的独立身份、数据保留和生命周期测试见 [Windows 安装版](INSTALLER.md)。默认不加该参数时继续只构建便携包。

```powershell
.\.venv\Scripts\python.exe scripts/build.py
.\.venv\Scripts\python.exe scripts/smoke_exe.py
```

默认输出为 `dist/<版本号>/`，目录内包含便携文件夹、ZIP 和 SHA256SUMS.txt。该目录是本地构建产物，不在 GitHub 代码目录中；构建脚本不会上传、发布或修改仓库设置。

已有输出不会被覆盖。再次构建请使用新的目录，并让验证脚本检查同一份产物：

```powershell
.\.venv\Scripts\python.exe scripts/build.py --output-dir build/package-check-2
.\.venv\Scripts\python.exe scripts/smoke_exe.py --package-dir build/package-check-2/TangerineXiaoAiAssistant
# 有可用播放设备时，可追加 --check-audio 做只读检查
```

每次构建从干净临时目录收集文件。项目源码及公开文档由 [source-files.txt](../scripts/source-files.txt) 明确列出；新增模块或文档时同步更新清单，不要把个人配置、日志、二维码或凭据加入清单。

pystray 完整对应源码及应用重建材料随便携包提供。修改库后重建的方法见 [桌面版说明](DESKTOP.md#依赖源码和重建)；项目与第三方的授权状态见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

## 准备公开更新

本地源码、GitHub main 和 Releases 是不同的交付物，不能用更新 README 代替修复二进制包。发布前核对版本号、下载链接、截图标签及已知限制；上传后重新下载核对 SHA256。是否推送或发布由维护者另行决定。

暂存后运行 `python scripts/check_public_files.py --staged`，检查实际要提交的内容。不要把本机目录写入 README 或 AGENTS.md；机器专属笔记保存在 `.git/info/local-notes.md`。分发清单是允许包含的文件列表，隐私检查仍会拒绝清单内的私有文件与路径。检查不覆盖 Git 历史和旧 Release，也不能替代图片与自由文本的人工审查。
