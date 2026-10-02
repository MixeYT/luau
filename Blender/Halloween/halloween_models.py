import bpy
import bmesh
import math
import os
import random
from mathutils import Euler, Matrix, Vector, noise
from mathutils.bvhtree import BVHTree

# Run inside Blender 4.1+: Scripting tab -> Open -> Run Script.
# Every model is built from continuous meshes (lathes, sweeps, metaballs, booleans),
# shaded smooth with auto smooth and colored through one shared palette texture.

COLLECTION_NAME = "Halloween"
PALETTE_NAME = "HalloweenPalette"
PALETTE_SIZE = 128
PALETTE_GRID = 8

ASSET_SPACING = 3.5
ROW_SPACING = 4.5
ASSETS_PER_ROW = 7

AUTO_SMOOTH_ANGLE = 40
METABALL_RESOLUTION = 0.04
METABALL_SURFACE_RATIO = 0.575  # visible radius of a metaball compared to its influence radius
CAP_STEPS = 4
CARVE_DEPTH = 0.16
LOLLIPOP_TWIST = 9

BRAIN_FOLD_SCALE = 2.8
BRAIN_GROOVE_WIDTH = 0.16
BRAIN_GROOVE_DEPTH = 0.16
BRAIN_GROOVE_BLUR = 2
BRAIN_TRIANGLES = 6000

# Leave empty to skip. Otherwise every model is exported as its own FBX into this folder.
EXPORT_FOLDER = ""

PALETTE = {
	"Pupil": "1E1726",
	"White": "F7F4EE",
	"CandyYellow": "FFD21F",
	"CandyOrange": "FF7A12",
	"CandyWhite": "FFF4D9",
	"LollipopRed": "FF2E4D",
	"LollipopPurple": "9B3BE8",
	"LollipopBlack": "2E2638",
	"PumpkinOrange": "FF8C1F",
	"PumpkinCarve": "5C1E06",
	"Glow": "FFE14D",
	"StemGreen": "4CAF3D",
	"StemDark": "2F7A2C",
	"BrainPink": "FFA3C8",
	"BrainDark": "F07AAA",
	"CauldronBody": "3B3049",
	"CauldronDark": "241D2E",
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
	"HatPurple": "9257E8",
	"HatDark": "6C3BBF",
	"HatBand": "8F4A22",
	"Gold": "FFC23A",
	"Wood": "A65A2A",
	"WoodCut": "E8A866",
	"Bristle": "EBA93C",
	"BristleLight": "F7CF6E",
	"BristleDark": "C98A2A",
	"ZombieGreen": "8EE04A",
	"ZombieDark": "5FA82B",
	"EyeWhite": "F7EEDB",
	"MouthDark": "5A1F45",
	"Tongue": "D6409F",
	"StoneBlue": "7896EA",
	"StoneLight": "93AEF5",
	"StoneDark": "5672C9",
}

COLOR_NAMES = list(PALETTE)


#// Math Helpers

def make_matrix(location=(0, 0, 0), rotation=(0, 0, 0), scale=1):
	if isinstance(scale, (int, float)):
		scale = (scale, scale, scale)
	euler = Euler([math.radians(angle) for angle in rotation])
	return Matrix.LocRotScale(Vector(location), euler, Vector(scale))


