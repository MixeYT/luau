"""
Stud-style asset generator for Roblox Studio.

Run headless:
    blender -b -P generate_assets.py
or with the bpy module:
    python3 generate_assets.py [--render]

Outputs (next to this script):
    Export/<Biome>/<Asset>.fbx   - one FBX per asset, import with Roblox 3D Importer
    StudAssets.blend             - every asset in one editable file (collection per biome)
    ApplyStudColors.lua          - Studio Command Bar script, generated from PALETTE
    Previews/<Biome>.png         - preview renders (only with --render)

Assets are built from boxes, prisms and pyramids. No 3D studs - the stud texture is added
in Roblox. UVs are projected in stud units (1 UV unit = 1 stud), so a stud texture tiles
once per stud on every face. The previews use a stud texture only to show how it will look.

Every asset is split into one mesh per colour. Mesh names end with the colour key
(e.g. "Torso_StoneGrey"), which ApplyStudColors.lua uses to colour the MeshParts.
"""

import math
import os
import random
import sys

import bpy
import numpy
from mathutils import Euler, Matrix, Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(ROOT, "Export")
PREVIEW_DIR = os.path.join(ROOT, "Previews")

# Roblox-style flat colours (0-255). Colour keys containing "Glow" become Neon in Studio.
PALETTE = {
    # Ground
    "Grass": (36, 222, 80),
    "GrassDark": (22, 176, 62),
    "Dirt": (204, 96, 74),
    "DirtDark": (168, 72, 58),
    # Trees
    "LeafGreen": (70, 206, 70),
    "LeafDark": (40, 164, 56),
    "Trunk": (176, 124, 150),
    "Bark": (150, 74, 56),
    "BarkDark": (112, 52, 44),
    "Wood": (196, 126, 110),
    "WoodLight": (222, 160, 136),
    "DeadWood": (140, 92, 92),
    "Apple": (222, 34, 44),
    # Rock
    "RockBlue": (146, 152, 236),
    "RockBlueDark": (112, 116, 206),
    "RockTop": (182, 186, 246),
    "StoneLilac": (152, 158, 212),
    "StoneLilacDark": (116, 120, 178),
    "StoneGrey": (163, 162, 165),
    "DarkStone": (99, 95, 98),
    "Brick": (214, 102, 72),
    # Flowers / misc
    "FlowerRed": (230, 40, 50),
    "FlowerBlue": (60, 190, 255),
    "FlowerPink": (240, 120, 200),
    "White": (242, 243, 243),
    "Yellow": (245, 205, 48),
    "Coal": (32, 32, 38),
    # Desert
    "Sand": (232, 184, 132),
    "SandDark": (214, 160, 110),
    "PyramidPink": (214, 150, 140),
    "Bone": (236, 238, 242),
    "Cactus": (96, 200, 64),
    "CactusDark": (60, 160, 52),
    # Snow
    "Snow": (240, 244, 255),
    "SnowShade": (196, 202, 236),
    "Ice": (80, 176, 255),
    "IceLight": (160, 220, 255),
    "Carrot": (255, 140, 30),
    # Market
    "StripeRed": (222, 40, 40),
    "StripeBlue": (30, 150, 240),
    "StripePurple": (140, 60, 220),
    # Sakura
    "Sakura": (238, 160, 236),
    "SakuraDark": (196, 112, 214),
    "ToriiRed": (212, 40, 44),
    "ToriiBlue": (40, 88, 180),
    "Gold": (250, 200, 40),
    "Bamboo": (84, 200, 60),
    "BambooDark": (52, 150, 46),
    # Halloween
    "Pumpkin": (255, 150, 24),
    "PumpkinDark": (226, 108, 16),
    "Stem": (96, 140, 40),
    "LanternGlow": (255, 214, 80),
    "Ghost": (248, 244, 255),
    "GhostShade": (214, 206, 242),
    "Blush": (255, 160, 200),
    "Tomb": (170, 170, 216),
    "TombDark": (130, 130, 182),
    # Props
    "WheelRim": (232, 96, 44),
    "WheelRed": (240, 40, 48),
    "WheelOrange": (255, 140, 20),
    "WheelYellow": (255, 220, 30),
    "WheelGreen": (60, 210, 60),
    "WheelCyan": (30, 200, 230),
    "WheelBlue": (40, 90, 240),
    "WheelPurple": (150, 60, 230),
    "WheelPink": (255, 70, 170),
    "PortalGlow": (90, 190, 255),
    # Golem boss
    "DarkBlue": (32, 52, 140),
    "ReallyDarkBlue": (20, 28, 88),
    "Cobalt": (16, 42, 220),
    "BrightBlue": (13, 105, 220),
    "LightBlue": (160, 220, 255),
    "RoyalPurple": (110, 40, 220),
    "BrightViolet": (170, 60, 255),
    "LightPurple": (214, 166, 255),
    "Moss": (60, 172, 60),
    "MossDark": (36, 120, 56),
    "Glow": (120, 230, 255),
}


# --------------------------------------------------------------------------------------
# Mesh builder
# --------------------------------------------------------------------------------------

def frame(position, rot=(0, 0, 0)):
    return Matrix.Translation(position) @ Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()


def circle(radius, sides, start=0.0, center=(0, 0)):
    return [(center[0] + math.cos(start + math.tau * i / sides) * radius,
             center[1] + math.sin(start + math.tau * i / sides) * radius) for i in range(sides)]


def arc(radius, from_angle, to_angle, steps, center=(0, 0)):
    return [(center[0] + math.cos(math.radians(from_angle + (to_angle - from_angle) * i / steps)) * radius,
             center[1] + math.sin(math.radians(from_angle + (to_angle - from_angle) * i / steps)) * radius)
            for i in range(steps + 1)]


