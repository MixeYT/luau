import bpy
import bmesh
import math
import os
import numpy
from mathutils import Euler, Matrix, Vector

# Run inside Blender 4.1+: Scripting tab -> Open -> Run Script.
# Builds blocky chibi pets and their eggs for every world, in the style of the Free Pet Pack:
# one rounded block for head and body, stubby feet and a face painted into the texture.
# Every model is one mesh with one baked texture, plus a second texture for its Golden variant
# (same mesh, swap the MeshPart TextureID). Front is -Y, exported so it faces -Z (LookVector) in Roblox.

TEXTURE_SIZE = 512
BAKE_SAMPLES = 32
UV_MARGIN = 0.01
PACK_SPACING = 3.6
ROW_SPACING = 5.0

SMOOTH_ANGLE = 40  # auto smooth angle, every edge sharper than this stays hard

#// Shapes

FEET_HEIGHT = 0.35  # bottom of the body, the feet fill the space below it
BODY_BEVEL = 0.3

#// Look

EDGE_BEVEL_RADIUS = 0.05
EDGE_START = 0.996
EDGE_FULL = 0.94
EDGE_STRENGTH = 0.75
CAVITY_DISTANCE = 0.25
CAVITY_STRENGTH = 0.6
COLOR_VARIATION = 0.06
BOTTOM_SHADE = 0.3  # how much the bottom of a model leans towards its shadow color
TOP_LIGHT = 0.15  # how much the top of a model leans towards its highlight color

HIGHLIGHT_LIGHTEN = 0.3  # highlight = base color mixed this much towards white
SHADOW_DARKEN = 0.4
SHADOW_TINT = "3B2D6E"
SHADOW_TINT_AMOUNT = 0.2

#// Face

FACE_RESOLUTION = 256  # pixels per unit
FACE_DARK = "2B2233"
FACE_WHITE = "FFFFFF"
FACE_BLUSH = "FF8FB3"

#// Golden

GOLD_DARK = "A8520E"
GOLD_LIGHT = "FFE680"
GOLD_SPARKLE = "FFF8D6"

# Leave empty to skip. Otherwise every model is exported as FBX + PNG + Golden PNG into this folder.
EXPORT_FOLDER = os.path.join(os.path.dirname(bpy.data.filepath), "Export") if bpy.data.filepath else ""

# Base color of every material, shadows and highlights are derived from it.
PALETTE = {
	"Nose": "3A2A35",
	"Gold": "FFC43A",
	"PigPink": "FFA3C2",
	"PigDark": "F07AA3",
	"ChickYellow": "FFD84A",
	"Beak": "FF9A2E",
	"Wool": "F7F4EE",
	"SheepFace": "F2D9BE",
	"SheepDark": "5A4A55",
	"CowWhite": "F7F5F2",
	"CowPink": "FFB3C7",
	"Horn": "F2E3C2",
	"BellRed": "E0414F",
	"Unicorn": "FBF8FF",
	"ManeRed": "FF5A6E",
	"ManeOrange": "FF9A3C",
	"ManeYellow": "FFE04A",
	"ManeGreen": "6EE07A",
	"ManeBlue": "5AB8FF",
	"ManePurple": "B07AFF",
	"Fox": "FF8A3A",
	"FoxWhite": "FFF4E6",
	"FoxDark": "4A3036",
	"Bear": "A8693E",
	"BearLight": "E8BE8A",
	"Raccoon": "9A9AAE",
	"RaccoonDark": "3E3A4A",
	"RaccoonLight": "E3E3EE",
	"Owl": "9A6A4A",
	"OwlLight": "F2DDB6",
	"OwlDark": "6A4232",
	"Deer": "C98A55",
	"DeerLight": "FFF0DC",
	"Antler": "8FF0FF",
	"Meerkat": "D9A56A",
	"MeerkatLight": "F7DFB6",
	"MeerkatDark": "5A3E2E",
	"MeerkatPatch": "A8754A",
	"Fennec": "F5D3A0",
	"FennecInner": "FFB3C2",
	"FennecDark": "8A5A3A",
	"Lizard": "7CCB4F",
	"LizardBelly": "F2E37A",
	"LizardSpike": "E0703A",
	"Camel": "D9A863",
	"CamelLight": "F2D3A0",
	"Fez": "D9343F",
	"Tassel": "2B2233",
	"Scorpion": "C2413A",
	"ScorpionDark": "7A1E24",
	"Venom": "9CFF5A",
	"Scarab": "2FB8A0",
	"ScarabDark": "1E6A6E",
	"Cobra": "4FAE5A",
	"CobraBelly": "F2E3A0",
	"Hood": "2E8A62",
	"Tongue": "FF4A6A",
	"Bandage": "F2E9D3",
	"MummyDark": "8A7A6A",
	"Jackal": "2E2A3A",
	"Lapis": "2E5BE0",
	"Sandstone": "E8B878",
	"Nemes": "3A6AE0",
	"EggWhite": "F4F8FF",
	"GrassEgg": "8EE05A",
	"ForestEgg": "6A9A4A",
	"SandEgg": "F2C77A",
	"PharaohEgg": "2E5BE0",
}


#// Colors

def to_srgb(hex_color):
	return [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def to_hex(channels):
	return "".join("%02X" % round(max(0, min(1, channel)) * 255) for channel in channels)


def to_linear(channels):
	return tuple(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels) + (1,)


def to_color(hex_color):
	return to_linear(to_srgb(hex_color))


def goldify(hex_color):
	# Keeps the brightness of a color but turns it into gold, used for the Golden texture.
	red, green, blue = to_srgb(hex_color)
	brightness = max(0, min(1, (0.3 * red + 0.59 * green + 0.11 * blue) * 1.1 - 0.02))
	dark, light = to_srgb(GOLD_DARK), to_srgb(GOLD_LIGHT)
	return to_hex([low + (high - low) * brightness for low, high in zip(dark, light)])


def material_colors(hex_color):
	base = to_srgb(hex_color)
	tint = to_srgb(SHADOW_TINT)
	highlight = [channel + (1 - channel) * HIGHLIGHT_LIGHTEN for channel in base]
	shadow = [channel * (1 - SHADOW_DARKEN) * (1 - SHADOW_TINT_AMOUNT) + tinted * SHADOW_TINT_AMOUNT for channel, tinted in zip(base, tint)]
	return to_linear(base), to_linear(shadow), to_linear(highlight)


#// Math Helpers

def catmull_rom(points, smoothness):
	points = [Vector(point) for point in points]
	result = []
	for i in range(len(points) - 1):
		p0 = points[max(i - 1, 0)]
		p1 = points[i]
		p2 = points[i + 1]
		p3 = points[min(i + 2, len(points) - 1)]

		for step in range(smoothness):
			t = step / smoothness
			result.append(0.5 * (
				2 * p1
				+ (p2 - p0) * t
				+ (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
				+ (3 * p1 - p0 - 3 * p2 + p3) * t ** 3
			))
	return result


def rotation_matrix(rotation):
	return Euler([math.radians(angle) for angle in rotation]).to_matrix().to_4x4()


#// Mesh Helpers

def new_verts_since(bm, before):
	return [vert for vert in bm.verts if vert not in before]


def add_block(bm, size, location=(0, 0, 0), bevel=0.08, rotation=(0, 0, 0), taper=1.0, segments=2):
	# Rounded box. Taper shrinks the top face, which turns the block into ears, beaks and spikes.
	before = set(bm.verts)
	result = bmesh.ops.create_cube(bm, size=1)
	for vert in result["verts"]:
		if vert.co.z > 0:
			vert.co.x *= taper
			vert.co.y *= taper
		vert.co.x *= size[0]
		vert.co.y *= size[1]
		vert.co.z *= size[2]
	edges = list({edge for vert in result["verts"] for edge in vert.link_edges})
	bevel = min(bevel, min(size) * 0.45, min(size[0], size[1]) * taper * 0.45)
	if bevel > 0.005:
		bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=segments, affect="EDGES", profile=0.5, clamp_overlap=True)
	bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(location)) @ rotation_matrix(rotation), verts=new_verts_since(bm, before))


def add_ball(bm, location, radius, scale=(1, 1, 1), segments=12, rings=7):
	bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius, matrix=Matrix.LocRotScale(Vector(location), None, Vector(scale)))


