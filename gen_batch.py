#!/usr/bin/env python

import sys
import json
import bpy, bmesh
from threading import Thread
import time
import numpy as np
from random import choices, seed, uniform
from math import ceil
from mathutils.bvhtree import BVHTree
from mathutils import Vector
import colorsys
import os

N_COAT_COLOR_SAMPLES, N_ACC_COLOR_SAMPLES = 16, 32


def obj_primary_material(obj):
    """
    Determines the primary material of an object based on the number of its occurrences on the object.
    """
    material_occurrences = {}
    most_common, most_occ = None, 0

    for f in obj.data.polygons:
        mat_idx = f.material_index

        if mat_idx not in material_occurrences:
            material_occurrences[mat_idx] = 0

        material_occurrences[mat_idx] += 1

        if (curr_occ := material_occurrences[mat_idx]) > most_occ:
            most_occ = curr_occ
            most_common = mat_idx

    return most_common


def geo_mesh_center(o):
    local_bbox_center = 0.125 * sum((Vector(b) for b in o.bound_box), Vector())
    global_bbox_center = o.matrix_world @ local_bbox_center

    return global_bbox_center


def render_sets(
    acc_sets, out_path, log_prefix, cameras, fur_color_dist, acc_color_dist, n_mats_randomized_dist
):
    for acc_name in acc_sets[0][1]:
        acc = acc_name and bpy.data.objects[acc_name]

        node_orig_colors = {}

        for i in range(N_ACC_COLOR_SAMPLES + 1):
            n_mats_randomizable = ceil(np.random.beta(a=n_mats_randomized_dist[0], b=n_mats_randomized_dist[1]) * len(acc.material_slots))

            # Change the color of the accessory
            for mat in acc.material_slots[:n_mats_randomizable]:
                if "Principled BSDF" in mat.material.node_tree.nodes:
                    # All accessories have a BSDF, but nothing else to vary
                    node = mat.material.node_tree.nodes["Principled BSDF"]

                    # Allow one pass with default material
                    if i == 0:
                        node_orig_colors[node] = node.inputs["Base Color"].default_value

                        continue

                    hsvoff = (
                        np.random.beta(a=acc_color_dist[0][0], b=acc_color_dist[0][1])
                        - 0.5,
                        np.random.beta(a=acc_color_dist[1][0], b=acc_color_dist[1][1])
                        - 0.5,
                        np.random.beta(a=acc_color_dist[2][0], b=acc_color_dist[2][1])
                        - 0.5,
                    )
                    alpha = np.random.beta(
                        a=acc_color_dist[3][0], b=acc_color_dist[3][1]
                    )
                    hsv = colorsys.rgb_to_hsv(
                        *[
                            orig + hsvoff
                            for orig, hsvoff in zip(node_orig_colors[node][:-1], hsvoff)
                        ]
                    )

                    node.inputs["Base Color"].default_value = (
                        *colorsys.hsv_to_rgb(*hsv),
                        alpha,
                    )

                if acc:
                    acc.hide_set(False)
                    acc.hide_render = False


                # Render at leaf
                if len(acc_sets) == 1:
                    print(f"{log_prefix}RENDERING")

                    for cam in cameras:
                        start = time.time()
                        print(f"{log_prefix}RENDERING WITH CAMERA {cam.name}")

                        bpy.context.scene.camera = cam
                        bpy.context.scene.render.filepath = f"{out_path}/color_{i}/{cam.name}.png"

                        bpy.ops.render.render(
                            animation=False, use_viewport=False, write_still=True
                        )

                        print(f"{log_prefix}DONE (took {time.time() - start}s)")
                # Continue depth-first traversal
                else:
                    start = time.time()
                    print(f"{log_prefix}GENERATING COMBINATIONS FOR PARENT {acc_name}")

                    # Generate combinations + different colors
                    render_sets(
                        acc_sets[1:],
                        f"{out_path}/{acc_name}",
                        log_prefix + "\t",
                        cameras,
                        fur_color_dist,
                        acc_color_dist,
                        n_mats_randomized_dist
                    )

                    print(f"{log_prefix}DONE (took {time.time() - start}s)")

                if acc:
                    acc.hide_set(True)
                    acc.hide_render = True