class Asset:
    def __init__(self, name):
        self.name = name
        self.group = None
        # (group, color) -> [verts, faces, uvs]
        self.meshes = {}

    def _add_face(self, color, world_points, local_points, local_normal):
        assert color in PALETTE, color
        key = (self.group, color)
        if key not in self.meshes:
            self.meshes[key] = [[], [], []]
        verts, faces, uvs = self.meshes[key]

        # Project on the two local axes the face lies in, so studs follow the brick
        axis = max(range(3), key=lambda i: abs(local_normal[i]))
        u_axis, v_axis = [i for i in range(3) if i != axis]

        start = len(verts)
        for world, local in zip(world_points, local_points):
            verts.append(tuple(world))
            uvs.append((local[u_axis], local[v_axis]))
        faces.append(tuple(range(start, start + len(world_points))))

    def box(self, center, size, color, rot=(0, 0, 0), mat=None):
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        world_mat = (mat or Matrix.Identity(4)) @ frame(center, rot)

        corners = [Vector((x, y, z)) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
        quads = [
            ((0, 1, 3, 2), (-1, 0, 0)),
            ((4, 6, 7, 5), (1, 0, 0)),
            ((0, 4, 5, 1), (0, -1, 0)),
            ((2, 3, 7, 6), (0, 1, 0)),
            ((0, 2, 6, 4), (0, 0, -1)),
            ((1, 5, 7, 3), (0, 0, 1)),
        ]
        offset = Vector((sx, sy, sz))
        for indices, normal in quads:
            self._add_face(color, [world_mat @ corners[i] for i in indices],
                           [corners[i] + offset for i in indices], normal)

    def prism(self, points, z0, z1, color, mat=None):
        """Counter-clockwise 2D outline extruded along local Z. Caps are fanned, so star shapes work."""
        world_mat = mat or Matrix.Identity(4)
        count = len(points)
        cx = sum(p[0] for p in points) / count
        cy = sum(p[1] for p in points) / count

        for z, flip in ((z1, False), (z0, True)):
            center = Vector((cx, cy, z))
            for i in range(count):
                a = Vector((*points[i], z))
                b = Vector((*points[(i + 1) % count], z))
                triangle = [center, b, a] if flip else [center, a, b]
                self._add_face(color, [world_mat @ p for p in triangle], triangle, (0, 0, -1 if flip else 1))

        for i in range(count):
            a, b = points[i], points[(i + 1) % count]
            quad = [Vector((*a, z0)), Vector((*b, z0)), Vector((*b, z1)), Vector((*a, z1))]
            normal = (b[1] - a[1], a[0] - b[0], 0)
            self._add_face(color, [world_mat @ p for p in quad], quad, normal)

    def cylinder(self, center, radius, height, color, sides=12, rot=(0, 0, 0), mat=None):
        world_mat = (mat or Matrix.Identity(4)) @ frame(center, rot)
        self.prism(circle(radius, sides, math.pi / sides), -height / 2, height / 2, color, mat=world_mat)

    def pyramid(self, base_center, width, height, color, rot=(0, 0, 0), mat=None):
        h = width / 2
        world_mat = (mat or Matrix.Identity(4)) @ frame(base_center, rot)

        base = [Vector((-h, -h, 0)), Vector((h, -h, 0)), Vector((h, h, 0)), Vector((-h, h, 0))]
        apex = Vector((0, 0, height))
        self._add_face(color, [world_mat @ p for p in reversed(base)], list(reversed(base)), (0, 0, -1))
        for i in range(4):
            a, b = base[i], base[(i + 1) % 4]
            side = (a + b) / 2
            self._add_face(color, [world_mat @ a, world_mat @ b, world_mat @ apex], [a, b, apex],
                           (side.x, side.y, 0.0001))

    def beam(self, start, end, thickness, color, mat=None):
        start, end = Vector(start), Vector(end)
        direction = end - start
        rotation = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()
        world_mat = (mat or Matrix.Identity(4)) @ Matrix.Translation((start + end) / 2) @ rotation
        self.box((0, 0, 0), (thickness, thickness, direction.length + thickness * 0.3), color, mat=world_mat)

    def crystal(self, base, width, height, color, tip_color, rot=(0, 0, 0), mat=None):
        world_mat = (mat or Matrix.Identity(4)) @ frame(base, rot)
        self.box((0, 0, height / 2), (width, width, height), color, mat=world_mat)
        self.pyramid((0, 0, height), width, width * 1.3, tip_color, mat=world_mat)


# --------------------------------------------------------------------------------------
# Shared details
# --------------------------------------------------------------------------------------

def tuft(a, rng, position, colors=("Grass", "GrassDark"), height=1.0):
    x, y, z = position
    turn = rng.uniform(0, 90)
    a.box((x, y, z + height / 2), (0.3, 0.3, height), colors[0], rot=(0, 0, turn))
    for side in (-1, 1):
        blade = height * rng.uniform(0.55, 0.8)
        a.box((x + side * 0.3, y, z + blade / 2), (0.28, 0.28, blade), colors[1], rot=(0, side * 18, turn))


def tufts(a, rng, count, inner, outer, z=0, colors=("Grass", "GrassDark")):
    for _ in range(count):
        angle = rng.uniform(0, math.tau)
        distance = rng.uniform(inner, outer)
        tuft(a, rng, (math.cos(angle) * distance, math.sin(angle) * distance, z), colors, rng.uniform(0.7, 1.2))


def debris(a, rng, count, inner, outer, colors):
    for _ in range(count):
        angle = rng.uniform(0, math.tau)
        distance = rng.uniform(inner, outer)
        a.box((math.cos(angle) * distance, math.sin(angle) * distance, 0.12),
              (rng.uniform(0.6, 1.4), rng.uniform(0.4, 0.8), 0.24), rng.choice(colors),
              rot=(0, 0, rng.uniform(0, 180)))


def roots(a, rng, color, spread=2.2, count=5, thickness=0.8):
    for i in range(count):
        angle = math.tau * i / count + rng.uniform(-0.3, 0.3)
        direction = Vector((math.cos(angle), math.sin(angle), 0))
        a.beam(direction * 0.5 + Vector((0, 0, 1.4)), direction * spread + Vector((0, 0, 0.25)), thickness, color)
        a.box(direction * (spread + 0.2) + Vector((0, 0, 0.2)), (0.9, 0.9, 0.4), color,
              rot=(0, 0, math.degrees(angle)))


def grass_cap(a, rng, width, depth, top, thickness=1.2, drip=2.4, grass=("Grass", "GrassDark")):
    """Grass slab on top of a block with tabs hanging down the sides."""
    a.box((0, 0, top - thickness / 2), (width + 0.3, depth + 0.3, thickness), grass[0])

    for axis, length, half in ((0, width, depth / 2), (1, depth, width / 2)):
        for sign in (-1, 1):
            position = -length / 2
            while position < length / 2 - 0.4:
                segment = min(rng.uniform(1, 2.4), length / 2 - position)
                drop = rng.choice([0, 0, rng.uniform(0.6, drip), rng.uniform(0.6, drip)])
                if drop > 0:
                    along = position + segment / 2
                    out = sign * half
                    z = top - thickness - drop / 2 + 0.05
                    if axis == 0:
                        a.box((along, out + sign * 0.02, z), (segment, 0.34, drop + 0.1), grass[0])
                    else:
                        a.box((out + sign * 0.02, along, z), (0.34, segment, drop + 0.1), grass[0])
                position += segment

    for _ in range(int(width * depth / 14) + 2):
        tuft(a, rng, (rng.uniform(-width / 2 + 0.6, width / 2 - 0.6), rng.uniform(-depth / 2 + 0.6, depth / 2 - 0.6),
                      top), grass, rng.uniform(0.8, 1.6))


def two_tone_chunk(a, center, size, main, top, rot=(0, 0, 0)):
    a.box(center, size, main, rot=rot)
    a.box((center[0], center[1], center[2] + size[2] / 2 + 0.2), (size[0] - 0.4, size[1] - 0.4, 0.4), top, rot=rot)


# --------------------------------------------------------------------------------------
# Forest
# --------------------------------------------------------------------------------------

def grass_block(name, size, height):
    def build(rng):
        a = Asset(name)
        a.box((0, 0, height * 0.18), (size - 0.2, size - 0.2, height * 0.36), "DirtDark")
        a.box((0, 0, height * 0.6 - 0.05), (size, size, height * 0.8 - 0.1), "Dirt")
        grass_cap(a, rng, size, size, height, thickness=height * 0.2, drip=height * 0.3)
        return a
    return build


def tree_trunk(a, rng, trunk_color, height=7, branch_spread=4.5):
    a.beam((0, 0, -0.3), (0, 0, height), 1.8, trunk_color)
    roots(a, rng, trunk_color)

    ends = []
    for i in range(3):
        angle = math.radians(i * 120 + rng.uniform(-20, 20))
        tip = Vector((math.cos(angle) * branch_spread, math.sin(angle) * branch_spread * 0.6,
                      height + rng.uniform(3, 4.5)))
        a.beam((0, 0, height - 1), tip, 1.1, trunk_color)
        ends.append(tip)
    ends.append(Vector((0, 0, height + 6)))
    a.beam((0, 0, height - 1), ends[-1], 1.2, trunk_color)
    return ends


def leafy_canopy(a, rng, ends, leaf_colors, cubes_per_end=3, size=(4.5, 6), dots=None, snow_caps=False):
    for tip in ends:
        for _ in range(cubes_per_end):
            s = rng.uniform(*size)
            offset = Vector((rng.uniform(-2, 2), rng.uniform(-1.5, 1.5), rng.uniform(-0.5, 2)))
            mat = frame(tip + offset, (rng.uniform(-25, 25), rng.uniform(-25, 25), rng.uniform(0, 90)))
            a.box((0, 0, 0), (s, s, s), rng.choice(leaf_colors), mat=mat)

            if snow_caps:
                a.box((0, 0, s / 2 + 0.25), (s + 0.2, s + 0.2, 0.5), "Snow", mat=mat)

            if dots:
                dot_color, count = dots
                for _ in range(count):
                    axis = rng.choice([0, 1, 2])
                    sign = rng.choice([-1, 1]) if axis != 2 else 1
                    position = [rng.uniform(-s / 2 + 0.6, s / 2 - 0.6) for _ in range(3)]
                    position[axis] = sign * (s / 2 + 0.2)
                    a.box(position, (0.8, 0.8, 0.8), dot_color, mat=mat)


def stepped_rock(a, rng, base_size, tiers, main, dark, top=None):
    a.box((0, 0, 0.6), (base_size + 1, base_size * 0.8 + 1, 1.2), dark)
    z = 1.2
    size = base_size
    for i in range(tiers):
        height = rng.uniform(1.5, 2.5)
        x = rng.uniform(-0.4, 0.4) * i
        a.box((x, 0, z + height / 2), (size, size * 0.8, height), main if i % 2 == 0 else dark,
              rot=(0, 0, rng.uniform(-8, 8)))
        z += height
        size *= rng.uniform(0.65, 0.8)
    if top:
        a.box((0, 0, z + 0.3), (size * 1.2, size, 0.6), top)
    for _ in range(3):
        s = rng.uniform(1.5, base_size * 0.45)
        angle = rng.uniform(0, math.tau)
        position = (math.cos(angle) * base_size * 0.6, math.sin(angle) * base_size * 0.5, s / 2 + 0.5)
        a.box(position, (s, s, s * rng.uniform(1, 1.8)), main, rot=(0, 0, rng.uniform(0, 45)))


def apple_tree(rng):
    a = Asset("AppleTree")
    ends = tree_trunk(a, rng, "Trunk")
    leafy_canopy(a, rng, ends, ["LeafGreen"], dots=("Apple", 5))
    tufts(a, rng, 4, 2.5, 4)
    debris(a, rng, 4, 2.5, 4.5, ["Wood", "RockBlue"])
    return a


def pine_tree(rng):
    a = Asset("PineTree")
    a.box((0, 0, 1.5), (1.6, 1.6, 3), "Bark")
    roots(a, rng, "Bark", spread=2, count=5, thickness=0.7)

    z = 2.4
    for size in (6.4, 5.4, 4.4, 3.4, 2.4):
        mat = frame((rng.uniform(-0.3, 0.3), 0, z + 1), (rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(-25, 25)))
        a.box((0, 0, 0), (size, size, 2), "LeafGreen", mat=mat)
        a.box((0, 0, -0.85), (size + 0.4, size + 0.4, 0.5), "LeafDark", mat=mat)
        for _ in range(3):
            side = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            along = rng.uniform(-size / 2 + 0.6, size / 2 - 0.6)
            position = (side[0] * (size / 2 + 0.15) + side[1] * along, side[1] * (size / 2 + 0.15) + side[0] * along,
                        rng.uniform(-0.4, 0.6))
            a.box(position, (0.6, 0.6, 0.6), "Apple", mat=mat)
        z += 1.7
    a.box((0, 0, z + 0.6), (1, 1, 1.2), "LeafGreen")

    tufts(a, rng, 3, 2.2, 3.5)
    debris(a, rng, 5, 2.4, 4.5, ["Bark", "BarkDark"])
    return a


def bush(rng):
    a = Asset("Bush")
    for _ in range(5):
        s = rng.uniform(2, 3.2)
        a.box((rng.uniform(-1.6, 1.6), rng.uniform(-1, 1), s / 2), (s, s, s), rng.choice(["LeafGreen", "LeafDark"]),
              rot=(rng.uniform(-8, 8), rng.uniform(-8, 8), rng.uniform(0, 45)))
    for _ in range(3):
        a.box((rng.uniform(-2, 2), rng.uniform(-1.4, -0.6), rng.uniform(1.2, 2.4)), (0.6, 0.6, 0.6), "FlowerPink")
    tufts(a, rng, 3, 2.6, 3.4)
    return a


def rock(rng):
    a = Asset("Rock")
    two_tone_chunk(a, (0, 0, 0.9), (4.2, 3.2, 1.8), "RockBlueDark", "RockBlue", rot=(0, 0, 10))
    two_tone_chunk(a, (-0.6, 0.2, 2.1), (2.6, 2.2, 1.2), "RockBlue", "RockTop", rot=(0, 0, -8))
    two_tone_chunk(a, (1.9, -0.6, 0.6), (1.6, 1.4, 1.2), "RockBlue", "RockTop", rot=(0, 0, 30))
    debris(a, rng, 5, 2.8, 4, ["RockBlue", "RockBlueDark"])
    return a


def rock_spire(rng):
    a = Asset("RockSpire")
    stepped_rock(a, rng, 7, 5, "RockBlue", "RockBlueDark", top="RockTop")
    a.beam((2, -2.5, 1), (3.5, -2, 7), 0.6, "LeafGreen")
    debris(a, rng, 6, 4.5, 6.5, ["RockBlue", "RockBlueDark"])
    return a


def log(rng):
    a = Asset("Log")
    a.cylinder((0, 0, 0.95), 0.95, 6, "Wood", sides=8, rot=(0, 90, 0))
    for x in (-3.02, 3.02):
        a.cylinder((x, 0, 0.95), 0.7, 0.1, "WoodLight", sides=8, rot=(0, 90, 0))
    a.box((0.8, 0, 1.95), (0.5, 0.4, 0.5), "Wood")
    tuft(a, rng, (1.4, 0, 1.75), height=0.7)
    return a


def log_pile(rng):
    a = Asset("LogPile")
    for y, z in ((-0.95, 0.9), (0.95, 0.9), (0, 2.5)):
        a.cylinder((0, y, z), 0.9, 5, "Wood", sides=8, rot=(0, 90, 0))
        for end in (-2.52, 2.52):
            a.cylinder((end, y, z), 0.65, 0.1, "WoodLight", sides=8, rot=(0, 90, 0))
    debris(a, rng, 4, 3, 4, ["Wood", "WoodLight"])
    return a


def stump(rng):
    a = Asset("Stump")
    a.cylinder((0, 0, 1), 1.4, 2, "Wood", sides=8)
    a.cylinder((0, 0, 2.03), 1.1, 0.1, "WoodLight", sides=8)
    a.cylinder((0, 0, 2.06), 0.5, 0.1, "Wood", sides=8)
    roots(a, rng, "Wood", spread=2, count=4, thickness=0.6)
    a.beam((0.6, 0.6, 2), (0.9, 0.7, 3), 0.3, "LeafGreen")
    tufts(a, rng, 3, 2, 3)
    return a


def mushroom(rng):
    a = Asset("Mushroom")
    for x, y, scale in ((0, 0, 1), (1.3, 0.5, 0.65), (-0.9, 0.9, 0.5)):
        a.cylinder((x, y, 0.6 * scale), 0.35 * scale, 1.2 * scale, "White", sides=8)
        a.cylinder((x, y, 1.45 * scale), 1 * scale, 0.7 * scale, "Apple", sides=8)
        a.cylinder((x, y, 1.9 * scale), 0.6 * scale, 0.3 * scale, "Apple", sides=8)
        a.box((x + 0.5 * scale, y - 0.5 * scale, 1.5 * scale), (0.35 * scale, 0.35 * scale, 0.35 * scale), "White")
        a.box((x - 0.3 * scale, y + 0.2 * scale, 2.05 * scale), (0.3 * scale, 0.3 * scale, 0.1), "White")
    tufts(a, rng, 2, 1, 2)
    return a


def flower_patch(rng):
    a = Asset("FlowerPatch")
    for _ in range(6):
        x, y = rng.uniform(-2, 2), rng.uniform(-2, 2)
        height = rng.uniform(0.8, 1.6)
        petal = rng.choice(["FlowerRed", "FlowerBlue", "FlowerPink"])
        a.box((x, y, height / 2), (0.2, 0.2, height), "LeafDark")
        a.box((x + 0.3, y, height * 0.4), (0.5, 0.2, 0.2), "LeafGreen")
        for dx, dy in ((0.35, 0), (-0.35, 0), (0, 0.35), (0, -0.35)):
            a.box((x + dx, y + dy, height), (0.35, 0.35, 0.2), petal)
        a.box((x, y, height + 0.05), (0.3, 0.3, 0.25), "Yellow")
    tufts(a, rng, 4, 0.5, 2.5)
    return a


def fence(rng):
    a = Asset("Fence")
    for x in (-2.5, 0, 2.5):
        a.box((x, 0, 1.2), (0.6, 0.6, 2.4), "Wood")
        a.pyramid((x, 0, 2.4), 0.6, 0.4, "WoodLight")
    for z in (0.8, 1.8):
        a.box((0, -0.4, z), (6, 0.2, 0.5), "WoodLight", rot=(0, rng.uniform(-2, 2), 0))
    tufts(a, rng, 3, 0.5, 2.5)
    return a


def pebbles(rng):
    a = Asset("Pebbles")
    debris(a, rng, 9, 0, 3, ["RockBlue", "RockBlueDark", "Wood"])
    return a


# --------------------------------------------------------------------------------------
# Desert
# --------------------------------------------------------------------------------------

def step_pyramid(rng):
    a = Asset("StepPyramid")
    size = 16
    z = 0
    while size > 1:
        a.box((0, 0, z + 0.75), (size, size, 1.5), "PyramidPink")
        a.box((0, 0, z + 1.45), (size - 0.6, size - 0.6, 0.1), "SandDark")
        z += 1.5
        size -= 2.6
    a.box((0, -6.4, 1.5), (3, 3.4, 3), "SandDark")
    a.box((0, -8.1, 1.2), (1.6, 0.1, 2.4), "Coal")
    debris(a, rng, 8, 9, 11, ["Sand", "SandDark", "PyramidPink"])
    return a


def dead_tree(rng):
    a = Asset("DeadTree")
    a.beam((0, 0, 0), (0, 0, 4), 0.9, "DeadWood")
    a.beam((0, 0, 3.5), (-2, 0.3, 7), 0.6, "DeadWood")
    a.beam((0, 0, 3.5), (2.2, -0.3, 6.5), 0.6, "DeadWood")
    a.beam((-1.2, 0.2, 5.5), (-0.4, 0.2, 7.2), 0.4, "DeadWood")
    roots(a, rng, "DeadWood", spread=1.6, count=3, thickness=0.5)
    debris(a, rng, 4, 1.5, 3, ["DeadWood", "SandDark"])
    return a


def cactus(rng):
    a = Asset("Cactus")
    a.box((0, 0, 2), (1.4, 1.4, 4), "Cactus")
    a.box((0, 0, 2), (1.5, 0.4, 3.6), "CactusDark")
    a.box((-1.2, 0, 2), (1, 0.9, 0.9), "Cactus")
    a.box((-1.5, 0, 2.9), (0.8, 0.8, 1.6), "Cactus")
    a.box((1.1, 0, 2.6), (0.8, 0.8, 0.8), "Cactus")
    a.box((1.4, 0, 3.3), (0.7, 0.7, 1.2), "Cactus")
    for position in ((0, 0, 4.15), (-1.5, 0, 3.85), (1.4, 0, 4.0)):
        a.box(position, (0.6, 0.6, 0.3), "FlowerRed")
    for z in (1, 2.4, 3.4):
        a.box((0.75, -0.4, z), (0.1, 0.2, 0.2), "White")
        a.box((-0.75, 0.4, z + 0.4), (0.1, 0.2, 0.2), "White")
    debris(a, rng, 4, 1.5, 2.5, ["SandDark", "Sand"])
    return a


def rib_bones(rng):
    a = Asset("RibBones")
    a.beam((-6, 0, 0.6), (6, 0, 0.9), 0.8, "Bone")
    for x in (-4.5, -2.5, -0.5, 1.5, 3.5):
        height = 4.5 - abs(x) * 0.25
        for side in (-1, 1):
            a.beam((x, 0, 0.8), (x, side * 1.5, height * 0.6), 0.6, "Bone")
            a.beam((x, side * 1.5, height * 0.6), (x, side * 2.2, 0.2), 0.6, "Bone")
    a.box((7, 0, 0.8), (2, 1.6, 1.6), "Bone")
    a.box((7.6, -0.4, 1.1), (0.6, 0.2, 0.4), "Coal")
    a.box((7.6, 0.4, 1.1), (0.6, 0.2, 0.4), "Coal")
    debris(a, rng, 6, 3, 6, ["Bone", "SandDark"])
    return a


def sand_rock(rng):
    a = Asset("SandRock")
    stepped_rock(a, rng, 6, 5, "Sand", "SandDark")
    debris(a, rng, 5, 4, 6, ["Sand", "SandDark"])
    return a


def bone_pile(rng):
    a = Asset("BonePile")
    for _ in range(5):
        x, y = rng.uniform(-2, 2), rng.uniform(-2, 2)
        mat = frame((x, y, 0.25), (0, 0, rng.uniform(0, 180)))
        a.box((0, 0, 0), (2, 0.4, 0.4), "Bone", mat=mat)
        a.box((-1, 0, 0.05), (0.5, 0.8, 0.5), "Bone", mat=mat)
        a.box((1, 0, 0.05), (0.5, 0.8, 0.5), "Bone", mat=mat)
    return a


# --------------------------------------------------------------------------------------
# Snow
# --------------------------------------------------------------------------------------

def snow_tree(rng):
    a = Asset("SnowTree")
    ends = tree_trunk(a, rng, "Bark")
    leafy_canopy(a, rng, ends, ["LeafGreen"], cubes_per_end=2, snow_caps=True)
    debris(a, rng, 4, 2.5, 4, ["SnowShade", "Bark"])
    return a


def frost_tree(rng):
    a = Asset("FrostTree")
    ends = tree_trunk(a, rng, "Wood")
    leafy_canopy(a, rng, ends, ["Snow", "Snow", "SnowShade"], dots=("SnowShade", 3))
    debris(a, rng, 4, 2.5, 4, ["SnowShade", "Ice"])
    return a


def snow_pine(rng):
    a = Asset("SnowPine")
    a.box((0, 0, 1.2), (1.6, 1.6, 2.4), "Bark")
    roots(a, rng, "Bark", spread=1.8, count=4, thickness=0.6)
    z = 2
    for size in (7, 5.5, 4, 2.6):
        a.box((0, 0, z + 1), (size, size, 2), "LeafGreen", rot=(0, 0, rng.uniform(-15, 15)))
        a.box((0, 0, z + 2.1), (size + 0.2, size + 0.2, 0.4), "Snow", rot=(0, 0, rng.uniform(-15, 15)))
        z += 2.2
    a.box((0, 0, z + 0.5), (1, 1, 1), "Snow")
    return a


def snowman(rng):
    a = Asset("Snowman")
    a.box((0, 0, 1.25), (2.5, 2.5, 2.5), "Snow")
    a.box((0, 0, 3.3), (1.9, 1.9, 1.7), "Snow")
    a.box((0, 0, 4.8), (1.4, 1.4, 1.4), "Snow")
    a.box((0, 0, 4.05), (2.1, 2.1, 0.4), "Ice")
    a.box((0.6, -1.05, 3.6), (0.5, 0.2, 1.2), "Ice")
    a.cylinder((0, 0, 5.6), 0.95, 0.2, "Coal", sides=10)
    a.cylinder((0, 0, 6.1), 0.65, 0.9, "Coal", sides=10)
    for x in (-0.35, 0.35):
        a.box((x, -0.72, 5), (0.25, 0.1, 0.25), "Coal")
    a.pyramid((0, -0.7, 4.75), 0.3, 0.7, "Carrot", rot=(90, 0, 0))
    for z in (2.8, 3.4):
        a.box((0, -0.96, z), (0.25, 0.1, 0.25), "Coal")
    for side in (-1, 1):
        a.beam((side * 0.9, 0, 3.6), (side * 2.2, 0, 4.4), 0.25, "DeadWood")
    debris(a, rng, 4, 1.8, 3, ["SnowShade"])
    return a


def ice_crystal(rng):
    a = Asset("IceCrystal")
    a.box((0, 0, 0.3), (4, 3, 0.6), "Ice")
    for _ in range(5):
        x, y = rng.uniform(-1.5, 1.5), rng.uniform(-1, 1)
        height = rng.uniform(2, 4.5)
        a.crystal((x, y, 0.4), rng.uniform(0.8, 1.3), height, "Ice", "IceLight",
                  rot=(rng.uniform(-15, 15), rng.uniform(-15, 15), rng.uniform(0, 90)))
    debris(a, rng, 4, 2.5, 3.5, ["Ice", "SnowShade"])
    return a


def snow_rock(rng):
    a = Asset("SnowRock")
    stepped_rock(a, rng, 6, 4, "RockBlueDark", "RockBlue", top="Snow")
    debris(a, rng, 4, 4, 5.5, ["SnowShade", "RockBlue"])
    return a


def snow_log(rng):
    a = log(rng)
    a.name = "SnowLog"
    a.box((0, 0, 1.85), (5.4, 1.2, 0.3), "Snow")
    return a


# --------------------------------------------------------------------------------------
# Market
# --------------------------------------------------------------------------------------

def market_stall(color, name):
    def build(rng):
        a = Asset(name)
        width, depth = 8, 5
        for x in (-width / 2 + 0.3, width / 2 - 0.3):
            for y in (-depth / 2 + 0.3, depth / 2 - 0.3):
                a.box((x, y, 2.75), (0.5, 0.5, 5.5), "Wood")

        for z in (0.4, 1.2, 2):
            a.box((0, -depth / 2 + 0.3, z), (width, 0.3, 0.3), "WoodLight")
            a.box((0, depth / 2 - 0.3, z), (width, 0.3, 0.3), "WoodLight")
            for x in (-width / 2 + 0.3, width / 2 - 0.3):
                a.box((x, 0, z), (0.3, depth, 0.3), "WoodLight")
        a.box((0, 0, 2.2), (width, depth, 0.3), "Wood")

        # Goods on the counter
        for x in (-2.5, 0, 2.5):
            a.box((x, -0.8, 2.75), (1.8, 1.6, 0.8), "WoodLight")
            for dx in (-0.4, 0.4):
                a.box((x + dx, -0.8, 3.35), (0.6, 0.6, 0.6), rng.choice(["Apple", "Pumpkin", "LeafGreen"]))

        stripes = 8
        stripe_width = (width + 1) / stripes
        for i in range(stripes):
            x = -(width + 1) / 2 + stripe_width * (i + 0.5)
            stripe = color if i % 2 == 0 else "White"
            a.box((x, 0, 5.8), (stripe_width, depth + 1, 0.4), stripe, rot=(10, 0, 0))
            a.box((x, -depth / 2 - 0.4, 5.0), (stripe_width, 0.2, 0.9), stripe)
            a.box((x, -depth / 2 - 0.4, 4.45), (stripe_width * 0.5, 0.2, 0.3), stripe)

        debris(a, rng, 5, 5, 6.5, ["Wood", "WoodLight"])
        return a
    return build


def crate(rng):
    a = Asset("Crate")
    a.box((0, 0, 1), (2, 2, 2), "Wood")
    for z in (0.1, 1.9):
        for y in (-1, 1):
            a.box((0, y, z), (2.1, 0.12, 0.2), "WoodLight")
        for x in (-1, 1):
            a.box((x, 0, z), (0.12, 2.1, 0.2), "WoodLight")
    for x in (-1, 1):
        for y in (-1, 1):
            a.box((x, y, 1), (0.2, 0.2, 2), "WoodLight")
    a.box((0, -1.02, 1), (0.2, 0.1, 2.6), "WoodLight", rot=(0, 45, 0))
    return a


def signboard(rng):
    a = Asset("Signboard")
    for x in (-1.6, 1.6):
        a.box((x, 0, 1.6), (0.4, 0.4, 3.2), "Wood")
    a.box((0, 0, 2.4), (3.6, 0.3, 1.4), "WoodLight")
    a.box((0, -0.2, 2.4), (2.6, 0.1, 0.8), "White")
    tufts(a, rng, 2, 0.5, 1.5)
    return a


# --------------------------------------------------------------------------------------
# Sakura
# --------------------------------------------------------------------------------------

def cherry_tree(rng):
    a = Asset("CherryTree")
    ends = tree_trunk(a, rng, "Trunk")
    leafy_canopy(a, rng, ends, ["Sakura"], dots=("SakuraDark", 3))
    debris(a, rng, 6, 2.5, 5, ["Sakura", "SakuraDark"])
    return a


def torii_frame(a, width=7, height=6):
    for x in (-width / 2, width / 2):
        a.box((x, 0, 0.5), (1, 1, 1), "ToriiBlue")
        a.cylinder((x, 0, height / 2 + 0.5), 0.4, height - 1, "ToriiRed", sides=8)
    a.box((0, 0, height - 1), (width + 1.4, 0.5, 0.4), "ToriiRed")
    a.box((0, 0, height + 0.15), (width + 2.2, 0.8, 0.5), "ToriiBlue")
    a.box((0, 0, height + 0.55), (width + 3, 0.9, 0.3), "ToriiBlue")
    for side in (-1, 1):
        a.box((side * (width + 3) / 2, 0, height + 0.85), (0.6, 0.9, 0.3), "ToriiBlue")


def torii(rng):
    a = Asset("Torii")
    torii_frame(a)
    a.box((0, 0, 5.5), (0.6, 0.3, 1), "ToriiRed")
    debris(a, rng, 5, 2, 5, ["Sakura", "StoneGrey"])
    return a


def gong_gate(rng):
    a = Asset("GongGate")
    torii_frame(a, width=7, height=7)
    gong = frame((0, 0, 3.2), (90, 0, 0))
    a.cylinder((0, 0, 0), 1.8, 0.4, "Gold", sides=16, mat=gong)
    a.cylinder((0, 0, 0.1), 0.7, 0.4, "Yellow", sides=16, mat=gong)
    for side in (-1, 1):
        a.beam((side * 1.2, 0, 4.6), (side * 2.6, 0, 6.6), 0.15, "White")
    return a


def bamboo(rng):
    a = Asset("Bamboo")
    for x in (-1.1, 0, 1.1):
        x += rng.uniform(-0.2, 0.2)
        y = rng.uniform(-0.6, 0.6)
        segments = rng.randint(4, 6)
        for i in range(segments):
            a.box((x, y, i * 1.4 + 0.65), (0.55, 0.55, 1.3), "Bamboo")
            a.box((x, y, i * 1.4 + 1.35), (0.65, 0.65, 0.12), "BambooDark")
        a.beam((x, y, segments * 1.4 - 1), (x + 0.9, y, segments * 1.4 - 0.2), 0.25, "LeafGreen")
    tufts(a, rng, 3, 1, 2)
    return a


def stone_lantern(rng):
    a = Asset("StoneLantern")
    a.box((0, 0, 0.3), (2, 2, 0.6), "StoneGrey")
    a.cylinder((0, 0, 1.4), 0.4, 1.6, "StoneGrey", sides=8)
    a.box((0, 0, 2.4), (1.6, 1.6, 0.4), "StoneGrey")
    a.box((0, 0, 3), (1.2, 1.2, 0.8), "DarkStone")
    a.box((0, -0.55, 3), (0.6, 0.2, 0.5), "LanternGlow")
    a.box((0, 0, 3.6), (2, 2, 0.4), "StoneGrey")
    a.pyramid((0, 0, 3.8), 1.4, 0.8, "StoneGrey")
    tufts(a, rng, 2, 1.2, 1.8)
    return a


# --------------------------------------------------------------------------------------
# Halloween
# --------------------------------------------------------------------------------------

def pumpkin_body(a, rng, radius=1.6):
    for z0, z1, scale in ((0, 0.35, 0.72), (0.35, 0.9, 0.95), (0.9, 1.9, 1), (1.9, 2.45, 0.93), (2.45, 2.8, 0.66)):
        a.prism(circle(radius * scale, 12, math.pi / 12), z0, z1, "Pumpkin")
    for i in range(6):
        angle = math.radians(360 / 6 * i)
        a.box((math.cos(angle) * (radius - 0.15), math.sin(angle) * (radius - 0.15), 1.4),
              (0.4, 0.45, 1.6), "PumpkinDark", rot=(0, 0, math.degrees(angle)))
    a.box((0, 0, 3.15), (0.4, 0.4, 0.8), "Stem", rot=(12, 0, 0))
    a.box((0.5, 0.2, 2.85), (0.9, 0.5, 0.15), "Grass", rot=(0, -15, 20))


def pumpkin(rng):
    a = Asset("Pumpkin")
    pumpkin_body(a, rng)
    tufts(a, rng, 2, 1.8, 2.3)
    return a


def jack_o_lantern(rng):
    a = Asset("JackOLantern")
    pumpkin_body(a, rng)
    face = frame((0, -1.4, 0), (90, 0, 0))
    for x in (-0.6, 0.6):
        a.prism([(x - 0.35, 1.7), (x + 0.35, 1.7), (x, 2.25)], 0, 0.3, "LanternGlow", mat=face)
    a.prism([(-0.15, 1.35), (0.15, 1.35), (0, 1.6)], 0, 0.3, "LanternGlow", mat=face)
    a.prism([(-0.9, 1.05), (-0.6, 0.75), (0.6, 0.75), (0.9, 1.05), (0, 0.95)], 0, 0.3, "LanternGlow", mat=face)
    tufts(a, rng, 2, 1.8, 2.3)
    return a


def ghost(rng):
    a = Asset("Ghost")
    a.box((0, 0, 3.4), (2.2, 2, 2), "Ghost")
    a.box((0, 0, 2.1), (1.9, 1.7, 1), "Ghost")
    a.box((0, 0, 1.45), (1.6, 1.5, 0.5), "GhostShade")
    for x in (-0.55, 0, 0.55):
        a.box((x, 0, 1.0 + (0.15 if x == 0 else 0)), (0.45, 1.3, 0.5), "GhostShade")
    for side in (-1, 1):
        a.box((side * 1.25, -0.2, 2.6), (0.5, 0.6, 0.5), "Ghost", rot=(0, side * -25, 0))
        a.box((side * 0.45, -1.02, 3.5), (0.3, 0.1, 0.55), "Coal")
        a.box((side * 0.8, -1.02, 3.05), (0.35, 0.1, 0.2), "Blush")
    a.box((0, -1.02, 3.0), (0.3, 0.1, 0.25), "Coal")
    return a


def tombstone(rng):
    a = Asset("Tombstone")
    outline = [(-1.2, 0), (1.2, 0)] + arc(1.2, 0, 180, 8, center=(0, 2))[:-1] + [(-1.2, 2)]
    stone = frame((0, 0.4, 0.5), (90 + 4, 0, rng.uniform(-6, 6)))
    a.prism(outline, -0.4, 0.4, "Tomb", mat=stone)
    a.box((0, 2.0, 0.45), (0.35, 1.4, 0.1), "TombDark", mat=stone)
    a.box((0, 2.3, 0.47), (1.1, 0.35, 0.14), "TombDark", mat=stone)
    a.box((0, 0.4, 0.25), (3.2, 1.6, 0.5), "TombDark")

    a.box((0, -1.6, 0.2), (2.4, 3, 0.4), "Dirt")
    a.box((0, -1.6, 0.45), (2, 2.6, 0.2), "DirtDark")
    tufts(a, rng, 4, 1.6, 2.6)
    debris(a, rng, 5, 2, 3.5, ["Dirt", "TombDark"])
    return a


# --------------------------------------------------------------------------------------
# Props
# --------------------------------------------------------------------------------------

def ring_segment(r1, r2, a0, a1):
    a0, a1 = math.radians(a0), math.radians(a1)
    return [(math.cos(a0) * r1, math.sin(a0) * r1), (math.cos(a0) * r2, math.sin(a0) * r2),
            (math.cos(a1) * r2, math.sin(a1) * r2), (math.cos(a1) * r1, math.sin(a1) * r1)]


def star(outer, inner, points, center=(0, 0)):
    outline = []
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi / 2 + math.pi * i / points
        outline.append((center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius))
    return outline


def spin_wheel(rng):
    a = Asset("SpinWheel")
    radius = 4
    wheel = frame((0, 0, 5.2), (90, 0, 0))
    colors = ["WheelRed", "WheelOrange", "WheelYellow", "WheelGreen", "WheelCyan", "WheelBlue", "WheelPurple",
              "WheelPink"]
    for i, color in enumerate(colors):
        a0, a1 = 360 / 8 * i, 360 / 8 * (i + 1)
        a.prism([(0, 0)] + arc(radius, a0, a1, 3), 0, 0.6, color, mat=wheel)
        middle = math.radians((a0 + a1) / 2)
        a.box((math.cos(middle) * 2.6, math.sin(middle) * 2.6, 0.7), (0.8, 0.8, 0.2), "White",
              rot=(0, 0, math.degrees(middle)), mat=wheel)
    for i in range(16):
        a.prism(ring_segment(radius - 0.05, radius + 0.6, 360 / 16 * i, 360 / 16 * (i + 1)), -0.1, 0.8, "WheelRim",
                mat=wheel)
        if i % 2 == 0:
            middle = math.radians(360 / 16 * (i + 0.5))
            a.box((math.cos(middle) * (radius + 0.27), math.sin(middle) * (radius + 0.27), 0.85),
                  (0.3, 0.3, 0.1), "Gold", mat=wheel)
    a.cylinder((0, 0, 0.5), 0.7, 1, "Gold", sides=12, mat=wheel)
    a.prism([(-0.6, radius + 1.2), (0, radius - 0.2), (0.6, radius + 1.2)], 0.2, 1, "Gold", mat=wheel)

    a.box((0, 0.6, 2.4), (0.8, 0.8, 4.8), "WheelRim")
    a.box((0, 0.3, 0.3), (3.6, 2.4, 0.6), "WheelRim")
    a.box((0, 0.3, 0.7), (2.4, 1.6, 0.3), "Gold")
    debris(a, rng, 4, 2.5, 4, ["WheelRim", "Brick"])
    return a


def portal_arch(rng):
    a = Asset("PortalArch")
    inner, outer, depth = 4.6, 6.6, 2.4
    arch = frame((0, 0, 6), (90, 0, 0))
    segments = 7
    for i in range(segments):
        a0, a1 = 180 / segments * i, 180 / segments * (i + 1)
        a.prism(ring_segment(inner, outer, a0 + 0.6, a1 - 0.6), -depth / 2, depth / 2,
                "StoneLilac" if i % 2 == 0 else "StoneLilacDark", mat=arch)
        middle = math.radians((a0 + a1) / 2)
        center = (math.cos(middle) * (inner + outer) / 2, math.sin(middle) * (inner + outer) / 2)
        a.prism(star(0.6, 0.28, 6, center), depth / 2, depth / 2 + 0.15, "White", mat=arch)

    for side in (-1, 1):
        x = side * (inner + outer) / 2
        for i, z in enumerate((1, 3, 5)):
            a.box((x, 0, z), (outer - inner + (0.3 if i % 2 == 0 else 0), depth + (0.3 if i % 2 == 0 else 0), 1.95),
                  "StoneLilacDark" if i % 2 == 0 else "StoneLilac")
        a.prism(star(0.6, 0.28, 6), 0, 0.15, "White", mat=frame((x, -depth / 2, 3), (90, 0, 0)))

    portal = [(-inner, -6), (inner, -6)] + arc(inner, 0, 180, 12)
    a.prism(portal, -0.2, 0.2, "PortalGlow", mat=arch)
    a.box((0, 0, 0.15), (outer * 2 + 1, depth + 1.2, 0.3), "StoneLilacDark")
    debris(a, rng, 6, 7.5, 9, ["StoneLilac", "Brick"])
    return a


def stone_door(rng):
    a = Asset("StoneDoor")
    for side in (-1, 1):
        for i in range(5):
            wide = i % 2 == 0
            a.box((side * 2.6, 0, 0.55 + i * 1.1), (1.6 if wide else 1.2, 1.6 if wide else 1.3, 1.05),
                  "StoneLilac" if wide else "Brick")
    a.box((0, 0, 6.0), (7, 1.7, 1), "Brick")
    a.box((0, 0, 6.65), (7.4, 1.9, 0.3), "StoneLilac")
    for x in (-3.4, 3.4):
        a.box((x, 0, 6.0), (0.6, 1.8, 1.1), "StoneLilacDark")
    a.box((0, 0.1, 2.75), (3.8, 0.4, 5.5), "WheelOrange")
    a.box((0, -0.15, 2.75), (3.2, 0.1, 4.9), "Pumpkin")
    a.box((1.2, -0.25, 2.6), (0.3, 0.15, 0.3), "Gold")
    debris(a, rng, 6, 3.5, 5, ["Brick", "StoneLilac"])
    return a


# --------------------------------------------------------------------------------------
# Boss - Crystal Golem (~22 studs tall, split into body parts for rigging)
# --------------------------------------------------------------------------------------

def golem_glyph(a, mat, color, scale=1):
    """Square spiral rune made of thin plates, drawn flat on the local XZ plane."""
    s = scale
    segments = [
        ((-0.9, 0.9), (0.9, 0.9)), ((0.9, 0.9), (0.9, -0.9)), ((0.9, -0.9), (-0.5, -0.9)),
        ((-0.5, -0.9), (-0.5, 0.4)), ((-0.5, 0.4), (0.4, 0.4)), ((0.4, 0.4), (0.4, -0.3)),
    ]
    for (x0, z0), (x1, z1) in segments:
        # Horizontal strokes cover the corners, vertical ones stop short so faces never overlap
        width = abs(x1 - x0) + 0.3 if z0 == z1 else 0.3
        height = abs(z1 - z0) - 0.3 if x0 == x1 else 0.3
        a.box(((x0 + x1) / 2 * s, 0, (z0 + z1) / 2 * s), (width * s, 0.15, height * s), color, mat=mat)


def golem_crystals(a, rng, mat, count, area, height_range, tilt=25):
    colors = [("Cobalt", "LightBlue"), ("BrightViolet", "LightPurple"), ("RoyalPurple", "White"),
              ("BrightBlue", "White"), ("LightBlue", "White")]
    for _ in range(count):
        color, tip = rng.choice(colors)
        x, y = rng.uniform(-area[0], area[0]), rng.uniform(-area[1], area[1])
        height = rng.uniform(*height_range)
        a.crystal((x, y, 0), height * 0.35, height, color, tip,
                  rot=(rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt), rng.uniform(0, 90)), mat=mat)