def add_lathe(bm, profile, sides, matrix=Matrix(), closed=False):
	# Revolves (radius, height) points around Z. A closed profile becomes a ring without caps.
	rings = []
	for radius, height in profile:
		if radius == 0:
			rings.append([bm.verts.new(matrix @ Vector((0, 0, height)))])
			continue

		ring = []
		for i in range(sides):
			angle = math.tau * i / sides
			ring.append(bm.verts.new(matrix @ Vector((math.cos(angle) * radius, math.sin(angle) * radius, height))))
		rings.append(ring)

	pairs = list(zip(rings, rings[1:]))
	if closed:
		pairs.append((rings[-1], rings[0]))
	for lower, upper in pairs:
		for i in range(sides):
			if len(lower) == 1:
				bm.faces.new((lower[0], upper[i], upper[i - 1]))
			elif len(upper) == 1:
				bm.faces.new((lower[i - 1], lower[i], upper[0]))
			else:
				bm.faces.new((lower[i - 1], lower[i], upper[i], upper[i - 1]))

	if not closed:
		for ring in (rings[0], rings[-1]):
			if len(ring) > 1:
				bm.faces.new(ring)


def add_sweep(bm, points, radii, sides=6, smoothness=3):
	# Tube along (x, y, z) points. A radius of 0 ends the tube in a point.
	points = [Vector(point) for point in points]
	path = catmull_rom(points, smoothness) + [points[-1]]
	path_radii = []
	for index in range(len(path)):
		segment = min(index // smoothness, len(radii) - 2)
		local = index / smoothness - segment
		path_radii.append(radii[segment] + (radii[segment + 1] - radii[segment]) * local)

	rings = []
	for index, (center, radius) in enumerate(zip(path, path_radii)):
		tangent = (path[min(index + 1, len(path) - 1)] - path[max(index - 1, 0)]).normalized()
		if radius <= 0:
			rings.append([bm.verts.new(center)])
			continue

		side = Vector((0, 1, 0)) - tangent * tangent.y
		side = side.normalized() if side.length > 1e-3 else Vector((1, 0, 0))
		normal = tangent.cross(side).normalized()
		rings.append([bm.verts.new(center + normal * math.cos(math.tau * i / sides) * radius + side * math.sin(math.tau * i / sides) * radius) for i in range(sides)])

	for lower, upper in zip(rings, rings[1:]):
		for i in range(sides):
			if len(lower) == 1:
				bm.faces.new((lower[0], upper[i], upper[i - 1]))
			elif len(upper) == 1:
				bm.faces.new((lower[i - 1], lower[i], upper[0]))
			else:
				bm.faces.new((lower[i - 1], lower[i], upper[i], upper[i - 1]))

	for ring in (rings[0], rings[-1]):
		if len(ring) > 1:
			bm.faces.new(ring)


def add_disc(bm, center, radius, depth, sides=12):
	# Short cylinder facing -Y, used for eye rings, round ears and muzzles.
	add_lathe(bm, [(0, -depth), (radius * 0.85, -depth), (radius, -depth * 0.6), (radius, depth * 0.6), (radius * 0.85, depth), (0, depth)], sides, Matrix.Translation(Vector(center)) @ rotation_matrix((90, 0, 0)))


#// Pet Helpers

def add_body(bm, width, depth, height, bottom=FEET_HEIGHT, bevel=BODY_BEVEL):
	add_block(bm, (width, depth, height), (0, 0, bottom + height / 2), bevel, segments=3)
	return bottom + height


def add_feet(bm, width, depth, size=(0.55, 0.6, 0.45), spread=0.27):
	for x in (-1, 1):
		for y in (-1, 1):
			add_block(bm, size, (x * width * spread, y * depth * 0.28, size[2] / 2), 0.1)


def face_region(width, depth, height, bottom=FEET_HEIGHT, bevel=BODY_BEVEL):
	return (-width / 2 + bevel * 0.5, width / 2 - bevel * 0.5, bottom + bevel * 0.4, bottom + height - bevel * 0.4)


def default_face(width, height, bottom=FEET_HEIGHT, **overrides):
	face = {
		"eyes": ("round", "round"),
		"eye_height": bottom + height * 0.6,
		"eye_spacing": width * 0.2,
		"eye_size": 0.17,
		"mouth": "w",
		"mouth_height": bottom + height * 0.42,
		"blush": True,
	}
	face.update(overrides)
	return face


#// Face Painting

def ellipse(grid_x, grid_z, center_x, center_z, radius_x, radius_z):
	return ((grid_x - center_x) / radius_x) ** 2 + ((grid_z - center_z) / radius_z) ** 2 <= 1


def arc(grid_x, grid_z, center_x, center_z, radius, thickness, upper):
	distance = numpy.sqrt((grid_x - center_x) ** 2 + (grid_z - center_z) ** 2)
	side = grid_z >= center_z if upper else grid_z <= center_z
	return (numpy.abs(distance - radius) <= thickness / 2) & side


def paint_face(name, face, region):
	# R: dark eyes and mouth, G: white eye shine, B: blush. Projected onto the front of the model.
	min_x, max_x, min_z, max_z = region
	pixel_width = int((max_x - min_x) * FACE_RESOLUTION)
	pixel_height = int((max_z - min_z) * FACE_RESOLUTION)
	grid_x, grid_z = numpy.meshgrid(
		min_x + (numpy.arange(pixel_width) + 0.5) / FACE_RESOLUTION,
		min_z + (numpy.arange(pixel_height) + 0.5) / FACE_RESOLUTION,
	)
	dark = numpy.zeros(grid_x.shape, dtype=bool)
	white = numpy.zeros(grid_x.shape, dtype=bool)
	blush = numpy.zeros(grid_x.shape, dtype=bool)

	size = face["eye_size"]
	eye_z = face["eye_height"]
	for side, style in zip((-1, 1), face["eyes"]):
		eye_x = side * face["eye_spacing"]
		if style == "round":
			dark |= ellipse(grid_x, grid_z, eye_x, eye_z, size * 0.8, size)
			white |= ellipse(grid_x, grid_z, eye_x - size * 0.28, eye_z + size * 0.38, size * 0.3, size * 0.3)
			white |= ellipse(grid_x, grid_z, eye_x + size * 0.25, eye_z - size * 0.4, size * 0.14, size * 0.14)
		elif style == "happy":
			dark |= arc(grid_x, grid_z, eye_x, eye_z - size * 0.4, size * 0.75, size * 0.32, True)
		elif style == "sleepy":
			dark |= arc(grid_x, grid_z, eye_x, eye_z + size * 0.2, size * 0.75, size * 0.32, False)

	mouth = face["mouth"]
	mouth_z = face["mouth_height"]
	if mouth == "w":
		for side in (-1, 1):
			dark |= arc(grid_x, grid_z, side * 0.075, mouth_z, 0.075, 0.045, False)
	elif mouth == "smile":
		dark |= arc(grid_x, grid_z, 0, mouth_z + 0.06, 0.13, 0.05, False)
	elif mouth == "o":
		dark |= ellipse(grid_x, grid_z, 0, mouth_z, 0.06, 0.075)
	elif mouth == "fangs":
		dark |= arc(grid_x, grid_z, 0, mouth_z + 0.06, 0.13, 0.05, False)
		for side in (-1, 1):
			tooth_x = side * 0.07
			white |= (numpy.abs(grid_x - tooth_x) <= 0.03 * (1 - (mouth_z - 0.08 - grid_z) / 0.09)) & (grid_z <= mouth_z - 0.065) & (grid_z >= mouth_z - 0.16)

	if face["blush"]:
		for side in (-1, 1):
			blush |= ellipse(grid_x, grid_z, side * (face["eye_spacing"] + size * 0.9), eye_z - size * 1.35, size * 0.75, size * 0.42)

	pixels = numpy.zeros((pixel_height, pixel_width, 4), dtype=numpy.float32)
	pixels[..., 0] = dark
	pixels[..., 1] = white
	pixels[..., 2] = blush & ~dark
	pixels[..., 3] = 1

	image = bpy.data.images.new(name + "Face", pixel_width, pixel_height, alpha=True, float_buffer=True)
	image.colorspace_settings.name = "Non-Color"
	image.pixels.foreach_set(pixels.ravel())
	image.pack()
	return image, region


#// Spawn 01 Farm Egg

def build_piggy(part):
	width, depth, height = 2.3, 1.9, 2.0
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.5, 0.18, 0.5), (side * 0.7, -0.3, top + 0.1), 0.06, rotation=(35, 0, side * 12), taper=0.3)
	tail = [(math.cos(angle) * 0.13, depth / 2 + 0.06 + angle * 0.025, FEET_HEIGHT + height * 0.55 + math.sin(angle) * 0.13) for angle in numpy.linspace(0, math.tau * 1.2, 10)]
	add_sweep(bm, tail, [0.06] * 9 + [0.04])
	part(bm, "PigPink")

	bm = bmesh.new()
	add_block(bm, (0.8, 0.32, 0.55), (0, -depth / 2 - 0.1, FEET_HEIGHT + height * 0.36), 0.12)
	add_feet(bm, width, depth)
	part(bm, "PigDark")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.12, 0.08, 0.2), (side * 0.15, -depth / 2 - 0.27, FEET_HEIGHT + height * 0.36), 0.03)
	part(bm, "Nose")

	return {
		"face": default_face(width, height, mouth=None),
		"region": face_region(width, depth, height),
		"effects": {"PigPink": {"patterns": [("spots", "FFC2D6", 2.5, 0.35)]}},
	}


