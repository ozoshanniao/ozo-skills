"""Blender-only entry point; import is inert. No UI registration or .blend save."""
from pathlib import Path
import importlib.util
import json
import sys


def load_core():
    spec = importlib.util.spec_from_file_location(
        'man_girl_transfer_core', Path(__file__).with_name('transfer_core.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def objects(source_name, target_name):
    import bpy
    return (bpy.context.scene.objects[source_name],
            bpy.context.scene.objects[target_name])


def check(source_name='Man_Armature', target_name='RIG_Girl',
          step=1.0, start=None, end=None):
    core = load_core()
    source, target = objects(source_name, target_name)
    plan = core.preflight(source, target, start, end, step)
    return {'source': source.name, 'target': target.name,
            'source_action': plan['action'].name, 'source_slot': plan['slot'].identifier,
            'mapping_count': len(plan['mapping']), 'mapping': plan['mapping'],
            'range': [plan['start'], plan['end']], 'bake_step': step,
            'verify_step': plan['verify_step'], 'root_motion': 'PRESERVE',
            'native_settings': plan['native_settings'], 'pose_validation_performed': False}


def snapshot_pose(obj):
    return {p.name: {'mode': p.rotation_mode, 'location': p.location.copy(),
                    'quaternion': p.rotation_quaternion.copy(),
                    'euler': p.rotation_euler.copy(),
                    'axis_angle': tuple(p.rotation_axis_angle), 'scale': p.scale.copy(),
                    'properties': {k: p[k] for k in p.keys()
                                   if isinstance(p[k], (bool, int, float))},
                    'ik_stretch': p.ik_stretch}
            for p in obj.pose.bones}


def restore_pose(obj, state):
    for name, value in state.items():
        p = obj.pose.bones[name]
        p.rotation_mode = value['mode']
        p.location = value['location']
        p.rotation_quaternion = value['quaternion']
        p.rotation_euler = value['euler']
        p.rotation_axis_angle = value['axis_angle']
        p.scale = value['scale']
        for k, v in value['properties'].items():
            p[k] = v
        p.ik_stretch = value['ik_stretch']
    obj.update_tag()


def run(source_name='Man_Armature', target_name='RIG_Girl', action_name='',
        step=1.0, start=None, end=None, commit=False, report_path=None):
    import bpy
    core = load_core()
    source, target = objects(source_name, target_name)
    plan = core.preflight(source, target, start, end, step)
    scene = bpy.context.scene
    frame = (scene.frame_current, scene.frame_subframe)
    had_animation_data = target.animation_data is not None
    original = target.animation_data.action if had_animation_data else None
    original_slot = target.animation_data.action_slot if had_animation_data else None
    original_fake_user = original.use_fake_user if original else None
    pose = snapshot_pose(target)
    action = None
    succeeded = False
    try:
        # Candidate gate runs before any formal target binding changes.
        action, report = core.convert(source, target, start, end, step, action_name, False)
        report['source_slot'] = plan['slot'].identifier
        report['committed'] = False
        if commit:
            target.animation_data_create()
            target.animation_data.action = action
            target.animation_data.action_slot = action.slots[report['slot']]
            target.update_tag()
            bpy.context.view_layer.update()
            plan['compensated'] = report['parent_compensation']
            pairs = list(core.arm_twist.entries())
            plan['arm_twist_controls'] = {c for c, _, _ in pairs}
            plan['arm_reference_results'] = {n: a for _, n, a in pairs}
            report['formal_target_validation'] = core.validate(plan, target)
            if not report['formal_target_validation']['passed']:
                raise ValueError('Formal target validation failed: ' + json.dumps(
                    report['formal_target_validation'], ensure_ascii=False))
            if original:
                original.use_fake_user = True
            report['committed'] = True
        report['mesh_validation_performed'] = False
        if report_path:
            try:
                Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                             encoding='utf-8')
            except OSError as error:
                report['report_write_error'] = str(error)
        payload = json.dumps(report, ensure_ascii=False)
        action['man_girl_repair_report'] = payload
        action['ozo_transfer_report'] = payload
        succeeded = True
        return action, report
    finally:
        if not succeeded:
            if target.animation_data:
                target.animation_data.action = original
                if original_slot:
                    target.animation_data.action_slot = original_slot
            if original:
                original.use_fake_user = original_fake_user
            if not had_animation_data and target.animation_data:
                target.animation_data_clear()
            if action:
                bpy.data.actions.remove(action)
        scene.frame_set(frame[0], subframe=frame[1])
        if not (succeeded and commit):
            restore_pose(target, pose)
        target.update_tag()
        bpy.context.view_layer.update()
