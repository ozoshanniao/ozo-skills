# Skills 详细分类目录

7 项 Skills 分为 4 个工作领域。分类用于查找；每项保留独立的触发描述、参考资料和执行边界。

## 绑定分析 · `rigging`

### 理解绑定：blender-rig-understand

[打开 Skill](../skills/rigging/blender-rig-understand/SKILL.md)

| 项目 | 说明 |
| --- | --- |
| 输入 | 当前绑定角色、对象 / 骨架和相关动画状态。 |
| 输出 | 职责 → 控制器映射、IK/FK 含义、空间 / 旋转轴、已验证接口与疑点。 |
| 依赖 | Blender MCP |
| 写入范围 | 默认只读 |
| 适用边界 | 用于动画前的绑定理解；不能只按骨名、同名属性或骨数套用其他角色。 |

调用示例：

```text
请使用 $blender-rig-understand 理解当前角色绑定，只读列出身体主控、四肢 IK/FK 和父空间。
```

## 角色动画 · `animation`

### 表演规划：blender-performance-plan

[打开 Skill](../skills/animation/blender-performance-plan/SKILL.md)

| 项目 | 说明 |
| --- | --- |
| 输入 | 动作目标、起止状态、时长、用途、性格和接触对象；角色档案按需提供。 |
| 输出 | 动作阶段、关键姿态、节奏、支撑与接触事件、衔接 / 循环计划。 |
| 依赖 | 动作目标；实时场景按需 |
| 写入范围 | 文字规划 |
| 适用边界 | 输出创作规划，不直接向场景写入动画，也不要求已有目标动画。 |

调用示例：

```text
请使用 $blender-performance-plan 规划一个从站立到坐下的动作，考虑重心、椅面接触和克制的表演。
```

### 动画制作：blender-character-animate

[打开 Skill](../skills/animation/blender-character-animate/SKILL.md)

| 项目 | 说明 |
| --- | --- |
| 输入 | 已绑定角色、动作意图、范围，以及已确认的身体位移 / 旋转分配方案。 |
| 输出 | 可直接播放的角色动画，以及控制器、接触和状态处理说明。 |
| 依赖 | Blender MCP；已绑定角色 |
| 写入范围 | 按请求创建或修改动画 |
| 适用边界 | 通过实际绑定控制器创作，不承担常规模型编辑或通用重定向；换角色先验证控制权。 |

调用示例：

```text
请使用 $blender-character-animate 为选定角色制作一次自然转身，先确认位移与旋转写入方案。
```

### 检查与修订：blender-animation-review

[打开 Skill](../skills/animation/blender-animation-review/SKILL.md)

| 项目 | 说明 |
| --- | --- |
| 输入 | 待检查 Action、真实求值范围、角色绑定及指定的地面 / 接触对象。 |
| 输出 | 带帧号和证据的问题、求值轨迹 / 网格检查结果；授权修订时保留原版。 |
| 依赖 | Blender MCP；待检查动画 |
| 写入范围 | 检查默认只读；修订需授权 |
| 适用边界 | 检查默认只读；未要求循环时不把所有端点差异当作错误。没有接触几何或视觉检查时说明证据边界。 |

调用示例：

```text
请使用 $blender-animation-review 只读检查当前走路动作的支撑脚滑动、膝盖翻转及循环接缝。
```

## 动画重定向 · `retargeting`

### 通用流程与修复：blender-retarget-repair

[打开 Skill](../skills/retargeting/blender-retarget-repair/SKILL.md)

| 项目 | 说明 |
| --- | --- |
| 输入 | 源 / 目标绑定、源 Action / Slot、所用映射工具，以及根运动目标。 |
| 输出 | 映射与设置建议、参考姿态协作步骤、求值诊断；请求修复时创建独立 Action。 |
| 依赖 | Blender MCP；源/目标绑定；所用重定向工具 |
| 写入范围 | 配置与修复按请求；正式重定向由用户操作 |
| 适用边界 | 面向不同绑定的 Remap / Retarget；用户手动调整参考姿态并点击正式重定向，不使用 Man → Girl 专用预设替代通用映射。 |

调用示例：

```text
请使用 $blender-retarget-repair 分析这段动画并检查源目标映射，正式重定向由我点击。
```

### 特定骨架预设：blender-man-girl-transfer

[打开 Skill](../skills/retargeting/blender-man-girl-transfer/SKILL.md)

| 项目 | 说明 |
| --- | --- |
| 输入 | 匹配校准的 Man_Armature / RIG_Girl 绑定、兼容源 Action，以及双臂 FK / 双腿 IK 模式。 |
| 输出 | 独立目标 Action、164 对控制器映射转换、扭转修复和自动骨架验收报告。 |
| 依赖 | Blender MCP；匹配随附校准的那对绑定 |
| 写入范围 | 检查只读；转换创建独立 Action |
| 适用边界 | 只适用于这对已校准绑定的 Man → Girl 方向；两套静止配置各 423 骨。check() 只做前置核对；run(commit=False) 会创建候选 Action，不是只读。骨架通过不等于网格 / 接触通过。 |

调用示例：

```text
请使用 $blender-man-girl-transfer 先只运行 check()，报告校准、模式和动作范围是否匹配，暂不转换。
```

## 课程字幕 · `subtitles`

### 翻译与校验：blender-subtitle-translate

[打开 Skill](../skills/subtitles/blender-subtitle-translate/SKILL.md)

| 项目 | 说明 |
| --- | --- |
| 输入 | 用户指定的 Blender 课程英语 SRT、课程上下文及已有术语偏好。 |
| 输出 | 保留编号 / 时间轴的 .zh-CN.srt 与 .zh-CN-en.srt；双语中文在上；术语与结构校验。 |
| 依赖 | 英语 SRT；Python 3 用于辅助脚本 |
| 写入范围 | 创建字幕；按 Skill 约定归档英文源文件 |
| 适用边界 | 不做视频转录或自动打轴；srt_tools.py 仅提取、组装与结构校验，不自动翻译。默认按约定将英文原字幕归档至同级英文字幕目录。 |

调用示例：

```text
请使用 $blender-subtitle-translate 翻译这份 Blender 英语 SRT，输出纯中文和中英双语字幕。
```

## 如何区分容易混淆的 Skills

| 需求 | 选择 |
| --- | --- |
| 不知道哪个控制器真正驱动身体 | 绑定分析 |
| 先编排动作，再做关键帧 | 表演规划 |
| 在现有绑定上从零做动作 | 动画制作 |
| 已有动作，要检查质量或授权修订 | 动画检查 |
| 不同角色之间重定向，需映射与参考姿态 | 通用重定向与修复 |
| 恰好是匹配校准的 Man → Girl 绑定 | 专用转换预设 |
| 课程英语字幕翻译 | 字幕翻译 |
