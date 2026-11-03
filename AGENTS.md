# TangerineXiaoAiAssistant

- 项目采用 GPL-3.0-only；保留复用代码与依赖的原始版权和许可证。
- 保持轻量 Windows 工具定位，复用已审查的 VoxNode 小米通信代码，不引入 Android/PWA、监控或智能家居平台功能。
- 语音只匹配白名单，不执行任意 Shell，不从语音拼接路径、网址或参数；不使用 GUI 模拟 WorkBuddy 操作。
- 设备登录、语音读取、播报和长期稳定性需真实设备验证；自动化测试不得被表述为真机验收。
- 自动化验证不得实际锁屏、改变系统音量或开启自启；这些写操作使用替身，真实音量检查只读。
- 运行配置、应用路径、设备 ID、登录凭据及日志只保存在本机数据目录，不提交到仓库或加入分发包。默认目录由 LOCALAPPDATA 动态确定。
- 机器目录、个人账号和会话偏好不写入公开文档；如需开发笔记，使用 Git 不跟踪的 `.git/info/local-notes.md`。
- 凭据使用 Windows 当前用户 DPAPI；日志不得输出网络响应原文、语音全文、密码或 Token。
- 提交前运行 `python scripts/check_public_files.py`；打包同时执行隐私规则检查。扫描不能代替截图、自由文本和第三方材料的人工审查。
- 修改 vendored 代码时更新 THIRD_PARTY_NOTICES.md；新增公开文件时同步 scripts/source-files.txt。
- 校验：`python -m unittest discover -s tests -v`；构建：`python scripts/build.py`。
- 推送、Release 和仓库设置修改以维护者的明确授权为准；不要将源码同步视为二进制发布。
