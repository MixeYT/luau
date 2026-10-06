"""
Stud-style asset generator for Roblox Studio.

Run headless:
    blender -b -P generate_assets.py
or with the bpy module:
    python3 generate_assets.py

Outputs (next to this script):
    Export/<Biome>/<Asset>.fbx   - one FBX per asset, import with Roblox 3D Importer
    StudAssets.blend             - every asset in one editable file (collection per biome)
    Previews/<Biome>.png         - preview renders (only with --render)

Every asset is made of plain boxes / pyramids. No 3D studs - the stud texture is added
in Roblox. UVs are box-projected in stud units (1 UV unit = 1 stud), so a stud texture
tiles once per stud on every face.

Every asset is split into one mesh per colour. Mesh names end with the colour key
(e.g. "Torso_StoneGrey"), which ApplyStudColors.lua uses to colour the MeshParts.
"""

import math
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(ROOT, "Export")
PREVIEW_DIR = os.path.join(ROOT, "Previews")

# Roblox-style flat colours (0-255). Keep in sync with ApplyStudColors.lua.
PALETTE = {
    # Nature
    "LeafGreen": (98, 200, 60),
    "LeafDark": (64, 160, 48),
    "Grass": (124, 226, 46),
    "Trunk": (176, 124, 150),
    "Wood": (196, 126, 110),
    "WoodLight": (222, 160, 136),
    "DeadWood": (140, 92, 92),
    "Apple": (206, 30, 40),
    "RockBlue": (146, 152, 236),
    "RockBlueDark": (112, 116, 206),
    "FlowerRed": (230, 40, 50),
    "FlowerBlue": (60, 190, 255),
    "FlowerPink": (240, 120, 200),
    "White": (242, 243, 243),
    "Yellow": (245, 205, 48),
    # Desert
    "Sand": (232, 184, 132),
    "SandDark": (214, 160, 110),
    "PyramidPink": (214, 150, 140),
    "Bone": (236, 238, 242),
    "Cactus": (96, 200, 64),
    # Snow
    "Snow": (240, 244, 255),
    "SnowShade": (196, 202, 236),
    "Ice": (80, 176, 255),
    "Coal": (32, 32, 38),
    "Carrot": (255, 140, 30),
    # Market
    "StripeRed": (222, 40, 40),
    "StripeBlue": (30, 150, 240),
    "StripePurple": (140, 60, 220),
    # Sakura
    "Sakura": (226, 156, 236),
    "SakuraDark": (176, 104, 214),
    "ToriiRed": (212, 40, 44),
    "ToriiBlue": (40, 88, 180),
    "Gold": (250, 200, 40),
    "Bamboo": (84, 200, 60),
    "BambooDark": (52, 150, 46),
    "StoneGrey": (163, 162, 165),
    # Golem boss
    "DarkStone": (99, 95, 98),
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

class Asset:
    def __init__(self, name):
        self.name = name
        self.group = None
        # (group, color) -> [verts, faces, uvs]
        self.meshes = {}

    def _bucket(self, color):
        assert color in PALETTE, color
        key = (self.group, color)
        if key not in self.meshes:
            self.meshes[key] = [[], [], []]
        return self.meshes[key]

    def _add_face(self, color, world_points, local_points, local_normal):
        verts, faces, uvs = self._bucket(color)

        # Project on the two local axes the face lies in, so studs follow the brick
        axis = max(range(3), key=lambda i: abs(local_normal[i]))
        u_axis, v_axis = [i for i in range(3) if i != axis]
        if axis == 1:
            u_axis, v_axis = 0, 2

        start = len(verts)
        for world, local in zip(world_points, local_points):
            verts.append(tuple(world))
            uvs.append((local[u_axis], local[v_axis]))
        faces.append(tuple(range(start, start + len(world_points))))

    def box(self, center, size, color, rot=(0, 0, 0), mat=None):
        """Axis aligned box in local space, optionally rotated (degrees) and transformed."""
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        world_mat = (mat or Matrix.Identity(4)) @ Matrix.Translation(center) @ \
            Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()

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
            local = [corners[i] + offset for i in indices]
            world = [world_mat @ corners[i] for i in indices]
            self._add_face(color, world, local, normal)

    def pyramid(self, base_center, width, height, color, rot=(0, 0, 0), mat=None):
        """Square pyramid standing on its base (used for crystal tips and spikes)."""
        h = width / 2
        world_mat = (mat or Matrix.Identity(4)) @ Matrix.Translation(base_center) @ \
            Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()

        base = [Vector((-h, -h, 0)), Vector((h, -h, 0)), Vector((h, h, 0)), Vector((-h, h, 0))]
        apex = Vector((0, 0, height))
        offset = Vector((h, h, 0))

        self._add_face(color, [world_mat @ p for p in reversed(base)],
                       [p + offset for p in reversed(base)], (0, 0, -1))
        for i in range(4):
            a, b = base[i], base[(i + 1) % 4]
            side = (a + b) / 2
            self._add_face(color, [world_mat @ a, world_mat @ b, world_mat @ apex],
                           [a + offset, b + offset, apex + offset], (side.x, side.y, 0.0001))

    def beam(self, start, end, thickness, color, roll=0, mat=None):
        """Box stretched between two points."""
        start, end = Vector(start), Vector(end)
        direction = end - start
        rotation = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()
        rotation = rotation @ Matrix.Rotation(math.radians(roll), 4, "Z")
        world_mat = (mat or Matrix.Identity(4)) @ Matrix.Translation((start + end) / 2) @ rotation
        self.box((0, 0, 0), (thickness, thickness, direction.length + thickness * 0.3), color, mat=world_mat)

    def crystal(self, base, width, height, color, tip_color, rot=(0, 0, 0), mat=None):
        world_mat = (mat or Matrix.Identity(4)) @ Matrix.Translation(base) @ \
            Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()
        self.box((0, 0, height / 2), (width, width, height), color, mat=world_mat)
        self.pyramid((0, 0, height), width, width * 1.3, tip_color, mat=world_mat)


def frame(position, rot=(0, 0, 0)):
    return Matrix.Translation(position) @ Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()


# --------------------------------------------------------------------------------------
# Shared pieces
# --------------------------------------------------------------------------------------

def tree_trunk(a, rng, trunk_color, height=7, branch_spread=4.5):
    a.beam((0, 0, -0.3), (0, 0, height), 1.8, trunk_color)
    for angle in (0, 90, 180, 270):
        direction = Vector((math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0))
        a.beam(direction * 0.6 + Vector((0, 0, 1.2)), direction * 1.8 + Vector((0, 0, 0.2)), 0.8, trunk_color)

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
                    position = [rng.uniform(-s / 2 + 0.5, s / 2 - 0.5) for _ in range(3)]
                    position[axis] = sign * (s / 2 + 0.2)
                    a.box(position, (0.8, 0.8, 0.8), dot_color, mat=mat)


def stepped_rock(a, rng, base_size, tiers, main, dark, top=None):
    a.box((0, 0, 0.6), (base_size + 1, base_size * 0.8 + 1, 1.2), dark)
    z = 1.2
    size = base_size
    for i in range(tiers):
        height = rng.uniform(1.5, 2.5)
        x = rng.uniform(-0.4, 0.4) * i
        a.box((x, 0, z + height / 2), (size, size * 0.8, height), main if i % 2 == 0 else dark)
        z += height
        size *= rng.uniform(0.65, 0.8)
    if top:
        a.box((0, 0, z + 0.3), (size * 1.2, size, 0.6), top)
    # Side chunks
    for _ in range(3):
        s = rng.uniform(1.5, base_size * 0.45)
        angle = rng.uniform(0, math.tau)
        position = (math.cos(angle) * base_size * 0.55, math.sin(angle) * base_size * 0.45, s / 2 + 0.5)
        a.box(position, (s, s, s * rng.uniform(1, 1.8)), main)


# --------------------------------------------------------------------------------------
# Forest
# --------------------------------------------------------------------------------------

def apple_tree(rng):
    a = Asset("AppleTree")
    ends = tree_trunk(a, rng, "Trunk")
    leafy_canopy(a, rng, ends, ["LeafGreen"], dots=("Apple", 5))
    return a


def pine_tree(rng):
    a = Asset("PineTree")
    a.box((0, 0, 1.2), (1.8, 1.8, 2.4), "Trunk")
    z = 2
    for i, size in enumerate((8, 6.5, 5, 3.5, 2)):
        a.box((0, 0, z + 1.2), (size, size, 2.4), "LeafGreen")
        a.box((0, 0, z + 0.3), (size + 0.6, size + 0.6, 0.6), "LeafDark")
        z += 2.6
    a.box((0, 0, z + 0.6), (1, 1, 1.2), "LeafGreen")
    return a


def bush(rng):
    a = Asset("Bush")
    for _ in range(4):
        s = rng.uniform(2, 3.2)
        a.box((rng.uniform(-1.5, 1.5), rng.uniform(-1, 1), s / 2), (s, s, s), rng.choice(["LeafGreen", "LeafDark"]),
              rot=(0, 0, rng.uniform(0, 45)))
    return a


def rock(rng):
    a = Asset("Rock")
    stepped_rock(a, rng, 5, 2, "RockBlue", "RockBlueDark")
    return a


def rock_spire(rng):
    a = Asset("RockSpire")
    stepped_rock(a, rng, 7, 5, "RockBlue", "RockBlueDark")
    a.beam((2, -2.5, 1), (3.5, -2, 7), 0.6, "LeafGreen")
    return a


def log(rng):
    a = Asset("Log")
    a.box((0, 0, 0.9), (6, 1.8, 1.8), "Wood")
    for x in (-3.05, 3.05):
        a.box((x, 0, 0.9), (0.2, 1.3, 1.3), "WoodLight")
    a.box((1, 0.95, 1.2), (1.2, 0.2, 0.4), "WoodLight")
    return a


def log_pile(rng):
    a = Asset("LogPile")
    for x, z in ((-1, 0.9), (1, 0.9), (0, 2.6)):
        a.box((0, x * 1.0, z), (5, 1.7, 1.7), "Wood")
        for end in (-2.55, 2.55):
            a.box((end, x * 1.0, z), (0.2, 1.2, 1.2), "WoodLight")
    return a


def stump(rng):
    a = Asset("Stump")
    a.box((0, 0, 1), (2.6, 2.6, 2), "Wood")
    a.box((0, 0, 2.05), (2.2, 2.2, 0.2), "WoodLight")
    for angle in (0, 90, 180, 270):
        direction = Vector((math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0))
        a.box(direction * 1.6 + Vector((0, 0, 0.3)), (0.8, 0.8, 0.6), "Wood", rot=(0, 0, angle))
    a.beam((0.6, 0.6, 2), (0.9, 0.7, 3), 0.3, "LeafGreen")
    return a


def mushroom(rng):
    a = Asset("Mushroom")
    for x, y, scale in ((0, 0, 1), (1.2, 0.5, 0.65), (-0.8, 0.9, 0.5)):
        a.box((x, y, 0.6 * scale), (0.6 * scale, 0.6 * scale, 1.2 * scale), "White")
        a.box((x, y, 1.5 * scale), (1.8 * scale, 1.8 * scale, 0.8 * scale), "Apple")
        a.box((x, y + 0.35 * scale, 1.95 * scale), (0.4 * scale, 0.4 * scale, 0.15), "White")
        a.box((x - 0.4 * scale, y - 0.3 * scale, 1.95 * scale), (0.3 * scale, 0.3 * scale, 0.15), "White")
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
    return a


def fence(rng):
    a = Asset("Fence")
    for x in (-2.5, 0, 2.5):
        a.box((x, 0, 1.2), (0.6, 0.6, 2.4), "Wood")
        a.box((x, 0, 2.45), (0.7, 0.7, 0.1), "WoodLight")
    for z in (0.8, 1.8):
        a.box((0, -0.4, z), (6, 0.2, 0.5), "WoodLight")
    return a


def pebbles(rng):
    a = Asset("Pebbles")
    for _ in range(7):
        a.box((rng.uniform(-3, 3), rng.uniform(-3, 3), 0.15), (rng.uniform(0.6, 1.4), rng.uniform(0.5, 1), 0.3),
              rng.choice(["RockBlue", "RockBlueDark", "Wood"]), rot=(0, 0, rng.uniform(0, 90)))
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
        z += 1.5
        size -= 2.6
    a.box((0, -6.4, 1.5), (3, 3.4, 3), "SandDark")
    a.box((0, -8.1, 1.2), (1.6, 0.1, 2.4), "Coal")
    return a


def dead_tree(rng):
    a = Asset("DeadTree")
    a.beam((0, 0, 0), (0, 0, 4), 0.9, "DeadWood")
    a.beam((0, 0, 3.5), (-2, 0.3, 7), 0.6, "DeadWood")
    a.beam((0, 0, 3.5), (2.2, -0.3, 6.5), 0.6, "DeadWood")
    a.beam((-1.2, 0.2, 5.5), (-0.4, 0.2, 7.2), 0.4, "DeadWood")
    for angle in (0, 120, 240):
        direction = Vector((math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0))
        a.beam(Vector((0, 0, 0.8)), direction * 1.3, 0.5, "DeadWood")
    return a


def cactus(rng):
    a = Asset("Cactus")
    a.box((0, 0, 2), (1.4, 1.4, 4), "Cactus")
    a.box((-1.2, 0, 2), (1, 0.9, 0.9), "Cactus")
    a.box((-1.5, 0, 2.9), (0.8, 0.8, 1.6), "Cactus")
    a.box((1.1, 0, 2.6), (0.8, 0.8, 0.8), "Cactus")
    a.box((1.4, 0, 3.3), (0.7, 0.7, 1.2), "Cactus")
    for position in ((0, 0, 4.15), (-1.5, 0, 3.85), (1.4, 0, 4.0)):
        a.box(position, (0.6, 0.6, 0.3), "FlowerRed")
    for z in (1, 2.4, 3.4):
        a.box((0.75, 0.3, z), (0.1, 0.2, 0.2), "White")
        a.box((-0.75, -0.3, z + 0.4), (0.1, 0.2, 0.2), "White")
    return a


def rib_bones(rng):
    a = Asset("RibBones")
    a.beam((-6, 0, 0.6), (6, 0, 0.9), 0.8, "Bone")
    for i, x in enumerate((-4.5, -2.5, -0.5, 1.5, 3.5)):
        height = 4.5 - abs(x) * 0.25
        for side in (-1, 1):
            a.beam((x, 0, 0.8), (x, side * 1.5, height * 0.6), 0.6, "Bone")
            a.beam((x, side * 1.5, height * 0.6), (x, side * 2.2, 0.2), 0.6, "Bone")
    a.box((7, 0, 0.8), (2, 1.6, 1.6), "Bone")
    a.box((7.6, -0.4, 1.1), (0.6, 0.2, 0.4), "Coal")
    a.box((7.6, 0.4, 1.1), (0.6, 0.2, 0.4), "Coal")
    return a


def sand_rock(rng):
    a = Asset("SandRock")
    stepped_rock(a, rng, 6, 5, "Sand", "SandDark")
    return a


def bone_pile(rng):
    a = Asset("BonePile")
    for _ in range(5):
        x, y = rng.uniform(-2, 2), rng.uniform(-2, 2)
        angle = rng.uniform(0, 180)
        mat = frame((x, y, 0.25), (0, 0, angle))
        a.box((0, 0, 0), (2, 0.4, 0.4), "Bone", mat=mat)
        a.box((-1, 0, 0.05), (0.5, 0.8, 0.5), "Bone", mat=mat)
        a.box((1, 0, 0.05), (0.5, 0.8, 0.5), "Bone", mat=mat)
    return a


# --------------------------------------------------------------------------------------
# Snow
# --------------------------------------------------------------------------------------

def snow_tree(rng):
    a = Asset("SnowTree")
    ends = tree_trunk(a, rng, "DeadWood")
    leafy_canopy(a, rng, ends, ["LeafGreen"], cubes_per_end=2, snow_caps=True)
    return a


def frost_tree(rng):
    a = Asset("FrostTree")
    ends = tree_trunk(a, rng, "Wood")
    leafy_canopy(a, rng, ends, ["Snow", "Snow", "SnowShade"], dots=("SnowShade", 3))
    return a


def snow_pine(rng):
    a = Asset("SnowPine")
    a.box((0, 0, 1.2), (1.6, 1.6, 2.4), "DeadWood")
    z = 2
    for size in (7, 5.5, 4, 2.6):
        a.box((0, 0, z + 1), (size, size, 2), "Snow")
        a.box((0, 0, z + 0.25), (size + 0.4, size + 0.4, 0.5), "SnowShade")
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
    a.box((0, 0, 5.55), (1.8, 1.8, 0.2), "Coal")
    a.box((0, 0, 6.1), (1.2, 1.2, 1), "Coal")
    for x in (-0.35, 0.35):
        a.box((x, -0.72, 5), (0.25, 0.1, 0.25), "Coal")
    a.box((0, -1, 4.7), (0.25, 0.6, 0.25), "Carrot")
    for z in (2.8, 3.4):
        a.box((0, -0.96, z), (0.25, 0.1, 0.25), "Coal")
    for side in (-1, 1):
        a.beam((side * 0.9, 0, 3.6), (side * 2.2, 0, 4.4), 0.25, "DeadWood")
    return a


def ice_crystal(rng):
    a = Asset("IceCrystal")
    for _ in range(4):
        x, y = rng.uniform(-1.5, 1.5), rng.uniform(-1, 1)
        height = rng.uniform(2, 4.5)
        width = rng.uniform(0.9, 1.4)
        a.box((x, y, height / 2), (width, width, height), "Ice")
        a.box((x, y, height + 0.4), (width * 0.6, width * 0.6, 0.8), "LightBlue")
    a.box((0, 0, 0.3), (4, 3, 0.6), "Ice")
    return a


def snow_rock(rng):
    a = Asset("SnowRock")
    stepped_rock(a, rng, 6, 4, "RockBlueDark", "RockBlue", top="Snow")
    return a


def snow_log(rng):
    a = log(rng)
    a.name = "SnowLog"
    a.box((0, 0, 1.9), (5.6, 1.6, 0.25), "Snow")
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

        # Counter frame with slats
        for z in (0.4, 1.2, 2):
            a.box((0, -depth / 2 + 0.3, z), (width, 0.3, 0.3), "WoodLight")
            a.box((0, depth / 2 - 0.3, z), (width, 0.3, 0.3), "WoodLight")
            for x in (-width / 2 + 0.3, width / 2 - 0.3):
                a.box((x, 0, z), (0.3, depth, 0.3), "WoodLight")
        a.box((0, 0, 2.2), (width, depth, 0.3), "Wood")

        # Striped roof, slightly tilted toward the front
        stripes = 8
        stripe_width = (width + 1) / stripes
        for i in range(stripes):
            x = -(width + 1) / 2 + stripe_width * (i + 0.5)
            a.box((x, 0, 5.8), (stripe_width, depth + 1, 0.4), color if i % 2 == 0 else "White", rot=(10, 0, 0))
            a.box((x, -depth / 2 - 0.4, 5.1), (stripe_width, 0.2, 0.8), color if i % 2 == 0 else "White")
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
    return a


def signboard(rng):
    a = Asset("Signboard")
    for x in (-1.6, 1.6):
        a.box((x, 0, 1.6), (0.4, 0.4, 3.2), "Wood")
    a.box((0, 0, 2.4), (3.6, 0.3, 1.4), "WoodLight")
    a.box((0, -0.2, 2.4), (2.6, 0.1, 0.8), "White")
    return a


# --------------------------------------------------------------------------------------
# Sakura
# --------------------------------------------------------------------------------------

def cherry_tree(rng):
    a = Asset("CherryTree")
    ends = tree_trunk(a, rng, "Trunk")
    leafy_canopy(a, rng, ends, ["Sakura"], dots=("SakuraDark", 3))
    return a


def torii_frame(a, width=7, height=6):
    for x in (-width / 2, width / 2):
        a.box((x, 0, 0.5), (1, 1, 1), "ToriiBlue")
        a.box((x, 0, height / 2 + 0.5), (0.7, 0.7, height - 1), "ToriiRed")
    a.box((0, 0, height - 1), (width + 1.4, 0.5, 0.4), "ToriiRed")
    a.box((0, 0, height + 0.15), (width + 2.2, 0.8, 0.5), "ToriiBlue")
    a.box((0, 0, height + 0.55), (width + 3, 0.9, 0.3), "ToriiBlue")
    for side in (-1, 1):
        a.box((side * (width + 3) / 2, 0, height + 0.85), (0.6, 0.9, 0.3), "ToriiBlue")


def torii(rng):
    a = Asset("Torii")
    torii_frame(a)
    a.box((0, 0, 5.5), (0.6, 0.3, 1), "ToriiRed")
    return a


def gong_gate(rng):
    a = Asset("GongGate")
    torii_frame(a, width=7, height=7)
    radius = 1.8
    for z in range(-4, 5):
        row_z = z * 0.4
        half = math.sqrt(max(radius ** 2 - row_z ** 2, 0))
        a.box((0, 0, 3.2 + row_z), (half * 2, 0.4, 0.42), "Gold")
    a.box((0, -0.25, 3.2), (0.8, 0.2, 0.8), "Yellow")
    for side in (-1, 1):
        a.beam((side * 1.4, 0, 4.4), (side * 2.6, 0, 6.6), 0.15, "White")
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
    return a


def stone_lantern(rng):
    a = Asset("StoneLantern")
    a.box((0, 0, 0.3), (2, 2, 0.6), "StoneGrey")
    a.box((0, 0, 1.4), (0.8, 0.8, 1.6), "StoneGrey")
    a.box((0, 0, 2.4), (1.6, 1.6, 0.4), "StoneGrey")
    a.box((0, 0, 3), (1.2, 1.2, 0.8), "DarkStone")
    a.box((0, -0.55, 3), (0.6, 0.2, 0.5), "Gold")
    a.box((0, 0, 3.6), (2, 2, 0.4), "StoneGrey")
    a.pyramid((0, 0, 3.8), 1.4, 0.8, "StoneGrey")
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

    # Shoulder block
    shoulder = frame((x, 0, 17), (0, side * -8, 0))
    a.box((0, 0, 0), (5.4, 5.4, 5), "StoneGrey", mat=shoulder)
    a.box((0, 0, -2.7), (5.8, 5.8, 0.6), "Yellow", mat=shoulder)
    golem_glyph(a, shoulder @ frame((0, -2.72, 0.2)), "BrightViolet", 0.9)
    golem_moss(a, rng, shoulder @ frame((0, 0, 2.5)), 6, (2.2, 2.2))
    golem_crystals(a, rng, shoulder @ frame((side * 0.8, 0.6, 2.5)), 5, (1.6, 1.6), (2.5, 4.5))

    # Upper arm and forearm
    a.box((x + side * 0.4, 0, 12.4), (3.6, 3.6, 4.4), "StoneGrey")
    a.box((x + side * 0.4, 0, 10.6), (4.2, 4.2, 0.8), "Yellow")
    a.box((x + side * 0.6, 0, 7.6), (4.8, 4.8, 5.2), "DarkBlue")
    golem_glyph(a, frame((x + side * 0.6, -2.42, 7.8)), "Cobalt", 0.8)
    golem_crystals(a, rng, frame((x + side * 3, 0, 8), (0, side * 90, 0)), 3, (1.5, 1.5), (1.2, 2.2))

    # Fist
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

    # Chest gem plate
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
    "Forest": [apple_tree, pine_tree, bush, rock, rock_spire, log, log_pile, stump, mushroom, flower_patch,
               fence, pebbles],
    "Desert": [step_pyramid, dead_tree, cactus, rib_bones, sand_rock, bone_pile],
    "Snow": [snow_tree, frost_tree, snow_pine, snowman, ice_crystal, snow_rock, snow_log],
    "Market": [market_stall("StripeRed", "MarketStallRed"), market_stall("StripeBlue", "MarketStallBlue"),
               market_stall("StripePurple", "MarketStallPurple"), crate, signboard],
    "Sakura": [cherry_tree, torii, gong_gate, bamboo, stone_lantern],
    "Boss": [crystal_golem],
}


