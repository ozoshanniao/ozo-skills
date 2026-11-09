"""Read evaluated hand surfaces for contact QA. No scene edits."""
from mathutils.bvhtree import BVHTree


def hand_surfaces(obj, depsgraph):
    ev = obj.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    try:
        positions = [ev.matrix_world @ v.co for v in mesh.vertices]
        result = {}
        for side in ('L','R'):
            palm_groups = {g.index for g in obj.vertex_groups if g.name == 'DEF_Hand.'+side
                           or g.name in [f'DEF_Palm_{letter}.{side}' for letter in 'BCDE']}
            hand_groups = {g.index for g in obj.vertex_groups if g.name.endswith('.'+side)
                           and g.name.startswith(('DEF_Hand','DEF_Palm','DEF_Finger'))}
            palm = {v.index for v in mesh.vertices
                    if sum(g.weight for g in v.groups if g.group in palm_groups)>0.5}
            hand = {v.index for v in mesh.vertices
                    if sum(g.weight for g in v.groups if g.group in hand_groups)>0.5}
            palm_faces = [tuple(p.vertices) for p in mesh.polygons if all(v in palm for v in p.vertices)]
            hand_faces = [tuple(p.vertices) for p in mesh.polygons if all(v in hand for v in p.vertices)]
            result[side] = {'points':[positions[i] for i in palm],
                            'bvh':BVHTree.FromPolygons(positions,palm_faces,all_triangles=False),
                            'hand_bvh':BVHTree.FromPolygons(positions,hand_faces,all_triangles=False),
                            'palm_vertex_count':len(palm),'palm_face_count':len(palm_faces)}
        return result
    finally:
        ev.to_mesh_clear()


def distances(obj, depsgraph):
    surfaces=hand_surfaces(obj,depsgraph)
    palm_min=float('inf');hand_min=float('inf')
    nearest_pair=None
    for side,other in [('L','R'),('R','L')]:
        for point in surfaces[side]['points']:
            location,normal,index,distance=surfaces[other]['bvh'].find_nearest(point)
            if distance is not None and distance<palm_min:
                palm_min=distance;nearest_pair=[list(point),list(location)]
            location,normal,index,distance=surfaces[other]['hand_bvh'].find_nearest(point)
            if distance is not None:hand_min=min(hand_min,distance)
    return {'palm_surface_distance':palm_min,'palm_to_hand_distance':hand_min,
            'palm_triangle_intersections':len(surfaces['L']['bvh'].overlap(surfaces['R']['bvh'])),
            'nearest_pair':nearest_pair,
            'surface_counts':{side:[s['palm_vertex_count'],s['palm_face_count']] for side,s in surfaces.items()}}
