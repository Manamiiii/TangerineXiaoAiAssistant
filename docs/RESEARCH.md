# 第一阶段研究记录

研究日期：2026-10-30（Asia/Shanghai）。已拉取并阅读实际源码，不以 README 的功能描述代替验证。

上游仓库：[Almmor/VoxNode](https://github.com/Almmor/VoxNode)，固定提交 `19ec9a0172e90eda1aee09cd338a4a3c2c4d5750`。完整研究副本在本地 `research/VoxNode`，不提交到本项目。

## 实际结构与依赖

| 上游文件/目录 | 源码证据及判断 | 本项目处理 |
|---|---|---|
| `miiotpcapi/xiaomi/account.py` | `MiAccount` 使用同步 requests.Session；serviceLogin → serviceLoginAuth2 → serviceToken；支持 OTP、passToken 换取各 sid 业务令牌 | 保留协议，修改缓存及错误处理 |
| `miiotpcapi/xiaomi/qrlogin.py` | 先 serviceLogin，再 longPolling/loginUrl；下载服务端二维码，轮询获得 passToken/userId | 独立复用，使用 mijia 扫码后换 micoapi；不申请米家控制权限 |
| `miiotpcapi/xiaomi/mina.py` | MiNA 设备列表、ubus text_to_speech、ubus nlp_result_get；从 nlp.meta 和 answer.intention.query 提取记录 | 独立复用，严格区分空记录、协议失败、网络失败 |
| `miiotpcapi/xiaomi/bridge.py` | 后台线程调用 latest_asks，再调用项目任务执行器，依赖 Config/secure/tasks/MIoT | 参考流程，重新实现窄桥接层 |
| `miiotpcapi/tasks.py`、`core/` | 涉及进程、电源、米家控制等大量超范围能力；apps.py 还依赖 monitor；inputctl.py 通过媒体按键相对调音量 | 不引入；特别不能将相对音量键当作精确设置 30% |
| `miiotpcapi/secure.py` | ctypes 调用 Windows DPAPI，仅用于保存密码 | 复用安全存储思路，新实现对完整令牌加密的存储层 |
| `voxnode/` | PyQt6 GUI、登录窗口、向导、多功能页面 | 不引入 |
| `android/`、`remote.py`、`channel.py`、`miot.py` | Android/PWA/本地遥控服务/米家属性通道等 | 不引入 |
| `tests/test_core.py` | 有命令与设备选择等测试，没有证明真实登录、nlp_result_get 或 TTS 在本设备可用 | 新增协议 fixture 和故障测试，真机单独验收 |

三个选用通信文件只需要标准库和 requests。整个 VoxNode 的 pyproject 还依赖 psutil、mss，可选 GUI 依赖 PyQt6；本项目不安装它们。小米通信模块本身不要求 Windows；本项目的 DPAPI、单实例文件锁和最终运行目标为 Windows。

源码链接：

- [account.py](https://github.com/Almmor/VoxNode/blob/19ec9a0172e90eda1aee09cd338a4a3c2c4d5750/miiotpcapi/xiaomi/account.py)
- [qrlogin.py](https://github.com/Almmor/VoxNode/blob/19ec9a0172e90eda1aee09cd338a4a3c2c4d5750/miiotpcapi/xiaomi/qrlogin.py)
- [mina.py](https://github.com/Almmor/VoxNode/blob/19ec9a0172e90eda1aee09cd338a4a3c2c4d5750/miiotpcapi/xiaomi/mina.py)
- [bridge.py](https://github.com/Almmor/VoxNode/blob/19ec9a0172e90eda1aee09cd338a4a3c2c4d5750/miiotpcapi/xiaomi/bridge.py)
- [pyproject.toml](https://github.com/Almmor/VoxNode/blob/19ec9a0172e90eda1aee09cd338a4a3c2c4d5750/pyproject.toml)

## 需要修正的上游行为

1. account.py 默认把令牌写为明文 JSON，secure.py 仅加密密码。本项目禁用明文缓存，通过 SecureAccount 的存储钩子加密整个 token 字典，写入失败不静默忽略。
2. 401 与部分鉴权错误清空全部令牌，可能破坏扫码得到的 passToken，导致无法免密码续期。现在只失效对应业务 sid，保留 passToken，且仅重试一次。
3. latest_asks 捕获全部请求异常后返回空列表，桥接层无法发现断线。本项目向上抛出网络异常；设备/记录格式错误与空列表分开。
4. 原桥接主要用单个最后时间戳及 request_id 去重，相同时间戳的多条记录可能被漏掉。本项目用有限集合去重、启动时刻和指令时效过滤，并在动作之前消费记录。
5. 部分异常带有原始响应、URL 或令牌字段。本项目移除这些内容，日志不写异常原文和语音全文。

## 最小架构

```text
小爱音箱 / 小米云
        ↓ requests（VoxNode 小米协议）
SecureAccount + XiaomiSpeaker
        ↓ 结构化对话记录
Bridge + VoiceGate（基线 / 时效 / 去重 / 重连）
        ↓ 新语音
CommandRouter（触发词 + 完整短语 + 动作白名单）
        ↓ 配置中固定的网址
Windows 默认浏览器
        ↓ 固定简短结果
可选音箱 TTS（失败不重做动作）
```

配置、账号、桥接、规则、WorkBuddy 适配边界分开。没有 Web 框架、数据库、云端自建服务或插件发现系统。新动作通过代码注册 handler，同时增加配置校验，不允许从 JSON 导入任意代码。

## 已证实与待验证

- **源码证实**：存在扫码/密码/OTP、MiNA 设备列表、nlp_result_get、TTS、passToken 续期实现及其请求形状。
- **本机接口实测**：未登录状态下成功申请二维码并下载有效 PNG；没有扫码授权，没有获取用户令牌。
- **自动化证实**：见 VALIDATION.md，使用模拟响应验证解析/错误/刷新逻辑，用真实 Windows API 验证 DPAPI。
- **尚未证实**：用户账号授权是否顺利、该音箱是否提供预期字段、实测轮询延迟、TTS 是否发声、长时稳定性。用户当前无法做真机验证，相关步骤保留待验收。

## 授权与分发

VoxNode 根许可证为 MIT。上游第三方声明列出 MiService 和 xiaomusic 的 MIT 版权许可。本项目保留原文并记录修改，不将它们当作额外安装依赖。[上游许可](https://github.com/Almmor/VoxNode/blob/19ec9a0172e90eda1aee09cd338a4a3c2c4d5750/LICENSE)

原第三方声明中关于 PyQt 动态链接的宽泛说明不作为本项目分发依据。PyQt 官方说明为 GPLv3/商业双许可；本项目不引入 PyQt。后续选 GUI 框架时重新审查。[PyQt 官方许可说明](https://www.riverbankcomputing.com/software/pyqt/intro)

requests 及其传递依赖的许可证随构建收集，Python 运行时许可也一并附带。具体清单见 THIRD_PARTY_NOTICES.md。未公开的小米协议仍可能随服务端或固件更新而变化，MIT 代码许可不代表官方 API 授权或稳定性承诺。

## 阶段计划

1. **研究**：源码定位、窄模块复用、安全差异、最小架构、二维码入口测试已完成；设备能力测试待用户可用。
2. **网页 MVP**：实现并测试 CLI 登录/设备选择、白名单网页规则、桥接、TTS、重连、加密存储，交付 Windows 控制台构建；真机验收不伪报完成。
3. **WorkBuddy**：依据官方本地助理 API 做真实接入，先解决开发者应用和 OAuth 授权。当前只有独立接口和 Mock，不阻塞本地命令。
4. **产品化**：基础语音链路可靠后增加其余简单命令、托盘、设置、自启和安装器；不提前铺设大型 GUI。

## 0.2.0 后续增量

用户随后授权继续推进不依赖音箱的功能。已实现应用白名单、精确音量和锁屏，见 LOCAL_COMMANDS.md。为复用成熟 Core Audio 实现，新增 pycaw/comtypes（含 pycaw 的 psutil 依赖），不增加任何系统监控功能。上文“三个小米模块只需要 requests”仍指该通信子集，不再代表 0.2.0 整个程序的依赖。
