# SPDX-License-Identifier: GPL-3.0-or-later
"""Man -> Girl animation basis conversion. No rig/rest/mesh edits or file saves.

This is a calibrated pair of rigs, not a general-purpose retargeter. Control
transforms change basis using both armatures' rest matrices. Result-bone motion
is independently checked on a disposable rig before an Action is committed.
"""
import hashlib
import json
import math
from pathlib import Path
import re

import bpy
from mathutils import Matrix, Vector
import importlib.util
import sys

_twist_spec = importlib.util.spec_from_file_location('man_girl_arm_twist', Path(__file__).with_name('arm_twist.py'))
arm_twist = importlib.util.module_from_spec(_twist_spec)
sys.modules[_twist_spec.name] = arm_twist
_twist_spec.loader.exec_module(arm_twist)

PROFILE_PATH = Path(__file__).resolve().parents[1] / "assets" / "man_girl_profile.json"
TRANSFORMS = {"location", "rotation_quaternion", "rotation_euler", "rotation_axis_angle", "scale"}
ROOTS = {"ROOT", "ROOT_Sec"}
PREFIXES = ("DEF", "ORG", "MCH", "VIS")
PATH = re.compile(r'^pose\.bones\["((?:[^"\\]|\\.)*)"\](.*)$')
ARM_IK_SETTINGS = re.compile(r'^MCH_IK_(Arm|Forarm)\.[LR]$')
ROTATION_LIMIT = 3.0  # degrees, result deformation rotation, after rest calibration
CONTROL_LIMIT = 0.15  # degrees; includes quarter-frame interpolation checks
MAX_SAMPLES = 20000
LOCATION_LIMIT = 0.00025
MAPPING_PATH = PROFILE_PATH.with_name("bone_mapping.json")


def control(name):
    return not name.startswith(PREFIXES)


def target_name(name):
    aliases = {"Torso": "Troso"}
    if name in aliases:
        return aliases[name]
    for old, new in (("Arm.L_Tweak.", "Arm_Tweak."),
                     ("Hand.L_Tweak_SEC.", "Hand_Tweak_SEC."),
                     ("Hand.L_Tweak.", "Hand_Tweak.")):
        if name.startswith(old):
            return name.replace(old, new, 1)
    if re.fullmatch(r"(Finger_[A-E]_\d\d|Palm_[A-E])\.[LR]", name):
        return name[:-2] + "_FK" + name[-2:]
    return name


def bags(action):
    for layer in action.layers:
        for strip in layer.strips:
            if hasattr(strip, "channelbags"):
                yield from strip.channelbags


def curves(action):
    return [fc for bag in bags(action) for fc in bag.fcurves]


def action_digest(action):
    """Include handles, interpolation, mute flags, modifiers and every slot."""
    data = []
    for fc in curves(action):
        data.append((fc.data_path, fc.array_index, fc.mute, fc.extrapolation,
                     [(list(k.co), list(k.handle_left), list(k.handle_right),
                       k.interpolation, k.handle_left_type, k.handle_right_type)
                      for k in fc.keyframe_points],
                     [list(k.co) for k in fc.sampled_points],
                     [m.type for m in fc.modifiers]))
    data.sort(key=lambda item: (item[0],item[1]))
    return hashlib.sha256(repr(data).encode()).hexdigest()


def bone_profile(rig):
    return {b.name: {"parent": b.parent.name if b.parent else None,
                     "matrix": [list(r) for r in b.matrix_local],
                     "length": b.length,
                     "inherit_scale": b.inherit_scale,
                     "inherit_rotation": b.use_inherit_rotation,
                     "local_location": b.use_local_location}
            for b in rig.data.bones}


def compare_profile(rig, expected, label):
    if set(expected) != set(rig.data.bones.keys()):
        raise ValueError(f"{label}: bone names differ from the calibrated rig")
    for name, ref in expected.items():
        b = rig.data.bones[name]
        parent = b.parent.name if b.parent else None
        err = max(abs(b.matrix_local[i][j] - ref["matrix"][i][j])
                  for i in range(4) for j in range(4))
        if (parent != ref["parent"] or err > 2e-5 or abs(b.length-ref["length"]) > 2e-5
                or b.inherit_scale != ref["inherit_scale"]
                or b.use_inherit_rotation != ref["inherit_rotation"]
                or b.use_local_location != ref["local_location"]):
            raise ValueError(f"{label}: rest/hierarchy differs at {name}; recalibration required")


