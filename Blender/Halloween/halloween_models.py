import bpy
import bmesh
import math
import os
import random
from mathutils import Euler, Matrix, Vector

# Run inside Blender: Scripting tab -> Open -> Run Script.
# Builds every Halloween asset into the "Halloween" collection using one shared palette texture.

COLLECTION_NAME = "Halloween"
PALETTE_NAME = "HalloweenPalette"
PALETTE_SIZE = 128
PALETTE_GRID = 8

ASSET_SPACING = 3.5
ROW_SPACING = 4.5
ASSETS_PER_ROW = 7
BEVEL = 0.04
OUTLINE_THICKNESS = 0.0  # e.g. 0.04 adds a black inverted-hull outline like the 2D icons

# Leave empty to skip. Otherwise every asset is exported as its own FBX into this folder.
EXPORT_FOLDER = ""

PALETTE = {
	"Outline": "140E1A",
	"White": "F7F4EE",
	"CandyYellow": "FFD21F",
	"CandyOrange": "FF7A12",
	"CandyWhite": "FFF4D9",
	"LollipopRed": "FF2E4D",
	"LollipopPurple": "9B3BE8",
	"LollipopBlack": "2E2638",
	"PumpkinOrange": "FF8C1F",
	"PumpkinLight": "FFA43D",
	"PumpkinCarve": "5C1E06",
	"Glow": "FFE14D",
	"StemGreen": "4CAF3D",
	"StemDark": "2F7A2C",
	"BrainPink": "FF9EC4",
	"BrainLight": "FFBAD6",
	"BrainDark": "F27AAA",
	"CauldronBody": "3B3049",
	"CauldronDark": "2A2235",
	"CauldronRim": "4E4063",
	"PotionPurple": "A64BFF",
	"PotionLight": "C98CFF",
	"PotionPale": "E3C2FF",
	"PotionGreen": "7EE02E",
	"PotionGreenLight": "A8F55A",
	"PotionGreenPale": "D4FFA6",
	"CoffinPurple": "9B3FE0",
	"CoffinDark": "6B2AA6",
	"CoffinLining": "2B2433",
	"CoffinQuilt": "3A3145",
	"RivetBlue": "8FB8FF",
	"Bone": "F2E4BC",
	"BoneShade": "DCC994",
	"HatPurple": "9257E8",
	"HatDark": "6C3BBF",
	"HatBand": "8F4A22",
	"Gold": "FFC23A",
	"Wood": "A65A2A",
	"WoodDark": "7F4220",
	"WoodCut": "E8A866",
	"Bristle": "EBA93C",
	"BristleLight": "F7CF6E",
	"BristleDark": "C98A2A",
	"ZombieGreen": "8EE04A",
	"ZombieDark": "6BBF2E",
	"EyeWhite": "F7EEDB",
	"MouthDark": "5A1F45",
	"Tongue": "D6409F",
	"StoneBlue": "7896EA",
	"StoneLight": "93AEF5",
	"StoneDark": "5672C9",
}

COLOR_NAMES = list(PALETTE)


def palette_uv(color):
	index = COLOR_NAMES.index(color)
	column = index % PALETTE_GRID
	row = index // PALETTE_GRID
	return ((column + 0.5) / PALETTE_GRID, (row + 0.5) / PALETTE_GRID)


