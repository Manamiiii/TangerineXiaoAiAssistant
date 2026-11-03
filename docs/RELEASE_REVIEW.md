# 发布材料核对与安装版收尾

2026-11-03 核对，仅涉及本项目。0.4.0 Setup / Portable 仍是本地候选，等待维护者验收；没有创建 Release、上传候选包、修改旧 Release 说明或替换旧附件。

## 公开 0.3.0：历史便携包

核对对象是 [v0.3.0 Release](https://github.com/Manamiiii/TangerineXiaoAiAssistant/releases/tag/v0.3.0) 中的 `TangerineXiaoAiAssistant-0.3.0-windows-x64.zip`：41,689,537 字节，SHA-256：

```text
16bf213ce08cd855a95b08b827ed3f20cce8b7a7f567cb7a625e8b5feba90609
```

本轮只读下载后，文件摘要与 GitHub 附件摘要、Release 的 `SHA256SUMS.txt` 一致，ZIP CRC 检查通过。它是 0.3.0 便携程序，没有 Setup、安装向导或 Windows 卸载注册；不能用它验收 0.4.0 安装版。

实际包含：

- `THIRD_PARTY_NOTICES.md`、VoxNode MIT 全文及上游声明。
- `licenses/runtime/` 中各依赖、Python、Tk 和 PyInstaller 的许可材料；pystray 的 GPL/LGPL 全文。
- `source/pystray-0.19.5.zip`，与当前固定的上游源码摘要一致。
- `source/TangerineXiaoAiAssistant-0.3.0-source.zip`：49 个文件，包括应用代码、依赖锁文件、构建脚本及重建说明。

确认缺项：包根目录与应用源码归档中都没有项目自己的 `LICENSE`，旧项目元数据也没有 GPL-3.0-only 声明。pystray 的 GPL/LGPL 文件是第三方材料，不能把它们当成已经补齐的项目许可声明。当前 main 中的 LICENSE 不会自动加入旧下载。

旧包仍含 Pillow 12.3.0，也没有后续配置保存防护；隐私清理仅改文档和源码归档，没有升级原 EXE。旧版不应作为当前推荐下载。

## 0.4.0：本地安装候选

候选包含以下材料，并与随包 `build-info.json` 文件清单、哈希及源码清单核对：

| 材料 | 核对范围 |
|---|---|
| 根目录 `LICENSE` | 项目 GPL v3 全文，与仓库一致；两个 EXE 内嵌副本一致 |
| `THIRD_PARTY_NOTICES.md` | 项目 GPL-3.0-only 声明、VoxNode 来源与修改、依赖许可、NSIS 说明、pystray 重建许可 |
| `licenses/` | 19 份许可文件，含 NSIS、VoxNode/上游及运行组件；两个 EXE 内嵌副本与包外文件逐字节一致 |
| 应用对应源码 ZIP | 覆盖显式分发清单，包括全部应用模块、项目许可、Windows 安装模板、锁文件和构建/验证脚本 |
| pystray 对应源码 ZIP | 完整上游 0.19.5 归档，固定摘要验证，Python 库源码与实际构建环境逐文件核对 |
| `SHA256SUMS.txt` | 对应本次本地 Setup 和 Portable ZIP；重新构建后以同目录的新校验文件为准 |

Setup 由同一份已校验 Portable 载荷生成；安装模板列出并复制其中的许可及源码文件，不只分发两个 EXE。没有新增运行依赖、付费签名或自动更新。更新嵌入声明和随包文档会改变候选包摘要，不能沿用上一轮 SHA-256。

## 已有验证与本轮边界

基线提交 `1f384ef` 的 [Windows CI](https://github.com/Manamiiii/TangerineXiaoAiAssistant/actions/runs/41606475445) 已实际通过 89 项源码测试、正式包构建/校验/启动及 14 项独立测试身份的安装生命周期检查。本轮不改业务代码，也不把这些自动测试重新交给用户；文档与嵌入声明更新后，重新构建候选并核对最终提交的 CI。

正式身份的安全自动核对限于候选包静态信息、源码/许可一致性以及隔离 profile 的成品检查。没有执行本机正式安装/升级/卸载，没有读取正式配置或登录凭据，也没有关闭正在使用的应用。测试身份升级使用当前代码的低版本号安装器，不代表真实旧版本业务迁移。

正式身份安装向导、干净 Windows 普通账号、Windows 10、真实音箱仍为**未验证**。真实设备仅需按 [README 的四步验收](../README.md#快速开始) 操作；一次成功不等于播报和长期稳定性已经通过。

## 旧公开资产的具体补充方案（仅方案，未执行）

1. 在维护者确认后，为旧 Release 说明增加醒目的“历史便携包，不是 0.4.0 Setup”提示，列明许可缺项、旧依赖及验证限制，并链接当前材料说明；本轮只更新 main 的 README。
2. 确认对旧版自有代码的 GPL-3.0-only 授权范围后，可新增独立的 `v0.3.0-license-supplement.zip`：包含项目 GPL 全文、授权范围说明、保留的第三方声明、旧版对应源码和重建材料，以及指向上述原 ZIP 摘要的说明。明确这是补充材料，不是修复后的运行包；现有 ZIP 与校验值保持原样。
3. 验收通过后再发布新的 0.4.0 Setup / Portable，附对应校验值、许可和源码材料；不要把 0.4.0 重命名为 0.3.0 或覆盖旧下载。

上述远端变更均未执行。机器专属的测试应用残留及候选绝对路径仅在本机交接中记录，不加入公开文档或分发源码。
