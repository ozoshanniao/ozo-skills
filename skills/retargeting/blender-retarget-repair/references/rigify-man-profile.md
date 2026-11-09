# 历史配置：Rigify → Man / ARP Remap

仅供匹配这对骨架时参考。依据 2026-10 的实际场景检查及修复记录；当前文件与安装版本优先。其他角色不能照抄骨名、数值或历史 57 项映射数量。

## 部分对应关系

| 源 Rigify | 目标 Man | 职责 |
| --- | --- | --- |
| `tweak_spine` | `Torso` | 某 UE2rigify 源的骨盆位移，ARP 唯一 Set as Root |
| `ORG-spine` | `Hips_FK` | 骨盆旋转 |
| `ORG-spine.001` | `Spine_01_FK` | 脊柱第一段 |
| `ORG-spine.002` | `Spine_02_FK` | 脊柱第二段 |
| `ORG-spine.008` | `Chest_FK` | 胸部，编号需按实际结构核对 |
| `neck` | `Neck` | 颈部，核对实际运动 |
| `ORG-spine.006` | `Head` | 头部，不只按编号判断 |
| `ORG-upper_arm.L/R` | `Arm_FK.L/R` | 上臂 FK |
| `ORG-forearm.L/R` | `Forarm_FK.L/R` | 前臂，目标拼写确为 Forarm |
| `ORG-hand.L/R` | `Hand_FK.L/R` | 手腕 FK |
| `ORG-foot.L/R` | `Foot_IK_Master.L/R` | IK，脚踝与目标主控原点不同 |
| `ORG-toe.L/R` | `IK_Toes.L/R` | 脚趾 |

此表不是完整预设；肩部、手指及其他段按本次骨架补齐。

- 源腿链为 `ORG-thigh → ORG-shin → ORG-foot`；目标 Pole 为 `Leg_IK_POLE.L/R`，历史使用 Relative: Chain。
- 目标已有 IK，历史关闭 Add IK Constraints，采用双臂 FK、双腿 IK。
- 某 UE2rigify 源在 FK 烘焙，Rigify 的 `IK_FK=1` 是该链 FK。Man 属性需另查，不能推断不同 rig 的 0/1 含义。
- 较早 `torso → Torso` 适合另一些源，但某 UE2rigify Idle 的 `torso` 静止而漏传重心，须按实际动画决定位置入口。

## ARP 要点

- Set as Root 是运动入口，不要求目标名为 ROOT。为固定目标根取消骨盆入口，可能丢失落座/重心位移。
- Source Action 可能留下旧字符串；刷新 Source 后核对真实 Action 和对象兼容 Slot。
- Saved 数据存在不代表 Preserve 在新源启用。检查 Redefine Rest Pose → Preserve → Saved/Rest Pose，由用户 Apply。
- 多槽批处理历史有默认取首槽的限制，当前先查实现，不能盲目批量；单动画不启用批量。
- 历史完整烘焙起点：真实 Action 全范围、Linear、Handles Default、Fake User 开启；不只烘焙已有关键帧；暂不 Clean FK Rotations / Clean IK Poles。Extract Root Motion 按事先约定决定，不照抄“总关闭”。参数须匹配当前工具版本。

## 已验证经验及边界

- 目标 `Properties` 控制骨超出身高，某版本 Auto Scale 将它计入高度。按变形骨/网格、髋高和腿长判断比例。
- FeetFix 曾只改左右 `Foot_IK_Master` 位置，保留用户最新身体与足部旋转，以鞋底网格检查帧间接地。方法见解法 5，不复制固定帧数、顶点索引或地面间隙。
- Walk 的 Torso、脚 IK、腿 Pole 通过父级约束跟随 ROOT_Sec，因此无须改层级即可转移前进；Pole 本地轴与世界前进不同。其他角色先查层级。
- Sit 须校准髋中心、脚踝、膝平面和手掌接触；固定 ROOT/ROOT_Sec 不等于去掉源根轨迹，落座所需下降后移保留。

历史脚本含绝对路径、固定 Action/帧数，部分会另存 .blend。只提取可验证思路，最终交付遵守主 skill 的新 Action 规则。