def golem_moss(a, rng, mat, count, area):
    for _ in range(count):
        s = rng.uniform(0.5, 1.2)
        a.box((rng.uniform(-area[0], area[0]), rng.uniform(-area[1], area[1]), s / 4), (s, s, s / 2),
              rng.choice(["Moss", "Moss", "MossDark"]), mat=mat)


def golem_leg(a, rng, side):
    a.group = "LeftLeg" if side < 0 else "RightLeg"
    x = side * 3.3
    a.box((x, 0, 7.6), (3.6, 3.6, 3.2), "DarkBlue")
    a.box((x, 0, 6), (4.2, 4.2, 0.8), "Yellow")
    a.box((x, 0, 3.6), (4.6, 4.6, 4), "ReallyDarkBlue")
    a.box((x, -2.35, 3.8), (1.6, 0.15, 1.6), "Cobalt")
    a.box((x, -2.4, 3.8), (0.6, 0.15, 0.6), "Glow")
    a.box((x, 0, 1.6), (5, 5, 0.8), "Yellow")
    a.box((x, -0.5, 0.6), (5.6, 6.4, 1.2), "ReallyDarkBlue")
    for toe in (-1.8, 0, 1.8):
        a.pyramid((x + toe, -3.7, 0.5), 1, 1.2, "LightBlue", rot=(90, 0, 0))
    golem_crystals(a, rng, frame((x + side * 2.3, 0, 3.6), (0, side * 90, 0)), 2, (1.2, 1.2), (1, 1.8))
    golem_moss(a, rng, frame((x, 0, 9.2)), 3, (1.6, 1.6))


