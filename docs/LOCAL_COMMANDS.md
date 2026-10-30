# 本地命令增量（0.2.0）

## 应用白名单

在本机执行，应用本身必须已经安装：

```powershell
.\TangerineXiaoAiAssistant.exe add-app 微信 'C:\实际安装目录\WeChat.exe' --alias WeChat
```

也可双击 `configure-app.cmd` 交互输入，路径可从资源管理器拖入。本命令只登记、不启动。再次登记相同名称会更新该条规则，其余命令保留。随后重启运行窗口。

只允许本机驱动器下的绝对 `.exe` 路径；不支持 UNC、脚本、快捷方式、参数或已知命令解释器。执行时再次验证解析后的路径，使用参数列表调用 CreateProcess，`shell=False`，工作目录为应用所在目录。语音只提供已配置名称，不能传入路径或参数。配置文件属于用户受信任的本地配置，不是抵御恶意本地软件篡改的安全边界。

```json
{
  "id": "wechat",
  "action": "launch_app",
  "phrases": ["打开微信", "打开WeChat"],
  "path": "C:\\实际安装目录\\WeChat.exe",
  "reply": "已请求启动微信"
}
```

启动返回成功仅表示进程创建请求成功，不保证应用窗口已经就绪。路径失效会给出重新登记提示；不会自动寻找替代程序或请求管理员提升。

## 系统音量

`set_volume` 的 phrases 必须包含一个 `{level}`。支持阿拉伯数字、常见中文整数、`百分之` 和 `%`，只允许 0–100。全短语匹配，拒绝小数、负数、超范围值及附加命令。同一条语音匹配到多条规则时不执行。

通过 [pycaw](https://github.com/AndreMiras/pycaw) 与 comtypes 调用默认多媒体播放设备的 `SetMasterVolumeLevelScalar`，随后读取实际百分比；超过容差时不报成功。保持静音状态，若设备仍静音，反馈中明确说明。无默认播放设备时返回固定错误，不影响其他网页/应用命令。

这使用 Windows 的 0–1 标量音量接口，和分贝值不同。参考 [Microsoft Core Audio 文档](https://learn.microsoft.com/en-us/windows/win32/api/endpointvolume/nf-endpointvolume-iaudioendpointvolume-setmastervolumelevelscalar)。设备可能有量化步进，反馈以实际读回值为准。

`volume-status` 只读取百分比和静音状态，方便确认音量接口，不改变系统设置。

## 锁屏

使用 Windows `user32.LockWorkStation()`，不经过 Shell。成功反馈为“已请求电脑锁屏”，不会把异步请求成功误报为桌面已经锁定。该接口要求已登录的交互桌面。[Microsoft LockWorkStation 文档](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-lockworkstation)

自动测试替换系统调用，验证参数、成功和失败处理；没有实际锁住开发机。用户可在方便时单独验收实际锁屏。

## 升级旧配置

`enable-local-commands`（或双击 `upgrade-config.cmd`）只补入缺少的音量/锁屏动作。已有相同动作的自定义规则保留；重复运行不重复添加。所有新增内容先校验，存在冲突时拒绝保存。不改变账号、设备、触发词、网页命令，也不在后台修改运行中的配置。