def catmull_rom(points, smoothness, cyclic=False):
	points = [Vector(point) for point in points]
	if smoothness <= 1:
		return points

	count = len(points)
	result = []
	for i in range(count if cyclic else count - 1):
		if cyclic:
			p0, p1, p2, p3 = (points[(i + offset) % count] for offset in (-1, 0, 1, 2))
		else:
			p0 = points[max(i - 1, 0)]
			p1 = points[i]
			p2 = points[i + 1]
			p3 = points[min(i + 2, count - 1)]

		for step in range(smoothness):
			t = step / smoothness
			result.append(0.5 * (
				2 * p1
				+ (p2 - p0) * t
				+ (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
				+ (3 * p1 - p0 - 3 * p2 + p3) * t ** 3
			))

	if not cyclic:
		result.append(points[-1])
	return result


def densify(outline, step):
	result = []
	for i, start in enumerate(outline):
		start = Vector(start)
		end = Vector(outline[(i + 1) % len(outline)])
		count = max(1, math.ceil((end - start).length / step))
		result += [start.lerp(end, j / count) for j in range(count)]
	return result


#// Mesh Helpers

def mesh_from_bmesh(bm, color=None):
	if color:
		for face in bm.faces:
			face.material_index = COLOR_NAMES.index(color)
	mesh = bpy.data.meshes.new("HalloweenPart")
	bm.to_mesh(mesh)
	bm.free()
	return mesh


def recolor(mesh, pick_color):
	for polygon in mesh.polygons:
		color = pick_color(polygon.center, polygon.normal)
		if color:
			polygon.material_index = COLOR_NAMES.index(color)
	return mesh


def transformed(mesh, location=(0, 0, 0), rotation=(0, 0, 0), scale=1):
	mesh.transform(make_matrix(location, rotation, scale))
	return mesh


def join_meshes(meshes):
	bm = bmesh.new()
	for mesh in meshes:
		bm.from_mesh(mesh)
		bpy.data.meshes.remove(mesh)
	return mesh_from_bmesh(bm)


def split_at_heights(mesh, heights):
	bm = bmesh.new()
	bm.from_mesh(mesh)
	for height in heights:
		geometry = list(bm.verts) + list(bm.edges) + list(bm.faces)
		bmesh.ops.bisect_plane(bm, geom=geometry, plane_co=(0, 0, height), plane_no=(0, 0, 1))
	bm.to_mesh(mesh)
	bm.free()
	return mesh


def apply_modifiers(mesh, modifiers):
	holder = bpy.data.objects.new("HalloweenTemp", mesh)
	bpy.context.scene.collection.objects.link(holder)

	for modifier_type, settings in modifiers:
		modifier = holder.modifiers.new(modifier_type, modifier_type)
		for key, value in settings.items():
			setattr(modifier, key, value)

	depsgraph = bpy.context.evaluated_depsgraph_get()
	result = bpy.data.meshes.new_from_object(holder.evaluated_get(depsgraph))
	bpy.data.objects.remove(holder)
	bpy.data.meshes.remove(mesh)
	return result


def carve(mesh, cutter):
	# Faces created by the cut keep the cutter's color
	cutter_object = bpy.data.objects.new("HalloweenCutter", cutter)
	bpy.context.scene.collection.objects.link(cutter_object)

	result = apply_modifiers(mesh, [("BOOLEAN", {
		"operation": "DIFFERENCE",
		"object": cutter_object,
		"solver": "EXACT",
		"material_mode": "INDEX",
	})])

	bpy.data.objects.remove(cutter_object)
	bpy.data.meshes.remove(cutter)
	return result


def decimate(mesh, triangle_count):
	current = sum(len(polygon.vertices) - 2 for polygon in mesh.polygons)
	if current <= triangle_count:
		return mesh
	return apply_modifiers(mesh, [("DECIMATE", {"ratio": triangle_count / current})])


def front_surface(mesh):
	bvh = BVHTree.FromPolygons([vertex.co.copy() for vertex in mesh.vertices], [tuple(polygon.vertices) for polygon in mesh.polygons])

	def surface_y(x, z):
		hit = bvh.ray_cast(Vector((x, -10, z)), Vector((0, 1, 0)))[0]
		return hit.y if hit else -1.0

	return surface_y


#// Shapes

def connect_rings(bm, first, second):
	count = max(len(first), len(second))
	for i in range(count):
		j = (i + 1) % count
		if len(first) == 1:
			bm.faces.new((first[0], second[i], second[j]))
		elif len(second) == 1:
			bm.faces.new((first[i], first[j], second[0]))
		else:
			bm.faces.new((first[i], first[j], second[j], second[i]))


def lathe(profile, color, segments=32, smoothness=3, shape=None, closed=False):
	# Profile is a list of (radius, z) points spun around Z. A radius of 0 at an end makes a pole.
	# shape(angle, radius, z) -> (radius, z) can bend the surface per angle.
	points = catmull_rom(profile, smoothness, closed)
	angles = [math.tau * i / segments for i in range(segments)]
	bm = bmesh.new()
	rings = []

	for index, point in enumerate(points):
		is_end = not closed and index in (0, len(points) - 1)
		if is_end and point.x <= 0.0001:
			rings.append([bm.verts.new((0, 0, point.y))])
			continue

		ring = []
		for angle in angles:
			radius, height = max(point.x, 0.01), point.y
			if shape:
				radius, height = shape(angle, radius, height)
			ring.append(bm.verts.new((math.cos(angle) * radius, math.sin(angle) * radius, height)))
		rings.append(ring)

	for first, second in zip(rings, rings[1:]):
		connect_rings(bm, first, second)

	if closed:
		connect_rings(bm, rings[-1], rings[0])
	else:
		for ring in (rings[0], rings[-1]):
			if len(ring) > 1:
				bm.faces.new(ring)

	bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
	return mesh_from_bmesh(bm, color)


def sweep(points, radii, color, segments=12, smoothness=4, start_cap="flat", end_cap="round", end_color=None):
	# A tube following a smooth path. Caps can be "flat", "round" or "none".
	path = catmull_rom(points, smoothness)
	count = len(path)

	# Radii are spread evenly along the path, so they can be given at any resolution
	path_radii = []
	for i in range(count):
		position = i / (count - 1) * (len(radii) - 1)
		lower = min(int(position), len(radii) - 2)
		path_radii.append(radii[lower] + (radii[lower + 1] - radii[lower]) * (position - lower))
	angles = [math.tau * i / segments for i in range(segments)]

	frames = []
	normal = (path[1] - path[0]).orthogonal().normalized()
	for i in range(count):
		tangent = (path[min(i + 1, count - 1)] - path[max(i - 1, 0)]).normalized()
		normal = (normal - tangent * normal.dot(tangent)).normalized()
		frames.append((tangent, normal, tangent.cross(normal)))

	bm = bmesh.new()

	def make_ring(center, frame, radius):
		_, ring_normal, binormal = frame
		return [bm.verts.new(center + (ring_normal * math.cos(angle) + binormal * math.sin(angle)) * radius) for angle in angles]

	def make_cap(center, frame, radius, direction):
		cap = []
		for step in range(1, CAP_STEPS):
			angle = math.pi / 2 * step / CAP_STEPS
			cap.append(make_ring(center + frame[0] * direction * radius * math.sin(angle), frame, radius * math.cos(angle)))
		cap.append([bm.verts.new(center + frame[0] * direction * radius)])
		return cap

	rings = [make_ring(path[i], frames[i], path_radii[i]) for i in range(count)]
	if start_cap == "round":
		rings = list(reversed(make_cap(path[0], frames[0], path_radii[0], -1))) + rings
	if end_cap == "round":
		rings += make_cap(path[-1], frames[-1], path_radii[-1], 1)

	for first, second in zip(rings, rings[1:]):
		connect_rings(bm, first, second)

	if start_cap == "flat":
		bm.faces.new(rings[0])
	end_face = bm.faces.new(rings[-1]) if end_cap == "flat" else None

	bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
	for face in bm.faces:
		face.material_index = COLOR_NAMES.index(color)
	if end_face and end_color:
		end_face.material_index = COLOR_NAMES.index(end_color)

	return mesh_from_bmesh(bm)


def sphere(color, radius, segments=16, scale=(1, 1, 1)):
	bm = bmesh.new()
	matrix = Matrix.Diagonal((*(Vector(scale) * radius), 1))
	bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2 + 1, radius=1, matrix=matrix)
	return mesh_from_bmesh(bm, color)