def build_chick(part):
	width, depth, height = 2.1, 1.8, 1.85
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for index, (x, tilt) in enumerate(((-0.14, -25), (0.0, 0), (0.14, 25))):
		add_block(bm, (0.16, 0.12, 0.4 if index == 1 else 0.3), (x, -0.2, top + 0.12), 0.04, rotation=(0, tilt, 0), taper=0.4)
	for side in (-1, 1):
		add_block(bm, (0.22, 0.85, 0.75), (side * (width / 2 + 0.04), 0.1, FEET_HEIGHT + height * 0.42), 0.1, rotation=(0, side * 12, 0))
	part(bm, "ChickYellow")

	bm = bmesh.new()
	add_block(bm, (0.42, 0.42, 0.34), (0, -depth / 2 - 0.08, FEET_HEIGHT + height * 0.45), 0.06, rotation=(90, 0, 0), taper=0.25)
	add_feet(bm, width, depth, size=(0.45, 0.55, 0.42))
	part(bm, "Beak")

	return {
		"face": default_face(width, height, mouth=None, eye_height=FEET_HEIGHT + height * 0.66),
		"region": face_region(width, depth, height),
	}


def build_sheep(part):
	width, depth, height = 2.3, 2.0, 2.0
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for x, y, z, radius in ((-0.6, -0.4, top, 0.42), (0.1, -0.5, top + 0.05, 0.45), (0.65, -0.2, top - 0.02, 0.4), (-0.3, 0.4, top, 0.45), (0.45, 0.5, top - 0.02, 0.42), (-1.1, 0.3, top - 0.6, 0.4), (1.1, 0.1, top - 0.55, 0.42), (0, 1.0, top - 0.5, 0.45)):
		add_ball(bm, (x, y, z), radius)
	part(bm, "Wool")

	bm = bmesh.new()
	add_block(bm, (1.45, 0.3, 1.25), (0, -depth / 2 - 0.05, FEET_HEIGHT + height * 0.48), 0.22, segments=3)
	for side in (-1, 1):
		add_block(bm, (0.5, 0.24, 0.24), (side * 0.9, -depth / 2 + 0.05, FEET_HEIGHT + height * 0.7), 0.08, rotation=(0, side * -20, 0))
	part(bm, "SheepFace")

	bm = bmesh.new()
	add_feet(bm, width, depth)
	part(bm, "SheepDark")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.58, eye_spacing=0.32, mouth="w", mouth_height=FEET_HEIGHT + height * 0.36),
		"region": face_region(width, depth, height),
		"effects": {"Wool": {"patterns": [("nebula", "E3E3F2", 4, 0.5)]}},
	}


def build_cow(part):
	width, depth, height = 2.4, 2.0, 2.0
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.55, 0.28, 0.24), (side * (width / 2 + 0.12), -0.3, top - 0.35), 0.08, rotation=(0, side * 15, 0))
	add_sweep(bm, [(0.2, depth / 2, FEET_HEIGHT + height * 0.6), (0.35, depth / 2 + 0.2, FEET_HEIGHT + height * 0.4), (0.3, depth / 2 + 0.25, FEET_HEIGHT + height * 0.15)], [0.05, 0.045, 0.04])
	part(bm, "CowWhite")

	bm = bmesh.new()
	add_block(bm, (1.1, 0.34, 0.65), (0, -depth / 2 - 0.1, FEET_HEIGHT + height * 0.3), 0.15)
	part(bm, "CowPink")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.12, 0.08, 0.2), (side * 0.22, -depth / 2 - 0.28, FEET_HEIGHT + height * 0.3), 0.03)
	add_ball(bm, (0.3, depth / 2 + 0.25, FEET_HEIGHT + height * 0.1), 0.11)
	add_feet(bm, width, depth)
	part(bm, "Nose")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.2, 0.2, 0.42), (side * 0.75, -0.3, top + 0.12), 0.05, rotation=(0, side * 25, 0), taper=0.45)
	part(bm, "Horn")

	bm = bmesh.new()
	add_lathe(bm, [(0, 0.0), (0.16, 0.02), (0.14, 0.2), (0.08, 0.3), (0, 0.32)], 10, Matrix.Translation((0, -depth / 2 - 0.12, FEET_HEIGHT - 0.12)))
	part(bm, "Gold")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.66, mouth=None),
		"region": face_region(width, depth, height),
		"effects": {"CowWhite": {"patterns": [("spots", "2B2233", 1.3, 1)]}},
	}


def build_unicorn(part):
	width, depth, height = 2.3, 2.0, 2.1
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.3, 0.18, 0.5), (side * 0.75, 0.1, top + 0.12), 0.05, rotation=(-10, side * 15, 0), taper=0.35)
	part(bm, "Unicorn")

	bm = bmesh.new()
	add_block(bm, (1.0, 0.32, 0.6), (0, -depth / 2 - 0.1, FEET_HEIGHT + height * 0.3), 0.15)
	part(bm, "CowPink")

	mane = ["ManeRed", "ManeOrange", "ManeYellow", "ManeGreen", "ManeBlue", "ManePurple"]
	path = [(0.25, -depth / 2 + 0.05, top - 0.05), (0, -0.3, top + 0.12), (0, 0.15, top + 0.15), (0, 0.6, top + 0.05), (0, depth / 2 + 0.1, top - 0.4), (0, depth / 2 + 0.16, top - 0.9)]
	for key, location, tilt in zip(mane, path, (20, 0, -5, -25, -60, -80)):
		bm = bmesh.new()
		add_block(bm, (0.55, 0.5, 0.48), location, 0.15, rotation=(tilt, 0, -25 if key == "ManeRed" else 0))
		if key == "ManeBlue":
			add_block(bm, (0.32, 0.3, 0.5), (0, depth / 2 + 0.3, FEET_HEIGHT + 0.6), 0.1, rotation=(-30, 0, 0))
		part(bm, key)

	bm = bmesh.new()
	horn = []
	for index in range(7):
		t = index / 6
		radius = 0.22 * (1 - t) + 0.03
		horn.append((radius * (1.15 if index % 2 else 0.85), 0.95 * t))
	horn.append((0, 1.08))
	add_lathe(bm, horn, 8, Matrix.Translation((-0.15, -0.55, top - 0.08)) @ rotation_matrix((-12, 0, 0)))
	add_feet(bm, width, depth)
	part(bm, "Gold")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.66, mouth=None),
		"region": face_region(width, depth, height),
		"effects": {"Unicorn": {"patterns": [("stars", "FFD6F5", 6, 0.8)]}},
	}


#// Spawn 02 Forest Egg

def build_fox(part):
	width, depth, height = 2.3, 1.9, 2.0
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.55, 0.2, 0.7), (side * 0.68, -0.15, top + 0.22), 0.05, rotation=(0, side * 12, 0), taper=0.2)
	add_block(bm, (0.75, 0.9, 0.75), (0.55, depth / 2 + 0.35, FEET_HEIGHT + 0.65), 0.25, rotation=(-40, 0, -20))
	part(bm, "Fox")

	bm = bmesh.new()
	add_block(bm, (1.5, 0.24, 0.8), (0, -depth / 2 - 0.02, FEET_HEIGHT + height * 0.25), 0.2)
	add_block(bm, (0.6, 0.6, 0.6), (0.8, depth / 2 + 0.75, FEET_HEIGHT + 1.05), 0.22, rotation=(-40, 0, -20))
	part(bm, "FoxWhite")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.22, 0.22, 0.25), (side * 0.75, -0.15, top + 0.5), 0.04, rotation=(0, side * 12, 0), taper=0.3)
	add_block(bm, (0.2, 0.12, 0.14), (0, -depth / 2 - 0.16, FEET_HEIGHT + height * 0.42), 0.05)
	add_feet(bm, width, depth)
	part(bm, "FoxDark")

	return {
		"face": default_face(width, height, mouth="w", mouth_height=FEET_HEIGHT + height * 0.34),
		"region": face_region(width, depth, height),
	}


