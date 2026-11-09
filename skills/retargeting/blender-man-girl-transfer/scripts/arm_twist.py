"""FK-relative arm reference and non-destructive twist fitting for this rig pair.

Unlike armature-space rest-delta comparison, this reference preserves twist
about each rig's own limb axis when their A-poses differ. Pose directions still
come from the calibrated source FK motion; all edits go to an isolated Action.
"""
import math
from mathutils import Quaternion, Vector


def entries():
    for side in ('L','R'):
        yield 'Arm_Tweak.'+side, 'DEF_Arm.'+side, 'Arm_FK.'+side
        yield 'Forarm_Tweak.'+side, 'DEF_Forarm.'+side, 'Forarm_FK.'+side
        for part in ('Arm','Forarm'):
            for segment in ('01','02'):
                yield f'{part}_{segment}_Tweak.{side}', f'DEF_{part}_{segment}.{side}', f'{part}_FK.{side}'


def reference(source, target, name, anchor):
    """Expected target result, relative to its own FK/rest limb coordinate frame."""
    s_fk = source.pose.bones[anchor].matrix.to_quaternion()
    s_rest = source.data.bones[anchor].matrix_local.to_quaternion()
    t_rest = target.data.bones[anchor].matrix_local.to_quaternion()
    s_bone_rest = source.data.bones[name].matrix_local.to_quaternion()
    t_bone_rest = target.data.bones[name].matrix_local.to_quaternion()
    s_bone = source.pose.bones[name].matrix.to_quaternion()
    s_y, t_y = s_rest @ Vector((0,1,0)), t_rest @ Vector((0,1,0))
    swing = s_y.rotation_difference(t_y)
    transported = t_rest.inverted() @ swing @ s_rest
    roll = Quaternion((0,1,0), transported.to_swing_twist('Y')[1])
    relative_motion = s_fk.inverted() @ s_bone @ s_bone_rest.inverted() @ s_rest
    expected_fk = s_fk @ s_rest.inverted() @ t_rest
    return (expected_fk @ roll @ relative_motion @ roll.inverted()
            @ t_rest.inverted() @ t_bone_rest).normalized()


def twist_error(actual, desired):
    relative = actual.inverted() @ desired
    return relative.to_swing_twist('Y')[1]


def fit(plan, candidate, bag, core):
    source = plan['source']
    pairs = list(entries())
    rotations = {control: [] for control,_,_ in pairs}
    stats = {'max_input_correction_deg':0.0, 'max_residual_deg':0.0,
             'max_fit_twist_residual_deg':0.0, 'samples':len(plan['bake_times']),
             'max_main_joint_position_change':0.0,
             'method':'FK-relative reference; scalar measured twist response'}
    plan['arm_twist_controls'] = {control for control,_,_ in pairs}
    plan['arm_reference_results'] = {name:anchor for _,name,anchor in pairs}
    for frame in plan['bake_times']:
        core.set_frame(__import__('bpy').context.scene, frame)
        bpy = __import__('bpy')
        src = source.evaluated_get(bpy.context.evaluated_depsgraph_get())
        goals = {name:reference(src,candidate,name,anchor) for _,name,anchor in pairs}
        originals = {control:candidate.pose.bones[control].rotation_quaternion.copy()
                     for control,_,_ in pairs}
        joint_heads = {f'DEF_{part}.{side}':candidate.pose.bones[f'DEF_{part}.{side}'].head.copy()
                       for part in ('Arm','Forarm','Hand') for side in ('L','R')}
        # Main result bones precede distributed segments so inherited corrections
        # are visible before measuring each segment's individual response.
        for control,name,_ in pairs:
            pb = candidate.pose.bones[control]
            for iteration in range(4):
                actual = candidate.pose.bones[name].matrix.to_quaternion()
                residual = twist_error(actual,goals[name])
                if abs(residual) < math.radians(0.0002):
                    break
                original_q = pb.rotation_quaternion.copy()
                delta = 0.002
                pb.rotation_quaternion = original_q @ Quaternion((0,1,0),delta)
                candidate.update_tag();bpy.context.view_layer.update()
                response = twist_error(actual,candidate.pose.bones[name].matrix.to_quaternion())/delta
                pb.rotation_quaternion = original_q
                candidate.update_tag();bpy.context.view_layer.update()
                if not math.isfinite(response) or abs(response)<0.05:
                    raise ValueError(f'Twist control has no stable response at {frame}: {control}')
                correction = max(-0.35,min(0.35,residual/response))
                pb.rotation_quaternion = original_q @ Quaternion((0,1,0),correction)
                candidate.update_tag();bpy.context.view_layer.update()
            actual = candidate.pose.bones[name].matrix.to_quaternion()
            stats['max_fit_twist_residual_deg'] = max(stats['max_fit_twist_residual_deg'],
                abs(math.degrees(twist_error(actual,goals[name]))))
            stats['max_residual_deg'] = max(stats['max_residual_deg'],core.rotation_error(actual,goals[name]))
        for control,_,_ in pairs:
            q = candidate.pose.bones[control].rotation_quaternion.copy()
            stats['max_input_correction_deg'] = max(stats['max_input_correction_deg'],
                core.rotation_error(q,originals[control]))
            if rotations[control] and q.dot(rotations[control][-1])<0:
                q.negate()
            rotations[control].append(q)
        for name,position in joint_heads.items():
            stats['max_main_joint_position_change'] = max(stats['max_main_joint_position_change'],
                (candidate.pose.bones[name].head-position).length)
    for control,qs in rotations.items():
        for i in range(4):
            core.fill_curve(bag,candidate.pose.bones[control].path_from_id()+'.rotation_quaternion',i,
                            plan['bake_times'],[q[i] for q in qs])
    return stats