def rounded_box(color, size, bevel, segments=3):
	bm = bmesh.new()
	bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Diagonal((*size, 1)))
	mesh = mesh_from_bmesh(bm, color)
	return apply_modifiers(mesh, [("BEVEL", {"width": bevel, "segments": segments, "limit_method": "NONE"})])


def prism(profile, depth, color, bevel=0.0, segments=3):
	# Profile is a list of (x, z) points, extruded along Y and centered on it
	bm = bmesh.new()
	front = [bm.verts.new((x, -depth / 2, z)) for x, z in profile]
	back = [bm.verts.new((x, depth / 2, z)) for x, z in profile]

	bm.faces.new(front)
	bm.faces.new(back)
	for i in range(len(profile)):
		j = (i + 1) % len(profile)
		bm.faces.new((front[i], front[j], back[j], back[i]))

	bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
	mesh = mesh_from_bmesh(bm, color)
	if bevel > 0:
		mesh = apply_modifiers(mesh, [("BEVEL", {"width": bevel, "segments": segments, "limit_method": "NONE"})])
	return mesh


def frame(color, outer, inner, depth, bevel):
	bm = bmesh.new()
	corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
	outer_front = [bm.verts.new((x * outer[0] / 2, -depth / 2, z * outer[1] / 2)) for x, z in corners]
	outer_back = [bm.verts.new((x * outer[0] / 2, depth / 2, z * outer[1] / 2)) for x, z in corners]
	inner_front = [bm.verts.new((x * inner[0] / 2, -depth / 2, z * inner[1] / 2)) for x, z in corners]
	inner_back = [bm.verts.new((x * inner[0] / 2, depth / 2, z * inner[1] / 2)) for x, z in corners]

	for i in range(4):
		j = (i + 1) % 4
		bm.faces.new((outer_front[i], outer_front[j], inner_front[j], inner_front[i]))
		bm.faces.new((outer_back[i], outer_back[j], inner_back[j], inner_back[i]))
		bm.faces.new((outer_front[i], outer_front[j], outer_back[j], outer_back[i]))
		bm.faces.new((inner_front[i], inner_front[j], inner_back[j], inner_back[i]))

	bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
	mesh = mesh_from_bmesh(bm, color)
	return apply_modifiers(mesh, [("BEVEL", {"width": bevel, "segments": 2, "limit_method": "NONE"})])


def blob(location, radii, negative=False):
	if isinstance(radii, (int, float)):
		radii = (radii, radii, radii)
	return {"location": Vector(location), "radii": Vector(radii), "negative": negative}


def metaball(blobs, color, triangle_count=3000):
	# Blobs melt into one smooth surface, so organic shapes have no seams
	data = bpy.data.metaballs.new("HalloweenMeta")
	data.resolution = METABALL_RESOLUTION
	data.render_resolution = METABALL_RESOLUTION
	data.threshold = 0.6

	for item in blobs:
		largest = max(item["radii"])
		element = data.elements.new(type="ELLIPSOID")
		element.co = item["location"]
		element.radius = largest / METABALL_SURFACE_RATIO
		element.size_x, element.size_y, element.size_z = item["radii"] / largest
		element.use_negative = item["negative"]

	holder = bpy.data.objects.new("HalloweenMeta", data)
	bpy.context.scene.collection.objects.link(holder)
	depsgraph = bpy.context.evaluated_depsgraph_get()
	mesh = bpy.data.meshes.new_from_object(holder.evaluated_get(depsgraph))
	bpy.data.objects.remove(holder)
	bpy.data.metaballs.remove(data)

	for polygon in mesh.polygons:
		polygon.material_index = COLOR_NAMES.index(color)
	return decimate(mesh, triangle_count)


#// Asset

class Asset:
	def __init__(self):
		self.parts = []

	def add(self, mesh, location=(0, 0, 0), rotation=(0, 0, 0), scale=1):
		self.parts.append(transformed(mesh, location, rotation, scale))

	def add_asset(self, other, location=(0, 0, 0), rotation=(0, 0, 0), scale=1):
		for mesh in other.parts:
			self.add(mesh, location, rotation, scale)


#// Shared Parts