def build_bear(part):
	width, depth, height = 2.4, 2.0, 2.1
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_disc(bm, (side * 0.8, 0.0, top + 0.05), 0.34, 0.14)
	part(bm, "Bear")

	bm = bmesh.new()
	for side in (-1, 1):
		add_disc(bm, (side * 0.8, -0.1, top + 0.05), 0.2, 0.08)
	add_block(bm, (0.85, 0.3, 0.55), (0, -depth / 2 - 0.08, FEET_HEIGHT + height * 0.38), 0.18)
	part(bm, "BearLight")

	bm = bmesh.new()
	add_block(bm, (0.3, 0.12, 0.18), (0, -depth / 2 - 0.25, FEET_HEIGHT + height * 0.44), 0.07)
	part(bm, "Nose")

	bm = bmesh.new()
	add_feet(bm, width, depth)
	part(bm, "OwlDark")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.64, mouth="w", mouth_height=FEET_HEIGHT + height * 0.33),
		"region": face_region(width, depth, height),
	}


def build_raccoon(part):
	width, depth, height = 2.3, 1.9, 2.0
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.45, 0.2, 0.45), (side * 0.72, -0.1, top + 0.12), 0.05, rotation=(0, side * 15, 0), taper=0.3)
	part(bm, "Raccoon")

	bm = bmesh.new()
	add_block(bm, (width - 0.25, 0.1, 0.5), (0, -depth / 2 - 0.02, FEET_HEIGHT + height * 0.6), 0.05)
	for index in range(2):
		add_block(bm, (0.52, 0.55, 0.42), (0.55 + index * 0.18, depth / 2 + 0.3 + index * 0.42, FEET_HEIGHT + 0.5 + index * 0.45), 0.15, rotation=(-35, 0, -15))
	add_feet(bm, width, depth)
	part(bm, "RaccoonDark")

	bm = bmesh.new()
	add_block(bm, (0.8, 0.28, 0.5), (0, -depth / 2 - 0.06, FEET_HEIGHT + height * 0.32), 0.15)
	add_block(bm, (0.5, 0.48, 0.38), (0.62, depth / 2 + 0.5, FEET_HEIGHT + 0.7), 0.13, rotation=(-35, 0, -15))
	add_block(bm, (0.42, 0.42, 0.42), (0.82, depth / 2 + 0.95, FEET_HEIGHT + 1.18), 0.15, rotation=(-35, 0, -15))
	for side in (-1, 1):
		add_block(bm, (0.26, 0.1, 0.26), (side * 0.72, -0.22, top + 0.08), 0.04, rotation=(0, side * 15, 0), taper=0.3)
	part(bm, "RaccoonLight")

	bm = bmesh.new()
	add_block(bm, (0.24, 0.12, 0.16), (0, -depth / 2 - 0.22, FEET_HEIGHT + height * 0.38), 0.06)
	part(bm, "Nose")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.6, mouth="w", mouth_height=FEET_HEIGHT + height * 0.28),
		"region": face_region(width, depth, height),
	}


def build_owl(part):
	width, depth, height = 2.2, 1.9, 2.25
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.4, 0.22, 0.55), (side * 0.78, 0.0, top + 0.12), 0.05, rotation=(0, side * 25, 0), taper=0.25)
	part(bm, "Owl")

	bm = bmesh.new()
	add_block(bm, (1.4, 0.24, 1.0), (0, -depth / 2 - 0.02, FEET_HEIGHT + height * 0.3), 0.25)
	for side in (-1, 1):
		add_disc(bm, (side * 0.45, -depth / 2 - 0.04, FEET_HEIGHT + height * 0.66), 0.38, 0.08, sides=14)
	part(bm, "OwlLight")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.25, 1.0, 1.1), (side * (width / 2 + 0.05), 0.15, FEET_HEIGHT + height * 0.45), 0.1, rotation=(0, side * 8, 0))
	part(bm, "OwlDark")

	bm = bmesh.new()
	add_block(bm, (0.3, 0.3, 0.3), (0, -depth / 2 - 0.12, FEET_HEIGHT + height * 0.5), 0.05, rotation=(110, 0, 0), taper=0.2)
	add_feet(bm, width, depth, size=(0.5, 0.5, 0.42))
	part(bm, "Beak")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.66, eye_spacing=0.45, eye_size=0.2, mouth=None, blush=False),
		"region": face_region(width, depth, height),
		"effects": {"OwlLight": {"patterns": [("bands", "D9B88A", 9, 0.5)]}},
	}


def build_mystic_deer(part):
	width, depth, height = 2.2, 1.9, 2.1
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.55, 0.2, 0.28), (side * (width / 2 + 0.15), -0.15, top - 0.3), 0.08, rotation=(0, side * -20, 0), taper=0.6)
	part(bm, "Deer")

	bm = bmesh.new()
	add_block(bm, (0.9, 0.3, 0.6), (0, -depth / 2 - 0.08, FEET_HEIGHT + height * 0.3), 0.18)
	add_block(bm, (0.3, 0.3, 0.32), (0, depth / 2 + 0.1, FEET_HEIGHT + height * 0.7), 0.1)
	part(bm, "DeerLight")

	bm = bmesh.new()
	add_block(bm, (0.26, 0.12, 0.16), (0, -depth / 2 - 0.25, FEET_HEIGHT + height * 0.36), 0.06)
	add_feet(bm, width, depth)
	part(bm, "Nose")

	bm = bmesh.new()
	for side in (-1, 1):
		beam = [(side * 0.5, -0.1, top - 0.05), (side * 0.65, -0.1, top + 0.45), (side * 0.95, -0.05, top + 0.85), (side * 1.0, 0.0, top + 1.15)]
		add_sweep(bm, beam, [0.08, 0.07, 0.055, 0.0], sides=6)
		for start, end in ((1, (side * 0.38, -0.12, top + 0.75)), (2, (side * 0.7, -0.02, top + 1.15)), (1, (side * 1.0, -0.1, top + 0.55))):
			root = Vector(beam[start])
			add_sweep(bm, [root, root.lerp(Vector(end), 0.5) + Vector((0, 0, 0.05)), end], [0.055, 0.045, 0.0], sides=6)
	part(bm, "Antler")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.64, mouth=None),
		"region": face_region(width, depth, height),
		"effects": {
			"Deer": {"patterns": [("spots", "FFF0DC", 3.2, 0.7)]},
			"Antler": {"gradient": (2.4, 3.6, [(0, "6ADFF0"), (1, "E8FFFF")]), "patterns": [("stars", "FFFFFF", 8, 1)]},
		},
	}


#// Desert 01 Sand Egg

def build_meerkat(part):
	width, depth, height = 1.95, 1.7, 2.5
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	add_sweep(bm, [(0.2, depth / 2, FEET_HEIGHT + 0.3), (0.45, depth / 2 + 0.4, FEET_HEIGHT + 0.2), (0.75, depth / 2 + 0.55, FEET_HEIGHT + 0.5)], [0.11, 0.09, 0.0], sides=6)
	part(bm, "Meerkat")

	bm = bmesh.new()
	add_block(bm, (1.2, 0.24, 1.2), (0, -depth / 2 - 0.02, FEET_HEIGHT + height * 0.3), 0.25)
	add_block(bm, (0.7, 0.26, 0.42), (0, -depth / 2 - 0.06, FEET_HEIGHT + height * 0.47), 0.12)
	part(bm, "MeerkatLight")

	bm = bmesh.new()
	for side in (-1, 1):
		add_disc(bm, (side * (width / 2 + 0.02), 0.0, top - 0.35), 0.18, 0.07)
		add_block(bm, (0.32, 0.36, 0.5), (side * 0.38, -depth / 2 - 0.12, FEET_HEIGHT + height * 0.3), 0.12, rotation=(-25, 0, 0))
	add_block(bm, (0.2, 0.12, 0.13), (0, -depth / 2 - 0.22, FEET_HEIGHT + height * 0.52), 0.05)
	part(bm, "MeerkatDark")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.38, -depth / 2 - 0.01, FEET_HEIGHT + height * 0.62), 0.27, (1, 0.25, 1.15))
	part(bm, "MeerkatPatch")

	bm = bmesh.new()
	add_feet(bm, width, depth)
	part(bm, "Meerkat")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.62, eye_spacing=0.38, eye_size=0.15, mouth="w", mouth_height=FEET_HEIGHT + height * 0.43),
		"region": face_region(width, depth, height),
	}