def sample_times(start, end, step, extras=()):
    count = math.ceil((end-start)/step)
    if count > MAX_SAMPLES:
        raise ValueError(f"Too many samples ({count}); split the Action")
    return sorted({round(min(end, start+i*step), 6) for i in range(count+1)}
                  | {float(start), float(end)}
                  | {float(x) for x in extras if start <= x <= end})


def set_frame(scene, value):
    frame = math.floor(value)
    scene.frame_set(frame, subframe=value-frame)


def rotation_error(a, b):
    q = a.normalized().rotation_difference(b.normalized())
    # atan2 is accurate at tiny angles and invariant to quaternion sign.
    return math.degrees(2*math.atan2(Vector((q.x,q.y,q.z)).length, abs(q.w)))


def numeric_properties(pb):
    return {key: pb[key] for key in pb.keys()
            if isinstance(pb[key], (bool, int, float))}


def preflight(source, target, start=None, end=None, step=0.5):
    if not source or not target or source == target or source.type != 'ARMATURE' or target.type != 'ARMATURE':
        raise ValueError("Choose two different armatures")
    if bpy.context.mode == 'EDIT_ARMATURE':
        raise ValueError("Exit Edit Mode first")
    if bpy.context.screen and bpy.context.screen.is_animation_playing:
        raise ValueError("Stop playback first")
    if source.name not in bpy.context.scene.objects or target.name not in bpy.context.scene.objects:
        raise ValueError("Both armatures must be in this scene")
    if target.library or target.override_library or target.data.library:
        raise ValueError("Target armature must be local and writable")
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    compare_profile(source, profile["source"], "Source")
    compare_profile(target, profile["target"], "Target")
    for rig in (source, target):
        if rig.parent or rig.constraints:
            raise ValueError(f"{rig.name}: parent/object constraints unsupported")
        if max(abs(rig.matrix_world[i][j] - (1.0 if i == j else 0.0))
               for i in range(3) for j in range(3)) > 2e-5:
            raise ValueError(f"{rig.name}: object rotation/scale must be identity")
        if rig.data.animation_data:
            raise ValueError("Animated armature datablock unsupported")
        ad = rig.animation_data
        if ad:
            if ad.use_tweak_mode or any(not tr.mute and tr.strips for tr in ad.nla_tracks):
                raise ValueError(f"{rig.name}: mute NLA tracks and exit NLA Tweak Mode")
            if ad.action_blend_type != 'REPLACE' or abs(ad.action_influence-1) > 1e-6:
                raise ValueError(f"{rig.name}: Action must use Replace / influence 1")
    ad = source.animation_data
    if not ad or not ad.action or not ad.action_slot:
        raise ValueError("Source needs an active Action and slot")
    action = ad.action
    if len(action.slots) != 1 or len(action.layers) != 1 or len(action.layers[0].strips) != 1:
        raise ValueError("Source Action must contain one slot/layer/keyframe strip")
    bag = action.layers[0].strips[0].channelbag(ad.action_slot)
    if not bag or not len(bag.fcurves):
        raise ValueError("Source slot has no FCurves")
    keytimes = [float(k.co.x) for fc in bag.fcurves for k in fc.keyframe_points]
    if not keytimes:
        raise ValueError("Source Action has no keys")
    start = min(keytimes) if start is None else float(start)
    end = max(keytimes) if end is None else float(end)
    if not math.isfinite(start+end+step) or start > end or step <= 0 or step > 1.0:
        raise ValueError("Invalid range; bake step must be greater than 0 and at most 1 frame")
    mapping = {p.name: target_name(p.name) for p in source.pose.bones
               if control(p.name) and target_name(p.name) in target.pose.bones}
    expected_mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))["mapping"]
    if mapping != expected_mapping:
        raise ValueError("Control mapping differs from the calibrated 164-pair mapping")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Duplicate destination bone mapping")
    unknown_target = [p.name for p in target.pose.bones if control(p.name) and p.name not in mapping.values()]
    if unknown_target:
        raise ValueError(f"Unmapped target controls: {unknown_target}")
    skipped = [p.name for p in source.pose.bones if control(p.name) and p.name not in mapping]
    for rig in (source, target):
        for p in rig.pose.bones:
            if control(p.name) and any(not c.mute and c.influence > 1e-7 for c in p.constraints):
                raise ValueError(f"Active control constraint: {rig.name}/{p.name}")
    native_settings = []
    for fc in bag.fcurves:
        if fc.modifiers or fc.sampled_points or fc.mute:
            raise ValueError(f"Muted/sampled/modifier FCurve unsupported: {fc.data_path}")
        match = PATH.match(fc.data_path)
        if not match:
            raise ValueError(f"Only pose channels supported: {fc.data_path}")
        name = json.loads('"'+match[1]+'"')
        suffix = match[2]
        if (ARM_IK_SETTINGS.fullmatch(name) and suffix == '.ik_stretch'
                and name in source.pose.bones and name in target.pose.bones
                and fc.array_index == 0):
            native_settings.append(fc.data_path)
            continue
        if not control(name) or name not in source.pose.bones:
            raise ValueError(f"Non-control/invalid source channel: {fc.data_path}")
        if not (suffix.startswith('["') or suffix.removeprefix('.') in TRANSFORMS):
            raise ValueError(f"Unsupported pose channel: {fc.data_path}")
    return {"source": source, "target": target, "action": action,
            "slot": ad.action_slot, "bag": bag, "mapping": mapping, "skipped": skipped,
            "native_settings": native_settings,
            "start": start, "end": end, "step": step,
            "bake_times": sample_times(start, end, step, keytimes),
            "verify_step": min(step/2, 0.25),
            "verify_times": sample_times(start, end, min(step/2, 0.25), keytimes)}