def folded_ellipsoid(center, radii, groove_at, color, subdivisions=6):
	# groove_at(direction) -> 0..1 pushes the surface in to form brain folds
	bm = bmesh.new()
	bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1)
	grooves = {vert: groove_at(vert.co.normalized()) for vert in bm.verts}

	# Blurring the groove map gives soft rounded folds instead of jagged pits
	for _ in range(BRAIN_GROOVE_BLUR):
		grooves = {
			vert: (grooves[vert] + sum(grooves[edge.other_vert(vert)] for edge in vert.link_edges) / len(vert.link_edges)) / 2
			for vert in bm.verts
		}

	for vert in bm.verts:
		surface = vert.co.normalized() * (1 - BRAIN_GROOVE_DEPTH * grooves[vert])
		vert.co = Vector(center) + Vector((surface.x * radii[0], surface.y * radii[1], surface.z * radii[2]))

	for face in bm.faces:
		average = sum(grooves[vert] for vert in face.verts) / len(face.verts)
		face.material_index = COLOR_NAMES.index("BrainDark" if average > 0.4 else color)

	return mesh_from_bmesh(bm)


def brain_mesh(size=1.0, seed=3, triangle_count=BRAIN_TRIANGLES):
	parts = []

	for side in (-1, 1):
		offset = Vector((seed * 3.1, side * 5.7, 0))

		def groove_at(direction, offset=offset, side=side):
			value = abs(noise.noise(direction * BRAIN_FOLD_SCALE + offset))
			groove = max(0.0, 1 - value / BRAIN_GROOVE_WIDTH)
			# The flat inner side stays smooth
			return groove * min(1.0, max(0.0, direction.x * side * 3 + 0.6))

		hemisphere = folded_ellipsoid((side * 0.28, 0, 0), (0.58, 0.92, 0.66), groove_at, "BrainPink", subdivisions=6)
		for vertex in hemisphere.vertices:
			if (vertex.co.x - side * 0.28) * side < 0:
				vertex.co.x = side * 0.28 + (vertex.co.x - side * 0.28) * 0.45
		parts.append(hemisphere)

	def cerebellum_groove(direction):
		return max(0.0, 1 - abs(math.sin(direction.z * 9)) / 0.35) ** 2

	parts.append(folded_ellipsoid((0, 0.52, -0.32), (0.55, 0.33, 0.27), cerebellum_groove, "BrainPink", subdivisions=5))

	mesh = decimate(join_meshes(parts), triangle_count)
	return transformed(mesh, scale=size)


def build_lollipop(color):
	asset = Asset()
	asset.add(sweep([(0, 0, 0), (0, 0, 0.62)], [0.035, 0.035], "White", segments=8, smoothness=1, start_cap="round", end_cap="flat"))

	head = lathe([(0, -0.09), (0.17, -0.085), (0.25, 0), (0.17, 0.085), (0, 0.09)], color, segments=24, smoothness=4)
	recolor(head, lambda point, normal: "White" if math.floor(math.atan2(point.y, point.x) / math.tau * 8) % 2 == 0 else None)

	for vertex in head.vertices:
		radius = Vector((vertex.co.x, vertex.co.y)).length
		vertex.co.rotate(Matrix.Rotation(radius * LOLLIPOP_TWIST, 3, "Z"))

	asset.add(head, (0, 0, 0.82), (90, 0, 0))
	return asset


PUMPKIN_LOBES = 8
PUMPKIN_PROFILE = [(0, 0.1), (0.45, 0.03), (0.85, 0.14), (1.05, 0.42), (1.08, 0.7), (0.98, 1.0), (0.7, 1.22), (0.35, 1.3), (0.12, 1.25), (0, 1.18)]


def lobe_strength(angle):
	return abs(math.cos(PUMPKIN_LOBES * angle / 2))


def pumpkin_mesh():
	def lobes(angle, radius, height):
		return radius * (0.8 + 0.2 * lobe_strength(angle) ** 0.5), height

	return lathe(PUMPKIN_PROFILE, "PumpkinOrange", segments=48, smoothness=3, shape=lobes)


def jack_o_lantern_cutter(surface_y, color):
	center = 0.72
	eye = [(-0.56, 0.06), (-0.14, 0.03), (-0.3, 0.36)]
	nose = [(-0.08, -0.04), (0.08, -0.04), (0, 0.1)]

	mouth_width = 0.6
	tooth_drop = 0.1
	teeth = ((-0.2, 0.07), (0.2, 0.07))
	steps = [-mouth_width + 2 * mouth_width * i / 12 for i in range(13)]

	def upper_lip(x):
		return -0.14 - 0.2 * (1 - (x / mouth_width) ** 2)

	def lower_lip(x):
		return upper_lip(x) - 0.05 - 0.2 * (1 - (x / mouth_width) ** 2)

	top = [(x, upper_lip(x)) for x in steps if not any(abs(x - tooth) < half for tooth, half in teeth)]
	for tooth, half in teeth:
		top += [
			(tooth - half, upper_lip(tooth - half)),
			(tooth - half, upper_lip(tooth - half) - tooth_drop),
			(tooth + half, upper_lip(tooth + half) - tooth_drop),
			(tooth + half, upper_lip(tooth + half)),
		]
	top.sort(key=lambda point: point[0])
	mouth = top + [(x, lower_lip(x)) for x in reversed(steps)]

	shapes = [eye, [(-x, z) for x, z in reversed(eye)], nose, mouth]
	bm = bmesh.new()

	for shape in shapes:
		outline = densify([(x, z + center) for x, z in shape], 0.06)
		# A flat back keeps the cutter clean; the center of each hole just ends up a bit deeper
		back_y = max(surface_y(point.x, point.y) for point in outline) + CARVE_DEPTH
		front = [bm.verts.new((point.x, -3, point.y)) for point in outline]
		back = [bm.verts.new((point.x, back_y, point.y)) for point in outline]

		bm.faces.new(front)
		bm.faces.new(back)
		for i in range(len(outline)):
			j = (i + 1) % len(outline)
			bm.faces.new((front[i], front[j], back[j], back[i]))

	bmesh.ops.triangulate(bm, faces=list(bm.faces))
	bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
	return mesh_from_bmesh(bm, color)


