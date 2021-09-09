#!/usr/bin/env python

import sys
import bpy, bmesh
import numpy as np
from random import choices, seed, uniform
from mathutils.bvhtree import BVHTree
from mathutils import Vector
import colorsys
import os


def geo_mesh_center(o):
    local_bbox_center = 0.125 * sum((Vector(b) for b in o.bound_box), Vector())
    global_bbox_center = o.matrix_world @ local_bbox_center

    return global_bbox_center


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
#    "Light",
}

capybara = bpy.data.objects["Base Capybara"]
eye = bpy.data.objects["Base Capybara Eye(left)"]

capybaras = list(filter(
    lambda obj: obj.name == "Base Capybara" or "capybara" in obj.name.lower() and "eye" not in obj.name.lower() and "nose" not in obj.name.lower(), bpy.data.objects
))

for obj in bpy.data.objects:
    obj.select_set(False)
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
        and obj.name != "Cylinder"
        and "capybara" not in obj.name.lower()
        and (
            len(obj.data.polygons) != len(eye.data.polygons)
            or len(obj.data.vertices) != len(eye.data.vertices)
            or len(obj.data.edges) != len(eye.data.edges)
        ),
        bpy.data.objects,
    )
)

for obj in all_accessories:
    obj.hide_set(False)

# The BVH trees of all capybaras, which with an item must intersect in order to be its child
capy_trees = {}
capy_geo_pos = {}

for accessory in all_accessories:
    # Determine which capybara the accessory is on
    most_likely_base = (None, (0, 0.00))

    # Find the distance between center of capy geometry and accessory geometry
    bmh = bmesh.new()
    bmh.from_mesh(accessory.data)
    bmh.transform(accessory.matrix_world)

    bvh_tree_pre_norm = BVHTree.FromBMesh(bmh)

    # Find the distance between the center of capy geometry and accessory geometry
    acc_geo_pos = geo_mesh_center(accessory)

    for base in capybaras:
        if base not in capy_trees:
            capy_bmh = bmesh.new()
            capy_bmh.from_mesh(base.data)
            capy_bmh.transform(base.matrix_world)

            capy_trees[base] = BVHTree.FromBMesh(capy_bmh)
            capy_geo_pos[base] = geo_mesh_center(base)

        likelihood = len((bvh_tree_pre_norm.overlap(capy_trees[base])))
        dist = abs((capy_geo_pos[base] - acc_geo_pos).length)

        print(likelihood, dist)

        if likelihood > most_likely_base[1][0] and likelihood > 0 and (dist <= most_likely_base[1][1] or most_likely_base[0] is None):
            most_likely_base = (base, (likelihood, dist))

    # Extraneous objects not part of the capybara accessories
    if most_likely_base[0] is None:
        continue

    base = most_likely_base[0]

    relative_loc = accessory.location[1] - base.location[1]
    accessory_relative_locs[accessory.name] = relative_loc

    # Re-position the accessory
    accessory.location.y = capybara.location[1] + relative_loc
    bpy.context.view_layer.update()

    bmh = bmesh.new()
    bmh.from_mesh(accessory.data)
    bmh.transform(accessory.matrix_world)

    bvh_tree = BVHTree.FromBMesh(bmh)
    set_x_disps = []

    acc_geo_pos = geo_mesh_center(accessory)

    # See if this accessory would overlap with an accessory in the set. If so, insert it in that set
    for i, (pos, acc_set) in enumerate(accessory_sets):
        displacement = abs(acc_geo_pos[0] - pos[0])
        set_x_disps.append((i, displacement))

    try:
        closest_set = min(set_x_disps, key=lambda item : item[1])
        assert closest_set[1] <= 1.00

        accessory_sets[closest_set[0]][1].append(accessory.name)
    except (ValueError, AssertionError) as e:
        accessory_sets.append((acc_geo_pos, [accessory.name]))

for obj in bpy.data.objects:
    obj.hide_set(True)

acc_set, set_members = accessory_sets[0]

for accessory in set_members:
    bpy.data.objects[accessory].hide_set(False)

raise Exception()

for (i, (acc_set, set_members)) in enumerate(accessory_sets):
    for mem in set_members:
        bpy.data.objects[mem].hide_set(False)
        bpy.data.objects[mem].hide_render = False

    bpy.context.scene.render.filepath = f"/home/dowlandaiello/Downloads/hmm{i}.png"
    bpy.ops.render.render(animation=False, use_viewport=False, write_still=True)

    for mem in set_members:
        bpy.data.objects[mem].hide_set(True)
        bpy.data.objects[mem].hide_render = True

raise Exception()

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