def golem_arm(a, rng, side):
    a.group = "LeftArm" if side < 0 else "RightArm"
    x = side * 9

    shoulder = frame((x, 0, 17), (0, side * -8, 0))
    a.box((0, 0, 0), (5.4, 5.4, 5), "StoneGrey", mat=shoulder)
    a.box((0, 0, -2.7), (5.8, 5.8, 0.6), "Yellow", mat=shoulder)
    golem_glyph(a, shoulder @ frame((0, -2.72, 0.2)), "BrightViolet", 0.9)
    golem_moss(a, rng, shoulder @ frame((0, 0, 2.5)), 6, (2.2, 2.2))
    golem_crystals(a, rng, shoulder @ frame((side * 0.8, 0.6, 2.5)), 5, (1.6, 1.6), (2.5, 4.5))

    a.box((x + side * 0.4, 0, 12.4), (3.6, 3.6, 4.4), "StoneGrey")
    a.box((x + side * 0.4, 0, 10.6), (4.2, 4.2, 0.8), "Yellow")
    a.box((x + side * 0.6, 0, 7.6), (4.8, 4.8, 5.2), "DarkBlue")
    golem_glyph(a, frame((x + side * 0.6, -2.42, 7.8)), "Cobalt", 0.8)
    golem_crystals(a, rng, frame((x + side * 3, 0, 8), (0, side * 90, 0)), 3, (1.5, 1.5), (1.2, 2.2))

    a.box((x + side * 0.6, -0.3, 3.7), (5, 5, 2.8), "ReallyDarkBlue")
    a.box((x + side * 0.6, -0.3, 5.3), (5.2, 5.2, 0.6), "Yellow")
    for kx in (-1.5, 0, 1.5):
        a.box((x + side * 0.6 + kx, -2.9, 3.9), (1, 0.3, 1), "LightBlue")
    a.crystal((x + side * 0.6, -2.9, 2.6), 1.6, 1, "LightBlue", "White", rot=(90, 0, 0))