CAULDRON_PROFILE = [
	(0, 0.2), (0.5, 0.21), (0.82, 0.35), (1.0, 0.62), (1.02, 0.85), (0.94, 1.08), (0.84, 1.2),
	(0.86, 1.27), (0.98, 1.3), (1.04, 1.37), (1.0, 1.45), (0.9, 1.47), (0.8, 1.43), (0.76, 1.32), (0.74, 1.15), (0, 1.1),
]


def cauldron_outer_radius(height):
	outer = CAULDRON_PROFILE[1:10]
	for (radius_a, height_a), (radius_b, height_b) in zip(outer, outer[1:]):
		if height_a <= height <= height_b:
			return radius_a + (radius_b - radius_a) * (height - height_a) / (height_b - height_a)
	return outer[-1][0]


def build_cauldron_pot():
	asset = Asset()
	pot = lathe(CAULDRON_PROFILE, "CauldronBody", segments=32, smoothness=2)

	def pick_color(point, normal):
		if point.z > 1.25:
			return "CauldronRim"
		outward = Vector((point.x, point.y, 0))
		if outward.length > 0.01 and normal.dot(outward.normalized()) < -0.2:
			return "CauldronDark"
		return None

	asset.add(recolor(pot, pick_color))

	for i in range(3):
		angle = math.tau * i / 3 + math.pi / 2
		leg = lathe([(0, 0), (0.13, 0.01), (0.2, 0.12), (0.18, 0.3), (0, 0.38)], "CauldronDark", segments=14, smoothness=2)
		asset.add(leg, (math.cos(angle) * 0.55, math.sin(angle) * 0.55, 0))

	return asset


def add_potion(asset, liquid_color, light_color, pale_color):
	blobs = [blob((0, 0, 1.33), (0.8, 0.8, 0.08))]

	for angle, length in ((-20, 0.42), (25, 0.26), (160, 0.3)):
		direction = Vector((math.sin(math.radians(angle)), -math.cos(math.radians(angle)), 0))
		blobs.append(blob(direction * 0.9 + Vector((0, 0, 1.44)), (0.22, 0.22, 0.09)))

		steps = 7
		for step in range(steps + 1):
			height = 1.4 - length * step / steps
			radius = 0.085 if step < steps else 0.11
			blobs.append(blob(direction * (cauldron_outer_radius(height) + 0.03) + Vector((0, 0, height)), radius))

	asset.add(metaball(blobs, liquid_color, 1600))

	rng = random.Random(11)
	bubble_colors = (light_color, pale_color, liquid_color)
	bubbles = []
	while len(bubbles) < 13:
		angle = rng.uniform(0, math.tau)
		distance = rng.uniform(0, 0.58)
		radius = rng.uniform(0.13, 0.26)
		location = Vector((math.cos(angle) * distance, math.sin(angle) * distance, 1.36 + (0.58 - distance) * 0.55))
		if all((location - other).length > (radius + other_radius) * 0.8 for other, other_radius in bubbles):
			bubbles.append((location, radius))

	for i, (location, radius) in enumerate(bubbles):
		asset.add(sphere(bubble_colors[i % 3], radius, segments=12), location)


#// Assets

def build_candy_corn(small=False):
	asset = Asset()
	profile = [(0, 0), (0.5, 0.02), (0.72, 0.12), (0.8, 0.32), (0.76, 0.6), (0.64, 0.92), (0.47, 1.25), (0.27, 1.52), (0.1, 1.68), (0, 1.72)]
	mesh = lathe(profile, "CandyYellow", segments=10 if small else 20, smoothness=2 if small else 3)
	mesh.transform(Matrix.Diagonal((1, 0.62, 1, 1)))
	split_at_heights(mesh, (0.6, 1.15))
	recolor(mesh, lambda point, normal: "CandyYellow" if point.z < 0.6 else "CandyOrange" if point.z < 1.15 else "CandyWhite")
	asset.add(mesh)
	return asset


def build_pumpkin():
	asset = Asset()
	asset.add(pumpkin_mesh())
	asset.add(sweep(
		[(0, 0, 1.1), (0, 0, 1.38), (0.05, 0, 1.58), (0.17, 0, 1.7), (0.32, 0, 1.72)],
		[0.17, 0.14, 0.12, 0.1, 0.085],
		"StemGreen",
		segments=8,
		end_cap="flat",
		end_color="StemDark",
	))

	tendril = []
	for i in range(10):
		t = i / 9
		angle = t * math.tau * 1.3
		radius = 0.2 - 0.13 * t
		tendril.append((-0.32 + math.cos(angle) * radius, -0.1 - 0.1 * t, 1.36 + math.sin(angle) * radius))
	asset.add(sweep(tendril, [0.04, 0.035, 0.03, 0.025, 0.02], "StemGreen", segments=6, start_cap="none", end_cap="round"))
	return asset