def main():
    assert ".json" in sys.argv[-1], "A JSON config file path must be provided"

    # Determine values for beta curves used in randomness from a config
    fur_color_dist, acc_color_dist, n_mats_randomized_dist = None, None, None

    with open(sys.argv[-1]) as f:
        fur_color_dist, acc_color_dist, n_mats_randomized_dist = json.load(f).values()

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

    capybaras = list(
        filter(
            lambda obj: obj.name == "Base Capybara"
            or "capybara" in obj.name.lower()
            and "eye" not in obj.name.lower()
            and "nose" not in obj.name.lower(),
            bpy.data.objects,
        )
    )
    cameras = list(filter(lambda obj: "camera" in obj.name.lower(), bpy.data.objects))

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
    most_common = obj_primary_material(capybara)

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

            if dist <= most_likely_base[1] or (
                most_likely_base[0] is None and dist < 10.0
            ):
                most_likely_base = (base, dist)

        # Extraneous objects not part of the capybara accessories
        if most_likely_base[0] is None:
            continue

        base = most_likely_base[0]

        relative_loc = acc_geo_pos - capy_geo_pos[base]
        accessory_relative_locs[accessory.name] = relative_loc

        # Re-position the accessory
        accessory.location = capybara.location + relative_loc
        bpy.context.view_layer.update()

        set_x_disps = []

        acc_geo_pos = accessory.location

        acc_bmesh = bmesh.new()
        acc_bmesh.from_mesh(accessory.data)
        acc_bmesh.transform(accessory.matrix_world)

        acc_tree = BVHTree.FromBMesh(acc_bmesh)

        # See if this accessory would overlap with an accessory in the set. If so, insert it in that set
        for i, ((pos, crit_tree), acc_set) in enumerate(accessory_sets):
            displacement = abs(acc_geo_pos[0] - pos[0])

            if (
                len(acc_tree.overlap(crit_tree)) == 0
                and abs((acc_geo_pos - pos).length) > 0.5
            ):
                continue

            set_x_disps.append((i, displacement))

        try:
            closest_set = min(set_x_disps, key=lambda item: item[1])
            assert closest_set[1] <= 1.00

            accessory_sets[closest_set[0]][1].append(accessory.name)
        except (ValueError, AssertionError):
            accessory_sets.append(((acc_geo_pos, acc_tree), [accessory.name]))

    print(f"DONE (took {time.time() - start}s)")

    start = time.time()
    print("GENERATING CAPYBARAS")

    bpy.data.objects["Light"].hide_set(False)
    bpy.data.objects["Light"].hide_render = False

    wh, ws, wv = colorsys.rgb_to_hsv(
        *bpy.data.worlds["World"]
        .node_tree.nodes["Background"]
        .inputs[0]
        .default_value[:-1]
    )

    # Generate 16 different colors per capy
    for i in range(N_COAT_COLOR_SAMPLES):
        # Uniform distribution of colors, but VERY rare translucent capybaras
        hsv = [
            np.random.beta(a=fur_color_dist[0][0], b=fur_color_dist[0][1]) - 0.48,
            np.random.beta(a=fur_color_dist[1][0], b=fur_color_dist[1][1]),
            np.random.beta(a=fur_color_dist[2][0], b=fur_color_dist[2][1]),
        ]
        a = choices([1.0, 0.6], [0.95, 0.05])[0]

        base_coat_colors.elements[1].color = (*colorsys.hsv_to_rgb(*hsv), a)

        # All animals have a difuse

        hsv[1] -= 0.05
        hsv[2] -= 0.075

        base_coat_colors.elements[0].color = (*colorsys.hsv_to_rgb(*hsv), a)

        start = time.time()
        print(f"GENERATING HAT COMBINATIONS FOR COLOR {i}")

        bpy.data.objects["Cylinder"].hide_set(False)
        bpy.data.objects["Cylinder"].hide_render = False

        # Generate all possible combinations of accessories. Also generate combinations
        # WITHOUT each level of accessory
        render_sets(
            accessory_sets,
            "/home/dowlandaiello/Downloads/capy_renders",
            "",
            cameras,
            fur_color_dist,
            acc_color_dist,
            n_mats_randomized_dist
        )


# This file cannot be used as a module
if __name__ == "__main__":
    main()