def golem_torso(a, rng):
    a.group = "Torso"
    a.box((0, 0, 10.2), (10, 6, 1.4), "DarkBlue")
    a.box((0, 0, 11.1), (10.4, 6.4, 0.5), "Yellow")
    a.box((0, -3.25, 10.2), (1.4, 0.15, 1), "Glow")
    a.box((0, 0, 14.6), (12, 7, 6.6), "StoneGrey")
    a.box((0, 0.3, 18.3), (10, 6.4, 1), "DarkStone")

    a.box((0, -3.55, 14.6), (2.8, 0.2, 2.8), "Gold")
    a.box((0, -3.6, 14.6), (2, 0.2, 2), "ReallyDarkBlue")
    a.pyramid((0, -3.65, 14.6), 1.3, 0.6, "LightBlue", rot=(90, 0, 0))

    golem_glyph(a, frame((-3.6, -3.55, 14.8)), "Cobalt")
    golem_glyph(a, frame((3.6, -3.55, 14.8), (0, 180, 0)), "Cobalt")
    golem_glyph(a, frame((0, 3.55, 14.8)), "BrightViolet", 1.2)

    golem_moss(a, rng, frame((0, 0, 18.8)), 14, (4.5, 3))
    golem_moss(a, rng, frame((0, 0, 11.4)), 6, (4.5, 2.8))
    golem_crystals(a, rng, frame((0, 2, 18.8)), 14, (4.5, 1.8), (3, 6.5), tilt=30)
    golem_crystals(a, rng, frame((0, 3.5, 15), (70, 0, 0)), 6, (4.5, 2), (2, 4))


