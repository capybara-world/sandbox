#!/usr/bin/env python

import sys
import bpy, bmesh
import numpy as np
from random import choices, seed, uniform
from mathutils.bvhtree import BVHTree
from mathutils import Vector
import colorsys
import os


def geo_mesh_center(obj):
    x, y, z = [sum([v.co[i] for v in obj.data.vertices]) for i in range(3)]
    count = float(len(obj.data.vertices))
    center = obj.matrix_world @ (Vector((x, y, z )) / count)

    return center


def polies_inside_of(mesh, bbox):
    def get_quartile(quartile):
        return [quartile([corner[i] for corner in bbox]) for i in range(3)]

    maxs, mins = get_quartile(max), get_quartile(min)

    return len(list(filter(lambda v : all([mins[i] < pos < maxs[i] for i, pos in enumerate(v.co)]), mesh.vertices)))


# This file cannot be used as a module
if __name__ != "__main__":
    sys.exit(1)

seed()

# Determine where items should be placed on the capybaras
accessory_relative_locations = {}

# TODO: Remove light
parts = {
    "Base Capybara",
    "Base Capybara Eye(left)",
    "Base Capybara Eye(right)",
    "Base Capybara Nose",
    "Light",
}

capybara = bpy.data.objects["Base Capybara"]
eye = bpy.data.objects["Base Capybara Eye(left)"]

capybaras = list(filter(
    lambda obj: obj.name == "Base Capybara" or "capybara" in obj.name.lower(), bpy.data.objects
))

for obj in bpy.context.selected_objects:
    obj.select_set(False)

for obj in bpy.data.objects:
    obj.hide_set(obj.name not in parts)
    obj.hide_render = obj.name not in parts

# BEGIN BASE COAT COLOR RANDOMIZATION

# Calculate the most common material to find the fur material
material_occurrences = {}
most_common, most_occ = None, 0

for f in capybara.data.polygons:
    mat_idx = f.material_index

    if mat_idx not in material_occurrences:
        material_occurrences[mat_idx] = 0

    material_occurrences[mat_idx] += 1

    if (curr_occ := material_occurrences[mat_idx]) > most_occ:
        most_occ = curr_occ
        most_common = mat_idx

base_coat_colors = (
    capybara.material_slots[most_common]
    .material.node_tree.nodes["ColorRamp"]
    .color_ramp
)

# Determine where to place all accessories on the capybaras
# The different types of accessories, each type containing items that cannot be placed on the same capybara
# at the same time because they would overlap
accessory_relative_locs = {}
accessory_sets = []

all_accessories = list(
    filter(
        lambda obj: hasattr(obj.data, "polygons")
        and obj.name not in parts
        and "capybara" not in obj.name.lower()
        and (
            len(obj.data.polygons) != len(eye.data.polygons)
            or len(obj.data.vertices) != len(eye.data.vertices)
            or len(obj.data.edges) != len(eye.data.edges)
        ),
        bpy.data.objects,
    )
)

# The geometric positions of all capybaras
capy_geo_pos = {}

for accessory in all_accessories:
    # Determine which capybara the accessory is on
    most_likely_base = (None, 0.00)

    # Find the distance between center of capy geometry and accessory geometry
    acc_geo_pos = geo_mesh_center(accessory)

    for base in capybaras:
        if base not in capy_geo_pos:
            capy_geo_pos[base] = geo_mesh_center(base)

        if (dist_acc_base := abs((capy_geo_pos[base] - acc_geo_pos).length)) < most_likely_base[1] or most_likely_base[0] is None and dist_acc_base < 10.0:
            most_likely_base = (base, dist_acc_base)

    # Extraneous objects not part of the capybara accessories
    if most_likely_base[0] is None:
        continue

    base = most_likely_base[0]

    relative_loc = accessory.location[1] - base.location[1]
    accessory_relative_locs[accessory.name] = relative_loc

    # Re-position the accessory
    accessory.location.y = capybara.location[1] + relative_loc
    bpy.context.view_layer.update()
    abs_loc = accessory.matrix_world

    found_set = False

    # See if this accessory would overlap with an accessory in the set. If so, insert it in that set
    for (crit_bbox, acc_set) in accessory_sets:
        if found_set := polies_inside_of(accessory.data, crit_bbox) > 20:
            acc_set.append(accessory.name)

            break

    if not found_set:
        accessory_sets.append((accessory.bound_box, [accessory.name]))

for (i, (acc_set, set_members)) in enumerate(accessory_sets):
    for mem in set_members:
        bpy.data.objects[mem].hide_set(False)
        bpy.data.objects[mem].hide_render = False

    bpy.context.scene.render.filepath = f"/home/dowlandaiello/Downloads/hmm{i}.png"
    bpy.ops.render.render(animation=False, use_viewport=False, write_still=True)

    for mem in set_members:
        bpy.data.objects[mem].hide_set(True)
        bpy.data.objects[mem].hide_render = True

sys.exit(0)

# Generate 16 different colors per capy
for i in range(16):
    # Uniform distribution of colors, but VERY rare translucent capybaras
    hsv = [
        np.random.beta(a=400, b=400) - 0.48,
        np.random.beta(a=65, b=30),
        np.random.beta(a=7, b=40),
    ]
    a = choices([1.0, 0.6], [0.95, 0.05])[0]

    base_coat_colors.elements[1].color = (*colorsys.hsv_to_rgb(*hsv), a)

    print(list(hsv))

    # All animals have a difuse

    hsv[1] -= 0.05
    hsv[2] -= 0.075

    base_coat_colors.elements[0].color = (*colorsys.hsv_to_rgb(*hsv), a)

    print(list(hsv))

    # Export the capybara to a GLB
    capybara.select_set(True)
    # bpy.ops.export_scene.gltf(filepath=f"out/{capybara.name}_{''.join([str(i) for i in hsv])}.glb", use_selection=True, export_materials="EXPORT")
    # bpy.ops.wm.save_as_mainfile(filepath="/home/dowlandaiello/hi.blend")
    # capybara.select_set(False)
