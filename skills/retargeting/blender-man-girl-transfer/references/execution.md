# 执行接口与约束

## 加载

在所选 Blender 实例里，通过 MCP 执行 Python。`skill_dir` 必须取本次实际安装路径，不能依赖原项目目录。以下示例使用用户级 Skills 目录；若安装在项目目录或其他位置，请替换为实际路径：

```python
from pathlib import Path
import importlib.util
import sys

skill_dir = Path.home() / ".agents" / "skills" / "blender-man-girl-transfer"
spec = importlib.util.spec_from_file_location(
    "man_girl_skill", skill_dir / "scripts" / "run_transfer.py")
transfer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = transfer
spec.loader.exec_module(transfer)

print(transfer.check(source_name="Man_Armature", target_name="RIG_Girl", step=1.0))
```

导入模块不执行转换、不注册 UI、不保存文件。需要 Blender 自带的 `bpy` 和 `mathutils`，不能用系统 Python 执行转换。

## 检查、试算与提交

```python
# 只检查配置，不切帧、不生成 Action。
summary = transfer.check("Man_Armature", "RIG_Girl", step=1.0)

# 默认 commit=False：完整隔离转换和自动验收，保留候选 Action。
action, report = transfer.run(
    source_name="Man_Armature", target_name="RIG_Girl",
    action_name="Girl_Converted", step=1.0, commit=False)

# 用户已要求转换/修复时：验证候选，绑定正式目标，再完整复验。
# 使用本次合适的新名字；Blender 自动避免重名覆盖。
action, report = transfer.run(
    source_name="Man_Armature", target_name="RIG_Girl",
    action_name="Girl_Repaired", step=1.0, commit=True)
print(report)
```

`run(source_name, target_name, action_name, step, start, end, commit, report_path)`：

- `start/end=None` 分别取源活动 Action 实际关键帧的最小/最大时间，包含两端。自定义时传明确帧值。
- `step=1.0` 每帧烘焙一次；`0.5` 每半帧。还会包含原关键帧时刻，验证间隔 `min(step/2, 0.25)`。超过样本上限需分段或另议方案，不静默截断。
- `commit=False` 会在场景中新建并以 Fake User 保留候选 Action，目标绑定保持原样；它不是纯只读。
- `commit=True` 正式目标复验失败时恢复原 Action/Slot、原 Fake User 状态、帧/子帧及姿态属性，移除本次失败 Action。
- 新 Action 中 `man_girl_repair_report` 保存 JSON 报告。可选 `report_path` 把报告写到调用者指定路径；父目录必须已存在。若报告写盘失败，会记录 `report_write_error`，动画结果仍以 Action 内报告为准。
- 脚本不保存 `.blend`，不自动调整播放范围，不清理之前的候选 Action。

不要通过传入自定义 validator、改 `passed` 或改验收常量提交失败结果。`core.convert(... validator=...)` 仅留作隔离回退测试入口。

## 前置条件

当前实现按校准结构严格核对；名字相同不代表适配：

- 两套骨架各 423 骨，静止矩阵/长度/层级与继承设置匹配 `assets/man_girl_profile.json`；164 对映射完全匹配 `assets/bone_mapping.json`。
- 目标为本地可写骨架，不是 Link 或 Library Override。源可 Link/Override。两个不同对象都在当前场景中。
- 对象旋转/缩放为单位变换；对象位置允许不同，但自动根矩阵验收是骨架空间，不能声称对象世界位置一致。
- 不支持对象父级/对象约束、Armature 数据块动画、控制骨上活跃约束、活动 NLA、NLA Tweak 模式、非 Replace 或不为 1 的 Action influence。不要为了通过检查擅自改用户绑定；先报告阻碍。
- 源活动 Action 需要唯一 Slot、Layer、Keyframe Strip。严格使用活动兼容 Slot；传统/多槽 Action 未适配，需单独讨论转换。
- 当前支持姿态变换通道、数值自定义属性和限定的原生 `.ik_stretch`。对象动画、其他机制骨变换、静音/采样/带 Modifier 曲线会拒绝。非均匀或负局部缩放拒绝；目标 Axis Angle 旋转模式拒绝。
- `Properties` 上双臂 `Arm_FK_IK.L/R=0`，双腿 `Leg_FK_IK.L/R=1`；以这对 rig 的含义为准。完整烘焙及验证采样均需满足，不自动切换模式来改变源动画。
- 未映射的源末端控制器只有实际为单位变换才允许跳过；有效动画不能静默丢失。完整列表见映射数据。

合法机制骨属性只包括 `MCH_IK_Arm.L/R`、`MCH_IK_Forarm.L/R` 的 `.ik_stretch`，逐条保留其关键帧、手柄与插值并验证求值。不能以此放开其他 MCH 通道。

## 回滚与状态

转换器在隔离骨架求值，处理内部自引用约束/驱动的重定向。最终只增加 Action 并按请求切换目标绑定；原骨架数据和原 Action 不重写。

外层入口在失败或试算结束时恢复目标姿态状态，防止切帧或切动作后未关键帧属性残留；帧/子帧始终恢复。成功提交后保留新动作的求值状态。临时骨架只清理本次创建的数据。

Action 摘要能发现曲线值、关键帧/手柄、插值、静音等变化，但不是整个文件、绑定或所有 Modifier 参数的完整证明。额外结构/网格修改不属于脚本的授权范围。