def ensure_curve(bag, path, index):
    match = PATH.match(path)
    name = json.loads('"'+match[1]+'"') if match else ""
    fc = bag.fcurves.find(path, index=index)
    if fc is None:
        return bag.fcurves.new(path, index=index, group_name=name)
    if name and (fc.group is None or fc.group.name != name):
        fc.group = bag.groups.get(name) or bag.groups.new(name)
    return fc


def group_channels(action):
    """Repair presentation metadata only; FCurve data paths/keys stay intact."""
    changed = 0
    for bag in bags(action):
        # Assignment can reorder a channelbag; don't iterate its live collection.
        for fc in list(bag.fcurves):
            match = PATH.match(fc.data_path)
            if not match:
                continue
            name = json.loads('"'+match[1]+'"')
            if fc.group is None or fc.group.name != name:
                fc.group = bag.groups.get(name) or bag.groups.new(name)
                changed += 1
    return changed


def fill_curve(bag, path, index, times, values, interpolation='LINEAR'):
    fc = ensure_curve(bag, path, index)
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(times))
    fc.keyframe_points.foreach_set('co', [v for pair in zip(times, values) for v in pair])
    for k in fc.keyframe_points:
        k.interpolation = interpolation
    fc.update()


def make_candidate(target):
    clone = target.copy()
    clone.data = target.data.copy()
    clone.name = "__OZO_TRANSFER_VALIDATION"
    bpy.context.scene.collection.objects.link(clone)
    clone.hide_set(True)
    clone.hide_render = True
    clone.animation_data_create()
    for tr in clone.animation_data.nla_tracks:
        tr.mute = True
    for p in clone.pose.bones:
        for c in p.constraints:
            for attr in ('target', 'pole_target', 'space_object'):
                if hasattr(c, attr) and getattr(c, attr) == target:
                    setattr(c, attr, clone)
    for fc in clone.animation_data.drivers:
        for variable in fc.driver.variables:
            for dst in variable.targets:
                if dst.id == target:
                    dst.id = clone
    return clone