def build_fennec(part):
	width, depth, height = 2.1, 1.8, 1.9
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.8, 0.2, 1.15), (side * 0.75, -0.05, top + 0.45), 0.06, rotation=(0, side * 22, 0), taper=0.18)
	add_block(bm, (0.6, 0.75, 0.6), (0.45, depth / 2 + 0.3, FEET_HEIGHT + 0.55), 0.2, rotation=(-40, 0, -15))
	part(bm, "Fennec")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.5, 0.1, 0.8), (side * 0.72, -0.15, top + 0.38), 0.04, rotation=(0, side * 22, 0), taper=0.18)
	part(bm, "FennecInner")

	bm = bmesh.new()
	add_block(bm, (0.45, 0.45, 0.42), (0.62, depth / 2 + 0.68, FEET_HEIGHT + 0.92), 0.15, rotation=(-40, 0, -15))
	add_block(bm, (0.2, 0.12, 0.14), (0, -depth / 2 - 0.08, FEET_HEIGHT + height * 0.42), 0.05)
	add_feet(bm, width, depth, size=(0.45, 0.55, 0.42))
	part(bm, "FennecDark")

	return {
		"face": default_face(width, height, mouth="w", mouth_height=FEET_HEIGHT + height * 0.33),
		"region": face_region(width, depth, height),
	}


def build_lizard(part):
	width, depth, height = 2.2, 2.3, 1.6
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	tail = [(0.0, depth / 2 - 0.1, FEET_HEIGHT + 0.5), (0.2, depth / 2 + 0.5, FEET_HEIGHT + 0.3), (0.8, depth / 2 + 0.7, FEET_HEIGHT + 0.25), (1.15, depth / 2 + 0.35, FEET_HEIGHT + 0.25), (1.0, depth / 2 + 0.05, FEET_HEIGHT + 0.25)]
	add_sweep(bm, tail, [0.36, 0.28, 0.2, 0.12, 0.0], sides=8)
	add_feet(bm, width, depth, size=(0.7, 0.7, 0.42), spread=0.33)
	part(bm, "Lizard")

	bm = bmesh.new()
	add_block(bm, (1.5, 0.22, 0.6), (0, -depth / 2 - 0.02, FEET_HEIGHT + height * 0.25), 0.18)
	part(bm, "LizardBelly")

	bm = bmesh.new()
	for index, y in enumerate((-0.6, -0.15, 0.3, 0.75)):
		add_block(bm, (0.12, 0.38, 0.38 - index * 0.04), (0, y, top + 0.1), 0.04, rotation=(0, 0, 0), taper=0.25)
	part(bm, "LizardSpike")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.62, eye_spacing=0.5, eye_size=0.18, mouth="smile", mouth_height=FEET_HEIGHT + height * 0.36),
		"region": face_region(width, depth, height),
		"effects": {"Lizard": {"patterns": [("spots", "5AA83A", 3.5, 0.6)]}},
	}


def build_camel(part):
	width, depth, height = 2.3, 2.0, 1.95
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	add_block(bm, (1.35, 1.1, 0.9), (0, 0.15, top + 0.2), 0.4, segments=3)
	for side in (-1, 1):
		add_block(bm, (0.4, 0.18, 0.22), (side * (width / 2 + 0.08), -0.35, top - 0.3), 0.06, rotation=(0, side * -20, 0))
	add_feet(bm, width, depth)
	part(bm, "Camel")

	bm = bmesh.new()
	add_block(bm, (1.0, 0.34, 0.65), (0, -depth / 2 - 0.1, FEET_HEIGHT + height * 0.3), 0.18)
	part(bm, "CamelLight")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.16, 0.08, 0.1), (side * 0.2, -depth / 2 - 0.28, FEET_HEIGHT + height * 0.4), 0.03)
	add_sweep(bm, [(0, -0.6, top + 0.62), (0.15, -0.72, top + 0.62), (0.3, -0.78, top + 0.45), (0.32, -0.8, top + 0.25)], [0.035, 0.03, 0.03, 0.03], sides=5)
	add_ball(bm, (0.32, -0.8, top + 0.2), 0.08)
	part(bm, "Tassel")

	bm = bmesh.new()
	add_lathe(bm, [(0, 0), (0.36, 0), (0.3, 0.55), (0, 0.55)], 12, Matrix.Translation((0, -0.62, top - 0.05)) @ rotation_matrix((-12, 0, 0)))
	part(bm, "Fez")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.65, mouth=None),
		"region": face_region(width, depth, height),
		"effects": {"Camel": {"patterns": [("nebula", "C99550", 3, 0.4)]}},
	}


def build_scorpion(part):
	width, depth, height = 2.3, 2.2, 1.55
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	segments = [(0, depth / 2 + 0.1, FEET_HEIGHT + 0.9), (0, depth / 2 + 0.35, top + 0.25), (0, depth / 2 + 0.25, top + 0.75), (0, depth / 2 - 0.15, top + 1.1), (0, depth / 2 - 0.6, top + 1.2)]
	for index, location in enumerate(segments):
		add_block(bm, (0.55 - index * 0.04, 0.5, 0.5), location, 0.18, rotation=(-30 - index * 30, 0, 0))
	for side in (-1, 1):
		add_block(bm, (0.35, 0.8, 0.3), (side * 0.95, -depth / 2 - 0.15, FEET_HEIGHT + 0.45), 0.1, rotation=(0, 0, side * -20))
		add_block(bm, (0.55, 0.6, 0.45), (side * 1.12, -depth / 2 - 0.6, FEET_HEIGHT + 0.5), 0.15)
	part(bm, "Scorpion")

	bm = bmesh.new()
	for side in (-1, 1):
		for tip_x in (0.1, -0.12):
			add_block(bm, (0.2, 0.5, 0.22), (side * (1.12 + tip_x), -depth / 2 - 1.05, FEET_HEIGHT + 0.5), 0.05, rotation=(90, 0, side * tip_x * -60), taper=0.3)
		for index in range(3):
			add_block(bm, (0.5, 0.16, 0.16), (side * (width / 2 + 0.15), -0.45 + index * 0.5, FEET_HEIGHT - 0.05), 0.05, rotation=(0, side * -30, 0))
	part(bm, "ScorpionDark")

	bm = bmesh.new()
	add_block(bm, (0.26, 0.26, 0.5), (0, depth / 2 - 0.95, top + 1.05), 0.05, rotation=(150, 0, 0), taper=0.15)
	part(bm, "Venom")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.6, mouth="fangs", mouth_height=FEET_HEIGHT + height * 0.36),
		"region": face_region(width, depth, height),
		"effects": {"Scorpion": {"patterns": [("bands", "A0302E", 8, 0.35)]}},
	}


#// Desert 02 Pharaoh Egg

def build_scarab(part):
	width, depth, height = 2.3, 2.1, 1.6
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	part(bm, "Scarab")

	bm = bmesh.new()
	add_block(bm, (0.08, depth - 0.2, 0.1), (0, 0.05, top + 0.0), 0.03)
	add_block(bm, (0.24, 0.24, 0.6), (0, -depth / 2 + 0.05, top + 0.2), 0.05, rotation=(-20, 0, 0), taper=0.2)
	part(bm, "Gold")

	bm = bmesh.new()
	add_block(bm, (1.6, 0.3, 0.9), (0, -depth / 2 - 0.04, FEET_HEIGHT + height * 0.36), 0.2)
	for side in (-1, 1):
		for index in range(3):
			add_block(bm, (0.55, 0.15, 0.15), (side * (width / 2 + 0.15), -0.55 + index * 0.55, FEET_HEIGHT - 0.02), 0.05, rotation=(0, side * -30, side * (index - 1) * 15))
	part(bm, "ScarabDark")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.42, eye_spacing=0.35, eye_size=0.14, mouth="w", mouth_height=FEET_HEIGHT + height * 0.22, blush=True),
		"region": face_region(width, depth, height),
		"effects": {"Scarab": {"gradient": (0.3, 2.0, [(0, "1E8A8A"), (1, "4FE0C0")]), "patterns": [("stars", "E8FFF6", 5, 0.8)]}},
	}


