#!/usr/bin/env python

import sys
import bpy
import numpy as np
from random import choices, seed, uniform
import colorsys

"""
This script separates each of the capybaras in the provided source file.

    ./separate_capybaras 'Cube.'
"""

# This file cannot be used as a module
if __name__ != "__main__":
    sys.exit(1)

seed()

CAPY_ID_SUFFIX = "Cube."
objs = set(bpy.data.objects)

occ = {}
most_common_z_pos, most_occ = 0.00, 0

for obj in objs:
    z = round(obj.location[2], 1)

    if z not in occ:
        occ[z] = 0

    occ[z] += 1

    if occ[z] > most_occ:
        most_common_z_pos = z
        most_occ = occ[z]

for obj in bpy.context.selected_objects:
    obj.select_set(False)

# Capybaras are only the ones with the specified prefix.
# Customize each one and export to GLB
for capybara in filter(
    lambda obj: CAPY_ID_SUFFIX in obj.name
    and abs(most_common_z_pos - obj.location[2]) < 1,
    objs,
):
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

    # SUS
    if "ColorRamp" not in capybara.material_slots[most_common].material.node_tree.nodes:
        continue

    base_coat_colors = (
        capybara.material_slots[most_common]
        .material.node_tree.nodes["ColorRamp"]
        .color_ramp
    )

    # Generate 16 different colors per capy
    for i in range(16):
        # Uniform distribution of colors, but VERY rare translucent capybaras
        hsv = [
            np.random.beta(a=400, b=400) - 0.48,
            np.random.beta(a=65, b=30),
            np.random.beta(a=7, b=40),
        ]
        a = choices([1.0, 0.6], [0.95, 0.05])[0]
        base_coat_colors.elements[0].color = (*colorsys.hsv_to_rgb(*hsv), a)

        print(list(hsv))

        # All animals have a difuse

        hsv[1] -= 0.05
        hsv[2] -= 0.1

        base_coat_colors.elements[1].color = (*colorsys.hsv_to_rgb(*hsv), a)

        print(list(hsv))

        # Export the capybara to a GLB
        capybara.select_set(True)
        # bpy.ops.export_scene.gltf(filepath=f"out/{capybara.name}_{''.join([str(i) for i in hsv])}.glb", use_selection=True, export_materials="EXPORT")
        # bpy.ops.wm.save_as_mainfile(filepath="/home/dowlandaiello/hi.blend")
        # capybara.select_set(False)

        break
    break