def compensate_parents(plan, candidate, bag):
    """Restore evaluated orientations when a mapped control changed parents.

    E.g. Shoe_Tip is parented to the man's shin but the girl's foot. A local
    basis change alone cannot preserve that motion. Solve only affected control
    rotations; retain the converted locations and the target's limb lengths.
    """
    source = plan['source']
    affected = [(sn,tn) for sn,tn in plan['mapping'].items()
                if (target_name(source.data.bones[sn].parent.name)
                    if source.data.bones[sn].parent else None)
                != (candidate.data.bones[tn].parent.name
                    if candidate.data.bones[tn].parent else None)]
    affected.sort(key=lambda pair: len(candidate.data.bones[pair[1]].parent_recursive))
    plan['compensated'] = dict(affected)
    rotations = {tn: [] for _,tn in affected}
    for frame in plan['bake_times']:
        set_frame(bpy.context.scene, frame)
        dg = bpy.context.evaluated_depsgraph_get()
        src = source.evaluated_get(dg)
        desired = {tn: src.pose.bones[sn].matrix.to_quaternion()
                   @ source.data.bones[sn].matrix_local.to_quaternion().inverted()
                   @ candidate.data.bones[tn].matrix_local.to_quaternion()
                   for sn,tn in affected}
        for _ in range(2):
            for sn,tn in affected:
                pb = candidate.pose.bones[tn]
                if rotation_error(pb.matrix.to_quaternion(),desired[tn]) < 0.0001:
                    continue
                matrix = Matrix.LocRotScale(pb.matrix.translation,desired[tn],pb.matrix.to_scale())
                kwargs = ({'parent_matrix':pb.parent.matrix,
                           'parent_matrix_local':pb.parent.bone.matrix_local} if pb.parent else {})
                basis = pb.bone.convert_local_to_pose(matrix,pb.bone.matrix_local,invert=True,**kwargs)
                q = basis.to_quaternion()
                if pb.rotation_mode == 'QUATERNION':
                    pb.rotation_quaternion = q
                else:
                    pb.rotation_euler = q.to_euler(pb.rotation_mode,pb.rotation_euler)
                candidate.update_tag()
                bpy.context.view_layer.update()
        for _,tn in affected:
            q = candidate.pose.bones[tn].matrix_basis.to_quaternion()
            if rotations[tn] and q.dot(rotations[tn][-1]) < 0:
                q.negate()
            rotations[tn].append(q)
    for _,tn in affected:
        pb = candidate.pose.bones[tn]
        qs = rotations[tn]
        if pb.rotation_mode == 'QUATERNION':
            prop,count = 'rotation_quaternion',4
        else:
            prop,count = 'rotation_euler',3
            es=[]
            for q in qs:
                es.append(q.to_euler(pb.rotation_mode,es[-1]) if es else q.to_euler(pb.rotation_mode))
            qs=es
        for i in range(count):
            fill_curve(bag,pb.path_from_id()+'.'+prop,i,plan['bake_times'],[q[i] for q in qs])
    return dict(affected)


def primary_result(name):
    # IK knee angles and distributed twist angles depend on the target's limb
    # lengths and its rig's twist distribution. Report them separately rather
    # than asserting that their source deformation matrices must be identical.
    return not re.match(r'DEF_(Leg|Shin)(?:_[0-9]+)?\.[LR]$',name) and not re.match(
        r'DEF_(Arm|Forarm)_[0-9]+\.[LR]$',name)


