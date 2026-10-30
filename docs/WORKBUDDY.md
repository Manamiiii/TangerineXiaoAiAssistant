# WorkBuddy 接入调查（2026-10-30）

依据：[腾讯 WorkBuddy 官方 Open API 文档](https://open.workbuddy.cn/docs/openapi)。此处是文档核验，不是已授权的真实调用验证。

## 适合本项目的能力

“整理这台电脑的下载文件夹”应使用文档的**本地助理 API**。云端任务运行环境不同，不能假设能访问本机文件。

| 用途 | 官方接口 | 权限 |
|---|---|---|
| 在线状态 | `GET https://www.workbuddy.cn/openapi/v2/localassistant` | `user.localassistant.readable` |
| 提交消息 | `POST https://www.workbuddy.cn/openapi/v2/localassistant/message` | `user.localassistant.invokable` |
| 增量消息历史 | `GET https://www.workbuddy.cn/openapi/v2/localassistant/message?message_id=...` | `user.localassistant.readable` |

提交使用 `content` 字符串和 `msg_type: text`；返回 `data.message_id`。在线状态是在线标志，消息历史是消息流，**不是独立任务完成状态**。存在回复不等于任务已经完成；存在其他来源的并发对话时，还需验证结果关联。

官方也提供 `/openapi/v2/tasks` 云端任务接口，但本项目不以云端任务代替本地文件操作。不能将云端任务的 status 枚举套用于本地消息。

## 授权前置条件

需要开放平台开发者账号、已创建的第三方应用、clientId/clientSecret、登记的回调地址和本地助理权限。OAuth 授权码通过 `/openapi/v2/authorize` 获取，再向 `/openapi/v2/token` 换取凭据；刷新也需要应用密钥。文档明确不允许在客户端代码暴露 client_secret。

因此，不把应用密钥硬编码进 exe，也不读取 WorkBuddy 桌面客户端内部登录缓存。普通用户分发之前需要确认官方是否支持适合桌面公共客户端的授权方式；否则需单独设计受控的授权服务。当前没有搭建该服务，也未得到开发者应用授权。已安装并登录 WorkBuddy 不足以完成 Open API 授权。

## 当前代码边界

`workbuddy.py` 定义 submit/status 协议、DisabledWorkBuddy 和 MockWorkBuddy。Mock 始终报告 `simulated`，明确说明没有提交或执行，且不接入当前语音主循环。

真实适配器尚未实现。后续需验证：授权与刷新、在线检查、提交确认、增量消息关联、等待用户审批的提示，以及无法判断最终状态时的诚实反馈。没有提交幂等性证据时，超时后不自动重新发送有副作用的任务。不得自动代答 WorkBuddy 工具审批。

用户暂时无需处理 WorkBuddy 授权；先完成小爱网页链路真机验证。