def golem_head(a, rng):
    a.group = "Head"
    a.box((0, -1.2, 20.6), (5, 4.4, 3.8), "StoneGrey")
    a.box((0, -3.5, 21.6), (5.4, 0.8, 0.8), "DarkStone")
    for x in (-1.2, 1.2):
        a.box((x, -3.45, 20.9), (1.2, 0.2, 0.5), "Glow")
    a.box((0, -3.5, 19.4), (3, 0.3, 0.4), "DarkStone")
    a.box((0, -3.5, 22.4), (1, 0.3, 1), "Gold")
    a.box((0, -3.6, 22.4), (0.5, 0.2, 0.5), "Glow")
    golem_moss(a, rng, frame((0, -1.2, 22.5)), 5, (2, 1.6))


def crystal_golem(rng):
    a = Asset("CrystalGolem")
    golem_leg(a, rng, -1)
    golem_leg(a, rng, 1)
    golem_torso(a, rng)
    golem_head(a, rng)
    golem_arm(a, rng, -1)
    golem_arm(a, rng, 1)
    return a


# --------------------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------------------

BIOMES = {
    "Forest": [grass_block("GrassBlockSmall", 6, 5), grass_block("GrassBlock", 9, 7),
               grass_block("GrassBlockLarge", 12, 9), apple_tree, pine_tree, bush, rock, rock_spire, log, log_pile,
               stump, mushroom, flower_patch, fence, pebbles],
    "Desert": [step_pyramid, dead_tree, cactus, rib_bones, sand_rock, bone_pile],
    "Snow": [snow_tree, frost_tree, snow_pine, snowman, ice_crystal, snow_rock, snow_log],
    "Market": [market_stall("StripeRed", "MarketStallRed"), market_stall("StripeBlue", "MarketStallBlue"),
               market_stall("StripePurple", "MarketStallPurple"), crate, signboard],
    "Sakura": [cherry_tree, torii, gong_gate, bamboo, stone_lantern],
    "Halloween": [ghost, tombstone, pumpkin, jack_o_lantern],
    "Props": [stone_door, spin_wheel, portal_arch],
    "Boss": [crystal_golem],
}