def validate(plan, candidate):
    """Compare evaluated deformation rotations, not converted input channels."""
    source, target = plan['source'], plan['target']
    scene = bpy.context.scene
    result = {"samples": len(plan['verify_times']), "step_frames": plan['verify_step'],
              "result_rotation_max_deg": 0.0, "result_worst": None,
              "control_rotation_max_deg": 0.0, "control_worst": None,
              "dependent_rotation_max_deg": 0.0,
              "arm_reference_rotation_max_deg": 0.0,
              "control_location_max_error": 0.0, "control_scale_max_error": 0.0,
              "native_setting_max_error": 0.0,
              "root_matrix_max_error": 0.0, "per_bone": {}, "root_motion": "PRESERVE",
              "knee_plane_min_dot": 1.0, "leg_stretch_max": 1.0}
    common = [b.name for b in source.data.bones if b.use_deform and b.name in candidate.data.bones]
    for frame in plan['verify_times']:
        set_frame(scene, frame)
        dg = bpy.context.evaluated_depsgraph_get()
        s, t = source.evaluated_get(dg), candidate.evaluated_get(dg)
        for rig in (s, t):
            mode = rig.pose.bones['Properties']
            for key, expected in (('Arm_FK_IK.L', 0), ('Arm_FK_IK.R', 0),
                                  ('Leg_FK_IK.L', 1), ('Leg_FK_IK.R', 1)):
                if abs(mode.get(key, -99) - expected) > 1e-6:
                    raise ValueError(f'Frame {frame}: calibrated mode is FK arms / IK legs')
        for path in plan['native_settings']:
            result['native_setting_max_error'] = max(result['native_setting_max_error'],
                abs(s.path_resolve(path)-t.path_resolve(path)))
        for sn, tn in plan['mapping'].items():
            # Twist/helper behavior differs slightly between these rigs. Input
            # matrix_basis conversion is additionally checked for all controls.
            c = t.data.bones[tn].matrix_local.to_quaternion().inverted() @ s.data.bones[sn].matrix_local.to_quaternion()
            if tn in plan.get('arm_twist_controls',set()):
                # These controls are fitted against independently evaluated
                # result-bone goals below, not their old uncorrected inputs.
                err = 0.0
            elif sn in plan.get('compensated',{}):
                expected = s.pose.bones[sn].matrix.to_quaternion() @ s.data.bones[sn].matrix_local.to_quaternion().inverted() @ t.data.bones[tn].matrix_local.to_quaternion()
                err = rotation_error(expected,t.pose.bones[tn].matrix.to_quaternion())
            else:
                expected = c @ s.pose.bones[sn].matrix_basis.to_quaternion() @ c.inverted()
                err = rotation_error(expected, t.pose.bones[tn].matrix_basis.to_quaternion())
            if err > result['control_rotation_max_deg']:
                result['control_rotation_max_deg'] = err
                result['control_worst'] = [frame, sn]
            expected_location = c @ s.pose.bones[sn].location
            result['control_location_max_error'] = max(result['control_location_max_error'],
                (t.pose.bones[tn].location-expected_location).length)
            result['control_scale_max_error'] = max(result['control_scale_max_error'],
                (t.pose.bones[tn].scale-s.pose.bones[sn].scale).length)
            for key,value in numeric_properties(s.pose.bones[sn]).items():
                if key in t.pose.bones[tn] and abs(t.pose.bones[tn][key]-value)>1e-5:
                    raise ValueError(f"Custom property mismatch at {frame}: {tn}/{key}")
        for name in common:
            a = s.pose.bones[name].matrix.to_quaternion() @ s.data.bones[name].matrix_local.to_quaternion().inverted()
            b = t.pose.bones[name].matrix.to_quaternion() @ t.data.bones[name].matrix_local.to_quaternion().inverted()
            if name in plan.get('arm_reference_results',{}):
                expected = arm_twist.reference(s,t,name,plan['arm_reference_results'][name])
                err = rotation_error(expected,t.pose.bones[name].matrix.to_quaternion())
                result['arm_reference_rotation_max_deg'] = max(result['arm_reference_rotation_max_deg'],err)
            else:
                err = rotation_error(a, b)
            prior = result['per_bone'].get(name, {'degrees': -1})
            if err > prior['degrees']:
                result['per_bone'][name] = {'degrees': err, 'frame': frame}
            if not primary_result(name):
                result['dependent_rotation_max_deg'] = max(result['dependent_rotation_max_deg'],err)
            elif err > result['result_rotation_max_deg']:
                result['result_rotation_max_deg'] = err
                result['result_worst'] = [frame, name]
        for side in ('L','R'):
            planes=[]
            for rig in (s,t):
                hip=rig.pose.bones['DEF_Leg.'+side].head
                knee=rig.pose.bones['DEF_Shin.'+side].head
                ankle=rig.pose.bones['DEF_Foot.'+side].head
                plane=(knee-hip).cross(ankle-knee)
                planes.append(plane.normalized() if plane.length>1e-6 else None)
            if all(p is not None for p in planes):
                result['knee_plane_min_dot'] = min(result['knee_plane_min_dot'],planes[0].dot(planes[1]))
            for part in ('Leg','Shin'):
                n='DEF_'+part+'.'+side
                result['leg_stretch_max']=max(result['leg_stretch_max'],t.pose.bones[n].length/t.data.bones[n].length)
        for name in ROOTS:
            a, b = s.pose.bones[name].matrix, t.pose.bones[name].matrix
            result['root_matrix_max_error'] = max(result['root_matrix_max_error'],
                max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4)))
    result['passed'] = (result['result_rotation_max_deg'] <= ROTATION_LIMIT
                        and result['control_rotation_max_deg'] <= CONTROL_LIMIT
                        and result['arm_reference_rotation_max_deg'] <= CONTROL_LIMIT
                        and result['control_location_max_error'] <= LOCATION_LIMIT
                        and result['control_scale_max_error'] <= 1e-4
                        and result['native_setting_max_error'] <= 1e-6
                        and result['root_matrix_max_error'] <= 2e-5
                        and result['knee_plane_min_dot'] > 0
                        and result['leg_stretch_max'] <= 1.05)
    return result