def build_witch_hat():
	asset = Asset()

	def wavy_brim(angle, radius, height):
		return radius, height + 0.05 * math.sin(3 * angle + 0.6) * (radius / 1.36) ** 2

	brim = lathe(
		[(0, 0.13), (0.6, 0.12), (1.0, 0.11), (1.24, 0.13), (1.34, 0.19), (1.37, 0.12), (1.31, 0.04), (1.0, 0.0), (0.6, 0.0), (0, 0.01)],
		"HatPurple",
		segments=36,
		smoothness=2,
		shape=wavy_brim,
	)
	asset.add(recolor(brim, lambda point, normal: "HatDark" if normal.z < -0.3 else None))

	asset.add(sweep(
		[(0, 0, 0.05), (0, 0, 0.55), (0.05, 0, 0.95), (0.18, 0, 1.25), (0.42, 0, 1.45), (0.64, 0, 1.4)],
		[0.68, 0.6, 0.46, 0.3, 0.15, 0.06],
		"HatPurple",
		segments=20,
	))

	asset.add(lathe([(0.63, 0.12), (0.71, 0.13), (0.73, 0.25), (0.71, 0.37), (0.62, 0.38)], "HatBand", segments=32, smoothness=2, closed=True))
	asset.add(frame("Gold", (0.34, 0.3), (0.17, 0.14), 0.07, 0.025), (0, -0.735, 0.25))
	return asset


def build_jack_o_lantern(carve_color="PumpkinCarve"):
	asset = Asset()
	body = pumpkin_mesh()
	cutter = jack_o_lantern_cutter(front_surface(body), carve_color)
	asset.add(carve(body, cutter))
	asset.add_asset(build_witch_hat(), (0.04, 0.06, 1.3), (5, -8, 0), 0.82)
	return asset


def build_glowing_jack_o_lantern():
	return build_jack_o_lantern("Glow")


def build_broom():
	asset = Asset()
	strand_count = 18

	def strand(angle):
		return abs(math.cos(strand_count * angle / 2))

	def bristles(angle, radius, height):
		if height < 0.5:
			height -= (0.5 - height) / 0.35 * 0.16 * strand(angle) ** 3
		return radius * (0.94 + 0.06 * strand(angle)), height

	bristle_mesh = lathe(
		[(0, 1.25), (0.36, 1.23), (0.46, 1.1), (0.56, 0.85), (0.68, 0.55), (0.76, 0.27), (0.72, 0.17), (0, 0.21)],
		"Bristle",
		segments=strand_count * 4,
		smoothness=2,
		shape=bristles,
	)
	asset.add(recolor(bristle_mesh, lambda point, normal: "BristleDark" if strand(math.atan2(point.y, point.x)) < 0.5 and normal.z < 0.5 else None))

	asset.add(lathe([(0.3, 1.15), (0.44, 1.17), (0.46, 1.25), (0.4, 1.31), (0.3, 1.29)], "BristleLight", segments=24, smoothness=2, closed=True))
	asset.add(lathe([(0.52, 0.77), (0.63, 0.78), (0.66, 0.87), (0.63, 0.96), (0.52, 0.97)], "HatPurple", segments=32, smoothness=2, closed=True))

	asset.add(sweep(
		[(0, 0, 1.05), (0.02, 0, 1.6), (-0.04, 0, 2.15), (0.03, 0.02, 2.65), (0.12, 0.03, 3.05)],
		[0.15, 0.14, 0.13, 0.125, 0.12],
		"Wood",
		segments=10,
		start_cap="none",
		end_cap="flat",
		end_color="WoodCut",
	))
	return asset


def build_bone():
	asset = Asset()
	blobs = [blob((x * 0.12, 0, 0.6), 0.2) for x in range(-7, 8)]
	for side in (-1, 1):
		for offset in (-1, 1):
			blobs.append(blob((side * 0.95, 0, 0.6 + offset * 0.2), 0.3))
	asset.add(metaball(blobs, "Bone", 1500))
	return asset


def build_brain():
	asset = Asset()
	asset.add(brain_mesh(), (0, 0, 0.75))
	return asset