# --------------------------------------------------------------------------------------
# Blender scene
# --------------------------------------------------------------------------------------

def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def get_material(color):
    material = bpy.data.materials.get(color)
    if material:
        return material
    material = bpy.data.materials.new(color)
    linear = [srgb_to_linear(c / 255) for c in PALETTE[color]]
    material.diffuse_color = (*linear, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = material.diffuse_color
    bsdf.inputs["Roughness"].default_value = 0.6
    if "Glow" in color:
        bsdf.inputs["Emission Color"].default_value = material.diffuse_color
        bsdf.inputs["Emission Strength"].default_value = 3
    return material


def build_objects(asset, collection):
    root = bpy.data.objects.new(asset.name, None)
    collection.objects.link(root)

    for (group, color), (verts, faces, uvs) in sorted(asset.meshes.items(), key=lambda item: (item[0][0] or "", item[0][1])):
        name = f"{group}_{color}" if group else color
        mesh = bpy.data.meshes.new(f"{asset.name}_{name}")
        mesh.from_pydata(verts, [], faces)
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for loop in mesh.loops:
            uv_layer.data[loop.index].uv = uvs[loop.vertex_index]
        mesh.materials.append(get_material(color))
        mesh.validate()
        mesh.update()

        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        obj.parent = root
    return root


def export_fbx(root, path):
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for child in root.children:
        child.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"EMPTY", "MESH"},
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        bake_anim=False,
        axis_forward="-Z",
        axis_up="Y",
        apply_scale_options="FBX_SCALE_UNITS",
    )