# --------------------------------------------------------------------------------------
# Blender scene
# --------------------------------------------------------------------------------------

def get_material(color):
    material = bpy.data.materials.get(color)
    if material:
        return material
    material = bpy.data.materials.new(color)
    r, g, b = (c / 255 for c in PALETTE[color])
    srgb_to_linear = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    material.diffuse_color = (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = material.diffuse_color
    bsdf.inputs["Roughness"].default_value = 0.6
    if color == "Glow":
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


def render_previews(roots_by_biome):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.view_settings.view_transform = "Standard"

    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.08, 0.28, 0.45, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.2
    scene.world = world

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4
    sun.rotation_euler = Euler((math.radians(50), math.radians(10), math.radians(-30)))
    scene.collection.objects.link(sun)

    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.data.type = "ORTHO"
    camera.data.clip_end = 1000
    scene.collection.objects.link(camera)
    scene.camera = camera

    ground_mesh = bpy.data.meshes.new("Ground")
    ground_mesh.from_pydata([(-2000, -2000, 0), (2000, -2000, 0), (2000, 2000, 0), (-2000, 2000, 0)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("Ground", ground_mesh)
    ground_material = bpy.data.materials.new("GroundMat")
    ground_material.use_nodes = True
    ground_material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.25, 0.25, 0.27, 1)
    ground_mesh.materials.append(ground_material)
    scene.collection.objects.link(ground)

    for biome, roots in roots_by_biome.items():
        for other in roots_by_biome.values():
            for root in other:
                hidden = other is not roots
                root.hide_render = hidden
                for child in root.children:
                    child.hide_render = hidden

        points = [child.matrix_world @ Vector(corner) for root in roots for child in root.children
                  for corner in child.bound_box]
        low = Vector([min(p[i] for p in points) for i in range(3)])
        high = Vector([max(p[i] for p in points) for i in range(3)])
        center = (low + high) / 2
        camera.rotation_euler = Euler((math.radians(70), 0, math.radians(20)))
        rotation = camera.rotation_euler.to_matrix()
        right, up, back = rotation.col[0], rotation.col[1], rotation.col[2]
        span_x = max(p.dot(right) for p in points) - min(p.dot(right) for p in points)
        span_y = max(p.dot(up) for p in points) - min(p.dot(up) for p in points)
        camera.data.ortho_scale = max(span_x, span_y * 16 / 9) * 1.1
        camera.location = center + back * 150
        scene.render.filepath = os.path.join(PREVIEW_DIR, f"{biome}.png")
        bpy.ops.render.render(write_still=True)


def bounds(asset):
    xs = [v[0] for verts, _, _ in asset.meshes.values() for v in verts]
    return min(xs), max(xs)


def main():
    render = "--render" in sys.argv
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

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
            root["width"] = high - low
            cursor += high - low + 4
            roots.append(root)
            print(f"[{biome}] {asset.name}: {sum(len(f) for _, f, _ in asset.meshes.values())} faces")
        roots_by_biome[biome] = roots

    if render:
        render_previews(roots_by_biome)
        bpy.data.objects.remove(bpy.data.objects["Camera"])
        bpy.data.objects.remove(bpy.data.objects["Sun"])
        bpy.data.objects.remove(bpy.data.objects["Ground"])

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "StudAssets.blend"))


if __name__ == "__main__":
    main()
