# Windows 安装版（0.4.0）

本工具独立提供 Windows x64 Setup，同时保留 Portable。0.4.0 的源码和构建流程已加入仓库，**尚未创建 Release，也未上传公开安装包**。真实小爱音箱链路仍需设备验收。

## 普通用户安装、升级与卸载

- Setup 文件名为 `TangerineXiaoAiAssistant-0.4.0-windows-x64-Setup.exe`。按当前 Windows 用户安装，不请求管理员权限，不需要 Python 或其他运行环境。程序安装到 `%LOCALAPPDATA%\Programs\TangerineXiaoAiAssistant`，首版不开放自定义安装目录。
- 安装后从开始菜单打开；桌面快捷方式是可选组件，名称带“安装版”，避免覆盖已有便携版快捷方式。安装器不会自动启动应用、扫码、开启自启或监听。
- 手动更新：正常退出助手（关闭窗口只是收起到托盘），下载并核对新 Setup 的 SHA256，确认后运行。程序在运行、存在另一个安装向导或卸载向导时，安装器拒绝继续，不强杀进程。拒绝降级。
- 卸载：在 Windows“已安装的应用”找到本工具，或使用开始菜单中的卸载入口。正常退出助手后继续；**默认保留配置、备份、日志和加密登录信息**。只删除安装器明确列出的程序文件，未知文件或旧版遗留文件可能保留。没有递归删除整个安装目录或数据目录的操作。
- 卸载只移除指向本安装目录的自启项，不移除指向另一份便携程序的自启项。首次安装默认不启用自启，是否启用仍由应用设置决定。
- 同一 Windows 用户重新安装会恢复保留的配置；换电脑或账号后，应重新扫码登录。若要彻底删除私有数据，先退出程序，再自行处理该工具的数据目录，不要删除上层目录。

## 身份、数据与功能边界

| 项目 | 正式应用 |
|---|---|
| 应用 ID | `io.github.Manamiiii.TangerineXiaoAiAssistant` |
| Windows 卸载 GUID | `{B498FC4D-8B2D-54A7-83A5-F0DF945A1C4C}` |
| 数据目录 | `%LOCALAPPDATA%\TangerineXiaoAiAssistant` |
| 注册表范围 | 当前用户 HKCU，64 位视图 |

安装版和便携版保持既有数据目录兼容，不自动迁移、清空或重置规则。它们属于同一个工具，不能同时操作同一个配置；固定操作白名单、小米接入和 WorkBuddy 未接入状态均不变。

这是 Python/Tk 原生窗口，没有 renderer、浏览器存储、Service Worker、Dexie、OCR 或网页版；Electron 协议、JSON 业务导入/合并要求不适用于本项目。已有 JSON 配置及备份格式保持不变，配置恢复方法见 [首次使用说明](QUICKSTART.md#配置恢复升级与卸载)。没有新增账号、云同步、遥测、付费、自动更新服务或统一应用中心。

仅生成 Windows x64 安装包；macOS、Linux 和 ARM64 未支持/未验证。Windows 安装模板与工具链锁定文件位于 `installer/windows/`，便于将来增加独立平台实现，不表示已有其他平台支持。

## 可复现的构建流程

先按 [开发说明](DEVELOPMENT.md) 安装本项目固定的 Python 构建依赖，然后在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe scripts/build.py --installer
.\.venv\Scripts\python.exe scripts/verify_package.py --package-dir dist/0.4.0/TangerineXiaoAiAssistant
.\.venv\Scripts\python.exe scripts/smoke_exe.py --package-dir dist/0.4.0/TangerineXiaoAiAssistant
```

输出到 `dist/0.4.0/`：Setup、便携 ZIP、完整便携目录和 `SHA256SUMS.txt`。已存在的输出不覆盖；重建使用 `--output-dir 新目录` 并让验证命令指向同一目录。构建脚本只在本地生成文件，不创建 Release 或上传文件。

NSIS 3.12 编译器从官方发布地址下载到项目内 `build/tools/`，由 `installer/windows/toolchain.json` 固定 URL 和 SHA256，每次使用前重新校验，并在独立临时目录解压。不安装全局工具、不修改 PATH、不要求管理员权限。编译器未安装到普通用户电脑；运行时只需要生成的 EXE。

`build-info.json` 记录应用身份、版本、平台、源码及载荷文件哈希，不记录本机路径、用户名、时间戳或凭据。`verify_package.py` 检查对应源码、载荷清单、x64 程序、无提权 manifest、字节码路径和校验值。可复现的是依赖与构建步骤，不承诺不同机器或时间生成的 PE/ZIP 字节完全一致。首版未签名，不采购证书，也不建议用户关闭 Windows 防护。

## 隔离安装测试

```powershell
$fixtureId = [guid]::NewGuid().ToString()
.\.venv\Scripts\python.exe scripts/build.py --output-dir build/installer-fixture --fixture-id $fixtureId --installer
.\.venv\Scripts\python.exe scripts/verify_package.py --package-dir build/installer-fixture/TangerineXiaoAiAssistant
.\.venv\Scripts\python.exe scripts/test_installer_lifecycle.py --package-dir build/installer-fixture/TangerineXiaoAiAssistant
```

Fixture 的 GUID、应用 ID、窗口名称、安装目录、数据目录、自启值名与快捷方式均独立。测试脚本拒绝正式身份以及已存在的 fixture 目录；只写虚构配置和测试加密数据。内部协作退出接口仅测试身份可用，不会强制结束任何进程。失败时保留隔离数据以便排错，正常通过后清理本轮 fixture。

覆盖：无关目录保护、安装器互斥、旧便携版文件锁、安装/快捷方式/HKCU 卸载入口、真实打包窗口和托盘、运行中拒绝升级与卸载、正常退出、低版本号 fixture 升级、降级拒绝、安装中拒绝启动、卸载保留数据与未知文件、重装恢复。低版本 fixture 使用当前应用代码，**不等于真实旧版本业务迁移验证**。

## 验证层级与验收

- 源码单元测试：`python -m unittest discover -s tests -v`。
- 打包程序测试：`verify_package.py` 与 `smoke_exe.py`，运行时移除 Python PATH 并使用隔离 profile。
- 测试身份安装器：`test_installer_lifecycle.py`，按上述覆盖检查。
- 正式身份安装器交互向导：未作为自动化测试操作真实用户安装或数据，需人工验收。
- 干净 Windows 普通账号、Windows 10、真实小米账号/音箱：仍需验收；CI 成功不能替代这些检查。

本项目的 [Windows CI](https://github.com/Manamiiii/TangerineXiaoAiAssistant/actions/workflows/windows.yml) 构建正式 Setup/Portable 和独立 fixture，再执行各层测试。只读仓库权限；不上传安装包或产物，不创建 Release。应核对当前提交的实际运行结论，不能将本地通过视为 CI 通过。

必要人工验收（推广前）：在干净 Windows 普通账号双击正式 Setup，预期无提权请求，出现独立窗口/开始菜单/卸载入口；正常退出后卸载，重新安装应保留自定义配置。使用现有音箱完成扫码到“打开一次 B 站”的链路。

可选验收：不同 DPI、手动开启自启后注销重登、断网与休眠恢复。自动测试不执行真实锁屏、改音量或开启本机自启。