def write_color_script():
    colors = "\n".join(f"\t{name} = Color3.fromRGB({r}, {g}, {b})," for name, (r, g, b) in PALETTE.items())
    script = f'''--[[
	Generated by generate_assets.py - edit PALETTE there and regenerate.

	Run in the Studio Command Bar after importing the FBX files.
	Select the imported models (or a folder containing them) and run.

	Colours every MeshPart by the colour key at the end of its name
	(e.g. "Torso_StoneGrey" -> StoneGrey). Keys containing "Glow" become Neon.
]]

--// Services

local Selection = game:GetService("Selection")

--// Constants

local PART_MATERIAL = Enum.Material.SmoothPlastic
local GLOW_MATERIAL = Enum.Material.Neon

local COLORS = {{
{colors}
}}

--// Apply Colors

local coloredCount = 0

for _, selected in Selection:Get() do
	local instances = selected:GetDescendants()
	table.insert(instances, selected)

	for _, meshPart in instances do
		if not meshPart:IsA("MeshPart") then
			continue
		end

		local colorKey = string.match(meshPart.Name, "([^_]+)$")
		local color = COLORS[colorKey]
		if not color then
			warn("No stud colour for", meshPart:GetFullName())
			continue
		end

		meshPart.Color = color
		meshPart.Material = if string.find(colorKey, "Glow") then GLOW_MATERIAL else PART_MATERIAL
		coloredCount += 1
	end
end

print(`Coloured {{coloredCount}} MeshParts`)
'''
    with open(os.path.join(ROOT, "ApplyStudColors.lua"), "w") as file:
        file.write(script)


def make_stud_image(size=64):
    """Grayscale stud tile used only for the previews."""
    v, u = numpy.mgrid[0:size, 0:size] / size + 0.5 / size
    dx, dy = u - 0.5, v - 0.5
    distance = numpy.sqrt(dx * dx + dy * dy)

    value = numpy.full((size, size), 0.9)
    rim = (distance > 0.24) & (distance < 0.3)
    value[rim] = 0.9 + (dx[rim] * -0.6 + dy[rim] * 0.6) * 1.2
    value[distance <= 0.24] = 0.97
    edge = numpy.minimum(numpy.minimum(u, 1 - u), numpy.minimum(v, 1 - v)) < 0.03
    value[edge] = 0.8
    value = numpy.clip(value, 0, 1)

    pixels = numpy.ones((size, size, 4), dtype=numpy.float32)
    pixels[..., 0] = pixels[..., 1] = pixels[..., 2] = value
    image = bpy.data.images.new("StudPreview", size, size)
    image.pixels.foreach_set(pixels.ravel())
    return image


def add_preview_studs(image):
    added = []
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        nodes, links = material.node_tree.nodes, material.node_tree.links
        bsdf = nodes.get("Principled BSDF")
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = image
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1
        color_a = [s for s in mix.inputs if s.name == "A" and s.type == "RGBA"][0]
        color_b = [s for s in mix.inputs if s.name == "B" and s.type == "RGBA"][0]
        color_a.default_value = bsdf.inputs["Base Color"].default_value
        links.new(texture.outputs["Color"], color_b)
        links.new([s for s in mix.outputs if s.type == "RGBA"][0], bsdf.inputs["Base Color"])
        added.append((material, texture, mix))
    return added


def remove_preview_studs(added, image):
    for material, texture, mix in added:
        material.node_tree.nodes.remove(texture)
        material.node_tree.nodes.remove(mix)
    bpy.data.images.remove(image)


def render_previews(roots_by_biome):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.view_settings.view_transform = "Standard"

    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.35, 0.75, 0.9, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    scene.world = world

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = Euler((math.radians(45), math.radians(10), math.radians(-30)))
    scene.collection.objects.link(sun)

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.data.type = "ORTHO"
    camera.data.clip_end = 1000
    scene.collection.objects.link(camera)
    scene.camera = camera

    ground_mesh = bpy.data.meshes.new("Ground")
    corners = [(-2000, -2000, 0), (2000, -2000, 0), (2000, 2000, 0), (-2000, 2000, 0)]
    ground_mesh.from_pydata(corners, [], [(0, 1, 2, 3)])
    ground_uv = ground_mesh.uv_layers.new(name="UVMap")
    for loop in ground_mesh.loops:
        ground_uv.data[loop.index].uv = corners[loop.vertex_index][:2]
    ground = bpy.data.objects.new("Ground", ground_mesh)
    ground_material = bpy.data.materials.new("GroundPreview")
    ground_material.use_nodes = True
    ground_material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.32, 0.36, 0.5, 1)
    ground_mesh.materials.append(ground_material)
    scene.collection.objects.link(ground)

    image = make_stud_image()
    added = add_preview_studs(image)

    for biome, roots in roots_by_biome.items():
        for other in roots_by_biome.values():
            for root in other:
                hidden = other is not roots
                root.hide_render = hidden
                for child in root.children:
                    child.hide_render = hidden

        points = [child.matrix_world @ Vector(corner) for root in roots for child in root.children
                  for corner in child.bound_box]
        center = sum(points, Vector()) / len(points)
        camera.rotation_euler = Euler((math.radians(70), 0, math.radians(20)))
        rotation = camera.rotation_euler.to_matrix()
        right, up, back = rotation.col[0], rotation.col[1], rotation.col[2]
        span_x = max(p.dot(right) for p in points) - min(p.dot(right) for p in points)
        span_y = max(p.dot(up) for p in points) - min(p.dot(up) for p in points)
        mid_x = (max(p.dot(right) for p in points) + min(p.dot(right) for p in points)) / 2
        mid_y = (max(p.dot(up) for p in points) + min(p.dot(up) for p in points)) / 2
        camera.data.ortho_scale = max(span_x, span_y * 16 / 9) * 1.08
        camera.location = right * mid_x + up * mid_y + back * (center.dot(back) + 150)
        scene.render.filepath = os.path.join(PREVIEW_DIR, f"{biome}.png")
        bpy.ops.render.render(write_still=True)

    remove_preview_studs(added, image)
    for name in ("Camera", "Sun", "Ground"):
        bpy.data.objects.remove(bpy.data.objects[name])
    bpy.data.materials.remove(ground_material)


def bounds(asset):
    xs = [v[0] for verts, _, _ in asset.meshes.values() for v in verts]
    return min(xs), max(xs)


def main():
    render = "--render" in sys.argv
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    write_color_script()

    roots_by_biome = {}
    for biome_index, (biome, builders) in enumerate(BIOMES.items()):
        collection = bpy.data.collections.new(biome)
        bpy.context.scene.collection.children.link(collection)
        os.makedirs(os.path.join(EXPORT_DIR, biome), exist_ok=True)

        roots = []
        cursor = 0
        for builder in builders:
            asset = builder(random.Random(sum(map(ord, biome)) + len(roots) * 31))
            root = build_objects(asset, collection)
            export_fbx(root, os.path.join(EXPORT_DIR, biome, f"{asset.name}.fbx"))

            low, high = bounds(asset)
            root.location = (cursor - low, biome_index * 60, 0)
            cursor += high - low + 3
            roots.append(root)
            print(f"[{biome}] {asset.name}: {sum(len(f) for _, f, _ in asset.meshes.values())} faces")
        roots_by_biome[biome] = roots

    if render:
        render_previews(roots_by_biome)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "StudAssets.blend"))


if __name__ == "__main__":
    main()