def make_matrix(location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
	euler = Euler([math.radians(angle) for angle in rotation])
	return Matrix.LocRotScale(Vector(location), euler, Vector(scale))


class AssetBuilder:
	def __init__(self, name):
		self.name = name
		self.bm = bmesh.new()
		self.uv_layer = self.bm.loops.layers.uv.new("UVMap")
		self.transform = Matrix.Identity(4)
		self.glow_builder = None

	def glow(self):
		# Parts that should become a separate Neon MeshPart in Roblox
		if self.glow_builder is None:
			self.glow_builder = AssetBuilder(self.name + "Glow")
		self.glow_builder.transform = self.transform
		return self.glow_builder

	def _paint(self, verts, color, bevel=0.0):
		faces = {face for vert in verts for face in vert.link_faces}
		uv = palette_uv(color)

		for face in faces:
			for loop in face.loops:
				loop[self.uv_layer].uv = uv

		if bevel > 0:
			edges = {edge for face in faces for edge in face.edges}
			bmesh.ops.bevel(
				self.bm,
				geom=list(edges),
				offset=bevel,
				segments=1,
				affect="EDGES",
				clamp_overlap=True,
			)

	def box(self, color, size, location, rotation=(0, 0, 0), bevel=BEVEL):
		matrix = self.transform @ make_matrix(location, rotation, size)
		verts = bmesh.ops.create_cube(self.bm, size=1, matrix=matrix)["verts"]
		self._paint(verts, color, bevel)

	def ball(self, color, radius, location, rotation=(0, 0, 0), scale=(1, 1, 1), subdivisions=1, segments=0):
		# segments > 0 makes a UV sphere with clean vertical facets instead of an icosphere
		matrix = self.transform @ make_matrix(location, rotation, Vector(scale) * radius)
		if segments > 0:
			verts = bmesh.ops.create_uvsphere(
				self.bm,
				u_segments=segments,
				v_segments=segments // 2 + 1,
				radius=1,
				matrix=matrix,
			)["verts"]
		else:
			verts = bmesh.ops.create_icosphere(self.bm, subdivisions=subdivisions, radius=1, matrix=matrix)["verts"]
		self._paint(verts, color)

	def cylinder(self, color, bottom_radius, top_radius, depth, location, rotation=(0, 0, 0), segments=8, bevel=BEVEL):
		matrix = self.transform @ make_matrix(location, rotation)
		verts = bmesh.ops.create_cone(
			self.bm,
			cap_ends=True,
			cap_tris=False,
			segments=segments,
			radius1=bottom_radius,
			radius2=top_radius,
			depth=depth,
			matrix=matrix,
		)["verts"]
		self._paint(verts, color, bevel)

	def prism(self, color, profile, depth, location, rotation=(0, 0, 0), bevel=BEVEL):
		# Profile is a list of (x, z) points, extruded along Y
		matrix = self.transform @ make_matrix(location, rotation)
		front = [self.bm.verts.new(matrix @ Vector((x, -depth / 2, z))) for x, z in profile]
		back = [self.bm.verts.new(matrix @ Vector((x, depth / 2, z))) for x, z in profile]

		faces = [self.bm.faces.new(front), self.bm.faces.new(back)]
		for i in range(len(profile)):
			j = (i + 1) % len(profile)
			faces.append(self.bm.faces.new((front[i], front[j], back[j], back[i])))

		bmesh.ops.recalc_face_normals(self.bm, faces=faces)
		self._paint(front + back, color, bevel)

	def lathe(self, color, profile, location=(0, 0, 0), scale=(1, 1, 1), segments=12, closed=False):
		# Profile is a list of (radius, z) points spun around Z. A radius of 0 makes a pole.
		matrix = self.transform @ make_matrix(location, (0, 0, 0), scale)
		angles = [math.tau * i / segments for i in range(segments)]
		rings = []

		for radius, height in profile:
			if radius == 0:
				rings.append([self.bm.verts.new(matrix @ Vector((0, 0, height)))])
			else:
				rings.append([
					self.bm.verts.new(matrix @ Vector((math.cos(angle) * radius, math.sin(angle) * radius, height)))
					for angle in angles
				])

		ring_pairs = list(zip(rings, rings[1:]))
		if closed:
			ring_pairs.append((rings[-1], rings[0]))

		faces = []
		for lower, upper in ring_pairs:
			for i in range(segments):
				j = (i + 1) % segments
				if len(lower) == 1:
					faces.append(self.bm.faces.new((lower[0], upper[i], upper[j])))
				elif len(upper) == 1:
					faces.append(self.bm.faces.new((lower[i], lower[j], upper[0])))
				else:
					faces.append(self.bm.faces.new((lower[i], lower[j], upper[j], upper[i])))

		if not closed:
			for ring in (rings[0], rings[-1]):
				if len(ring) > 1:
					faces.append(self.bm.faces.new(ring))

		bmesh.ops.recalc_face_normals(self.bm, faces=faces)
		self._paint([vert for ring in rings for vert in ring], color)

	def bent_tube(self, color, start, segments, side_color=None):
		# Segments are (bottom_radius, top_radius, length, tilt) chained end to end, tilting around Y
		top = Vector(start)
		for index, (bottom_radius, top_radius, length, tilt) in enumerate(segments):
			rotation = Euler((0, math.radians(tilt), 0)).to_matrix()
			center = top + rotation @ Vector((0, 0, length / 2 - 0.03))
			top = center + rotation @ Vector((0, 0, length / 2))
			segment_color = side_color if side_color and index % 2 == 1 else color
			self.cylinder(segment_color, bottom_radius, top_radius, length, center, rotation=(0, tilt, 0), bevel=0)
		return top

	def nested(self, location, rotation, scale, build_function, *args):
		previous = self.transform
		self.transform = previous @ make_matrix(location, rotation, scale)
		build_function(self, *args)
		self.transform = previous

	def _add_outline(self):
		hull = self.bm.copy()
		hull.normal_update()
		uv_layer = hull.loops.layers.uv.active
		outline_uv = palette_uv("Outline")

		for vert in hull.verts:
			vert.co += vert.normal * OUTLINE_THICKNESS

		bmesh.ops.reverse_faces(hull, faces=hull.faces)
		for face in hull.faces:
			for loop in face.loops:
				loop[uv_layer].uv = outline_uv

		hull_mesh = bpy.data.meshes.new("OutlineTemp")
		hull.to_mesh(hull_mesh)
		hull.free()
		self.bm.from_mesh(hull_mesh)
		bpy.data.meshes.remove(hull_mesh)

	def build(self, collection, material, location):
		if OUTLINE_THICKNESS > 0:
			self._add_outline()

		for face in self.bm.faces:
			face.smooth = False

		mesh = bpy.data.meshes.new(self.name)
		self.bm.to_mesh(mesh)
		self.bm.free()
		mesh.materials.append(material)

		asset = bpy.data.objects.new(self.name, mesh)
		asset.location = location
		collection.objects.link(asset)

		if self.glow_builder:
			glow_part = self.glow_builder.build(collection, material, (0, 0, 0))
			glow_part.parent = asset

		return asset


#// Palette

def get_palette_material():
	image = bpy.data.images.get(PALETTE_NAME)
	if image is None:
		image = bpy.data.images.new(PALETTE_NAME, PALETTE_SIZE, PALETTE_SIZE, alpha=False)

	cell_size = PALETTE_SIZE // PALETTE_GRID
	pixels = [1.0] * (PALETTE_SIZE * PALETTE_SIZE * 4)

	for index, color in enumerate(COLOR_NAMES):
		hex_color = PALETTE[color]
		rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
		start_x = (index % PALETTE_GRID) * cell_size
		start_y = (index // PALETTE_GRID) * cell_size

		for y in range(start_y, start_y + cell_size):
			for x in range(start_x, start_x + cell_size):
				offset = (y * PALETTE_SIZE + x) * 4
				pixels[offset:offset + 3] = rgb

	image.pixels = pixels
	image.pack()

	material = bpy.data.materials.get(PALETTE_NAME) or bpy.data.materials.new(PALETTE_NAME)
	material.use_nodes = True
	nodes = material.node_tree.nodes
	links = material.node_tree.links
	nodes.clear()

	output = nodes.new("ShaderNodeOutputMaterial")
	shader = nodes.new("ShaderNodeBsdfPrincipled")
	texture = nodes.new("ShaderNodeTexImage")

	output.location = (300, 0)
	texture.location = (-350, 0)
	texture.image = image
	texture.interpolation = "Closest"
	shader.inputs["Roughness"].default_value = 0.8

	links.new(texture.outputs["Color"], shader.inputs["Base Color"])
	links.new(shader.outputs["BSDF"], output.inputs["Surface"])
	return material


#// Shared Parts

def add_brain(builder, center, size, seed):
	rng = random.Random(seed)
	center = Vector(center)
	radii = Vector((0.6, 0.95, 0.7)) * size

	for side in (-1, 1):
		hemisphere_center = center + Vector((side * 0.36 * size, 0, 0))
		builder.ball("BrainPink", 1, hemisphere_center, scale=radii, subdivisions=2)

		fold_count = 0
		while fold_count < 13:
			direction = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
			if direction.x * side < -0.25 or direction.z < -0.15:
				continue

			surface_point = hemisphere_center + Vector((
				direction.x * radii.x,
				direction.y * radii.y,
				direction.z * radii.z,
			)) * 0.97

			# Folds lie flat on the surface and mostly run front to back, like real gyri
			normal = Vector((direction.x / radii.x, direction.y / radii.y, direction.z / radii.z)).normalized()
			tangent = Vector((0, 1, 0))
			tangent = (tangent - normal * tangent.dot(normal)).normalized()
			tangent.rotate(Matrix.Rotation(math.radians(rng.uniform(-40, 40)), 3, normal))
			bitangent = normal.cross(tangent)
			fold_rotation = Matrix((tangent, bitangent, normal)).transposed().to_euler()

			builder.ball(
				"BrainLight" if fold_count % 2 == 0 else "BrainPink",
				0.2 * size,
				surface_point,
				rotation=[math.degrees(angle) for angle in fold_rotation],
				scale=(2.0, 0.75, 0.5),
				segments=6,
			)
			fold_count += 1

	builder.ball("BrainDark", 0.5 * size, center + Vector((0, 0.7, -0.35)) * size, scale=(1.3, 0.8, 0.6))


def add_lollipop(builder, color):
	builder.cylinder("White", 0.035, 0.035, 0.6, (0, 0, 0.3), segments=6, bevel=0)
	builder.ball(color, 0.24, (0, 0, 0.72), scale=(1, 0.75, 1), subdivisions=2)


def add_cauldron_pot(builder):
	builder.lathe(
		"CauldronBody",
		[(0, 0.2), (0.55, 0.22), (0.86, 0.4), (1.0, 0.7), (0.98, 1.0), (0.86, 1.22), (0.8, 1.3)],
	)
	builder.lathe(
		"CauldronRim",
		[(0.82, 1.2), (0.98, 1.23), (1.04, 1.33), (0.98, 1.43), (0.8, 1.42), (0.76, 1.32)],
		closed=True,
	)

	for i in range(3):
		angle = math.tau * i / 3 + math.pi / 2
		builder.cylinder("CauldronDark", 0.11, 0.18, 0.3, (math.cos(angle) * 0.5, math.sin(angle) * 0.5, 0.15), segments=6)


def add_potion(builder, liquid_color, light_color, pale_color):
	builder.cylinder(liquid_color, 0.8, 0.8, 0.06, (0, 0, 1.34), segments=12, bevel=0)

	rng = random.Random(11)
	bubble_colors = (liquid_color, light_color, pale_color)
	for i in range(16):
		angle = rng.uniform(0, math.tau)
		distance = rng.uniform(0, 0.6)
		radius = rng.uniform(0.14, 0.26)
		height = 1.38 + (0.6 - distance) * 0.55 + rng.uniform(0, 0.08)
		builder.ball(bubble_colors[i % 3], radius, (math.cos(angle) * distance, math.sin(angle) * distance, height))

	for angle, length in ((-18, 0.3), (22, 0.2)):
		direction = Vector((math.sin(math.radians(angle)), -math.cos(math.radians(angle)), 0))
		builder.ball(liquid_color, 1, direction * 0.9 + Vector((0, 0, 1.43)), rotation=(0, 0, angle), scale=(0.24, 0.2, 0.08), subdivisions=2)
		builder.ball(liquid_color, 1, direction * 0.99 + Vector((0, 0, 1.38 - length * 0.5)), rotation=(0, 0, angle), scale=(0.12, 0.08, length), subdivisions=2)


def add_jack_o_lantern_face(builder, color):
	# Face shapes are drawn flat as (x, z offset from pumpkin center) and wrapped onto the pumpkin front
	center_z = 0.75
	radii = Vector((1.0, 1.0, 0.72))

	def add_plate(points):
		center_x = sum(x for x, _ in points) / len(points)
		center_offset = sum(z for _, z in points) / len(points)
		height_ratio = (center_x / radii.x) ** 2 + (center_offset / radii.z) ** 2
		surface_y = -radii.y * math.sqrt(max(0.05, 1 - height_ratio))

		normal = Vector((center_x / radii.x ** 2, surface_y / radii.y ** 2, center_offset / radii.z ** 2)).normalized()
		yaw = math.degrees(math.atan2(normal.x, -normal.y))
		pitch = -math.degrees(math.asin(normal.z))
		profile = [(x - center_x, z - center_offset) for x, z in points]

		builder.prism(color, profile, 0.12, (center_x, surface_y - 0.02, center_z + center_offset), rotation=(pitch, 0, yaw), bevel=0)

	add_plate([(-0.5, 0.12), (-0.14, 0.06), (-0.24, 0.36)])
	add_plate([(0.14, 0.06), (0.5, 0.12), (0.24, 0.36)])
	add_plate([(-0.07, -0.06), (0.07, -0.06), (0, 0.06)])

	mouth_width = 0.62
	segment_count = 6
	teeth_segments = (1, 4)

	def upper_lip(x):
		return -0.1 - 0.22 * (1 - (x / mouth_width) ** 2)

	def lower_lip(x):
		return upper_lip(x) - 0.05 - 0.17 * (1 - (x / mouth_width) ** 2)

	for i in range(segment_count):
		left = -mouth_width + 2 * mouth_width * i / segment_count
		right = left + 2 * mouth_width / segment_count
		tooth_drop = 0.08 if i in teeth_segments else 0
		add_plate([
			(left, lower_lip(left)),
			(right, lower_lip(right)),
			(right, upper_lip(right) - tooth_drop),
			(left, upper_lip(left) - tooth_drop),
		])


#// Assets

def build_candy_corn(builder):
	builder.lathe("CandyYellow", [(0.5, 0), (0.75, 0.12), (0.78, 0.35), (0.72, 0.6)], scale=(1, 0.6, 1), segments=10)
	builder.lathe("CandyOrange", [(0.72, 0.6), (0.62, 0.9), (0.5, 1.15)], scale=(1, 0.6, 1), segments=10)
	builder.lathe("CandyWhite", [(0.5, 1.15), (0.36, 1.4), (0.18, 1.6), (0, 1.68)], scale=(1, 0.6, 1), segments=10)


def build_pumpkin(builder, with_stem=True):
	lobe_count = 7

	for i in range(lobe_count):
		angle = 360 * i / lobe_count - 90
		direction = Vector((math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0))
		builder.ball(
			"PumpkinOrange" if i % 2 == 0 else "PumpkinLight",
			1,
			direction * 0.42 + Vector((0, 0, 0.75)),
			rotation=(0, 0, angle),
			scale=(0.62, 0.52, 0.72),
			segments=10,
		)

	builder.ball("PumpkinOrange", 0.85, (0, 0, 0.78), scale=(1, 1, 0.82), segments=10)

	if not with_stem:
		return

	builder.cylinder("StemGreen", 0.16, 0.12, 0.35, (0, 0, 1.48), rotation=(0, -10, 0), segments=6)
	builder.cylinder("StemGreen", 0.12, 0.09, 0.3, (0.07, 0, 1.74), rotation=(0, 35, 0), segments=6)
	builder.cylinder("StemDark", 0.07, 0.04, 0.25, (0.27, 0, 1.86), rotation=(0, 80, 0), segments=6)
	builder.ball("StemDark", 0.22, (-0.3, -0.1, 1.45), rotation=(0, 0, 30), scale=(1.4, 0.8, 0.3))


def build_witch_hat(builder):
	builder.cylinder("HatDark", 1.3, 1.26, 0.08, (0, 0, 0.04), segments=14)
	builder.cylinder("HatPurple", 1.22, 1.15, 0.08, (0, 0, 0.11), segments=14)

	builder.bent_tube("HatPurple", (0, 0, 0.14), [
		(0.68, 0.5, 0.72, 0),
		(0.5, 0.33, 0.6, -14),
		(0.33, 0.17, 0.5, -38),
		(0.17, 0.05, 0.36, -75),
	])

	builder.cylinder("HatBand", 0.72, 0.67, 0.22, (0, 0, 0.27), segments=8, bevel=0.02)

	buckle_y = -0.72
	builder.box("Gold", (0.32, 0.06, 0.07), (0, buckle_y, 0.375), bevel=0.015)
	builder.box("Gold", (0.32, 0.06, 0.07), (0, buckle_y, 0.165), bevel=0.015)
	builder.box("Gold", (0.07, 0.06, 0.28), (-0.125, buckle_y, 0.27), bevel=0.015)
	builder.box("Gold", (0.07, 0.06, 0.28), (0.125, buckle_y, 0.27), bevel=0.015)


def build_jack_o_lantern(builder):
	build_pumpkin(builder, with_stem=False)
	add_jack_o_lantern_face(builder, "PumpkinCarve")
	builder.nested((0.08, 0.08, 1.36), (8, 10, 0), (0.8, 0.8, 0.8), build_witch_hat)


def build_glowing_jack_o_lantern(builder):
	build_pumpkin(builder, with_stem=False)
	add_jack_o_lantern_face(builder.glow(), "Glow")
	builder.nested((0.08, 0.08, 1.36), (8, 10, 0), (0.8, 0.8, 0.8), build_witch_hat)


def build_bone(builder):
	builder.cylinder("Bone", 0.22, 0.22, 1.7, (0, 0, 0.5), rotation=(0, 90, 0), segments=8, bevel=0)

	for side in (-1, 1):
		for offset in (-1, 1):
			builder.ball("BoneShade" if offset == 1 else "Bone", 0.3, (side * 0.9, 0, 0.5 + offset * 0.2), subdivisions=1)


def build_brain(builder):
	add_brain(builder, (0, 0, 0.75), 1, seed=3)


def build_zombie_head(builder):
	builder.ball("ZombieGreen", 1, (0, 0, 1), scale=(0.92, 0.85, 1), subdivisions=2)
	builder.ball("ZombieDark", 0.3, (-0.88, 0.05, 0.95), scale=(0.5, 1, 1.2))
	builder.ball("ZombieDark", 0.28, (0.88, 0.05, 1.0), scale=(0.5, 1, 1.2))

	add_brain(builder, (0.18, 0.08, 1.72), 0.62, seed=7)

	builder.ball("EyeWhite", 0.3, (-0.38, -0.66, 1.08), subdivisions=2)
	builder.ball("EyeWhite", 0.26, (0.4, -0.64, 0.98), subdivisions=2)
	builder.ball("Outline", 0.1, (-0.32, -0.94, 1.1), scale=(1, 0.5, 1))
	builder.ball("Outline", 0.09, (0.47, -0.88, 0.95), scale=(1, 0.5, 1))

	builder.ball("Outline", 0.05, (-0.07, -0.81, 0.72))
	builder.ball("Outline", 0.05, (0.07, -0.81, 0.72))

	builder.ball("MouthDark", 1, (0.05, -0.7, 0.42), scale=(0.27, 0.1, 0.19), subdivisions=2)
	builder.ball("Tongue", 1, (0.09, -0.74, 0.34), scale=(0.15, 0.07, 0.07))
	builder.box("EyeWhite", (0.1, 0.06, 0.12), (-0.05, -0.78, 0.53), bevel=0.015)
	builder.box("EyeWhite", (0.1, 0.06, 0.12), (0.1, -0.78, 0.53), bevel=0.015)


def build_purple_cauldron(builder):
	add_cauldron_pot(builder)
	add_potion(builder, "PotionPurple", "PotionLight", "PotionPale")


def build_green_cauldron(builder):
	add_cauldron_pot(builder)
	add_potion(builder, "PotionGreen", "PotionGreenLight", "PotionGreenPale")


def build_candy_cauldron(builder):
	add_cauldron_pot(builder)
	builder.cylinder("CauldronDark", 0.8, 0.8, 0.06, (0, 0, 1.34), segments=12, bevel=0)

	rng = random.Random(5)
	lollipop_colors = ("LollipopRed", "LollipopPurple", "LollipopBlack", "CandyOrange")

	for i in range(7):
		angle = math.tau * i / 7 + rng.uniform(-0.2, 0.2)
		distance = rng.uniform(0.35, 0.62)
		location = (math.cos(angle) * distance, math.sin(angle) * distance, 1.25)
		rotation = (rng.uniform(-25, 25), rng.uniform(-25, 25), rng.uniform(0, 360))
		builder.nested(location, rotation, (1, 1, 1), add_lollipop, lollipop_colors[i % 4])

	for i in range(11):
		angle = rng.uniform(0, math.tau)
		distance = rng.uniform(0, 0.62)
		height = 1.28 + (0.62 - distance) * 0.55
		location = (math.cos(angle) * distance, math.sin(angle) * distance, height)
		rotation = (rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(0, 360))
		builder.nested(location, rotation, (0.4, 0.4, 0.4), build_candy_corn)

	builder.nested((-0.75, -0.95, 0.24), (0, 75, 30), (1, 1, 1), add_lollipop, "LollipopRed")
	builder.nested((0.45, -1.05, 0), (0, 0, 10), (0.4, 0.4, 0.4), build_candy_corn)
	builder.nested((0.95, -0.7, 0.02), (0, 25, -30), (0.36, 0.36, 0.36), build_candy_corn)


def build_coffin(builder):
	profile = [(-0.32, 0), (0.32, 0), (0.55, 1.45), (0.4, 2.0), (-0.4, 2.0), (-0.55, 1.45)]
	lining_profile = [(x * 0.82, z * 0.86 + 0.14) for x, z in profile]

	builder.prism("CoffinDark", profile, 0.45, (0, 0.1, 0))
	builder.prism("CoffinLining", lining_profile, 0.06, (0, -0.12, 0), bevel=0.02)

	for z in (0.5, 0.85, 1.2, 1.55):
		builder.box("CoffinQuilt", (0.12, 0.04, 0.12), (0, -0.155, z), rotation=(0, 45, 0), bevel=0.01)

	lid_location = (-0.18, -0.24, 0)
	lid_rotation = (0, 0, 14)
	builder.prism("CoffinPurple", profile, 0.14, lid_location, lid_rotation)

	lid_matrix = make_matrix(lid_location, lid_rotation)
	for x, z in ((-0.36, 1.45), (0.36, 1.45), (-0.22, 0.2), (0.22, 0.2)):
		builder.ball("RivetBlue", 0.05, lid_matrix @ Vector((x, -0.08, z)), scale=(1, 0.5, 1))


def build_tombstone(builder):
	builder.box("StoneDark", (1.6, 0.8, 0.25), (0, 0, 0.125))

	profile = [(-0.6, 0), (0.6, 0), (0.6, 1.5), (0.42, 1.8), (-0.42, 1.8), (-0.6, 1.5)]
	panel_profile = [(-0.45, 0), (0.45, 0), (0.45, 1.15), (0.32, 1.38), (-0.32, 1.38), (-0.45, 1.15)]
	builder.prism("StoneBlue", profile, 0.4, (0, 0.05, 0.24))
	builder.prism("StoneLight", panel_profile, 0.06, (0, -0.17, 0.4), bevel=0.02)

	builder.ball("StoneBlue", 0.2, (0, -0.2, 1.3), scale=(1, 0.4, 0.9), subdivisions=2)
	builder.box("StoneBlue", (0.2, 0.06, 0.12), (0, -0.2, 1.12), bevel=0.02)
	builder.ball("StoneDark", 0.055, (-0.075, -0.27, 1.3), scale=(1, 0.5, 1.2))
	builder.ball("StoneDark", 0.055, (0.075, -0.27, 1.3), scale=(1, 0.5, 1.2))

	builder.box("StoneDark", (0.02, 0.02, 0.3), (-0.3, -0.205, 0.75), rotation=(0, 25, 0), bevel=0)
	builder.box("StoneDark", (0.02, 0.02, 0.22), (-0.25, -0.205, 0.5), rotation=(0, -30, 0), bevel=0)
	builder.box("StoneDark", (0.02, 0.02, 0.28), (0.3, -0.205, 1.55), rotation=(0, -40, 0), bevel=0)


def build_broom(builder):
	builder.lathe("Bristle", [(0.72, 0.1), (0.64, 0.45), (0.5, 0.82), (0.4, 1.0)], segments=10)

	strand_count = 16
	for i in range(strand_count):
		angle = 360 * i / strand_count
		direction = Vector((math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0))
		builder.cylinder(
			"BristleDark" if i % 2 == 0 else "BristleLight",
			0.04,
			0.17,
			0.55,
			direction * 0.6 + Vector((0, 0, 0.27)),
			rotation=(0, -12, angle),
			segments=4,
			bevel=0,
		)

	builder.cylinder("HatPurple", 0.56, 0.54, 0.18, (0, 0, 0.74), segments=10, bevel=0.03)
	builder.cylinder("BristleLight", 0.42, 0.38, 0.12, (0, 0, 1.04), segments=10, bevel=0.03)

	handle_top = builder.bent_tube("Wood", (0, 0, 1.0), [
		(0.17, 0.16, 0.75, 4),
		(0.16, 0.15, 0.65, -6),
		(0.15, 0.14, 0.65, 7),
		(0.14, 0.13, 0.5, 13),
	], side_color="WoodDark")
	builder.cylinder("WoodCut", 0.135, 0.135, 0.03, handle_top, rotation=(0, 13, 0), bevel=0)


ASSETS = [
	("CandyCorn", build_candy_corn),
	("Pumpkin", build_pumpkin),
	("JackOLantern", build_jack_o_lantern),
	("JackOLanternGlowing", build_glowing_jack_o_lantern),
	("WitchHat", build_witch_hat),
	("Broom", build_broom),
	("Bone", build_bone),
	("Brain", build_brain),
	("ZombieHead", build_zombie_head),
	("PurpleCauldron", build_purple_cauldron),
	("GreenCauldron", build_green_cauldron),
	("CandyCauldron", build_candy_cauldron),
	("Coffin", build_coffin),
	("Tombstone", build_tombstone),
]


#// Setup

def get_clean_collection():
	collection = bpy.data.collections.get(COLLECTION_NAME)
	if collection is None:
		collection = bpy.data.collections.new(COLLECTION_NAME)
		bpy.context.scene.collection.children.link(collection)

	for old_object in list(collection.objects):
		old_mesh = old_object.data
		bpy.data.objects.remove(old_object)
		if old_mesh.users == 0:
			bpy.data.meshes.remove(old_mesh)

	return collection


def export_assets(assets):
	os.makedirs(EXPORT_FOLDER, exist_ok=True)

	for asset in assets:
		bpy.ops.object.select_all(action="DESELECT")
		original_location = asset.location.copy()
		asset.location = (0, 0, 0)
		asset.select_set(True)
		for child in asset.children:
			child.select_set(True)
		bpy.context.view_layer.objects.active = asset

		bpy.ops.export_scene.fbx(
			filepath=os.path.join(EXPORT_FOLDER, asset.name + ".fbx"),
			use_selection=True,
			object_types={"MESH"},
			path_mode="COPY",
			embed_textures=True,
		)
		asset.location = original_location


def main():
	collection = get_clean_collection()
	material = get_palette_material()
	assets = []

	for index, (name, build_function) in enumerate(ASSETS):
		builder = AssetBuilder(name)
		build_function(builder)

		column = index % ASSETS_PER_ROW
		row = index // ASSETS_PER_ROW
		x = (column - (ASSETS_PER_ROW - 1) / 2) * ASSET_SPACING
		assets.append(builder.build(collection, material, (x, row * ROW_SPACING, 0)))

	if EXPORT_FOLDER:
		export_assets(assets)

	if bpy.context.screen:
		for area in bpy.context.screen.areas:
			if area.type == "VIEW_3D":
				area.spaces.active.shading.type = "MATERIAL"


main()