def convert(source, target, start=None, end=None, step=0.5, name="", commit=True,
            validator=None):
    """Transactional conversion; return (new Action, JSON-compatible report).

    commit=False validates and returns a retained Action without switching target.
    validator is an internal test hook for exercising rollback.
    """
    plan = preflight(source, target, start, end, step)
    scene = bpy.context.scene
    old_frame, old_sub = scene.frame_current, scene.frame_subframe
    original = target.animation_data.action if target.animation_data else None
    original_slot = target.animation_data.action_slot if target.animation_data else None
    source_hash = action_digest(plan['action'])
    target_hash = action_digest(original) if original else None
    new = clone = None
    succeeded = False
    report = {'source': source.name, 'target': target.name,
              'source_action': plan['action'].name,
              'original_target_action': original.name if original else None,
              'range': [plan['start'], plan['end']], 'bake_step': step,
              'mapping': plan['mapping'], 'skipped_identity_controls': plan['skipped'],
              'preserved_native_settings': plan['native_settings'],
              'source_only_properties': [], 'support': 'Calibrated Man/Girl; FK arms / IK legs',
              'limits': {'result_rotation_degrees': ROTATION_LIMIT,
                         'control_interpolation_degrees': CONTROL_LIMIT}}
    try:
        # Source is sampled completely before any candidate is bound. This also
        # captures unkeyed controls and mode settings, not just named FCurves.
        values = {tn: [] for tn in plan['mapping'].values()}
        props = {tn: [] for tn in plan['mapping'].values()}
        corrections = {sn: target.data.bones[tn].matrix_local.to_quaternion().inverted()
                       @ source.data.bones[sn].matrix_local.to_quaternion()
                       for sn, tn in plan['mapping'].items()}
        previous = {}
        for frame in plan['bake_times']:
            set_frame(scene, frame)
            p = source.pose.bones['Properties']
            if any(abs(p.get(key, -99)-expected) > 1e-6 for key, expected in
                   (('Arm_FK_IK.L', 0), ('Arm_FK_IK.R', 0),
                    ('Leg_FK_IK.L', 1), ('Leg_FK_IK.R', 1))):
                raise ValueError(f"Frame {frame}: calibrated mode is FK arms / IK legs")
            for sn in plan['skipped']:
                b = source.pose.bones[sn].matrix_basis
                if max(abs(b[i][j]-(1 if i==j else 0)) for i in range(4) for j in range(4)) > 2e-5:
                    raise ValueError(f"Unmapped non-identity source control at {frame}: {sn}")
            for sn, tn in plan['mapping'].items():
                p = source.pose.bones[sn]
                loc, q, scale = p.matrix_basis.decompose()
                if max(scale)-min(scale) > 2e-5 or min(scale) <= 0:
                    raise ValueError(f"Nonuniform/negative local scale at {frame}: {sn}")
                c = corrections[sn]
                q = (c @ q @ c.inverted()).normalized()
                if tn in previous and q.dot(previous[tn]) < 0:
                    q.negate()
                previous[tn] = q.copy()
                values[tn].append((c @ loc, q, scale))
                props[tn].append(numeric_properties(p))
        new = plan['action'].copy()
        new.name = name or plan['action'].name + '_Girl'
        new.use_frame_range = True
        new.frame_start = plan['start']
        new.frame_end = plan['end']
        slot = new.slots[plan['slot'].identifier]
        bag = new.layers[0].strips[0].channelbag(slot)
        # Retain exact root FCurves (handles and interpolation included). All other
        # transforms are replaced, removing obsolete names and duplicate paths.
        for fc in list(bag.fcurves):
            match = PATH.match(fc.data_path)
            sn = json.loads('"'+match[1]+'"')
            if fc.data_path in plan['native_settings']:
                continue
            if sn in ROOTS and match[2].startswith('.'):
                continue
            bag.fcurves.remove(fc)
        for sn, tn in plan['mapping'].items():
            pb = target.pose.bones[tn]
            if pb.rotation_mode == 'AXIS_ANGLE':
                raise ValueError(f"Axis Angle target control unsupported: {tn}")
            path = pb.path_from_id()
            rotations = [v[1] for v in values[tn]]
            rotation_prop, rotation_count = 'rotation_quaternion', 4
            if pb.rotation_mode != 'QUATERNION':
                rotation_prop, rotation_count = 'rotation_euler', 3
                eulers = []
                for q in rotations:
                    eulers.append(q.to_euler(pb.rotation_mode, eulers[-1]) if eulers
                                  else q.to_euler(pb.rotation_mode))
                rotations = eulers
            for prop, count, component in [('location',3,0),(rotation_prop,rotation_count,1),('scale',3,2)]:
                for i in range(count):
                    if sn in ROOTS:
                        # Unkeyed root components must be explicit as well.
                        if bag.fcurves.find(path+'.'+prop, index=i):
                            continue
                    fill_curve(bag, path+'.'+prop, i, plan['bake_times'],
                               [v[i] for v in rotations] if component == 1 else
                               [v[component][i] for v in values[tn]])
            propnames = set().union(*(p.keys() for p in props[tn]))
            for key in sorted(propnames):
                if key not in pb:
                    if sn == 'ROOT' and key == '根运动Y':
                        report['source_only_properties'].append('ROOT/根运动Y (source UI/limit flag)')
                        continue
                    raise ValueError(f"Target lacks custom property: {tn}/{key}")
                # Copy keyed property curves exactly, including constant switches.
                sourcepath = source.pose.bones[sn].path_from_id()+'['+json.dumps(key,ensure_ascii=False)+']'
                original_fc = plan['bag'].fcurves.find(sourcepath)
                destpath = path+'['+json.dumps(key,ensure_ascii=False)+']'
                if original_fc:
                    copy_fcurve(original_fc, bag, destpath)
                else:
                    fill_curve(bag,destpath,0,plan['bake_times'],[v[key] for v in props[tn]],'CONSTANT')
        clone = make_candidate(target)
        clone.animation_data.action = new
        clone.animation_data.action_slot = slot
        clone.update_tag()
        report['parent_compensation'] = compensate_parents(plan,clone,bag)
        report['arm_twist_fit'] = arm_twist.fit(plan,clone,bag,sys.modules[__name__])
        group_channels(new)
        report['channel_group_count'] = len(bag.groups)
        report['ungrouped_curve_count'] = sum(fc.group is None for fc in bag.fcurves)
        report['validation'] = (validator or validate)(plan, clone)
        if not report['validation']['passed']:
            raise ValueError("Validation failed: "+json.dumps({k:v for k,v in report['validation'].items()
                if k!='per_bone'},ensure_ascii=False))
        if action_digest(plan['action']) != source_hash or (original and action_digest(original) != target_hash):
            raise RuntimeError("Original Action changed during evaluation; conversion cancelled")
        report['source_curves_unchanged'] = True
        report['original_target_curves_unchanged'] = True
        report['new_action'] = new.name
        report['slot'] = slot.identifier
        report['committed'] = bool(commit)
        new['ozo_transfer_report'] = json.dumps(report,ensure_ascii=False)
        new.use_fake_user = True
        if commit:
            target.animation_data_create()
            target.animation_data.action = new
            target.animation_data.action_slot = slot
            if original:
                original.use_fake_user = True
        succeeded = True
        return new, report
    finally:
        if clone:
            data = clone.data
            bpy.data.objects.remove(clone, do_unlink=True)
            bpy.data.armatures.remove(data)
        if not succeeded:
            if target.animation_data:
                target.animation_data.action = original
                if original_slot:
                    target.animation_data.action_slot = original_slot
            if new:
                bpy.data.actions.remove(new)
        scene.frame_set(old_frame, subframe=old_sub)
        target.update_tag()
        bpy.context.view_layer.update()


def copy_fcurve(source, bag, path):
    fc = ensure_curve(bag, path, source.array_index)
    fc.extrapolation = source.extrapolation
    fc.keyframe_points.add(len(source.keyframe_points))
    for src, dst in zip(source.keyframe_points, fc.keyframe_points):
        dst.co = src.co
        dst.interpolation = src.interpolation
        dst.easing = src.easing
        dst.amplitude, dst.back, dst.period = src.amplitude, src.back, src.period
        dst.handle_left_type, dst.handle_right_type = src.handle_left_type, src.handle_right_type
        dst.handle_left, dst.handle_right = src.handle_left, src.handle_right
    fc.update()