def build_cobra(part):
	head_bottom = 1.15
	width, depth, height = 1.9, 1.6, 1.45
	bm = bmesh.new()
	top = add_body(bm, width, depth, height, bottom=head_bottom, bevel=0.28)
	for radius, height_offset, thickness, sides in ((1.0, 0.25, 0.25, 18), (0.68, 0.68, 0.22, 16)):
		ring = [(radius + math.cos(angle) * thickness, height_offset + math.sin(angle) * thickness) for angle in numpy.linspace(0, math.tau, 9)[:-1]]
		add_lathe(bm, ring, sides, Matrix.Translation((0, 0.1, 0)), closed=True)
	add_block(bm, (0.9, 0.8, 0.6), (0, 0.2, head_bottom - 0.05), 0.25)
	add_lathe(bm, [(0.9, 0.0), (1.05, 0.1), (1.05, 0.2), (0, 0.22)], 16)
	part(bm, "Cobra")

	bm = bmesh.new()
	add_ball(bm, (0, depth / 2 - 0.3, head_bottom + 0.7), 1.0, (1.4, 0.16, 1.05), segments=16, rings=10)
	part(bm, "Hood")

	bm = bmesh.new()
	add_block(bm, (1.1, 0.2, 0.55), (0, -depth / 2 - 0.01, head_bottom + height * 0.25), 0.15)
	part(bm, "CobraBelly")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.06, 0.32, 0.06), (side * 0.05, -depth / 2 - 0.15, head_bottom + 0.12), 0.02, rotation=(0, 0, side * 18))
	part(bm, "Tongue")

	return {
		"face": default_face(width, height, bottom=head_bottom, eye_spacing=0.42, mouth="smile", mouth_height=head_bottom + height * 0.32),
		"region": face_region(width, depth, height, bottom=head_bottom, bevel=0.28),
		"effects": {"Hood": {"patterns": [("spots", "F2E3A0", 2.2, 0.8)]}, "Cobra": {"patterns": [("spots", "2E7A3E", 3, 0.5)]}},
	}


def build_mummy_cat(part):
	width, depth, height = 2.2, 1.9, 2.0
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.5, 0.2, 0.55), (side * 0.7, -0.1, top + 0.15), 0.05, rotation=(0, side * 12, 0), taper=0.2)
	add_sweep(bm, [(0.4, depth / 2, FEET_HEIGHT + 0.4), (0.6, depth / 2 + 0.3, FEET_HEIGHT + 0.8), (0.4, depth / 2 + 0.35, FEET_HEIGHT + 1.3), (0.6, depth / 2 + 0.25, FEET_HEIGHT + 1.6)], [0.13, 0.12, 0.11, 0.09], sides=6)
	add_block(bm, (0.9, 0.08, 0.2), (0.55, -depth / 2 - 0.03, FEET_HEIGHT + height * 0.62), 0.03, rotation=(0, -25, 0))
	add_block(bm, (0.2, 0.08, 0.8), (-0.75, -depth / 2 - 0.03, FEET_HEIGHT + 0.1), 0.03, rotation=(0, 15, 0))
	add_feet(bm, width, depth)
	part(bm, "Bandage")

	bm = bmesh.new()
	add_block(bm, (0.2, 0.12, 0.14), (0, -depth / 2 - 0.06, FEET_HEIGHT + height * 0.44), 0.05)
	part(bm, "Nose")

	return {
		"face": default_face(width, height, eyes=("round", None), mouth="w", mouth_height=FEET_HEIGHT + height * 0.36),
		"region": face_region(width, depth, height),
		"effects": {"Bandage": {"patterns": [("bands", "C9B898", 14, 0.55), ("nebula", "B8A888", 4, 0.3)]}},
	}


def build_anubis(part):
	width, depth, height = 2.2, 1.9, 2.1
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.5, 0.22, 1.0), (side * 0.65, 0.05, top + 0.38), 0.05, rotation=(0, side * 8, 0), taper=0.15)
	add_block(bm, (0.75, 0.6, 0.5), (0, -depth / 2 - 0.2, FEET_HEIGHT + height * 0.36), 0.16)
	add_feet(bm, width, depth)
	part(bm, "Jackal")

	bm = bmesh.new()
	for side in (-1, 1):
		add_block(bm, (0.3, 0.1, 0.6), (side * 0.62, -0.1, top + 0.3), 0.03, rotation=(0, side * 8, 0), taper=0.15)
	add_block(bm, (width + 0.12, depth + 0.12, 0.22), (0, 0, FEET_HEIGHT + 0.42), 0.08)
	add_block(bm, (width + 0.12, depth + 0.12, 0.1), (0, 0, FEET_HEIGHT + 0.72), 0.04)
	add_block(bm, (0.24, 0.12, 0.14), (0, -depth / 2 - 0.52, FEET_HEIGHT + height * 0.4), 0.05)
	part(bm, "Gold")

	bm = bmesh.new()
	add_block(bm, (width + 0.1, depth + 0.1, 0.2), (0, 0, FEET_HEIGHT + 0.58), 0.06)
	part(bm, "Lapis")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.66, mouth=None, blush=False),
		"region": face_region(width, depth, height),
		"effects": {"Jackal": {"gradient": (0.0, 3.4, [(0, "1E1A28"), (1, "4A4460")])}},
	}


def build_sphinx(part):
	width, depth, height = 2.3, 2.0, 2.1
	bm = bmesh.new()
	top = add_body(bm, width, depth, height)
	for side in (-1, 1):
		add_block(bm, (0.55, 1.0, 0.42), (side * width * 0.27, -depth / 2 - 0.05, 0.21), 0.12)
		add_block(bm, (0.55, 0.6, 0.42), (side * width * 0.27, depth * 0.28, 0.21), 0.12)
	add_sweep(bm, [(0.5, depth / 2, FEET_HEIGHT + 0.3), (0.8, depth / 2 + 0.35, FEET_HEIGHT + 0.25), (0.9, depth / 2 + 0.45, FEET_HEIGHT + 0.6)], [0.1, 0.09, 0.0], sides=6)
	part(bm, "Sandstone")

	bm = bmesh.new()
	add_block(bm, (width + 0.16, depth + 0.1, 0.75), (0, 0.04, top - 0.25), 0.3, segments=3)
	for side in (-1, 1):
		add_block(bm, (0.42, 0.3, 1.1), (side * (width / 2 - 0.12), -depth / 2 - 0.02, FEET_HEIGHT + height * 0.48), 0.12, rotation=(0, side * -6, 0))
	add_block(bm, (0.32, 0.22, 0.6), (0, -depth / 2 - 0.05, FEET_HEIGHT + 0.12), 0.06, rotation=(180, 0, 0), taper=0.7)
	part(bm, "Nemes")

	bm = bmesh.new()
	add_block(bm, (0.18, 0.2, 0.45), (0, -depth / 2 - 0.04, top - 0.35), 0.05, taper=0.5)
	add_ball(bm, (0, -depth / 2 - 0.06, top - 0.08), 0.1)
	part(bm, "Gold")

	return {
		"face": default_face(width, height, eye_height=FEET_HEIGHT + height * 0.56, eye_spacing=0.36, mouth="smile", mouth_height=FEET_HEIGHT + height * 0.36),
		"region": face_region(width, depth, height),
		"effects": {
			"Sandstone": {"patterns": [("nebula", "C9965A", 3, 0.45), ("spots", "F7D9A8", 4, 0.3)]},
			"Nemes": {"patterns": [("bands", "FFC43A", 8, 1)]},
		},
	}


#// Eggs

def egg_builder(key):
	def build_egg(part):
		bm = bmesh.new()
		profile = [(0, 0), (0.55, 0.03), (0.98, 0.17), (1.28, 0.45), (1.43, 0.85), (1.45, 1.25), (1.38, 1.7), (1.2, 2.15), (0.95, 2.55), (0.62, 2.9), (0.3, 3.12), (0, 3.18)]
		add_lathe(bm, profile, 20)
		part(bm, key)
		return {"effects": {key: EGG_EFFECTS[key]}}
	return build_egg


