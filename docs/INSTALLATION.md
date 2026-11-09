# 安装与依赖

## 选择需要的 Skill

先查 [分类目录](CATALOG.md)。每个包含 `SKILL.md` 的叶级文件夹都是一个完整 Skill。按需安装，不要只复制单个 `SKILL.md`，否则可能缺少 references、scripts、agents 或 assets。

## 手动安装到 Codex

1. 克隆仓库或通过 GitHub 的 Code → Download ZIP 下载并解压。
2. 选择完整 Skill 文件夹，例如 `skills/animation/blender-character-animate/`。
3. 复制到用户级 `~/.agents/skills/blender-character-animate/`，或目标项目的 `.agents/skills/blender-character-animate/`。
4. 检查最终路径下直接有 `SKILL.md`。分类目录用于仓库导航；不要误把整个 animation 或 retargeting 分类当成单个 Skill。
5. 在 Codex 中显式调用 `$blender-character-animate`，也可使用符合其用途的自然语言。新 Skill 未出现时重启 Codex。

Windows 用户级位置可用 `%USERPROFILE%\.agents\skills\` 表示。已有同名技能时先比较内容并保留自己的修改，避免同时安装重复副本。

上述位置与调用方式参考 [OpenAI 官方 Skills 文档](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。历史本机安装目录可能使用 `.codex/skills`，发布示例使用当前文档的 `.agents/skills`。

## 使用 skill-installer

将仓库和具体叶级路径交给内置安装器，例如：

```text
请使用 $skill-installer 安装 GitHub 仓库 ozoshanniao/ozo-skills 中的
skills/rigging/blender-rig-understand
```

安装器如何从其他仓库下载 Skills，见 [官方安装说明](https://learn.chatgpt.com/docs/build-skills#install-curated-skills-for-local-use)。

## 运行依赖

| 分类 | 必需内容 | 补充说明 |
| --- | --- | --- |
| 绑定分析 | 可用的 Blender MCP、目标绑定 | 仅安装 Skill 不会自动连接 Blender |
| 动画规划 | 动作目标和上下文 | 需要核对实时角色时再使用 MCP |
| 动画制作 / 检查 | Blender MCP、已绑定角色 / 动画 | 视觉验收还需要能获取图像的工具 |
| 通用重定向 | Blender MCP、源 / 目标绑定及实际重定向工具 | ARP 流程需要用户已有 ARP；仓库不分发第三方插件 |
| Man → Girl | Blender MCP、严格匹配校准的两套绑定 | 脚本在 Blender 的 Python 中运行，使用 bpy / mathutils；无需 OZO Tools / ARP |
| 字幕翻译 | 英语 SRT；辅助脚本用 Python 3 | 脚本仅用标准库；翻译由助手完成，不要求启动 Blender |

## 专用校准资料

`blender-man-girl-transfer/assets/` 的两个 JSON 必须与 scripts 一起保留。不要改骨名或验收阈值来绕过配置不匹配；不同角色使用通用重定向流程。加载脚本时按 `references/execution.md` 使用实际安装路径。

## 与 OZO Tools 的区别

本仓库是 AI 工作流知识与辅助代码，不能在 Blender 的 Add-ons 中作为插件 ZIP 安装。[OZO Tools](https://github.com/ozoshanniao/ozo-tools) 是独立的 Blender 插件仓库。
