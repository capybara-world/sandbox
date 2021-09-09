#!/usr/bin/env python

import sys
import bpy, bmesh
from threading import Thread
import time
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


def main():
    seed()

    start = time.time()
    print("IDENTIFYING COMPONENTS")

    # TODO: Remove light
    parts = {
        "Base Capybara",
        "Base Capybara Eye(left)",
        "Base Capybara Eye(right)",
        "Base Capybara Nose",
    }

    capybara = bpy.data.objects["Base Capybara"]
    eye = bpy.data.objects["Base Capybara Eye(left)"]

    capybaras = list(filter(
        lambda obj: obj.name == "Base Capybara" or "capybara" in obj.name.lower() and "eye" not in obj.name.lower() and "nose" not in obj.name.lower(), bpy.data.objects
    ))
    cameras = list(filter(lambda obj : "camera" in obj.name.lower(), bpy.data.objects))

    print(f"DONE (took {time.time() - start}s)")

    start = time.time()
    print("NORMALIZING COMPONENT ORIGINS")

    for obj in bpy.data.objects:
        # Normalize all locations to their geometric centers
        for o in bpy.context.selected_objects:
            o.select_set(False)
        obj.select_set(True)

        bpy.context.scene.cursor.location = geo_mesh_center(obj)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

        obj.select_set(False)
        obj.hide_set(obj.name not in parts)
        obj.hide_render = obj.name not in parts

    print(f"DONE (took {time.time() - start}s)")

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

    start = time.time()
    print("IDENTIFYING ACCESSORIES")

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

    print(f"DONE (took {time.time() - start}s)")

    # The BVH trees of all capybaras, which with an item must intersect in order to be its child
    capy_geo_pos = {}

    start = time.time()
    print("GENERATING ACCESSORY SETS")

    for accessory in all_accessories:
        # Determine which capybara the accessory is on
        most_likely_base = (None, 0.00)

        # Find the distance between the center of capy geometry and accessory geometry
        acc_geo_pos = accessory.location

        for base in capybaras:
            if base not in capy_geo_pos:
                capy_geo_pos[base] = base.location

            dist = abs(capy_geo_pos[base][1] - acc_geo_pos[1])

            if dist <= most_likely_base[1] or (most_likely_base[0] is None and dist < 10.0):
                most_likely_base = (base, dist)

        # Extraneous objects not part of the capybara accessories
        if most_likely_base[0] is None:
            continue

        base = most_likely_base[0]

        print(accessory.name, base.name)

        relative_loc = acc_geo_pos[1] - capy_geo_pos[base][1]
        accessory_relative_locs[accessory.name] = relative_loc

        # Re-position the accessory
        accessory.location.y = capybara.location[1] + relative_loc
        bpy.context.view_layer.update()

        set_x_disps = []

        acc_geo_pos = accessory.location

        # See if this accessory would overlap with an accessory in the set. If so, insert it in that set
        for i, (pos, acc_set) in enumerate(accessory_sets):
            displacement = abs(acc_geo_pos[0] - pos[0])
            set_x_disps.append((i, displacement))

        try:
            closest_set = min(set_x_disps, key=lambda item : item[1])
            assert closest_set[1] <= 1.00

            accessory_sets[closest_set[0]][1].append(accessory.name)
        except (ValueError, AssertionError):
            accessory_sets.append((acc_geo_pos, [accessory.name]))

    print(f"DONE (took {time.time() - start}s)")

    start = time.time()
    print("GENERATING CAPYBARAS")

    bpy.data.objects["Light"].hide_set(False)
    bpy.data.objects["Light"].hide_render = False

    # Generate 16 different colors per capy
    for i in range(16):
        # Uniform distribution of colors, but VERY rare translucent capybaras
        hsv = [
            np.random.beta(a=400, b=400) - 0.48,
            np.random.beta(a=65, b=30),
            np.random.beta(a=7, b=20),
        ]
        a = choices([1.0, 0.6], [0.95, 0.05])[0]

        base_coat_colors.elements[1].color = (*colorsys.hsv_to_rgb(*hsv), a)

        print(list(hsv))

        # All animals have a difuse

        hsv[1] -= 0.05
        hsv[2] -= 0.075

        base_coat_colors.elements[0].color = (*colorsys.hsv_to_rgb(*hsv), a)

        start = time.time()
        print(f"GENERATING HAT COMBINATIONS FOR COLOR {i}")

        # Generate all possible combinations of accessories
        for j, acc_name in enumerate(accessory_sets[0][1]):
            acc = bpy.data.objects[acc_name]

            acc.hide_set(False)
            acc.hide_render = False

            start = time.time()
            print(f"GENERATING MIDDLE ACC COMBINATIONS FOR HAT {j}")

            for k, secondary_name in enumerate(accessory_sets[1][1]):
                secondary = bpy.data.objects[secondary_name]

                secondary.hide_set(False)
                secondary.hide_render = False

                start = time.time()
                print(f"GENERATING FINAL ACC COMBINATIONS FOR MIDDLE {k}")

                for l, tertiary_name in enumerate(accessory_sets[2][1]):
                    tertiary = bpy.data.objects[tertiary_name]

                    tertiary.hide_set(False)
                    tertiary.hide_render = False

                    # Render the capybara with all of the available cameras
                    for cam in cameras:
                        start = time.time()
                        print(f"RENDERING WITH CAMERA {cam.name}")

                        bpy.context.scene.camera = cam
                        bpy.context.scene.render.filepath = f"/home/dowlandaiello/Downloads/capy_renders/{i}_{j}_{k}_{l}/{cam.name}.png"

                        bpy.ops.render.render(animation=False, use_viewport=False, write_still=True)

                        print(f"DONE (took {time.time() - start}s)")

                    tertiary.hide_set(True)
                    tertiary.hide_render = True
                secondary.hide_set(True)
                secondary.hide_render = True
            acc.hide_set(True)
            acc.hide_render = True
            
            print(f"DONE (took {time.time() - start})")
        print(f"DONE (took {time.time() - start})")
    print(f"DONE (took {time.time() - start})")

# This file cannot be used as a module
if __name__ == "__main__":
    main()