EGG_EFFECTS = {
	"GrassEgg": {"gradient": (0, 3.2, [(0, "4FB83A"), (1, "C8FF8A")]), "patterns": [("spots", "F4FFE8", 1.6, 1), ("zigzag", "2E8A3A", (1.2, 0.18, 8, 0.12), 1)]},
	"ForestEgg": {"gradient": (0, 3.2, [(0, "3E6A2E"), (1, "9AC86A")]), "patterns": [("spots", "C98A4A", 1.4, 1), ("zigzag", "2A4A1E", (1.6, 0.2, 6, 0.14), 1)]},
	"SandEgg": {"gradient": (0, 3.2, [(0, "E09A4A"), (1, "FFE8B8")]), "patterns": [("spots", "FFFFFF", 1.6, 0.8), ("zigzag", "C2602E", (1.3, 0.16, 10, 0.1), 1)]},
	"PharaohEgg": {"gradient": (0, 3.2, [(0, "1E3A9A"), (1, "4F8AFF")]), "patterns": [("zigzag", "FFC43A", (1.0, 0.0, 1, 0.12), 1), ("zigzag", "FFC43A", (1.7, 0.15, 8, 0.1), 1), ("stars", "FFE8A0", 5, 1)]},
}

WORLDS = [
	("Spawn", [
		("GrassEgg", egg_builder("GrassEgg"), [
			("Piggy", "Common", build_piggy),
			("Chick", "Common", build_chick),
			("Sheep", "Uncommon", build_sheep),
			("Cow", "Rare", build_cow),
			("Unicorn", "Legendary", build_unicorn),
		]),
		("ForestEgg", egg_builder("ForestEgg"), [
			("Bear", "Common", build_bear),
			("Fox", "Common", build_fox),
			("Raccoon", "Uncommon", build_raccoon),
			("Owl", "Rare", build_owl),
			("MysticDeer", "Legendary", build_mystic_deer),
		]),
	]),
	("Desert", [
		("SandEgg", egg_builder("SandEgg"), [
			("Meerkat", "Common", build_meerkat),
			("Fennec", "Common", build_fennec),
			("Lizard", "Uncommon", build_lizard),
			("Camel", "Rare", build_camel),
			("Scorpion", "Epic", build_scorpion),
		]),
		("PharaohEgg", egg_builder("PharaohEgg"), [
			("Scarab", "Common", build_scarab),
			("Cobra", "Uncommon", build_cobra),
			("MummyCat", "Rare", build_mummy_cat),
			("Anubis", "Epic", build_anubis),
			("Sphinx", "Legendary", build_sphinx),
		]),
	]),
]


#// Bake Materials

def setup_bake_material(material, key, bake_image, bounds, face=None, effects=None, golden=False):
	recolor = goldify if golden else (lambda hex_color: hex_color)
	base, shadow, highlight = material_colors(recolor(PALETTE[key]))
	effects = effects or {}
	nodes = material.node_tree.nodes
	links = material.node_tree.links
	nodes.clear()

	def node(node_type, location, **properties):
		new_node = nodes.new(node_type)
		new_node.location = location
		for property_name, property_value in properties.items():
			setattr(new_node, property_name, property_value)
		return new_node

	def map_range(source, from_min, from_max, location, to_min=0, to_max=1):
		new_node = node("ShaderNodeMapRange", location, clamp=True)
		links.new(source, new_node.inputs["Value"])
		new_node.inputs["From Min"].default_value = from_min
		new_node.inputs["From Max"].default_value = from_max
		new_node.inputs["To Min"].default_value = to_min
		new_node.inputs["To Max"].default_value = to_max
		return new_node.outputs["Result"]

	def math_node(operation, first, second, location):
		new_node = node("ShaderNodeMath", location, operation=operation)
		for index, source in enumerate((first, second)):
			if isinstance(source, (int, float)):
				new_node.inputs[index].default_value = source
			else:
				links.new(source, new_node.inputs[index])
		return new_node.outputs[0]

	def mix(factor, first, second, location):
		new_node = node("ShaderNodeMix", location, data_type="RGBA", clamp_factor=True)
		for socket, source in ((new_node.inputs[0], factor), (new_node.inputs[6], first), (new_node.inputs[7], second)):
			if isinstance(source, (tuple, int, float)):
				socket.default_value = source
			else:
				links.new(source, socket)
		return new_node.outputs[2]

	geometry = node("ShaderNodeNewGeometry", (-1200, 300))
	coordinates = node("ShaderNodeTexCoord", (-1200, -200))
	position = node("ShaderNodeSeparateXYZ", (-1000, -800))
	links.new(coordinates.outputs["Object"], position.inputs[0])

	def pattern(kind, scale, location):
		x, y = location
		if kind == "spots":
			cells = node("ShaderNodeTexVoronoi", (x, y))
			cells.inputs["Scale"].default_value = scale
			cells.inputs["Randomness"].default_value = 0.8
			links.new(coordinates.outputs["Object"], cells.inputs["Vector"])
			dot = map_range(cells.outputs["Distance"], 0.32, 0.26, (x + 200, y))
			return math_node("MULTIPLY", dot, math_node("GREATER_THAN", cells.outputs["Color"], 0.45, (x + 200, y - 150)), (x + 400, y))

		if kind == "stars":
			cells = node("ShaderNodeTexVoronoi", (x, y))
			cells.inputs["Scale"].default_value = scale
			links.new(coordinates.outputs["Object"], cells.inputs["Vector"])
			sparkle = map_range(cells.outputs["Distance"], 0.2, 0.08, (x + 200, y))
			return math_node("MULTIPLY", sparkle, math_node("GREATER_THAN", cells.outputs["Color"], 0.6, (x + 200, y - 150)), (x + 400, y))

		if kind == "bands":
			bands = node("ShaderNodeTexWave", (x, y), bands_direction="Z")
			bands.inputs["Scale"].default_value = scale
			bands.inputs["Distortion"].default_value = 0.5
			links.new(coordinates.outputs["Object"], bands.inputs["Vector"])
			return map_range(bands.outputs["Fac"], 0.55, 0.6, (x + 200, y))

		if kind == "zigzag":
			height, amplitude, count, thickness = scale
			angle = math_node("ARCTAN2", position.outputs["Y"], position.outputs["X"], (x - 400, y))
			wave = math_node("ARCSINE", math_node("SINE", math_node("MULTIPLY", angle, count, (x - 300, y)), 0, (x - 200, y)), 0, (x - 100, y))
			line = math_node("ADD", math_node("MULTIPLY", wave, amplitude * 2 / math.pi, (x, y - 100)), height, (x + 100, y - 100))
			distance = math_node("ABSOLUTE", math_node("SUBTRACT", position.outputs["Z"], line, (x + 200, y - 100)), 0, (x + 300, y - 100))
			return map_range(distance, thickness, thickness * 0.75, (x + 400, y))

		cloud = node("ShaderNodeTexNoise", (x, y))
		cloud.inputs["Scale"].default_value = scale
		cloud.inputs["Detail"].default_value = 3
		links.new(coordinates.outputs["Object"], cloud.inputs["Vector"])
		return map_range(cloud.outputs["Fac"], 0.45, 0.7, (x + 200, y))

	if "gradient" in effects:
		start, end, stops = effects["gradient"]
		ramp = node("ShaderNodeValToRGB", (-800, -650))
		links.new(map_range(position.outputs["Z"], start, end, (-1000, -650)), ramp.inputs["Fac"])
		elements = ramp.color_ramp.elements
		for index, (stop, hex_color) in enumerate(stops):
			element = elements[index] if index < 2 else elements.new(stop)
			element.position = stop
			element.color = to_color(recolor(hex_color))
		base = ramp.outputs["Color"]

	bevel = node("ShaderNodeBevel", (-1000, 300), samples=16)
	bevel.inputs["Radius"].default_value = EDGE_BEVEL_RADIUS
	facing = node("ShaderNodeVectorMath", (-800, 300), operation="DOT_PRODUCT")
	links.new(geometry.outputs["Normal"], facing.inputs[0])
	links.new(bevel.outputs["Normal"], facing.inputs[1])
	edge = map_range(facing.outputs["Value"], EDGE_START, EDGE_FULL, (-600, 300), 0, EDGE_STRENGTH)

	occlusion = node("ShaderNodeAmbientOcclusion", (-1000, 0), samples=16, only_local=True)
	occlusion.inputs["Distance"].default_value = CAVITY_DISTANCE
	convex = math_node("MULTIPLY", edge, map_range(occlusion.outputs["AO"], 0.7, 0.92, (-800, 0)), (-400, 200))
	cavity = map_range(occlusion.outputs["AO"], 0.95, 0.35, (-800, -100), 0, CAVITY_STRENGTH)

	noise = node("ShaderNodeTexNoise", (-1000, -300))
	noise.inputs["Scale"].default_value = 5
	noise.inputs["Detail"].default_value = 3
	links.new(coordinates.outputs["Object"], noise.inputs["Vector"])
	variation = map_range(noise.outputs["Fac"], 0.3, 0.7, (-800, -450))
	light_tone = mix(COLOR_VARIATION, base, highlight, (-400, -400))
	dark_tone = mix(COLOR_VARIATION, base, shadow, (-400, -550))
	color = mix(variation, dark_tone, light_tone, (0, -400))

	bottom, top = bounds
	color = mix(map_range(position.outputs["Z"], bottom + (top - bottom) * 0.45, bottom, (-800, -1000), 0, BOTTOM_SHADE), color, shadow, (100, -300))
	color = mix(map_range(position.outputs["Z"], bottom + (top - bottom) * 0.55, top, (-800, -1100), 0, TOP_LIGHT), color, highlight, (150, -300))

	patterns = list(effects.get("patterns", ()))
	if golden:
		patterns.append(("stars", GOLD_SPARKLE, 7, 0.9))
	for index, (kind, hex_color, scale, strength) in enumerate(patterns):
		factor = pattern(kind, scale, (-600, -1300 - index * 300))
		color = mix(math_node("MULTIPLY", factor, strength, (0, -1300 - index * 300)), color, to_color(recolor(hex_color)), (200, -250 - index * 50))

	color = mix(cavity, color, shadow, (400, 0))
	color = mix(convex, color, highlight, (500, 100))

	if face:
		image, (min_x, max_x, min_z, max_z) = face
		normal = node("ShaderNodeSeparateXYZ", (-1000, 600))
		links.new(geometry.outputs["Normal"], normal.inputs[0])
		front = map_range(normal.outputs["Y"], -0.6, -0.85, (-800, 600))
		combine = node("ShaderNodeCombineXYZ", (-600, 700))
		links.new(map_range(position.outputs["X"], min_x, max_x, (-800, 750)), combine.inputs["X"])
		links.new(map_range(position.outputs["Z"], min_z, max_z, (-800, 850)), combine.inputs["Y"])
		mask = node("ShaderNodeTexImage", (-400, 700), image=image, extension="CLIP")
		links.new(combine.outputs[0], mask.inputs["Vector"])
		channels = node("ShaderNodeSeparateColor", (-150, 700))
		links.new(mask.outputs["Color"], channels.inputs[0])
		for index, (channel, hex_color) in enumerate((("Blue", FACE_BLUSH), ("Red", FACE_DARK), ("Green", FACE_WHITE))):
			factor = math_node("MULTIPLY", channels.outputs[channel], front, (100, 700 - index * 100))
			color = mix(math_node("MULTIPLY", factor, 0.85 if channel == "Blue" else 1, (250, 700 - index * 100)), color, to_color(hex_color), (650 + index * 100, 200))

	emission = node("ShaderNodeEmission", (1000, 0))
	links.new(color, emission.inputs["Color"])
	output = node("ShaderNodeOutputMaterial", (1200, 0))
	links.new(emission.outputs[0], output.inputs["Surface"])

	target = node("ShaderNodeTexImage", (1000, 300), image=bake_image)
	nodes.active = target


