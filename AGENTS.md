# TangerineXiaoAiAssistant

- 用户指定固定开发目录为 `D:\IdeaProjects\TangerineXiaoAiAssistant`，直接在 `main` 开发，不自动创建功能分支。
- 优先复用已审查的 VoxNode 小米协议代码，不整体导入其 GUI、Android/PWA、监控或智能家居能力。
- 已交付网页 MVP；用户随后授权继续补齐应用白名单启动、精确音量和锁屏。真实设备验收尚未完成；用户暂时无法做真机测试，不反复要求当前扫码。
- 自动验证不得实际锁住用户桌面；锁屏验证使用替身。音量实机检查只读或回写原值，不改变用户正在使用的音量。
- 语音只命中白名单；不得执行任意 Shell、从语音拼接路径/网址，或增加 GUI 模拟 WorkBuddy 操作。
- 凭据使用 Windows 当前用户 DPAPI。禁止提交真实配置、二维码、日志、密码、Token；日志不得输出网络响应原文或语音全文。
- 上游引用、固定版本和修改记录见 docs/RESEARCH.md 与 THIRD_PARTY_NOTICES.md；修改 vendored 代码时更新说明。
- 核心校验：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`。构建：`.\.venv\Scripts\python.exe scripts/build.py`。
- 最终交接说明已完成内容、实际验证与待真机验证项，并给出具体下一步。无需用户立即操作时明确说明，不把待验收等同于完成。
