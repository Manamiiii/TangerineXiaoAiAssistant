# 源码运行与构建

普通用户请从 [README 的下载入口](../README.md#下载与版本) 获取便携包，无需安装开发环境。

## 版本与环境

本文对应 main 分支的 `0.4.2` 安装版源码。Releases 目前仍提供 0.3.0 便携测试包；0.4.2 尚无 Release 包。以下步骤以**含有本文档的工作树**为准，旧版本请按对应版本 README 操作。

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

## 桌面免安装验收入口交付

日常 `.lnk` 直接指向已验证目录中的 `TangerineXiaoAiAssistant-Desktop.exe`。没有参数时，包内 `scripts/desktop_entry.py` 调用 `desktop_main()`，转入 `desktop` 命令和 Tk 窗口；窗口标题显示内嵌版本。它不是源码入口，不会随 Git 更新，也不会在双击时构建。默认使用当前 Windows 用户的数据，无本地端口或浏览器缓存。

1. 读取本项目入口的目标、参数、工作目录和图标，核对整条启动链。检查本项目 EXE 及源码 Python 进程；存在任务、未保存状态或归属不明时不关闭、不重启、不覆盖原文件。
2. 运行行为改变时，在新输出目录构建并执行包体、对应源码、隐私和隔离成品检查。仅文档或维护工具改动可复用已验证产物，记录构建提交，并核对运行源码、依赖和安装配置没有变化。历史产物含旧文档时不能声称整个包对应最新提交。
3. 用以下只读工具比对实际快捷方式与待交付包。将 `入口路径` 替换为本机已核对的 `.lnk`；它只加载快捷方式和包体，不运行程序或读取配置、凭据。输出包含本机路径，仅保存在 `build/` 或 `.git/info/`。返回 2 表示入口尚未指向目标包；返回 0 也只证明静态入口一致，不证明已有进程已更新。

   ```powershell
   .\.venv\Scripts\python.exe scripts/check_desktop_entry.py --shortcut '入口路径' --expected-package dist/0.4.2-candidate/TangerineXiaoAiAssistant
   ```

4. 复核数据兼容和迁移授权。0.4.1 的默认数据在旧平铺目录，0.4.2 首次默认启动会执行 [目录迁移](STORAGE.md)。旧默认配置存在且没有迁移完成证据时，单独的入口维护授权不足以切换。只检查目录/标记是否存在，不为判定而打开真实配置或凭据。保持旧入口，报告“候选已验证，待真实数据迁移授权”；不要通过添加测试 `--data-dir` 或空库参数伪装为日常入口已更新。
5. 只有安全条件和所需授权齐备时才更新入口。先在忽略目录备份原 `.lnk`，再使用 Windows ShellLink 保持入口名称、既有参数和语义，只调整已确认归属的程序目标及对应工作目录/图标；保留旧包。回读链接、重复版本/哈希检查。不得维护被排除的安装候选“当前”目录或重试被拒的卸载。
6. 成品隔离验证可用 `scripts/smoke_exe.py --package-dir 包目录 --no-window`。该选项不打开窗口，不联网或执行硬件命令；测试使用虚构 LOCALAPPDATA。实际桌面启动必须另核对其加载版本、数据身份和任务状态。没有执行正式启动时明确写“运行实例未更新/未验证”，不把静态核对或隔离程序冒充用户实例。

交接分别记录源码提交、工作区状态、包的构建来源、实际版本与 SHA-256、入口是否更新、是否存在运行实例、验证和阻塞。物理桌面路径不写入公共文档。源码推送不发布安装包，也不授权真实迁移。