def build_zombie_head():
	asset = Asset()
	head = metaball([
		blob((0, 0, 1.0), (0.9, 0.82, 0.95)),
		blob((0, -0.12, 0.55), (0.72, 0.62, 0.42)),
		blob((-0.9, 0.05, 0.95), (0.16, 0.22, 0.3)),
		blob((0.9, 0.05, 1.0), (0.16, 0.22, 0.3)),
	], "ZombieGreen", 2200)
	surface_y = front_surface(head)

	cut_line = []
	for i in range(17):
		x = -1.2 + i * 0.15
		cut_line.append((x, 1.45 - 0.28 * x + (0.06 if i % 2 else -0.06)))
	skull_cutter = prism(cut_line + [(1.2, 3), (-1.2, 3)], 4, "ZombieDark")

	mouth_y = surface_y(0.05, 0.42)
	mouth_cutter = transformed(sphere("MouthDark", 1, segments=20, scale=(0.27, 0.22, 0.19)), (0.05, mouth_y + 0.06, 0.42))
	asset.add(carve(head, join_meshes([skull_cutter, mouth_cutter])))

	asset.add(brain_mesh(0.55, seed=7, triangle_count=3500), (0.22, 0.05, 1.48), (0, 15, 0))

	for x, z, radius, look in ((-0.38, 1.1, 0.3, (0.25, 0.08)), (0.4, 0.98, 0.27, (0.3, -0.12))):
		eye_center = Vector((x, surface_y(x, z) + radius * 0.45, z))
		asset.add(sphere("EyeWhite", radius, segments=20), eye_center)
		look_direction = Vector((look[0], -1, look[1])).normalized()
		asset.add(sphere("Pupil", 0.11, segments=14, scale=(1, 0.4, 1)), eye_center + look_direction * radius * 0.93)

	for x in (-0.07, 0.07):
		asset.add(sphere("MouthDark", 0.045, segments=10), (x, surface_y(x, 0.72) + 0.015, 0.72))

	asset.add(sphere("Tongue", 1, segments=16, scale=(0.16, 0.1, 0.07)), (0.09, mouth_y + 0.05, 0.31))
	for x in (-0.04, 0.12):
		asset.add(rounded_box("EyeWhite", (0.1, 0.08, 0.13), 0.025), (x, mouth_y + 0.04, 0.54))
	return asset


def build_purple_cauldron():
	asset = build_cauldron_pot()
	add_potion(asset, "PotionPurple", "PotionLight", "PotionPale")
	return asset


def build_green_cauldron():
	asset = build_cauldron_pot()
	add_potion(asset, "PotionGreen", "PotionGreenLight", "PotionGreenPale")
	return asset


def build_candy_cauldron():
	asset = build_cauldron_pot()
	asset.add(lathe([(0, 1.36), (0.6, 1.34), (0.8, 1.3), (0, 1.2)], "CauldronDark", segments=32, smoothness=2))

	rng = random.Random(5)
	lollipop_colors = ("LollipopRed", "LollipopPurple", "LollipopBlack", "CandyOrange")

	for i in range(6):
		angle = math.tau * i / 6 + rng.uniform(-0.25, 0.25)
		distance = rng.uniform(0.3, 0.55)
		location = (math.cos(angle) * distance, math.sin(angle) * distance, 1.05)
		rotation = (rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(0, 360))
		asset.add_asset(build_lollipop(lollipop_colors[i % 4]), location, rotation)

	for i in range(12):
		angle = rng.uniform(0, math.tau)
		distance = rng.uniform(0, 0.62)
		height = 1.25 + (0.62 - distance) * 0.55
		location = (math.cos(angle) * distance, math.sin(angle) * distance, height)
		rotation = (rng.uniform(-60, 60), rng.uniform(-60, 60), rng.uniform(0, 360))
		asset.add_asset(build_candy_corn(small=True), location, rotation, 0.38)

	asset.add_asset(build_lollipop("LollipopRed"), (-0.4, -1.05, 0.25), (0, -80, 25))
	asset.add_asset(build_candy_corn(small=True), (0.45, -1.1, 0), (0, 0, 10), 0.42)
	asset.add_asset(build_candy_corn(small=True), (0.95, -0.75, 0.05), (0, 30, -30), 0.38)
	return asset


COFFIN_PROFILE = [(-0.36, 0), (0.36, 0), (0.6, 1.45), (0.44, 2.0), (-0.44, 2.0), (-0.6, 1.45)]


def build_coffin():
	asset = Asset()
	body = transformed(prism(COFFIN_PROFILE, 0.5, "CoffinDark", bevel=0.07), (0, 0.1, 0))
	cavity = transformed(prism([(x * 0.78, 0.16 + z * 0.84) for x, z in COFFIN_PROFILE], 0.55, "CoffinLining"), (0, -0.225, 0))
	asset.add(carve(body, cavity))

	for row in range(5):
		z = 0.45 + row * 0.28
		for x in ((-0.13, 0.13) if row % 2 == 0 else (0,)):
			asset.add(rounded_box("CoffinQuilt", (0.13, 0.06, 0.13), 0.03), (x, 0.05, z), (0, 45, 0))

	lid_location = (-0.26, -0.27, 0.02)
	lid_rotation = (0, 0, 6)
	asset.add(prism(COFFIN_PROFILE, 0.14, "CoffinPurple", bevel=0.05), lid_location, lid_rotation)

	lid_matrix = make_matrix(lid_location, lid_rotation)
	for x, z in ((-0.36, 1.45), (0.36, 1.45), (-0.22, 0.22), (0.22, 0.22)):
		asset.add(sphere("RivetBlue", 0.055, segments=12, scale=(1, 0.5, 1)), lid_matrix @ Vector((x, -0.075, z)))
	return asset


