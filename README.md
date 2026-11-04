# astrbot_plugin_group_speaker_tag

在**不隔离对话**（整个群共享一份上下文）的前提下，让 bot 分得清是谁在 @ 它。

## 解决什么问题

AstrBot 内置的「群聊上下文感知」（`provider_ltm_settings.group_icl_enable`）只把**当前触发消息之前**的群聊记录以 `[昵称/时间]` 的形式注入模型上下文，而触发对话的那条 @ 消息本身是**匿名的** `role:user`——模型不知道现在 @ 它的人，是不是刚才参与闲聊的那位群友。

本插件挂载 `@filter.on_llm_request()` 钩子，在请求 LLM 前把当前消息改写为：

```
[张三/15:49:52] 在吗？
```

与内置历史标注格式一致，模型看到的是一份连续、带身份的群聊记录。标注会随该轮 user 消息一起存入会话历史，之后的每一轮上下文里都能看到"每句话是谁说的"。

## 安装

1. 把整个 `astrbot_plugin_group_speaker_tag` 文件夹复制到 AstrBot 的 `data/plugins/` 目录下：
   - 本地部署：直接复制；
   - Docker：`docker cp astrbot_plugin_group_speaker_tag <容器名>:/AstrBot/data/plugins/`
2. 重启 AstrBot，或在 WebUI「插件管理」里重载。
3. 无需任何指令，装上即生效。

## 配置（WebUI → 插件管理 → 本插件 → 配置）

- `format`：标注格式，默认 `[{nickname}/{time}] {message}`
  - `{nickname}` 发言人昵称（群名片/群昵称，取不到时回退为 ID）
  - `{user_id}` 发言人 QQ 号/平台 ID（群内有人昵称相同时可加上，如 `[{nickname}({user_id})/{time}] {message}`）
  - `{time}` 时间 HH:MM:SS
  - `{message}` 原消息内容

## 注意

- 与内置「群聊上下文感知」**不冲突、不替代**，两者建议同时开启（内置负责背景消息，本插件负责当前消息）。
- 与内置「用户识别」（配置项 `provider_settings.identifier`，「在用户提示词前带上用户 ID 信息」）**功能重复**：那边会在用户消息尾部追加 `<system_reminder>User ID: xxx, Nickname: yyy</system_reminder>`。检测到该选项开启时本插件自动让位（不标注），关闭后自动恢复，无需重载插件。
- 插件启用前的历史消息无法追溯标注，仍是匿名 user。介意的话 `/reset` 重开会话即可从头带标注。
- 私聊不标注（私聊不存在多人混淆）。
- 依赖 `filter.on_llm_request` 钩子与 `ProviderRequest.prompt`，AstrBot v3.5+ 均支持。
