# 连接与场景读取

## 实例选择

先发现可用 Blender MCP 工具与实例标识。多个 Blender 窗口时先让用户选定文件/窗口，再连接。Windows 可只读查看 Blender 的 PID、MainWindowTitle 和监听端口 OwningProcess 的关系。标题不能识别文件时明确说明不确定，请用户给文件或窗口标识。

选定后，通过该 MCP 实例读取 `bpy.data.filepath`、场景、骨架和 Action，核对身份。未保存场景路径为空，要结合 PID/窗口和场景对象确认。进程存在、端口可连不等于连接正确。

优先用已暴露的 MCP 工具。历史环境曾通过 Blender MCP 插件的本地 JSON socket 接口连接；仅作为后备：先检查本机插件实现、实际主机/端口、请求响应协议与实例身份，不硬编码 localhost:9876。历史请求出现过 `{"type":"execute_code","params":{"code":"..."}}`，不能保证其他版本相同。

连接断开或没有工具时，说明无法读取实时场景。磁盘文件可作有限分析，但不一定有用户最新 Action；不能修改旧文件冒充实时修改，也不能悄悄换连另一窗口。本次创建/维护 skill 无需连接或修改 Blender。

## 采集基线

- 文件、场景、单位、FPS、当前帧/子帧、动作范围及播放范围。
- 源/目标对象、Armature 数据、网格绑定、世界变换、父级和父级逆矩阵。
- 实际活动 Action、Slot 标识、保留状态、共享用户和多槽数据。
- NLA 的 mute、blend、influence、extrapolation，有无 Action 重复叠加。
- 主要骨链静止矩阵/层级、求值关节位置和旋转、约束、IK/FK 属性与驱动。
- 重定向工具的 Source、Target、Source Action、映射、参考姿态数据及启用状态。
- Auto Key、Animation Auto Offset 等会把单帧编辑传播到全段的功能。

分析需要临时切帧或求值其他 Action 时，在 finally 中恢复帧/子帧、Action/Slot、NLA 和受影响属性，不写入关键帧或保存文件。复杂/破坏性诊断放隔离副本。

原始 FCurve 与最终姿态是不同证据。最终姿态以依赖图求值为准，每帧更新后采样，临时网格用完释放。复制测试对象可能仍共享 Armature 数据，约束/驱动也可能指向原骨架；结构测试前隔离相关数据与依赖。

## Action 与 Slot

独立新 Action 是最终交付约定，其内部仍需选择与目标对象兼容的 Slot。不能默认 `slots[0]`，尤其是骨架与形态键混合的动作。

按运行版本使用传统 FCurve 或分层 Action 的 layer/strip/channelbag 接口，需要时查 RNA。复制或导入后验证实际绑定和曲线，不只看名字。

切回原 Action 不一定恢复未驱动的 IK/FK、静音曲线最后求值值和临时设置；要记录状态并实际播放检查。