def build_tombstone():
	asset = Asset()
	asset.add(rounded_box("StoneDark", (1.7, 0.85, 0.26), 0.06), (0, 0, 0.13))

	stone_profile = [(-0.62, 0), (0.62, 0), (0.62, 1.45), (0.44, 1.82), (-0.44, 1.82), (-0.62, 1.45)]
	panel_profile = [(-0.46, 0), (0.46, 0), (0.46, 1.12), (0.33, 1.38), (-0.33, 1.38), (-0.46, 1.12)]
	asset.add(prism(stone_profile, 0.42, "StoneBlue", bevel=0.07), (0, 0.05, 0.24))

	panel = transformed(prism(panel_profile, 0.08, "StoneLight", bevel=0.03), (0, -0.17, 0.42))
	cracks = [
		sweep([(-0.32, -0.215, 0.98), (-0.25, -0.215, 0.86), (-0.31, -0.215, 0.74), (-0.22, -0.215, 0.6)], [0.02] * 4, "StoneDark", segments=6, smoothness=1, start_cap="round"),
		sweep([(0.17, -0.215, 1.66), (0.27, -0.215, 1.55), (0.21, -0.215, 1.45), (0.3, -0.215, 1.34)], [0.02] * 4, "StoneDark", segments=6, smoothness=1, start_cap="round"),
	]
	asset.add(carve(panel, join_meshes(cracks)))

	skull = metaball([
		blob((0, 0, 0.06), (0.21, 0.1, 0.2)),
		blob((0, 0, -0.12), (0.13, 0.07, 0.09)),
	], "StoneBlue", 900)
	sockets = [transformed(sphere("StoneDark", 0.065, segments=12), (side * 0.08, -0.12, 0.03)) for side in (-1, 1)]
	sockets.append(transformed(sphere("StoneDark", 0.03, segments=10, scale=(1, 1, 1.4)), (0, -0.1, -0.07)))
	asset.add(carve(skull, join_meshes(sockets)), (0, -0.21, 1.3))
	return asset


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


#// Palette

def palette_uv(index):
	column = index % PALETTE_GRID
	row = index // PALETTE_GRID
	return ((column + 0.5) / PALETTE_GRID, (row + 0.5) / PALETTE_GRID)


def get_palette_material(name=PALETTE_NAME, emission_strength=0.0):
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

	material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
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
	shader.inputs["Roughness"].default_value = 0.6

	links.new(texture.outputs["Color"], shader.inputs["Base Color"])
	links.new(shader.outputs["BSDF"], output.inputs["Surface"])

	if emission_strength > 0:
		links.new(texture.outputs["Color"], shader.inputs["Emission Color"])
		shader.inputs["Emission Strength"].default_value = emission_strength
	return material


#// Objects

def split_glow(mesh):
	glow_index = COLOR_NAMES.index("Glow")
	if not any(polygon.material_index == glow_index for polygon in mesh.polygons):
		return None

	bm = bmesh.new()
	bm.from_mesh(mesh)
	glow_bm = bm.copy()
	bmesh.ops.delete(bm, geom=[face for face in bm.faces if face.material_index == glow_index], context="FACES")
	bmesh.ops.delete(glow_bm, geom=[face for face in glow_bm.faces if face.material_index != glow_index], context="FACES")
	bm.to_mesh(mesh)
	bm.free()
	return mesh_from_bmesh(glow_bm)


def finish_mesh(mesh, name, material):
	bm = bmesh.new()
	bm.from_mesh(mesh)
	uv_layer = bm.loops.layers.uv.verify()

	for face in bm.faces:
		uv = palette_uv(face.material_index)
		for loop in face.loops:
			loop[uv_layer].uv = uv
		face.material_index = 0

	bm.to_mesh(mesh)
	bm.free()
	mesh.name = name
	mesh.materials.clear()
	mesh.materials.append(material)

	if hasattr(mesh, "set_sharp_from_angle"):
		mesh.shade_smooth()
		mesh.set_sharp_from_angle(angle=math.radians(AUTO_SMOOTH_ANGLE))
	else:
		for polygon in mesh.polygons:
			polygon.use_smooth = True
		mesh.use_auto_smooth = True
		mesh.auto_smooth_angle = math.radians(AUTO_SMOOTH_ANGLE)


def create_asset_object(name, asset, collection, material, glow_material, location):
	mesh = join_meshes(asset.parts)
	glow_mesh = split_glow(mesh)

	finish_mesh(mesh, name, material)
	asset_object = bpy.data.objects.new(name, mesh)
	asset_object.location = location
	collection.objects.link(asset_object)

	if glow_mesh:
		# Separate part so it can use the Neon material in Roblox
		finish_mesh(glow_mesh, name + "Glow", glow_material)
		glow_object = bpy.data.objects.new(name + "Glow", glow_mesh)
		glow_object.parent = asset_object
		collection.objects.link(glow_object)

	return asset_object


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
	glow_material = get_palette_material(PALETTE_NAME + "Glow", emission_strength=2.0)
	assets = []

	for index, (name, build_function) in enumerate(ASSETS):
		column = index % ASSETS_PER_ROW
		row = index // ASSETS_PER_ROW
		location = ((column - (ASSETS_PER_ROW - 1) / 2) * ASSET_SPACING, row * ROW_SPACING, 0)
		assets.append(create_asset_object(name, build_function(), collection, material, glow_material, location))

	if EXPORT_FOLDER:
		export_assets(assets)

	if bpy.context.screen:
		for area in bpy.context.screen.areas:
			if area.type == "VIEW_3D":
				area.spaces.active.shading.type = "MATERIAL"


main()