def create_final_material(name, texture):
	material = bpy.data.materials.new(name)
	material.use_nodes = True
	shader = material.node_tree.nodes["Principled BSDF"]
	shader.inputs["Roughness"].default_value = 0.6
	image_node = material.node_tree.nodes.new("ShaderNodeTexImage")
	image_node.image = texture
	image_node.location = (-400, 300)
	material.node_tree.links.new(image_node.outputs["Color"], shader.inputs["Base Color"])
	return material


#// Build

def clear_scene():
	for collection in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.collections):
		for block in list(collection):
			if block.name != "Render Result":
				collection.remove(block)


def select_only(objects):
	if bpy.context.object and bpy.context.object.mode != "OBJECT":
		bpy.ops.object.mode_set(mode="OBJECT")
	bpy.ops.object.select_all(action="DESELECT")
	for target in objects:
		target.select_set(True)
	bpy.context.view_layer.objects.active = objects[0]


def new_part(name, bm, material):
	bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
	for face in bm.faces:
		face.smooth = True
	for edge in bm.edges:
		edge.smooth = not (len(edge.link_faces) == 2 and edge.calc_face_angle(0) > math.radians(SMOOTH_ANGLE))

	mesh = bpy.data.meshes.new(name)
	bm.to_mesh(mesh)
	bm.free()
	mesh.materials.append(material)
	part = bpy.data.objects.new(name, mesh)
	bpy.context.scene.collection.objects.link(part)
	return part


def bake(model, details, texture, golden):
	heights = [vertex.co.z for vertex in model.data.vertices]
	bounds = (min(heights), max(heights))
	effects = details.get("effects", {})
	for material in model.data.materials:
		key = material["Key"]
		setup_bake_material(material, key, texture, bounds, details.get("face_image"), effects.get(key), golden)
	select_only([model])
	bpy.ops.object.bake(type="EMIT")


def build_model(name, rarity, build, collection):
	parts = []

	def part(bm, key):
		material = bpy.data.materials.get(name + key)
		if not material:
			material = bpy.data.materials.new(name + key)
			material.use_nodes = True
			material["Key"] = key
		parts.append(new_part(name + key, bm, material))

	details = build(part)
	if "face" in details:
		details["face_image"] = paint_face(name, details["face"], details["region"])

	select_only(parts)
	bpy.ops.object.join()
	model = bpy.context.view_layer.objects.active
	model.name = name
	model.data.name = name
	model["Rarity"] = rarity

	bpy.ops.object.mode_set(mode="EDIT")
	bpy.ops.mesh.select_all(action="SELECT")
	bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=UV_MARGIN, scale_to_bounds=True)
	bpy.ops.object.mode_set(mode="OBJECT")

	texture = bpy.data.images.new(name, TEXTURE_SIZE, TEXTURE_SIZE)
	golden_texture = bpy.data.images.new(name + "Golden", TEXTURE_SIZE, TEXTURE_SIZE)
	bake(model, details, texture, False)
	bake(model, details, golden_texture, True)

	model.data.materials.clear()
	model.data.materials.append(create_final_material(name, texture))
	for polygon in model.data.polygons:
		polygon.material_index = 0
	for user_collection in list(model.users_collection):
		user_collection.objects.unlink(model)
	collection.objects.link(model)
	return model, texture, golden_texture


def export_model(model, textures):
	for texture in textures:
		texture.filepath_raw = os.path.join(EXPORT_FOLDER, texture.name + ".png")
		texture.file_format = "PNG"
		texture.save()

	original_location = model.location.copy()
	model.location = (0, 0, 0)
	select_only([model])
	bpy.ops.export_scene.fbx(
		filepath=os.path.join(EXPORT_FOLDER, model.name + ".fbx"),
		use_selection=True,
		object_types={"MESH"},
		axis_forward="Z",
		axis_up="Y",
		path_mode="COPY",
		embed_textures=True,
	)
	model.location = original_location


def main():
	clear_scene()
	scene = bpy.context.scene
	scene.render.engine = "CYCLES"
	scene.cycles.device = "CPU"
	scene.cycles.samples = BAKE_SAMPLES
	scene.render.bake.margin = 6

	models = []
	row = 0
	for world, eggs in WORLDS:
		world_collection = bpy.data.collections.new(world + "Pets")
		scene.collection.children.link(world_collection)
		for egg_name, egg_build, pets in eggs:
			collection = bpy.data.collections.new(egg_name)
			world_collection.children.link(collection)
			for column, (name, rarity, build) in enumerate([(egg_name, "Egg", egg_build)] + pets):
				model, texture, golden_texture = build_model(name, rarity, build, collection)
				model.location = (column * PACK_SPACING, 0, -row * ROW_SPACING)
				model["World"] = world
				model["Egg"] = egg_name
				models.append((model, texture, golden_texture))
			row += 1

	if EXPORT_FOLDER:
		os.makedirs(EXPORT_FOLDER, exist_ok=True)
		for model, texture, golden_texture in models:
			export_model(model, (texture, golden_texture))

	for _, texture, golden_texture in models:
		texture.pack()
		golden_texture.pack()

	return [model for model, _, _ in models]


if __name__ == "__main__":
	main()
