import bpy
import bmesh
import math
import os
import numpy
from mathutils import Matrix, Vector

# Run inside Blender 4.1+: Scripting tab -> Open -> Run Script.
# Builds a pack of stylized low poly swords for one world, from a common sword up to a Robux exclusive.
# Every sword gets its own hand-painted curvature texture (edge highlights, cavity shadows, wear,
# painted decals) baked into one image, auto smooth shading and an FBX export for Roblox.
# Glowing parts are split into their own mesh named <Sword><Material>, meant to become Neon in Roblox.
# The black inverted hull outline is a separate object named <Sword>Outline, parented to the sword.

WORLD = "Starter"  # which pack to build, see WORLDS: "Starter" or "Desert"

TEXTURE_SIZE = 1024
BAKE_SAMPLES = 64
UV_MARGIN = 0.008
PACK_SPACING = 2.8

SMOOTH_ANGLE = 22  # auto smooth angle, every edge sharper than this stays hard
CRYSTAL_SMOOTH_ANGLE = 1

#// Curvature Look

EDGE_BEVEL_RADIUS = 0.035
EDGE_START = 0.996  # dot(normal, bevelNormal) where the highlight starts
EDGE_FULL = 0.94  # dot(normal, bevelNormal) where the highlight is at full strength
EDGE_WEAR_SCALE = 7
CAVITY_DISTANCE = 0.22
COLOR_VARIATION = 0.07
BEVEL_BRIGHTNESS = 0.45  # how much lighter the blade chamfer is than its flat center
LENGTH_GRADIENT = 0.25  # darkens the sword towards the pommel

DECAL_WIDTH = 0.02
DECAL_RESOLUTION = 300  # pixels per unit

#// Shapes

OUTLINE_SMOOTHNESS = 3
OUTLINE_TOLERANCE = 0.006  # points closer than this to a straight line are removed
PROFILE_SAMPLES_PER_UNIT = 5
BLADE_EDGE_THICKNESS = 0.02
BLADE_CENTER_THICKNESS = 0.1
GRIP_THICKNESS = 1.4  # scales every grip, pommel and grip collar
GUARD_THICKNESS = 1.45  # scales every swept guard arm, horn and curl

#// Outline

OUTLINE_THICKNESS = 0.022  # inverted hull made by a Solidify modifier with flipped normals
OUTLINE_COLOR = "0B0710"

# Leave empty to skip. Otherwise every sword is exported as FBX + PNG into this folder.
EXPORT_FOLDER = os.path.join(os.path.dirname(bpy.data.filepath), "Export") if bpy.data.filepath else ""

# Base, shadow and highlight color of every material.
PALETTE = {
	"Wood": ("B57A45", "5E3517", "E9B97E"),
	"WoodDark": ("7A4A26", "3A1F0E", "B07A4A"),
	"Cloth": ("D9C49C", "7A6346", "F5EBD3"),
	"Iron": ("7B828E", "30343D", "C9D0DA"),
	"Rust": ("A0613C", "4A2214", "D9A27A"),
	"Steel": ("8A9CB0", "2C3850", "EEF5FF"),
	"DarkSteel": ("5C6577", "1E2330", "AEB9CC"),
	"Leather": ("70432A", "2A150E", "B07A52"),
	"Gold": ("E9A73B", "7A3A14", "FFE7A1"),
	"Ruby": ("E8384F", "5E0E2A", "FFC2CC"),
	"BlueCloth": ("3157B5", "142659", "8FB0F2"),
	"Sapphire": ("2F7BFF", "0E2A7A", "B8DCFF"),
	"RedCloth": ("B52A3A", "4F0C17", "F07A84"),
	"Crystal": ("5FE0F0", "1C5F9C", "E8FFFF"),
	"Silver": ("C3CCD9", "5A6478", "FFFFFF"),
	"NavyLeather": ("2B3D6B", "0F1631", "6F86C0"),
	"Fire": ("FF7A1F", "9C1D0C", "FFE36B"),
	"DarkIron": ("4A4552", "18151E", "9A90A8"),
	"DarkLeather": ("4A2E22", "1A0E09", "8A604A"),
	"FireGem": ("FFB02E", "B33A0A", "FFF3B0"),
	"Flame": ("FFC23A", "D9480F", "FFF6C2"),
	"Ice": ("9FE4FF", "2B6CB0", "F4FFFF"),
	"FrostMetal": ("BCCBE6", "4F5E85", "FFFFFF"),
	"FrostCloth": ("DCEBF7", "7891B3", "FFFFFF"),
	"DemonBlade": ("3B2547", "120818", "A777D6"),
	"DemonGlow": ("FF3FD0", "9E0F7A", "FFC2F2"),
	"DemonMetal": ("2E2537", "0E0A14", "8C74A8"),
	"DemonEye": ("FF3B30", "7A0A0A", "FFD27A"),
	"DemonLeather": ("4A1F3D", "1A0815", "8A4C78"),
	"Celestial": ("F3EEDF", "A8956D", "FFFFFF"),
	"Feather": ("F4F6FC", "98A6C9", "FFFFFF"),
	"StarGlow": ("FFE98A", "D99A1F", "FFFFFF"),
	"HaloGlow": ("FFE27A", "E0A21E", "FFFFFF"),
	"WhiteCloth": ("EDEBE4", "9C978A", "FFFFFF"),
	"Void": ("2A1452", "0B0421", "8E62FF"),
	"VoidGlow": ("FF4FD8", "A8128C", "FFD1F5"),
	"VoidCyan": ("4FF3FF", "0E7A9E", "E6FFFF"),
	"VoidMetal": ("1F1830", "08050F", "6E5AA6"),
	"VoidLeather": ("221A2E", "09060F", "5E4A7A"),
	"CactusGreen": ("5DA34A", "1F4A2A", "B6E37A"),
	"CactusSpine": ("F2E6C2", "8A7650", "FFFFFF"),
	"Flower": ("FF6F9C", "8A1F4A", "FFC2D6"),
	"DesertWood": ("A8723F", "4A2A12", "E3B06E"),
	"Rope": ("D9BC7E", "7A5A2E", "F7E6B8"),
	"Bone": ("EFE3C4", "8C7A56", "FFFFFF"),
	"Tooth": ("FFF8E8", "A89878", "FFFFFF"),
	"BronzeEdge": ("F7C784", "8A5A22", "FFF0D0"),
	"Fang": ("F4EAD2", "8C7A56", "FFFFFF"),
	"Hood": ("2E8A62", "0E3A2A", "7FD8A8"),
	"BoneDark": ("C9B48A", "6A5634", "F2E6C6"),
	"Socket": ("3A2A24", "140C0A", "6A5048"),
	"Sandstone": ("E3A462", "7A4120", "FFD9A0"),
	"SandstoneDark": ("B9733E", "5A2E14", "E8B07A"),
	"Bronze": ("C9873A", "5A2E10", "F7C784"),
	"Turquoise": ("2FC9B8", "0E5E66", "A8FFF2"),
	"Chitin": ("8A2E2E", "2E0C12", "D8735E"),
	"ChitinDark": ("4E1A22", "1A060C", "A0505A"),
	"Venom": ("9CFF3A", "3A8A0E", "EFFFB0"),
	"Serpent": ("3FAE7A", "0E4A3A", "A6F0C0"),
	"SnakeEye": ("FFD23A", "8A5A0E", "FFF4B0"),
	"Bandage": ("E8DCC0", "8C7A5A", "FFFFFF"),
	"Cursed": ("3E6B5E", "12261F", "8ACBA8"),
	"CurseGlow": ("7CFF5A", "2A8A1E", "E0FFD0"),
	"PharaohGold": ("F2B635", "7A3A14", "FFE7A1"),
	"Lapis": ("2A4BC9", "0E1A5C", "8AA8FF"),
	"Sand": ("E8C27A", "8A5A2A", "FFF0C8"),
	"SandGlow": ("FFB347", "B8580E", "FFF0C0"),
	"Scarab": ("2FB8A0", "0E3A5A", "B8FFE0"),
	"ScarabWing": ("E0A030", "7A4A0E", "FFE0A0"),
	"SunBlade": ("FFD86A", "B8641A", "FFF6D0"),
	"SunGlow": ("FF9A2E", "B8400E", "FFE8A0"),
	"SunFeather": ("F7D9A0", "A8743A", "FFFFFF"),
	"Djinn": ("5A3AE0", "1A0E5A", "B8A8FF"),
	"DjinnGlow": ("4FE3FF", "0E7A9E", "E0FFFF"),
	"DjinnSmoke": ("C9A8FF", "6A3AC0", "F4ECFF"),
	"DjinnLeather": ("3A2A6E", "120A2E", "7A6AB0"),
}

# Materials split into their own mesh so they can be set to Neon in Roblox.
GLOW_MATERIALS = {
	"FireGem", "Flame", "DemonGlow", "DemonEye", "StarGlow", "HaloGlow", "VoidGlow", "VoidCyan",
	"Venom", "CurseGlow", "SandGlow", "SunGlow", "DjinnGlow", "DjinnSmoke",
}


#// Math Helpers

def to_color(hex_color):
	channels = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
	return tuple(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels) + (1,)


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


def simplify(outline):
	removed = True
	while removed and len(outline) > 3:
		removed = False
		for i in range(len(outline)):
			previous, current, following = outline[i - 1], outline[i], outline[(i + 1) % len(outline)]
			edge = following - previous
			if edge.length < 1e-6:
				continue

			distance = abs(edge.x * (current.y - previous.y) - edge.y * (current.x - previous.x)) / edge.length
			if distance < OUTLINE_TOLERANCE:
				outline.pop(i)
				removed = True
				break
	return outline


def build_outline(curves):
	outline = []
	for curve in curves:
		outline += catmull_rom(curve, OUTLINE_SMOOTHNESS)
	return simplify(outline)


def mirror(points):
	return [(-x, z) for x, z in points]


def point_at_distance(outline, lengths, distance):
	for i in range(len(outline)):
		if lengths[i + 1] >= distance:
			t = (distance - lengths[i]) / max(lengths[i + 1] - lengths[i], 1e-6)
			start = outline[i]
			end = outline[(i + 1) % len(outline)]
			return start.lerp(end, t), (end - start).normalized()
	return outline[0], (outline[1] - outline[0]).normalized()


def cut_notch(outline, position, width, depth, skew):
	# Positive depth chips into the outline, negative depth grows a tooth out of it.
	lengths = [0]
	for i, point in enumerate(outline):
		lengths.append(lengths[-1] + (outline[(i + 1) % len(outline)] - point).length)

	position = Vector(position)
	best_distance = math.inf
	center = 0
	for i, start in enumerate(outline):
		edge = outline[(i + 1) % len(outline)] - start
		t = max(0, min(1, (position - start).dot(edge) / edge.length_squared))
		distance = (start + edge * t - position).length
		if distance < best_distance:
			best_distance = distance
			center = lengths[i] + t * edge.length

	before, _ = point_at_distance(outline, lengths, center - width / 2)
	bottom, tangent = point_at_distance(outline, lengths, center + skew * width / 2)
	after, _ = point_at_distance(outline, lengths, center + width / 2)
	bottom = bottom + Vector((-tangent.y, tangent.x)) * depth

	kept = [i for i in range(len(outline)) if abs(lengths[i] - center) > width / 2]
	insert_at = next((index for index, i in enumerate(kept) if lengths[i] > center), len(kept))
	points = [outline[i] for i in kept]
	return points[:insert_at] + [before, bottom, after] + points[insert_at:]


def oriented(location, direction, scale=(1, 1, 1)):
	rotation = Vector((0, 0, 1)).rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()
	return Matrix.Translation(Vector(location)) @ rotation @ Matrix.Diagonal(Vector(scale)).to_4x4()


#// Profile Shapes

def profile_shape(spine, stations, tip="point", chamfer=0.08, plateau_ratio=0.3, features=()):
	# spine: centerline control points (x, z). stations: (t, halfWidth) or (t, leftWidth, rightWidth) along it.
	# tip: "point", "round", "flat" or a list of (side, offset) points going from the right corner to the left one.
	# features: (t, side, width, depth, skew) notches (depth > 0) or teeth (depth < 0), side 1 is right, -1 is left.
	path = catmull_rom(spine, 8) + [Vector(spine[-1])]
	lengths = [0]
	for start, end in zip(path, path[1:]):
		lengths.append(lengths[-1] + (end - start).length)
	total = lengths[-1]

	stations = [(station[0], station[1], station[1]) if len(station) == 2 else station for station in stations]

	def frame(t):
		distance = t * total
		for i in range(len(path) - 1):
			if lengths[i + 1] >= distance or i == len(path) - 2:
				local = (distance - lengths[i]) / max(lengths[i + 1] - lengths[i], 1e-6)
				tangent = (path[i + 1] - path[i]).normalized()
				return path[i].lerp(path[i + 1], local), tangent, Vector((-tangent.y, tangent.x))

	def widths(t):
		for start, end in zip(stations, stations[1:]):
			if start[0] <= t <= end[0]:
				local = (t - start[0]) / max(end[0] - start[0], 1e-6)
				return start[1] + (end[1] - start[1]) * local, start[2] + (end[2] - start[2]) * local
		return stations[-1][1], stations[-1][2]

	count = max(2, math.ceil(total * PROFILE_SAMPLES_PER_UNIT))
	samples = sorted({round(i / count, 4) for i in range(count + 1)} | {station[0] for station in stations})

	def edges(t_values, inset=0):
		right, left = [], []
		for t in t_values:
			center, _, normal = frame(t)
			left_width, right_width = widths(t)
			if inset:
				left_width = max(left_width - inset, left_width * plateau_ratio)
				right_width = max(right_width - inset, right_width * plateau_ratio)
			right.append(center - normal * right_width)
			left.append(center + normal * left_width)
		return right, left

	def tip_points(t, inset=0):
		center, tangent, normal = frame(t)
		left_width, right_width = widths(t)
		radius = (left_width + right_width) / 2
		if tip == "point":
			return [center]
		if tip == "round":
			radius = max(radius - inset, radius * plateau_ratio)
			return [center + (-normal * math.cos(angle) + tangent * math.sin(angle)) * radius for angle in (math.pi * i / 6 for i in range(1, 6))]
		if tip == "flat":
			return []
		return [center + tangent * (offset - inset) - normal * side * radius * (1 if not inset else plateau_ratio) for side, offset in tip]

	end_t = 1 if tip == "point" else 1.0001
	right, left = edges([t for t in samples if t < end_t])
	outline = simplify(right + tip_points(1) + left[::-1])

	if tip == "point":
		plateau_end = 1 - chamfer * 2.2 / total
	elif tip == "round":
		plateau_end = 1
	else:
		plateau_end = 1 - chamfer / total
	plateau_start = chamfer * 0.3 / total
	plateau_samples = [plateau_start] + [t for t in samples if plateau_start < t < plateau_end] + [plateau_end]
	if tip == "point":
		right, left = edges(plateau_samples[:-1], chamfer)
		plateau = right + [frame(plateau_end)[0]] + left[::-1]
	else:
		right, left = edges(plateau_samples, chamfer)
		plateau = right + (tip_points(plateau_end, chamfer) if tip == "round" else []) + left[::-1]
	plateau = simplify(plateau)

	for t, side, width, depth, skew in features:
		center, _, normal = frame(t)
		left_width, right_width = widths(t)
		position = center - normal * right_width if side > 0 else center + normal * left_width
		outline = cut_notch(outline, position, width, depth, skew * side)

	return outline, plateau


def star_shape(points, outer_radius, inner_radius):
	outline = []
	for i in range(points * 2):
		angle = math.pi / 2 + math.pi * i / points
		radius = outer_radius if i % 2 == 0 else inner_radius
		outline.append(Vector((math.cos(angle) * radius, math.sin(angle) * radius)))
	return outline


#// Mesh Helpers

def new_part(name, bm, material, smooth_angle):
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
	for face in bm.faces:
		face.smooth = True
	for edge in bm.edges:
		if len(edge.link_faces) == 2 and edge.calc_face_angle(0) > math.radians(smooth_angle):
			edge.smooth = False

	mesh = bpy.data.meshes.new(name)
	bm.to_mesh(mesh)
	bm.free()
	mesh.materials.append(material)

	part = bpy.data.objects.new(name, mesh)
	bpy.context.scene.collection.objects.link(part)
	return part


def bridge_loops(bm, outer, inner):
	start = min(range(len(inner)), key=lambda j: (inner[j].co - outer[0].co).xz.length)
	inner = inner[start:] + inner[:start]
	i = j = 0
	while i < len(outer) or j < len(inner):
		current_outer = outer[i % len(outer)]
		current_inner = inner[j % len(inner)]
		next_outer = outer[(i + 1) % len(outer)]
		next_inner = inner[(j + 1) % len(inner)]

		advance_outer = j >= len(inner) or (
			i < len(outer)
			and (next_outer.co - current_inner.co).xz.length < (next_inner.co - current_outer.co).xz.length
		)
		if advance_outer:
			bm.faces.new((current_outer, next_outer, current_inner))
			i += 1
		else:
			bm.faces.new((current_outer, next_inner, current_inner))
			j += 1


def add_plate(bm, outline, plateau=None, edge_thickness=BLADE_EDGE_THICKNESS, center_thickness=BLADE_CENTER_THICKNESS, matrix=Matrix()):
	# Flat shape in the XZ plane. With a plateau the center is raised and the rim becomes a chamfer.
	new_verts = []
	sides = {}
	for side in (-1, 1):
		outer = [bm.verts.new((point.x, side * edge_thickness, point.y)) for point in outline]
		new_verts += outer
		sides[side] = outer
		if plateau:
			inner = [bm.verts.new((point.x, side * center_thickness, point.y)) for point in plateau]
			new_verts += inner
			bridge_loops(bm, outer, inner)
			bm.faces.new(inner)
		else:
			bm.faces.new(outer)

	front, back = sides[-1], sides[1]
	for i in range(len(outline)):
		bm.faces.new((front[i - 1], front[i], back[i], back[i - 1]))

	bm.normal_update()
	ngons = list({face for vert in new_verts for face in vert.link_faces if len(face.verts) > 4})
	bmesh.ops.triangulate(bm, faces=ngons, ngon_method="BEAUTY")
	bmesh.ops.transform(bm, matrix=matrix, verts=new_verts)


def add_lathe(bm, profile, sides, matrix=Matrix()):
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


def add_torus(bm, radius, thickness, segments, sides, matrix=Matrix()):
	# Ring in the XZ plane, use the matrix to turn it.
	rings = []
	for i in range(segments):
		angle = math.tau * i / segments
		direction = Vector((math.cos(angle), 0, math.sin(angle)))
		ring = []
		for j in range(sides):
			side_angle = math.tau * j / sides
			offset = direction * math.cos(side_angle) + Vector((0, 1, 0)) * math.sin(side_angle)
			ring.append(bm.verts.new(matrix @ (direction * radius + offset * thickness)))
		rings.append(ring)

	for i in range(segments):
		for j in range(sides):
			bm.faces.new((rings[i - 1][j - 1], rings[i][j - 1], rings[i][j], rings[i - 1][j]))


def add_sweep(bm, points, radii, sides=6, flatten=1.0, smoothness=4, matrix=Matrix()):
	# Tube along a path given as (x, z) points. A radius of 0 ends the tube in a point.
	points = [Vector((point[0], 0, point[1])) if len(point) == 2 else Vector(point) for point in points]
	radii = [radius * GUARD_THICKNESS for radius in radii]
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
			rings.append([bm.verts.new(matrix @ center)])
			continue

		binormal = Vector((0, 1, 0)) - tangent * tangent.y
		binormal = binormal.normalized() if binormal.length > 1e-4 else Vector((1, 0, 0))
		normal = tangent.cross(binormal).normalized()
		ring = []
		for i in range(sides):
			angle = math.tau * i / sides + math.pi / sides
			offset = normal * math.cos(angle) * radius + binormal * math.sin(angle) * radius * flatten
			ring.append(bm.verts.new(matrix @ (center + offset)))
		rings.append(ring)

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


def add_box(bm, size, location, bevel):
	result = bmesh.ops.create_cube(bm, size=1, matrix=Matrix.LocRotScale(Vector(location), None, Vector(size)))
	edges = list({edge for vert in result["verts"] for edge in vert.link_edges})
	bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=1, affect="EDGES", profile=0.5)


def add_ball(bm, location, radius, scale=(1, 1, 1)):
	bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius, matrix=Matrix.LocRotScale(Vector(location), None, Vector(scale)))


def add_spike(bm, base, direction, length, radius, sides=6):
	add_lathe(bm, [(radius, 0), (radius * 0.85, length * 0.2), (0, length)], sides, oriented(base, direction))


def add_crystal(bm, base, direction, length, radius, sides=5):
	add_lathe(bm, [(0, -radius * 0.6), (radius, 0), (radius * 0.85, length * 0.7), (0, length)], sides, oriented(base, direction))


def add_gem(bm, center, radius, height, flatten=0.6):
	# Upright lens shaped gem.
	profile = [(0, -height), (radius * 0.8, -height * 0.4), (radius, 0), (radius * 0.8, height * 0.4), (0, height)]
	add_lathe(bm, profile, 6, Matrix.LocRotScale(Vector(center), None, Vector((1, flatten, 1))))


def add_cabochon(bm, center, radius, depth, sides=8, direction=(0, 1, 0)):
	# Round gem going through the guard so it shows on both sides.
	profile = [(0, -depth), (radius * 0.7, -depth * 0.8), (radius, -depth * 0.35), (radius, depth * 0.35), (radius * 0.7, depth * 0.8), (0, depth)]
	add_lathe(bm, profile, sides, oriented(center, direction))


def add_pommel(bm, profile, sides=8):
	add_lathe(bm, [(radius * GRIP_THICKNESS, height) for radius, height in profile], sides)


def add_grip(bm, top, length, radius, wrap_radius, wraps, sides=8):
	radius *= GRIP_THICKNESS
	wrap_radius *= GRIP_THICKNESS
	wrap_length = length / wraps
	height = top
	profile = []
	for _ in range(wraps):
		profile += [
			(radius, height),
			(wrap_radius, height - wrap_length * 0.15),
			(wrap_radius, height - wrap_length * 0.75),
			(radius, height - wrap_length * 0.9),
		]
		height -= wrap_length
	profile.append((radius, height))
	add_lathe(bm, profile, sides)
	return height


#// 01 Wooden Sword (Common)

def build_wooden_sword(part):
	blade_base = 0.1
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 2.0)],
		[(0, 0.2), (0.06, 0.25), (1, 0.25)],
		tip="round",
		chamfer=0.07,
		features=[(0.45, 1, 0.08, 0.05, 0), (0.72, -1, 0.1, 0.06, 0.3)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.045, 0.085)
	part(bm, "Wood")

	bm = bmesh.new()
	add_box(bm, (0.9, 0.22, 0.16), (0, 0, 0.06), 0.035)
	bottom = -0.02 - 0.7
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.09), (0.06, bottom - 0.13), (0, bottom - 0.14)])
	part(bm, "WoodDark")

	bm = bmesh.new()
	for side in (-1, 1):
		for y in (-0.11, 0.11):
			add_ball(bm, (side * 0.33, y, 0.06), 0.03, (1, 0.5, 1))
	part(bm, "Iron")

	bm = bmesh.new()
	add_grip(bm, -0.02, 0.7, 0.068, 0.08, 6)
	part(bm, "Cloth")

	knot = [(math.cos(a) * 0.045, 1.2 + math.sin(a) * 0.07) for a in (math.tau * i / 8 for i in range(9))]
	return {
		"blade": "Wood",
		"decals": [
			[(-0.1, 0.35), (-0.08, 0.9), (-0.12, 1.5), (-0.09, 2.1)],
			[(0.06, 0.25), (0.08, 0.8), (0.05, 1.05), (0.1, 1.2), (0.07, 1.9), (0.05, 2.25)],
			[(0.15, 0.9), (0.14, 1.45)],
			[(-0.02, 1.6), (-0.03, 2.2)],
			knot,
		],
		"decal_width": 0.009,
	}


#// 02 Rusty Sword (Common)

def build_rusty_sword(part):
	blade_base = 0.1
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 2.0)],
		[(0, 0.17), (0.06, 0.2), (1, 0.19)],
		tip=[(0.7, 0.06), (0.35, -0.08), (0.05, 0.02), (-0.3, -0.14), (-0.6, -0.05)],
		chamfer=0.07,
		features=[
			(0.16, 1, 0.08, 0.05, 0.2),
			(0.3, -1, 0.12, 0.07, -0.3),
			(0.48, 1, 0.1, 0.06, 0),
			(0.62, -1, 0.07, 0.05, 0.4),
			(0.78, 1, 0.09, 0.05, -0.2),
			(0.86, -1, 0.06, 0.04, 0),
		],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.018, 0.075)
	part(bm, "Rust")

	bm = bmesh.new()
	add_sweep(bm, [(-0.46, -0.02), (-0.25, 0.05), (0, 0.07), (0.25, 0.06), (0.44, 0.1)], [0.055, 0.06, 0.07, 0.06, 0.05], sides=4)
	bottom = -0.74
	add_pommel(bm, [(0.05, bottom + 0.01), (0.11, bottom - 0.02), (0.11, bottom - 0.09), (0.05, bottom - 0.12)])
	part(bm, "Iron")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.7, 0.062, 0.074, 6)
	part(bm, "Leather")

	return {
		"blade": "Rust",
		"decals": [
			[(0.1, 1.95), (0.04, 1.88), (0.09, 1.82), (0.02, 1.74)],
			[(-0.1, 1.5), (-0.04, 1.45), (-0.08, 1.38)],
			[(0.1, 1.05), (0.03, 1.0), (0.06, 0.92)],
			[(-0.09, 0.62), (-0.02, 0.58), (-0.06, 0.5), (0.0, 0.44)],
		],
	}


#// 03 Iron Sword (Uncommon)

def build_iron_sword(part):
	blade_base = 0.12
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 2.5)],
		[(0, 0.16), (0.08, 0.18), (0.45, 0.2), (0.72, 0.26), (0.88, 0.17), (1, 0)],
		chamfer=0.08,
		features=[(0.35, 1, 0.07, 0.04, 0), (0.55, -1, 0.09, 0.05, 0.3)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Steel")

	bm = bmesh.new()
	add_sweep(bm, [(-0.58, 0.16), (-0.3, 0.07), (0, 0.05), (0.3, 0.07), (0.58, 0.16)], [0.045, 0.06, 0.08, 0.06, 0.045])
	for side in (-1, 1):
		add_ball(bm, (side * 0.62, 0, 0.18), 0.095)
	add_box(bm, (0.3, 0.22, 0.2), (0, 0, 0.07), 0.03)
	bottom = -0.04 - 0.75
	add_pommel(bm, [(0.05, bottom + 0.01), (0.09, bottom - 0.02), (0.1, bottom - 0.07), (0.08, bottom - 0.12), (0, bottom - 0.15)])
	part(bm, "DarkSteel")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.75, 0.064, 0.077, 7)
	part(bm, "Leather")

	return {
		"blade": "Steel",
		"decals": [
			[(0, 0.4), (0, 1.75)],
			[(0.12, 2.0), (0.06, 1.95), (0.1, 1.88)],
			[(-0.1, 1.2), (-0.05, 1.15), (-0.08, 1.08)],
		],
	}


#// 04 Knight Sword (Uncommon)

def build_knight_sword(part):
	blade_base = 0.2
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 3.0)],
		[(0, 0.19), (0.06, 0.22), (0.55, 0.2), (0.8, 0.16), (1, 0)],
		chamfer=0.09,
		features=[(0.42, -1, 0.07, 0.04, 0)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Steel")

	bm = bmesh.new()
	add_sweep(
		bm,
		[(-0.78, -0.06), (-0.5, 0.06), (-0.2, 0.12), (0, 0.13), (0.2, 0.12), (0.5, 0.06), (0.78, -0.06)],
		[0.04, 0.055, 0.07, 0.08, 0.07, 0.055, 0.04],
	)
	for side in (-1, 1):
		add_ball(bm, (side * 0.82, 0, -0.08), 0.09)
	add_box(bm, (0.34, 0.2, 0.34), (0, 0, 0.14), 0.04)
	bottom = -0.03 - 0.8
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.02), (0.12, bottom - 0.08), (0.1, bottom - 0.14), (0.05, bottom - 0.17), (0, bottom - 0.18)])
	part(bm, "Gold")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.14), 0.09, 0.14)
	add_cabochon(bm, (0, 0, bottom - 0.08), 0.05, 0.2)
	part(bm, "Sapphire")

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.8, 0.065, 0.078, 7)
	part(bm, "BlueCloth")

	return {
		"blade": "Steel",
		"decals": [
			[(0, 0.5), (0, 2.3)],
			[(0.1, 2.6), (0.05, 2.55), (0.08, 2.48)],
		],
		"decal_width": 0.03,
	}


#// 05 Scimitar (Rare)

def build_scimitar(part):
	outline, plateau = profile_shape(
		[(0, 0.14), (0.0, 0.9), (0.1, 1.8), (0.32, 2.45), (0.62, 2.85)],
		[(0, 0.15, 0.15), (0.08, 0.17, 0.15), (0.6, 0.28, 0.13), (0.85, 0.3, 0.11), (1, 0, 0)],
		chamfer=0.08,
		features=[(0.5, -1, 0.08, 0.05, 0.2)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.018, 0.085)
	part(bm, "Steel")

	bm = bmesh.new()
	arm = [(-0.08, 0.06), (-0.3, 0.08), (-0.48, 0.0), (-0.46, -0.13), (-0.34, -0.13), (-0.32, -0.05)]
	radii = [0.07, 0.055, 0.045, 0.04, 0.035, 0.0]
	add_sweep(bm, arm, radii)
	add_sweep(bm, mirror(arm), radii)
	add_box(bm, (0.26, 0.22, 0.18), (0, 0, 0.06), 0.035)
	bottom = -0.03 - 0.75
	add_sweep(bm, [(0, bottom + 0.02), (0.01, bottom - 0.08), (0.08, bottom - 0.17), (0.2, bottom - 0.19)], [0.08, 0.08, 0.06, 0.0])
	part(bm, "Gold")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.06), 0.07, 0.13)
	part(bm, "Ruby")

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.75, 0.062, 0.075, 6)
	part(bm, "RedCloth")

	return {"blade": "Steel"}


#// 06 Cleaver Sword (Rare)

CLEAVER_OUTLINE = [
	[(0.30, 0.90), (0.40, 1.04), (0.40, 2.20), (0.41, 3.12), (0.47, 3.42), (0.64, 3.62)],
	[(0.64, 3.62), (0.50, 3.80), (0.18, 3.92), (-0.18, 3.93), (-0.46, 3.84), (-0.66, 3.68)],
	[(-0.66, 3.68), (-0.48, 3.50), (-0.42, 3.20), (-0.40, 2.20), (-0.40, 1.04), (-0.30, 0.90)],
	[(-0.30, 0.90), (0.30, 0.90)],
]

CLEAVER_PLATEAU = [
	[(0.20, 0.97), (0.28, 1.10), (0.28, 2.20), (0.29, 3.12), (0.34, 3.40), (0.44, 3.57)],
	[(0.44, 3.57), (0.36, 3.70), (0.15, 3.78), (-0.15, 3.79), (-0.36, 3.73), (-0.46, 3.62)],
	[(-0.46, 3.62), (-0.34, 3.47), (-0.30, 3.20), (-0.28, 2.20), (-0.28, 1.10), (-0.20, 0.97)],
	[(-0.20, 0.97), (0.20, 0.97)],
]

CLEAVER_NOTCHES = [
	((0.40, 2.75), 0.11, 0.09, 0.25),
	((0.40, 1.38), 0.07, 0.05, -0.2),
	((-0.40, 1.55), 0.15, 0.11, 0.3),
	((-0.40, 2.40), 0.06, 0.05, 0),
	((-0.44, 3.32), 0.07, 0.05, -0.3),
	((0.30, 3.89), 0.08, 0.06, 0.2),
	((0.55, 3.53), 0.06, 0.04, 0),
]


def build_cleaver_sword(part):
	ring_center = 0.48
	ring_radius = 0.26
	spike_angle = math.radians(22)

	outline = build_outline(CLEAVER_OUTLINE)
	for position, width, depth, skew in CLEAVER_NOTCHES:
		outline = cut_notch(outline, position, width, depth, skew)
	bm = bmesh.new()
	add_plate(bm, outline, build_outline(CLEAVER_PLATEAU), 0.02, 0.11)
	part(bm, "Steel")

	bm = bmesh.new()
	add_box(bm, (0.70, 0.24, 0.13), (0, 0, 0.87), 0.03)
	add_box(bm, (0.50, 0.21, 0.08), (0, 0, 0.77), 0.025)
	add_torus(bm, ring_radius, 0.06, 18, 8, Matrix.Translation((0, 0, ring_center)))
	add_box(bm, (0.15, 0.18, 0.12), (0, 0, ring_center - ring_radius - 0.02), 0.02)
	spike_roots = []
	for side in (-1, 1):
		root = Vector((side * math.cos(spike_angle) * ring_radius, 0, ring_center + math.sin(spike_angle) * ring_radius))
		add_ball(bm, root, 0.075)
		spike_roots.append((root, Vector((side * math.cos(spike_angle * 1.6), 0, math.sin(spike_angle * 1.6)))))

	grip_top = 0.11
	add_pommel(bm, [(0.06, grip_top - 0.03), (0.095, grip_top - 0.01), (0.095, grip_top + 0.04), (0.05, grip_top + 0.07)])
	bottom = grip_top - 0.7
	add_pommel(bm, [
		(0.05, bottom + 0.02),
		(0.095, bottom - 0.01),
		(0.095, bottom - 0.05),
		(0.05, bottom - 0.08),
		(0.068, bottom - 0.12),
		(0.05, bottom - 0.17),
		(0, bottom - 0.19),
	])
	add_torus(bm, 0.055, 0.018, 10, 6, Matrix.Translation((0, 0, bottom - 0.24)))
	part(bm, "Gold")

	bm = bmesh.new()
	for root, direction in spike_roots:
		add_spike(bm, root + direction * 0.04, direction, 0.3, 0.055)
	part(bm, "Steel")

	bm = bmesh.new()
	add_gem(bm, (0, 0, ring_center), 0.085, 0.17)
	part(bm, "Ruby", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, grip_top, 0.7, 0.064, 0.078, 7)
	part(bm, "Leather")

	return {
		"blade": "Steel",
		"decals": [
			[(0.24, 3.16), (0.16, 3.09), (0.22, 3.03), (0.12, 2.95)],
			[(-0.26, 3.44), (-0.17, 3.37), (-0.23, 3.31), (-0.15, 3.25)],
			[(0.25, 2.76), (0.15, 2.72), (0.19, 2.64)],
			[(-0.25, 1.66), (-0.15, 1.60), (-0.21, 1.53), (-0.11, 1.46)],
			[(0.25, 1.42), (0.16, 1.38), (0.19, 1.30)],
			[(-0.08, 3.74), (-0.03, 3.66), (-0.09, 3.60)],
			[(-0.25, 2.44), (-0.16, 2.38), (-0.19, 2.32)],
		],
	}


#// 07 Crystal Sword (Epic)

def build_crystal_sword(part):
	blade_base = 0.22
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 2.9)],
		[(0, 0.17), (0.12, 0.27), (0.35, 0.22), (0.62, 0.27), (0.84, 0.2), (1, 0)],
		chamfer=0.2,
		plateau_ratio=0.08,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.015, 0.12)
	add_crystal(bm, (-0.2, 0, blade_base + 0.3), (-0.5, 0, 1), 0.5, 0.07)
	add_crystal(bm, (0.22, 0, blade_base + 0.5), (0.45, 0, 1), 0.42, 0.06)
	add_crystal(bm, (-0.18, 0, blade_base + 1.05), (-0.4, 0, 1), 0.3, 0.05)
	add_crystal(bm, (0.2, 0, blade_base + 1.75), (0.35, 0, 1), 0.28, 0.05)
	part(bm, "Crystal", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	arm = [(-0.1, 0.12), (-0.38, 0.1), (-0.58, 0.24), (-0.64, 0.46)]
	radii = [0.08, 0.065, 0.05, 0.03]
	add_sweep(bm, arm, radii)
	add_sweep(bm, mirror(arm), radii)
	add_box(bm, (0.32, 0.22, 0.24), (0, 0, 0.12), 0.04)
	bottom = -0.8
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.09), (0.05, bottom - 0.12)])
	part(bm, "Silver")

	bm = bmesh.new()
	for side in (-1, 1):
		add_crystal(bm, (side * 0.64, 0, 0.44), (side * 0.3, 0, 1), 0.36, 0.065)
	add_cabochon(bm, (0, 0, 0.12), 0.1, 0.16, sides=6)
	add_crystal(bm, (0, 0, bottom - 0.1), (0, 0, -1), 0.26, 0.06)
	part(bm, "Crystal", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, 0, 0.8, 0.064, 0.077, 7)
	part(bm, "NavyLeather")

	return {
		"blade": "Crystal",
		"outline": outline,
		"edge_glow": ("E6FFFF", 0.12),
		"effects": {
			"Crystal": {
				"gradient": (blade_base, blade_base + 2.9, [(0, "2C78D4"), (0.45, "4FD0F0"), (1, "E6FFFF")]),
				"patterns": [("cells", "E8FFFF", 2.2, 0.6), ("stars", "FFFFFF", 8, 1)],
			},
			"Silver": {"gradient": (-0.1, 0.6, [(0, "8E9AB5"), (1, "E6F4FF")])},
			"NavyLeather": {"gradient": (-0.8, 0, [(0, "1B2550"), (1, "34508F")])},
		},
	}


#// 08 Flame Sword (Epic)

def build_flame_sword(part):
	blade_base = 0.22
	waves = [(t / 40, 0.23 + 0.045 * math.sin(t / 40 * 5 * math.tau)) for t in range(2, 35)]
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 3.0)],
		[(0, 0.2)] + waves + [(1, 0)],
		chamfer=0.08,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Fire")

	bm = bmesh.new()
	horn = [(-0.08, 0.1), (-0.36, 0.05), (-0.58, 0.16), (-0.66, 0.42), (-0.6, 0.62)]
	radii = [0.09, 0.075, 0.055, 0.03, 0.0]
	add_sweep(bm, horn, radii)
	add_sweep(bm, mirror(horn), radii)
	add_box(bm, (0.32, 0.22, 0.27), (0, 0, 0.1), 0.04)
	bottom = -0.8
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.09), (0.05, bottom - 0.12)])
	part(bm, "DarkIron")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.1), 0.085, 0.15)
	part(bm, "FireGem")

	bm = bmesh.new()
	for side in (-1, 1):
		for spine, width in (
			([(-0.2, 0.15), (-0.34, 0.45), (-0.3, 0.85)], 0.1),
			([(-0.3, 0.12), (-0.48, 0.32), (-0.52, 0.6)], 0.07),
		):
			flame, flame_plateau = profile_shape(
				[(x * -side, z) for x, z in spine],
				[(0, width * 0.3), (0.3, width), (0.55, width * 0.6), (0.7, width * 0.75), (1, 0)],
				chamfer=width * 0.4,
			)
			add_plate(bm, flame, flame_plateau, 0.008, 0.03)
	add_crystal(bm, (0, 0, bottom - 0.1), (0, 0, -1), 0.28, 0.06)
	part(bm, "Flame")

	bm = bmesh.new()
	add_grip(bm, 0, 0.8, 0.064, 0.077, 7)
	part(bm, "DarkLeather")

	return {
		"blade": "Fire",
		"outline": outline,
		"edge_glow": ("FFE36B", 0.1),
		"effects": {
			"Fire": {
				"gradient": (blade_base, blade_base + 3.0, [(0, "7A1208"), (0.3, "D9361A"), (0.65, "FF8A1F"), (1, "FFD84A")]),
				"patterns": [("flames", "FFE36B", 4, 0.6), ("stars", "FFF6C2", 10, 0.9)],
			},
			"DarkIron": {"gradient": (0, 0.65, [(0, "3A3540"), (0.6, "6B3328"), (1, "E0601F")])},
			"Flame": {"gradient": (0.1, 0.9, [(0, "FF6A1F"), (1, "FFF0A0")])},
		},
	}


#// 09 Frost Sword (Legendary)

def build_frost_sword(part):
	blade_base = 0.22
	teeth = [(0.2, 1), (0.28, -1), (0.4, 1), (0.48, -1), (0.6, 1), (0.68, -1), (0.8, 1)]
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 3.1)],
		[(0, 0.2), (0.1, 0.27), (0.7, 0.25), (0.88, 0.19), (1, 0)],
		chamfer=0.12,
		plateau_ratio=0.25,
		features=[(t, side, 0.15, -0.1, 0.7) for t, side in teeth],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Ice")

	bm = bmesh.new()
	for side in (-1, 1):
		for angle, length, radius in ((8, 0.62, 0.08), (32, 0.5, 0.07), (58, 0.36, 0.06)):
			direction = (side * math.cos(math.radians(angle)), 0, math.sin(math.radians(angle)))
			add_crystal(bm, (side * 0.12, 0, 0.12), direction, length, radius)
	bottom = -0.8
	add_crystal(bm, (0, 0, bottom - 0.1), (0, 0, -1), 0.32, 0.07)
	part(bm, "Ice", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_box(bm, (0.36, 0.24, 0.26), (0, 0, 0.12), 0.05)
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.09), (0.05, bottom - 0.12)])
	part(bm, "FrostMetal")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.12), 0.09, 0.17)
	part(bm, "Sapphire")

	bm = bmesh.new()
	add_grip(bm, 0, 0.8, 0.064, 0.077, 7)
	part(bm, "FrostCloth")

	return {
		"blade": "Ice",
		"outline": outline,
		"edge_glow": ("FFFFFF", 0.1),
		"effects": {
			"Ice": {
				"gradient": (blade_base, blade_base + 3.1, [(0, "3A82D6"), (0.4, "7CCBF5"), (1, "F0FFFF")]),
				"patterns": [("cells", "FFFFFF", 3, 0.55), ("nebula", "FFFFFF", 3, 0.35), ("stars", "FFFFFF", 9, 1)],
			},
			"FrostMetal": {"gradient": (-0.9, 0.3, [(0, "6D7FA8"), (1, "DDE8FF")])},
		},
		"decals": [
			[(0.08, 2.9), (0.02, 2.78), (0.07, 2.66), (0.0, 2.55)],
			[(-0.1, 2.2), (-0.03, 2.1), (-0.08, 1.98)],
			[(0.09, 1.5), (0.03, 1.42), (0.06, 1.3), (0.0, 1.22)],
			[(-0.08, 0.85), (-0.02, 0.78), (-0.06, 0.68)],
		],
		"decal_width": 0.015,
	}


#// 10 Demon Sword (Legendary)

def build_demon_sword(part):
	spine = [(0, 0.24), (0, 3.2)]
	stations = [(0, 0.22, 0.22), (0.08, 0.27, 0.27), (0.6, 0.3, 0.25), (0.88, 0.25, 0.32), (1, 0.24, 0.3)]
	tip = [(1.6, 0.3), (0.6, 0.08), (-0.1, 0.6), (-0.6, 0.18), (-1.3, 0.22)]
	outline, plateau = profile_shape(
		spine,
		stations,
		tip=tip,
		chamfer=0.1,
		features=[(t, -1, 0.15, -0.14, 0.6) for t in (0.18, 0.3, 0.42, 0.54, 0.66)] + [(0.3, 1, 0.07, 0.04, 0), (0.6, 1, 0.08, 0.05, 0.3)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "DemonBlade")

	rim, rim_plateau = profile_shape(spine, [(t, left + 0.06, right + 0.06) for t, left, right in stations], tip=tip, chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	part(bm, "DemonGlow")

	bm = bmesh.new()
	wing = [
		(0.1, -0.08), (0.32, -0.06), (0.4, 0.08), (0.5, 0.02), (0.56, 0.2), (0.66, 0.14),
		(0.72, 0.34), (0.8, 0.3), (0.86, 0.56), (0.55, 0.3), (0.3, 0.12), (0.1, 0.02),
	]
	for side in (1, -1):
		add_plate(bm, [Vector((side * x, z)) for x, z in (wing if side > 0 else wing[::-1])], None, 0.035)
	horn = [(0.22, 0.14), (0.42, 0.32), (0.46, 0.55), (0.38, 0.74)]
	radii = [0.07, 0.055, 0.035, 0.0]
	add_sweep(bm, horn, radii)
	add_sweep(bm, mirror(horn), radii)
	add_box(bm, (0.34, 0.24, 0.3), (0, 0, 0.1), 0.05)
	bottom = -0.85
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.08), (0.06, bottom - 0.11)])
	add_spike(bm, (0, 0, bottom - 0.1), (0, 0, -1), 0.3, 0.07)
	part(bm, "DemonMetal")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.1), 0.1, 0.17)
	add_cabochon(bm, (0, 0, bottom - 0.05), 0.045, 0.17)
	part(bm, "DemonEye")

	bm = bmesh.new()
	add_grip(bm, -0.05, 0.8, 0.064, 0.077, 7)
	part(bm, "DemonLeather")

	return {
		"blade": "DemonBlade",
		"outline": outline,
		"edge_glow": ("FF3FD0", 0.055),
		"effects": {
			"DemonBlade": {
				"gradient": (0.24, 3.6, [(0, "12061A"), (0.5, "2E1640"), (1, "5A1E78")]),
				"patterns": [("nebula", "4A1466", 2, 0.5), ("cells", "E02AB8", 2.2, 0.7)],
			},
			"DemonMetal": {"gradient": (-0.1, 0.8, [(0, "241C2E"), (1, "5E2F78")])},
		},
		"decals": [
			[(0.12, 3.05), (0.04, 2.95), (0.1, 2.84), (0.0, 2.72)],
			[(-0.12, 2.35), (-0.04, 2.25), (-0.1, 2.12), (-0.02, 2.02)],
			[(0.1, 1.6), (0.02, 1.5), (0.08, 1.38)],
			[(-0.1, 0.95), (-0.02, 0.86), (-0.07, 0.75)],
		],
		"decal_colors": ("FF3FD0", "FFC2F2"),
	}


#// 11 Celestial Sword (Mythic)

def build_celestial_sword(part):
	blade_base = 0.26
	spine = [(0, blade_base), (0, blade_base + 3.2)]
	stations = [(0, 0.2), (0.08, 0.26), (0.55, 0.22), (0.74, 0.32), (0.82, 0.3), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Celestial")

	trim, trim_plateau = profile_shape(spine, [(t, width + 0.05) for t, width in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, trim, trim_plateau, 0.008, 0.016)
	arm = [(0.1, 0.1), (0.32, 0.12), (0.46, 0.2)]
	radii = [0.09, 0.08, 0.05]
	add_sweep(bm, arm, radii)
	add_sweep(bm, mirror(arm), radii)
	add_box(bm, (0.36, 0.24, 0.3), (0, 0, 0.12), 0.05)
	add_pommel(bm, [(0.06, -0.05), (0.09, -0.03), (0.09, 0.02), (0.06, 0.04)])
	bottom = -0.85
	add_pommel(bm, [(0.06, bottom + 0.04), (0.09, bottom + 0.02), (0.11, bottom - 0.04), (0.08, bottom - 0.1), (0.05, bottom - 0.12)])
	part(bm, "Gold")

	bm = bmesh.new()
	feathers = [
		(6, 1.25, 0.12, 0),
		(22, 1.12, 0.115, 0.014),
		(38, 0.98, 0.105, 0),
		(54, 0.8, 0.095, 0.014),
		(68, 0.6, 0.085, 0),
		(14, 0.62, 0.1, -0.04),
		(40, 0.52, 0.09, -0.04),
		(62, 0.4, 0.08, -0.04),
	]
	for side in (-1, 1):
		root = Vector((side * 0.34, 0.14))
		for angle, length, width, depth in feathers:
			direction = Vector((side * math.cos(math.radians(angle)), math.sin(math.radians(angle))))
			lift = Vector((0, 0.06))
			feather_spine = [root, root + direction * length * 0.5 + lift, root + direction * length]
			feather, feather_plateau = profile_shape(feather_spine, [(0, width * 0.5), (0.3, width), (0.75, width * 0.85), (1, 0)], chamfer=width * 0.4)
			add_plate(bm, feather, feather_plateau, 0.008, 0.028, Matrix.Translation((0, depth - 0.007, 0)))
	part(bm, "Feather")

	bm = bmesh.new()
	star = star_shape(5, 0.13, 0.06)
	for y in (-0.14, 0.14):
		add_plate(bm, star, [point * 0.5 for point in star], 0.012, 0.035, Matrix.Translation((0, y, 0.12)))
	add_crystal(bm, (0, 0, bottom - 0.1), (0, 0, -1), 0.28, 0.06)
	part(bm, "StarGlow")

	bm = bmesh.new()
	add_torus(bm, 0.42, 0.03, 24, 6, Matrix.Translation((0, 0, blade_base + 0.6)) @ Matrix.Rotation(math.radians(68), 4, "X"))
	part(bm, "HaloGlow")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.8, 0.064, 0.077, 7)
	part(bm, "WhiteCloth")

	vine = [[(0, blade_base + 0.35), (0, blade_base + 2.3)]]
	for index in range(6):
		side = 1 if index % 2 == 0 else -1
		z = blade_base + 0.55 + index * 0.3
		vine.append([(0, z), (0.05 * side, z + 0.06), (0.1 * side, z + 0.04), (0.11 * side, z - 0.02), (0.07 * side, z - 0.03)])
	return {
		"blade": "Celestial",
		"outline": outline,
		"edge_glow": ("FFE7A1", 0.08),
		"effects": {
			"Celestial": {
				"gradient": (blade_base, blade_base + 3.2, [(0, "E8C784"), (0.35, "F5EEDC"), (1, "FFFFFF")]),
				"patterns": [("nebula", "FFF3C4", 2.5, 0.35), ("stars", "FFD54A", 9, 1)],
			},
			"Feather": {"gradient": (0.1, 1.3, [(0, "E3C98E"), (0.4, "F2F4FB"), (1, "FFFFFF")])},
		},
		"decals": vine,
		"decal_width": 0.02,
		"decal_colors": ("D9A12E", "FFE7A1"),
	}


#// 12 Void King Sword (Exclusive)

VOID_RUNES = [
	[(-1, -1), (0, 1), (1, -1)],
	[(-1, 1), (1, 1), (-1, -1), (1, -1)],
	[(0, -1), (0, 1), (1, 0.3)],
	[(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 0)],
	[(-1, 1), (0, -1), (1, 1)],
	[(0, 1), (0, -1), (-1, -0.3)],
	[(-1, -1), (-1, 1), (1, -1), (1, 1)],
]


def build_void_king_sword(part):
	blade_base = 0.2
	spine = [(0, blade_base), (0, blade_base + 4.0)]
	stations = [(0, 0.28), (0.06, 0.36), (0.25, 0.32), (0.45, 0.38), (0.6, 0.34), (0.72, 0.46), (0.78, 0.42), (1, 0)]
	teeth = [(0.18, 1), (0.22, -1), (0.38, 1), (0.42, -1), (0.56, 1), (0.6, -1), (0.75, 1), (0.77, -1)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.13, features=[(t, side, 0.2, -0.18, 0.8) for t, side in teeth])
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.022, 0.12)
	part(bm, "Void")

	rim, rim_plateau = profile_shape(spine, [(t, width + 0.08) for t, width in stations], chamfer=0.04, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	add_torus(bm, 0.62, 0.03, 28, 6, Matrix.Translation((0, 0, blade_base + 1.3)) @ Matrix.Rotation(math.radians(64), 4, "X"))
	part(bm, "VoidGlow")

	bm = bmesh.new()
	for position, direction, length, radius in (
		((-0.8, 0, 1.3), (-0.25, 0, 1), 0.42, 0.08),
		((0.82, 0, 1.95), (0.2, 0, 1), 0.36, 0.07),
		((-0.72, 0, 2.75), (-0.15, 0, 1), 0.32, 0.06),
		((0.68, 0, 3.45), (0.2, 0, 1), 0.28, 0.05),
	):
		add_crystal(bm, position, direction, length, radius)
	add_cabochon(bm, (0, 0, 0.04), 0.11, 0.2)
	bottom = -1.0
	add_crystal(bm, (0, 0, bottom - 0.12), (0, 0, -1), 0.38, 0.08)
	part(bm, "VoidCyan", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_sweep(bm, [(-0.85, 0.22), (-0.5, 0.08), (0, 0.04), (0.5, 0.08), (0.85, 0.22)], [0.06, 0.09, 0.11, 0.09, 0.06])
	for y in (-0.14, 0.14):
		add_torus(bm, 0.14, 0.035, 16, 6, Matrix.Translation((0, y, 0.04)))
	add_box(bm, (0.76, 0.26, 0.16), (0, 0, 0.2), 0.04)
	for x, angle in ((-0.62, -32), (-0.42, -16), (0.42, 16), (0.62, 32)):
		direction = Vector((math.sin(math.radians(angle)), 0, math.cos(math.radians(angle))))
		root = Vector((x, 0, 0.12 + abs(x) * 0.12))
		add_spike(bm, root, direction, 0.42, 0.06, sides=4)
		add_ball(bm, root + direction * 0.44, 0.04)
	add_pommel(bm, [(0.06, -0.04), (0.1, -0.02), (0.1, 0.03), (0.06, 0.05)])
	add_pommel(bm, [(0.06, -0.5), (0.088, -0.48), (0.088, -0.44), (0.06, -0.42)])
	add_pommel(bm, [(0.05, bottom + 0.04), (0.12, bottom), (0.12, bottom - 0.07), (0.06, bottom - 0.12)])
	for direction in ((1, 0, -0.4), (-1, 0, -0.4), (0, 1, -0.4), (0, -1, -0.4)):
		add_spike(bm, (0, 0, bottom - 0.04), direction, 0.2, 0.035, sides=4)
	part(bm, "Gold")

	bm = bmesh.new()
	wing = [
		(0.15, -0.12), (0.32, -0.1), (0.45, -0.24), (0.6, -0.04), (0.75, -0.16), (0.85, 0.06),
		(0.95, -0.02), (1.0, 0.18), (1.18, 0.44), (0.6, 0.12), (0.15, 0.02),
	]
	for side in (1, -1):
		add_plate(bm, [Vector((side * x, z)) for x, z in (wing if side > 0 else wing[::-1])], None, 0.035)
	part(bm, "VoidMetal")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.96, 0.07, 0.084, 8)
	part(bm, "VoidLeather")

	runes = []
	for index in range(8):
		center = Vector((0, blade_base + 0.55 + index * 0.4))
		runes.append([center + Vector(point) * 0.075 for point in VOID_RUNES[index % len(VOID_RUNES)]])
	return {
		"blade": "Void",
		"outline": outline,
		"edge_glow": ("FF4FD8", 0.07),
		"effects": {
			"Void": {
				"gradient": (blade_base, blade_base + 4.0, [(0, "0B0420"), (0.4, "241050"), (0.75, "3A1A7A"), (1, "6A2FC0")]),
				"patterns": [("nebula", "C23FD8", 1.6, 0.4), ("nebula", "3F8FFF", 2.6, 0.3), ("stars", "FFFFFF", 10, 1)],
			},
			"VoidMetal": {
				"gradient": (-0.3, 0.5, [(0, "140E22"), (1, "4A2E8A")]),
				"patterns": [("nebula", "FF4FD8", 3, 0.25)],
			},
		},
		"decals": runes,
		"decal_width": 0.016,
		"decal_colors": ("4FF3FF", "E6FFFF"),
	}


SWORDS = [
	("WoodenSword", "Common", build_wooden_sword),
	("RustySword", "Common", build_rusty_sword),
	("IronSword", "Uncommon", build_iron_sword),
	("KnightSword", "Uncommon", build_knight_sword),
	("Scimitar", "Rare", build_scimitar),
	("CleaverSword", "Rare", build_cleaver_sword),
	("CrystalSword", "Epic", build_crystal_sword),
	("FlameSword", "Epic", build_flame_sword),
	("FrostSword", "Legendary", build_frost_sword),
	("DemonSword", "Legendary", build_demon_sword),
	("CelestialSword", "Mythic", build_celestial_sword),
	("VoidKingSword", "Exclusive", build_void_king_sword),
]


#// Desert World

def point_on_path(path, u):
	lengths = [0]
	for start, end in zip(path, path[1:]):
		lengths.append(lengths[-1] + (end - start).length)
	distance = u * lengths[-1]
	for i in range(len(path) - 1):
		if lengths[i + 1] >= distance:
			return path[i].lerp(path[i + 1], (distance - lengths[i]) / max(lengths[i + 1] - lengths[i], 1e-6))
	return path[-1]


def glyph_strokes(shapes, centers, size):
	strokes = []
	for shape, center in zip(shapes, centers):
		for stroke in shape:
			strokes.append([(center[0] + x * size, center[1] + z * size) for x, z in stroke])
	return strokes


GLYPHS = [
	[[(-1, -1), (0, 1), (1, -1), (-1, -1)]],
	[[(-1, 0), (-0.5, 0.5), (0, 0), (0.5, 0.5), (1, 0)], [(-1, -0.6), (-0.5, -0.1), (0, -0.6), (0.5, -0.1), (1, -0.6)]],
	[[(-1, 0), (0, 0.6), (1, 0), (0, -0.6), (-1, 0)], [(0, 0.15), (0, -0.15)]],
	[[(0, -1), (0, 0.25)], [(-0.6, 0.25), (0.6, 0.25)], [(0, 0.25), (-0.35, 0.6), (0, 1), (0.35, 0.6), (0, 0.25)]],
	[[(-1, 1), (-1, -1), (1, -1)], [(-0.4, 0.4), (0.6, 0.4)]],
]


#// Desert 01 Cactus Sword (Common)

def build_cactus_sword(part):
	blade_base = 0.12
	length = 2.1
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.21), (0.08, 0.25), (0.85, 0.24), (1, 0.21)],
		tip="round",
		chamfer=0.11,
		plateau_ratio=0.35,
	)
	arms = ((1, 0.95, 0.52), (-1, 0.55, 0.44))
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.08, 0.13)
	for side, start, height in arms:
		root = blade_base + start
		arm = [(side * 0.16, root), (side * 0.36, root + 0.02), (side * 0.47, root + 0.14), (side * 0.47, root + height)]
		add_sweep(bm, arm, [0.06, 0.064, 0.066, 0.066], sides=8)
		add_ball(bm, (side * 0.47, 0, root + height), 0.096)
	for side in (-1, 1):
		pad, pad_plateau = profile_shape([(side * 0.08, 0.06), (side * 0.32, 0.12), (side * 0.56, 0.24)], [(0, 0.08), (0.45, 0.14), (1, 0.1)], tip="round", chamfer=0.05)
		add_plate(bm, pad, pad_plateau, 0.035, 0.065)
	part(bm, "CactusGreen")

	bm = bmesh.new()

	def spine_pair(location, direction):
		direction = Vector(direction).normalized()
		spread = Vector((0, 0, 0.35)) if abs(direction.z) < 0.7 else Vector((0.35, 0, 0))
		for tilt in (-1, 1):
			add_spike(bm, location, direction + spread * tilt, 0.08, 0.013, sides=4)

	for index, z in enumerate(numpy.arange(blade_base + 0.3, blade_base + length, 0.28)):
		for side in (-1, 1):
			spine_pair((side * 0.24, 0, z), (side, 0, 0.3))
			if index % 2 == 0:
				spine_pair((0.115 * side, side * 0.13, z + 0.14), (0, side, 0.3))
	for side, start, height in arms:
		root = blade_base + start
		spine_pair((side * 0.47, 0, root + height + 0.09), (side * 0.2, 0, 1))
		spine_pair((side * 0.57, 0, root + height * 0.55), (side, 0, 0.2))
		spine_pair((side * 0.47, side * 0.0 - 0.09, root + height * 0.4), (0, -1, 0.2))
	for side in (-1, 1):
		spine_pair((side * 0.56, 0, 0.3), (side, 0, 0.6))
	part(bm, "CactusSpine")

	top = blade_base + length + 0.2
	bm = bmesh.new()
	for index in range(6):
		angle = math.tau * index / 6 + math.pi / 2
		add_ball(bm, (math.cos(angle) * 0.1, 0, top + math.sin(angle) * 0.1), 0.085, (1, 2.0, 1))
	add_ball(bm, (0.47, 0, blade_base + 0.95 + 0.52 + 0.1), 0.06, (1, 1.6, 1))
	part(bm, "Flower")

	bm = bmesh.new()
	add_ball(bm, (0, 0, top), 0.06, (1, 2.8, 1))
	part(bm, "Gold")

	bm = bmesh.new()
	for height in (0.03, 0.11):
		add_torus(bm, 0.12, 0.028, 14, 6, Matrix.Translation((0, 0, height)) @ Matrix.Rotation(math.radians(90), 4, "X"))
	add_grip(bm, -0.04, 0.7, 0.062, 0.075, 6)
	part(bm, "Rope")

	bm = bmesh.new()
	bottom = -0.04 - 0.7
	add_pommel(bm, [(0.06, -0.02), (0.08, -0.04), (0.08, 0.0), (0.06, 0.02)])
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.09), (0.06, bottom - 0.13), (0, bottom - 0.14)])
	part(bm, "DesertWood")

	ribs = [[(x, blade_base + 0.2), (x, blade_base + length + 0.05)] for x in (-0.12, 0, 0.12)]
	return {
		"blade": "CactusGreen",
		"decals": ribs,
		"decal_width": 0.016,
		"decal_colors": ("2F6B2E", "A6E07A"),
		"effects": {"CactusGreen": {"gradient": (0.0, 2.5, [(0, "3A7A32"), (1, "8AD460")])}},
	}


#// Desert 02 Jawbone Sword (Common)

def build_jawbone_sword(part):
	spine = [(0, 0.12), (0, 1.2), (0.08, 1.95), (0.24, 2.45)]
	stations = [(0, 0.3, 0.16), (0.12, 0.24, 0.17), (0.55, 0.19, 0.18), (0.88, 0.16, 0.14), (1, 0, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.07, plateau_ratio=0.4)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.045, 0.1)
	bottom = -0.03 - 0.72
	add_ball(bm, (0, 0, bottom - 0.12), 0.14, (1, 0.95, 1))
	add_ball(bm, (0, -0.03, bottom - 0.24), 0.1, (0.85, 0.8, 0.55))
	part(bm, "Bone")

	path = catmull_rom(spine, 8) + [Vector(spine[-1])]
	bm = bmesh.new()
	for index in range(11):
		t = 0.1 + 0.075 * index
		center = point_on_path(path, t)
		ahead = point_on_path(path, min(t + 0.01, 1))
		tangent = (ahead - center).normalized()
		normal = Vector((tangent.y, -tangent.x))
		width = 0.16 + 0.02 * math.sin(t * math.pi)
		root = center + normal * (width - 0.03)
		direction = normal + tangent * 0.45
		length = 0.11 if index % 2 == 0 else 0.075
		add_spike(bm, (root.x, 0, root.y), (direction.x, 0, direction.y), length, 0.04, sides=5)
	for side in (-1, 1):
		add_ball(bm, (side * 0.07, -0.13, bottom - 0.2), 0.03, (1, 0.6, 1.3))
	part(bm, "Tooth")

	bm = bmesh.new()
	add_box(bm, (0.26, 0.24, 0.2), (0, 0, 0.06), 0.06)
	for side in (-1, 1):
		add_sweep(bm, [(side * 0.1, 0.07), (side * 0.32, 0.12), (side * 0.48, 0.04)], [0.045, 0.04, 0.03])
		add_ball(bm, (side * 0.5, 0, 0.03), 0.06)
		add_spike(bm, (side * 0.2, 0, 0.15), (side * 0.3, 0, 1), 0.14, 0.035, sides=5)
	add_pommel(bm, [(0.06, bottom + 0.02), (0.09, bottom), (0.09, bottom - 0.03), (0.06, bottom - 0.04)])
	part(bm, "BoneDark")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.055, -0.115, bottom - 0.1), 0.04, (1, 0.5, 1.2))
	add_ball(bm, (0, -0.13, bottom - 0.16), 0.022, (1, 0.5, 1))
	part(bm, "Socket")

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.72, 0.062, 0.075, 6)
	part(bm, "Leather")

	return {
		"blade": "Bone",
		"decals": [
			[(-0.12, 1.85), (-0.07, 1.78), (-0.1, 1.7)],
			[(-0.1, 1.2), (-0.05, 1.13), (-0.08, 1.05), (-0.03, 0.98)],
			[(-0.14, 0.55), (-0.08, 0.5), (-0.11, 0.42)],
		],
		"effects": {"Bone": {"gradient": (0.1, 2.5, [(0, "D2BE92"), (1, "F7EFD9")])}},
	}


#// Desert 03 Obelisk Sword (Uncommon)

def build_obelisk_sword(part):
	blade_base = 0.3
	length = 2.15
	top = blade_base + length
	outline, plateau = profile_shape(
		[(0, blade_base), (0, top)],
		[(0, 0.27), (0.04, 0.29), (1, 0.23)],
		tip=[(1.0, 0), (0, 0.36), (-1.0, 0)],
		chamfer=0.09,
		features=[(0.3, 1, 0.08, 0.05, 0.3), (0.6, -1, 0.1, 0.06, 0), (0.82, 1, 0.07, 0.04, -0.2)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.05, 0.12)
	part(bm, "Sandstone")

	bm = bmesh.new()
	cap = [Vector((-0.255, top - 0.06)), Vector((0.255, top - 0.06)), Vector((0, top + 0.37))]
	add_plate(bm, cap, [Vector((0, top + 0.06)) + (point - Vector((0, top + 0.06))) * 0.5 for point in cap], 0.065, 0.14)
	add_box(bm, (0.64, 0.33, 0.06), (0, 0, 0.29), 0.02)
	bottom = -0.03 - 0.72
	add_lathe(bm, [(0.2, bottom - 0.26), (0, bottom)], 4, Matrix.Rotation(math.radians(45), 4, "Z"))
	part(bm, "Gold", 30)

	bm = bmesh.new()
	for width, height, z in ((0.86, 0.34, 0.03), (0.68, 0.3, 0.13), (0.5, 0.28, 0.22)):
		add_box(bm, (width, height, 0.1), (0, 0, z), 0.03)
	part(bm, "SandstoneDark")

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.72, 0.064, 0.077, 6)
	add_pommel(bm, [(0.06, bottom + 0.02), (0.1, bottom), (0.1, bottom - 0.03), (0.06, bottom - 0.04)])
	part(bm, "DesertWood")

	centers = [(0, blade_base + 0.3 + index * 0.37) for index in range(5)]
	return {
		"blade": "Sandstone",
		"decals": glyph_strokes(GLYPHS, centers, 0.1),
		"decal_width": 0.022,
		"decal_colors": ("5A2A10", "FFE2B0"),
		"effects": {
			"Sandstone": {"gradient": (0.3, 2.8, [(0, "C47A38"), (1, "F2BC7A")]), "patterns": [("bands", "D08A48", 4, 0.3)]},
			"SandstoneDark": {"patterns": [("bands", "8A4A22", 9, 0.35)]},
		},
	}


#// Desert 04 Nomad Khopesh (Uncommon)

def build_nomad_khopesh(part):
	spine = [(0, 0.16), (0, 0.95), (0.12, 1.55), (0.5, 1.95), (0.95, 2.0), (1.25, 1.78)]
	stations = [(0, 0.08, 0.08), (0.3, 0.08, 0.08), (0.42, 0.16, 0.08), (0.65, 0.44, 0.09), (0.86, 0.34, 0.08), (1, 0, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.08, features=[(0.7, -1, 0.08, 0.04, 0)])
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.025, 0.1)
	bottom = -0.04 - 0.75
	add_pommel(bm, [(0.05, bottom + 0.01), (0.08, bottom - 0.02), (0.13, bottom - 0.06), (0.12, bottom - 0.1), (0, bottom - 0.12)])
	part(bm, "Bronze")

	edge, edge_plateau = profile_shape(spine, [(t, left + 0.035, right + 0.02) for t, left, right in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, edge, edge_plateau, 0.008, 0.02)
	part(bm, "BronzeEdge")

	bm = bmesh.new()
	add_pommel(bm, [(0.06, -0.04), (0.13, -0.01), (0.13, 0.12), (0.07, 0.17)])
	for side in (-1, 1):
		add_sweep(bm, [(side * 0.08, 0.06), (side * 0.25, 0.08), (side * 0.32, 0.16)], [0.04, 0.035, 0.0])
	for height in (-0.25, -0.5):
		add_pommel(bm, [(0.06, height - 0.02), (0.088, height - 0.01), (0.088, height + 0.01), (0.06, height + 0.02)])
	part(bm, "Gold")

	bm = bmesh.new()
	add_pommel(bm, [(0.125, 0.03), (0.14, 0.04), (0.14, 0.08), (0.125, 0.09)])
	add_cabochon(bm, (0, 0, bottom - 0.06), 0.05, 0.2)
	part(bm, "Turquoise", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.75, 0.062, 0.075, 7)
	part(bm, "DarkLeather")

	eye_center = (0.38, 1.82)
	eye = [
		[(eye_center[0] - 0.12, eye_center[1]), (eye_center[0], eye_center[1] + 0.07), (eye_center[0] + 0.12, eye_center[1]), (eye_center[0], eye_center[1] - 0.05), (eye_center[0] - 0.12, eye_center[1])],
		[(eye_center[0] - 0.02, eye_center[1] - 0.05), (eye_center[0] - 0.04, eye_center[1] - 0.14)],
		[(eye_center[0] + 0.04, eye_center[1] - 0.04), (eye_center[0] + 0.1, eye_center[1] - 0.1), (eye_center[0] + 0.14, eye_center[1] - 0.06)],
	]
	return {
		"blade": "Bronze",
		"decals": [[(0, 0.3), (0, 0.95)]] + eye,
		"decal_width": 0.02,
		"decal_colors": ("2FC9B8", "A8FFF2"),
		"effects": {"Bronze": {"gradient": (0.1, 2.1, [(0, "8A4E1C"), (1, "E8A858")])}},
	}


#// Desert 05 Scorpion Sword (Rare)

def build_scorpion_sword(part):
	path = catmull_rom([(0, 0.24), (0, 1.1), (0.08, 1.8), (0.32, 2.35), (0.62, 2.62)], 8) + [Vector((0.62, 2.62))]
	bm = bmesh.new()
	segments = 6
	for index in range(segments):
		start = index / segments * 0.96 + 0.01
		end = start + 0.96 / segments - 0.02
		spine = [point_on_path(path, start), point_on_path(path, (start + end) / 2), point_on_path(path, end)]
		width = 0.27 - 0.025 * index
		outline, plateau = profile_shape(spine, [(0, width * 0.7), (0.5, width), (1, width * 0.75)], tip="round", chamfer=0.08, plateau_ratio=0.25)
		add_plate(bm, outline, plateau, 0.04, 0.12)
	stinger = [(0.62, 2.62), (0.82, 2.76), (0.98, 2.74), (1.08, 2.58), (1.04, 2.44)]
	add_ball(bm, (0.72, 0, 2.7), 0.13, (1.2, 0.9, 0.9))
	add_sweep(bm, stinger, [0.07, 0.065, 0.05, 0.03, 0.0], sides=8)
	part(bm, "Chitin")

	bm = bmesh.new()
	add_sweep(bm, [point_on_path(path, t) for t in (0, 0.33, 0.66, 1)], [0.07, 0.065, 0.055, 0.05], sides=8)
	for side in (-1, 1):
		arm = [(side * 0.12, 0.12), (side * 0.32, 0.18), (side * 0.48, 0.34)]
		add_sweep(bm, arm, [0.06, 0.055, 0.05])
		add_ball(bm, (side * 0.48, 0, 0.34), 0.085)
		add_sweep(bm, [(side * 0.48, 0.34), (side * 0.66, 0.52), (side * 0.6, 0.74)], [0.065, 0.045, 0.0])
		add_sweep(bm, [(side * 0.46, 0.38), (side * 0.38, 0.56), (side * 0.44, 0.68)], [0.05, 0.03, 0.0])
		for step in range(3):
			t = 0.25 + step * 0.22
			base = Vector((side * (0.58 - 0.02 * step), 0, 0.46 + t * 0.3))
			add_spike(bm, base, (-side, 0, 0.3), 0.06, 0.018, sides=4)
	add_box(bm, (0.32, 0.26, 0.26), (0, 0, 0.12), 0.07)
	bottom = -0.02 - 0.75
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.08), (0.06, bottom - 0.11)])
	add_spike(bm, (0, 0, bottom - 0.1), (0, 0, -1), 0.25, 0.07)
	add_grip(bm, -0.02, 0.75, 0.064, 0.08, 6)
	part(bm, "ChitinDark")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.12), 0.08, 0.16)
	add_ball(bm, (1.02, 0, 2.38), 0.045, (1, 1, 1.4))
	part(bm, "Venom")

	return {
		"blade": "Chitin",
		"effects": {
			"Chitin": {"gradient": (0.2, 2.8, [(0, "4A1218"), (0.6, "A63A2E"), (1, "E86A3A")])},
			"ChitinDark": {"gradient": (-0.9, 0.8, [(0, "2A0A10"), (1, "6A2028")])},
		},
	}


#// Desert 06 Cobra Fang (Rare)

def build_cobra_fang(part):
	spine = [(0, 0.3), (0.02, 1.2), (0.1, 2.0), (0.26, 2.6)]
	stations = [(0, 0.17, 0.17), (0.1, 0.2, 0.2), (0.6, 0.17, 0.2), (0.88, 0.12, 0.15), (1, 0, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.08, plateau_ratio=0.35)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.03, 0.1)
	part(bm, "Fang")

	bm = bmesh.new()
	hood, hood_plateau = profile_shape([(0, -0.1), (0, 0.5), (0, 1.15)], [(0, 0.16), (0.3, 0.56), (0.65, 0.5), (1, 0.18)], tip="round", chamfer=0.08)
	add_plate(bm, hood, hood_plateau, 0.03, 0.065, Matrix.Translation((0, 0.13, 0)))
	add_ball(bm, (0, -0.03, 0.22), 0.2, (1.25, 1.05, 0.8))
	add_ball(bm, (0, -0.1, 0.08), 0.12, (1.0, 0.9, 0.5))
	tail = [(0, -0.03 - 0.75), (0.08, -0.03 - 0.86), (0.2, -0.03 - 0.88), (0.24, -0.03 - 0.78)]
	add_sweep(bm, tail, [0.065, 0.055, 0.04, 0.0])
	part(bm, "Serpent")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.32, 0.06, 0.68), 0.09, (1, 0.4, 1.2))
		add_ball(bm, (side * 0.32, 0.06, 0.68), 0.05, (1, 0.6, 1.2))
	add_box(bm, (0.1, 0.07, 0.6), (0, 0.07, 0.6), 0.02)
	for height in (-0.2, -0.45, -0.7):
		add_pommel(bm, [(0.06, height - 0.02), (0.088, height - 0.01), (0.088, height + 0.01), (0.06, height + 0.02)])
	part(bm, "Gold")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.13, -0.19, 0.28), 0.045, (1, 0.6, 1))
	part(bm, "SnakeEye")

	bm = bmesh.new()
	for side in (-1, 1):
		add_spike(bm, (side * 0.07, -0.19, 0.12), (0, -0.2, -1), 0.12, 0.02, sides=5)
	part(bm, "Bone")

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.75, 0.064, 0.077, 7)
	part(bm, "Hood")

	return {
		"blade": "Fang",
		"outline": outline,
		"edge_glow": ("B8FF6A", 0.05),
		"effects": {
			"Fang": {"gradient": (0.3, 2.7, [(0, "F4EAD2"), (0.6, "E8E2B8"), (1, "9CFF3A")])},
			"Serpent": {"gradient": (-0.1, 1.0, [(0, "1E6A4A"), (1, "4FC08A")]), "patterns": [("cells", "8FE8B8", 10, 0.5)]},
			"Hood": {"patterns": [("cells", "2E7A5A", 9, 0.4)]},
		},
	}


#// Desert 07 Mummy Blade (Epic)

def build_mummy_blade(part):
	blade_base = 0.22
	spine = [(0, blade_base), (0, blade_base + 2.9)]
	stations = [(0, 0.2), (0.08, 0.26), (0.7, 0.25), (0.88, 0.18), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Cursed")

	rim, rim_plateau = profile_shape(spine, [(t, width + 0.05) for t, width in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	add_cabochon(bm, (0, 0, 0.12), 0.09, 0.16)
	bottom = -0.04 - 0.78
	for side in (-1, 1):
		add_ball(bm, (side * 0.05, -0.13, bottom - 0.1), 0.03)
	part(bm, "CurseGlow")

	bm = bmesh.new()
	for index in range(6):
		low = blade_base + 0.3 + index * 0.4
		lean = 0.16 if index % 2 == 0 else -0.16
		half = 0.33
		band = [Vector((-half, low)), Vector((half, low + lean)), Vector((half, low + lean + 0.1)), Vector((-half, low + 0.1))]
		if lean < 0:
			band = [Vector((-half, low - lean)), Vector((half, low)), Vector((half, low + 0.1)), Vector((-half, low - lean + 0.1))]
		add_plate(bm, band, None, 0.115)
	flap = [Vector((0.3, 1.32)), Vector((0.5, 1.2)), Vector((0.56, 1.05)), Vector((0.47, 1.1)), Vector((0.3, 1.24))]
	add_plate(bm, flap, None, 0.02, matrix=Matrix.Translation((0, -0.1, 0)))
	add_sweep(bm, [(-0.55, 0.14), (0, 0.1), (0.55, 0.14)], [0.055, 0.065, 0.055])
	add_ball(bm, (0, 0, bottom - 0.12), 0.14)
	for height, tilt in ((-0.05, 18), (-0.12, -14), (-0.2, 10)):
		add_torus(bm, 0.135, 0.025, 14, 5, Matrix.Translation((0, 0, bottom - 0.12 + height + 0.12)) @ Matrix.Rotation(math.radians(90 + tilt), 4, "X"))
	add_grip(bm, -0.04, 0.78, 0.064, 0.077, 7)
	part(bm, "Bandage")

	bm = bmesh.new()
	add_box(bm, (0.32, 0.24, 0.26), (0, 0, 0.12), 0.06)
	for side in (-1, 1):
		add_ball(bm, (side * 0.6, 0, 0.14), 0.07)
	part(bm, "Gold")

	return {
		"blade": "Cursed",
		"outline": outline,
		"edge_glow": ("7CFF5A", 0.07),
		"effects": {
			"Cursed": {"gradient": (0.2, 3.1, [(0, "14302A"), (1, "3E7A60")]), "patterns": [("cells", "7CFF5A", 3, 0.55)]},
			"Bandage": {"patterns": [("nebula", "C9BA98", 7, 0.45)]},
		},
	}


#// Desert 08 Pharaoh Sword (Epic)

def build_pharaoh_sword(part):
	blade_base = 0.24
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 3.0)],
		[(0, 0.19), (0.08, 0.24), (0.45, 0.21), (0.76, 0.32), (0.88, 0.27), (1, 0)],
		chamfer=0.1,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "PharaohGold")

	nemes = {"Lapis": bmesh.new(), "PharaohGold": bmesh.new()}
	for side in (-1, 1):
		for index in range(4):
			low = 0.2 - index * 0.11
			band = [Vector((side * 0.16, low + 0.2)), Vector((side * 0.7, low + 0.02)), Vector((side * 0.72, low - 0.06)), Vector((side * 0.16, low + 0.1))]
			add_plate(nemes["Lapis" if index % 2 == 0 else "PharaohGold"], band if side > 0 else band[::-1], None, 0.045)
	for key, nemes_part in nemes.items():
		part(nemes_part, key)

	bm = bmesh.new()
	add_box(bm, (0.34, 0.24, 0.32), (0, 0, 0.14), 0.06)
	add_torus(bm, 0.14, 0.03, 16, 6, Matrix.Translation((0, -0.13, 0.14)))
	add_torus(bm, 0.14, 0.03, 16, 6, Matrix.Translation((0, 0.13, 0.14)))
	bottom = -0.03 - 0.78
	for height in (-0.04, bottom + 0.02):
		add_pommel(bm, [(0.06, height - 0.02), (0.095, height - 0.01), (0.095, height + 0.02), (0.06, height + 0.03)])
	add_torus(bm, 0.11, 0.035, 16, 6, Matrix.Translation((0, 0, bottom - 0.2)))
	add_box(bm, (0.32, 0.08, 0.07), (0, 0, bottom - 0.06), 0.02)
	add_box(bm, (0.07, 0.08, 0.1), (0, 0, bottom - 0.03), 0.02)
	part(bm, "Gold")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.14), 0.1, 0.16)
	part(bm, "Turquoise", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.78, 0.064, 0.077, 7)
	part(bm, "Lapis")

	return {
		"blade": "PharaohGold",
		"outline": outline,
		"edge_glow": ("FFF0B0", 0.05),
		"decals": [[(0, blade_base + 0.2), (0, blade_base + 2.55)]],
		"decal_width": 0.05,
		"decal_colors": ("2A4BC9", "8AA8FF"),
		"effects": {"PharaohGold": {"gradient": (0.2, 3.2, [(0, "D98E1E"), (1, "FFD86A")])}},
	}


#// Desert 09 Sandstorm Sword (Legendary)

def build_sandstorm_sword(part):
	spine = [(0, 0.22), (0, 1.5), (0.1, 2.4), (0.3, 3.2)]
	stations = [(0, 0.2, 0.2), (0.1, 0.25, 0.25), (0.45, 0.22, 0.36), (0.7, 0.2, 0.44), (0.85, 0.12, 0.34), (1, 0, 0)]
	teeth = [(t, 1, 0.2, -0.12, -0.6) for t in (0.38, 0.53, 0.68)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1, features=teeth)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Sand")

	rim, rim_plateau = profile_shape(spine, [(t, left + 0.05, right + 0.05) for t, left, right in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	add_torus(bm, 0.5, 0.025, 24, 6, Matrix.Translation((0.02, 0, 1.0)) @ Matrix.Rotation(math.radians(62), 4, "X"))
	add_torus(bm, 0.4, 0.022, 20, 6, Matrix.Translation((0.1, 0, 2.15)) @ Matrix.Rotation(math.radians(-58), 4, "X") @ Matrix.Rotation(math.radians(12), 4, "Y"))
	add_cabochon(bm, (0, 0, 0.1), 0.085, 0.15)
	part(bm, "SandGlow")

	bm = bmesh.new()
	for location, radius in (((-0.62, 0.05, 1.3), 0.07), ((0.66, -0.05, 1.65), 0.06), ((-0.5, 0, 2.45), 0.05), ((0.58, 0.05, 0.75), 0.055)):
		add_ball(bm, location, radius, (1, 0.9, 0.8))
	part(bm, "SandstoneDark", SMOOTH_ANGLE)

	bm = bmesh.new()
	curl = [(-0.1, 0.12), (-0.35, 0.1), (-0.5, 0.22), (-0.45, 0.36), (-0.34, 0.32)]
	radii = [0.06, 0.05, 0.04, 0.03, 0.0]
	add_sweep(bm, curl, radii)
	add_sweep(bm, mirror(curl), radii)
	add_box(bm, (0.32, 0.22, 0.24), (0, 0, 0.1), 0.05)
	bottom = -0.03 - 0.78
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.09), (0.06, bottom - 0.13), (0, bottom - 0.14)])
	part(bm, "Bronze")

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.78, 0.064, 0.077, 7)
	part(bm, "Rope")

	swirls = []
	for center_x, center_z, turn in ((0.05, 0.85, 1), (-0.05, 1.55, -1), (0.1, 2.25, 1)):
		swirls.append([
			(center_x + math.cos(turn * step * 0.42) * (0.02 + 0.016 * step), center_z + math.sin(turn * step * 0.42) * (0.02 + 0.016 * step))
			for step in range(13)
		])
	return {
		"blade": "Sand",
		"outline": outline,
		"edge_glow": ("FFB347", 0.06),
		"decals": swirls,
		"decal_width": 0.018,
		"decal_colors": ("B86A2E", "FFF0C8"),
		"effects": {
			"Sand": {
				"gradient": (0.2, 3.2, [(0, "B8763A"), (0.5, "E8B868"), (1, "FFE8B0")]),
				"patterns": [("nebula", "FFF0C8", 3, 0.35), ("stars", "FFFFFF", 9, 0.8)],
			},
		},
	}


#// Desert 10 Scarab Sword (Legendary)

def build_scarab_sword(part):
	blade_base = 0.34
	spine = [(0, blade_base), (0, blade_base + 2.95)]
	stations = [(0, 0.2), (0.1, 0.3), (0.45, 0.34), (0.75, 0.3), (0.92, 0.18), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.12)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	add_ball(bm, (0, 0, 0.18), 0.2, (1.0, 0.85, 1.25))
	part(bm, "Scarab")

	rim, rim_plateau = profile_shape(spine, [(t, width + 0.035) for t, width in stations], chamfer=0.02, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	for y in (-0.1, 0.1):
		add_sweep(bm, [(0, y, blade_base + 0.1), (0, y, blade_base + 1.5), (0, y, blade_base + 2.7)], [0.014, 0.014, 0.0], sides=5)
	add_ball(bm, (0, 0, 0.43), 0.08, (1.1, 0.8, 0.8))
	for side in (-1, 1):
		add_sweep(bm, [(side * 0.08, 0.42), (side * 0.2, 0.52), (side * 0.12, 0.66)], [0.025, 0.022, 0.016])
		add_sweep(bm, [(side * 0.12, 0.1), (side * 0.3, 0.0), (side * 0.34, -0.14)], [0.025, 0.022, 0.0])
	add_torus(bm, 0.15, 0.03, 18, 6, Matrix.Translation((0, -0.14, 0.72)))
	add_torus(bm, 0.15, 0.03, 18, 6, Matrix.Translation((0, 0.14, 0.72)))
	bottom = -0.03 - 0.8
	for height in (-0.04, -0.4, bottom + 0.02):
		add_pommel(bm, [(0.06, height - 0.02), (0.095, height - 0.01), (0.095, height + 0.02), (0.06, height + 0.03)])
	add_pommel(bm, [(0.06, bottom + 0.01), (0.1, bottom - 0.03), (0.12, bottom - 0.09), (0.07, bottom - 0.14), (0, bottom - 0.16)])
	part(bm, "Gold")

	feathers = [(-6, 0.95, 0.12), (8, 0.88, 0.115), (22, 0.76, 0.11), (36, 0.62, 0.1)]
	gold_feathers = bmesh.new()
	blue_feathers = bmesh.new()
	for side in (-1, 1):
		root = Vector((side * 0.16, 0.22))
		for index, (angle, length, width) in enumerate(feathers):
			direction = Vector((side * math.cos(math.radians(angle)), math.sin(math.radians(angle))))
			feather_spine = [root, root + direction * length * 0.5 + Vector((0, 0.04)), root + direction * length]
			feather, feather_plateau = profile_shape(feather_spine, [(0, width * 0.5), (0.3, width), (1, width * 0.75)], tip="round", chamfer=width * 0.35)
			target = gold_feathers if index % 2 == 0 else blue_feathers
			add_plate(target, feather, feather_plateau, 0.01, 0.03, Matrix.Translation((0, 0.06 + index * 0.012, 0)))
	part(gold_feathers, "ScarabWing")
	part(blue_feathers, "Lapis")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.72), 0.12, 0.17)
	part(bm, "SunGlow")

	bm = bmesh.new()
	add_grip(bm, -0.03, 0.8, 0.064, 0.077, 7)
	add_cabochon(bm, (0, 0, bottom - 0.08), 0.05, 0.22)
	part(bm, "Lapis")

	return {
		"blade": "Scarab",
		"outline": outline,
		"edge_glow": ("FFD86A", 0.05),
		"effects": {
			"Scarab": {
				"gradient": (0.0, 3.3, [(0, "1E6B8A"), (0.4, "2FB8A0"), (0.75, "7AD05A"), (1, "B07AE0")]),
				"patterns": [("cells", "B8FFE0", 3, 0.25)],
			},
			"ScarabWing": {"gradient": (0.1, 0.9, [(0, "D08A20"), (1, "FFD86A")])},
		},
	}


#// Desert 11 Sun God Sword (Mythic)

def build_sun_god_sword(part):
	blade_base = 0.3
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + 3.2)],
		[(0, 0.22), (0.08, 0.3), (0.55, 0.27), (0.78, 0.36), (0.88, 0.3), (1, 0)],
		chamfer=0.11,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "SunBlade")

	disk_center = Vector((0, 0, 0.62))
	bm = bmesh.new()
	add_torus(bm, 0.62, 0.05, 32, 6, Matrix.Translation(disk_center))
	add_cabochon(bm, (0, 0, 0.14), 0.1, 0.17)
	bottom = -0.04 - 0.8
	add_cabochon(bm, (0, 0, bottom - 0.08), 0.05, 0.2)
	part(bm, "SunGlow")

	bm = bmesh.new()
	for index in range(16):
		angle = math.tau * index / 16
		if abs(math.degrees(angle) - 270) < 50:
			continue
		direction = Vector((math.cos(angle), 0, math.sin(angle)))
		add_spike(bm, disk_center + direction * 0.66, direction, 0.24 if index % 2 == 0 else 0.15, 0.05, sides=4)
	add_box(bm, (0.36, 0.24, 0.3), (0, 0, 0.14), 0.05)
	add_pommel(bm, [(0.06, -0.06), (0.095, -0.04), (0.095, -0.01), (0.06, 0.0)])
	add_pommel(bm, [(0.06, bottom + 0.04), (0.09, bottom + 0.02), (0.11, bottom - 0.04), (0.08, bottom - 0.1), (0.05, bottom - 0.12)])
	part(bm, "Gold")

	bm = bmesh.new()
	feathers = [(4, 1.0, 0.12), (20, 0.9, 0.11), (36, 0.78, 0.1), (52, 0.64, 0.09)]
	for side in (-1, 1):
		root = Vector((side * 0.3, 0.16))
		for index, (angle, length, width) in enumerate(feathers):
			direction = Vector((side * math.cos(math.radians(angle)), math.sin(math.radians(angle))))
			feather_spine = [root, root + direction * length * 0.5 + Vector((0, 0.05)), root + direction * length]
			feather, feather_plateau = profile_shape(feather_spine, [(0, width * 0.5), (0.3, width), (0.75, width * 0.85), (1, 0)], chamfer=width * 0.4)
			add_plate(bm, feather, feather_plateau, 0.008, 0.028, Matrix.Translation((0, 0.09 + (index % 2) * 0.014, 0)))
	part(bm, "SunFeather")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.8, 0.064, 0.077, 7)
	part(bm, "WhiteCloth")

	sun = [[(math.cos(math.tau * i / 12) * 0.09, blade_base + 0.75 + math.sin(math.tau * i / 12) * 0.09) for i in range(13)]]
	for index in range(8):
		angle = math.tau * index / 8
		sun.append([
			(math.cos(angle) * 0.13, blade_base + 0.75 + math.sin(angle) * 0.13),
			(math.cos(angle) * 0.19, blade_base + 0.75 + math.sin(angle) * 0.19),
		])
	return {
		"blade": "SunBlade",
		"outline": outline,
		"edge_glow": ("FFFFFF", 0.07),
		"decals": sun,
		"decal_width": 0.016,
		"decal_colors": ("D9782A", "FFF6D0"),
		"effects": {
			"SunBlade": {"gradient": (0.3, 3.5, [(0, "F29A2E"), (0.5, "FFD45A"), (1, "FFF4C8")]), "patterns": [("stars", "FFFFFF", 9, 1)]},
			"SunFeather": {"gradient": (0.1, 1.2, [(0, "E0A040"), (1, "FFF2D0")])},
		},
	}


#// Desert 12 Djinn King Scimitar (Exclusive)

def crescent_shape(outer_radius, inner_radius, offset, steps=14):
	# Outer circle minus a smaller circle shifted along +X, both arcs end where the circles cross.
	cross_x = (outer_radius ** 2 - inner_radius ** 2 + offset ** 2) / (2 * offset)
	cross_y = math.sqrt(outer_radius ** 2 - cross_x ** 2)
	outer_start = math.atan2(cross_y, cross_x)
	inner_start = math.atan2(cross_y, cross_x - offset)
	outer = [Vector((math.cos(angle), math.sin(angle))) * outer_radius for angle in numpy.linspace(outer_start, math.tau - outer_start, steps)]
	inner = [Vector((math.cos(angle), math.sin(angle))) * inner_radius + Vector((offset, 0)) for angle in numpy.linspace(math.tau - inner_start, inner_start, steps)[1:-1]]
	return outer + inner


def build_djinn_king_scimitar(part):
	spine = [(0, 0.3), (0, 1.5), (0.12, 2.5), (0.42, 3.25), (0.85, 3.85)]
	stations = [(0, 0.3, 0.3), (0.08, 0.36, 0.34), (0.4, 0.42, 0.3), (0.6, 0.48, 0.25), (0.74, 0.43, 0.21), (0.85, 0.32, 0.15), (0.93, 0.18, 0.08), (1, 0, 0)]
	teeth = [(t, 1, 0.16, -0.12, 0.6) for t in (0.3, 0.45, 0.6)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.13, features=teeth)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.022, 0.12)
	part(bm, "Djinn")

	rim, rim_plateau = profile_shape(spine, [(t, left + 0.07, right + 0.07) for t, left, right in stations], chamfer=0.04, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	bottom = -0.08 - 0.9
	add_gem(bm, (0, 0, bottom - 0.2), 0.1, 0.17)
	part(bm, "DjinnGlow")

	path = catmull_rom(spine, 8) + [Vector(spine[-1])]
	bm = bmesh.new()
	for phase in (0, math.pi):
		helix = []
		for step in range(14):
			t = step / 13
			center = point_on_path(path, 0.08 + 0.6 * t)
			angle = t * math.tau * 1.6 + phase
			helix.append((center.x + math.cos(angle) * 0.55, math.sin(angle) * 0.35, center.y))
		add_sweep(bm, helix, [0.03] * 4 + [0.026] * 6 + [0.015, 0.01, 0.005, 0.0], sides=5, smoothness=3)
	part(bm, "DjinnSmoke")

	bm = bmesh.new()
	lamp = Matrix.Translation((0, 0, 0.1)) @ Matrix.Rotation(math.radians(90), 4, "Y")
	add_lathe(bm, [(0, -0.36), (0.1, -0.32), (0.17, -0.12), (0.17, 0.08), (0.11, 0.24), (0.05, 0.3)], 12, lamp)
	add_sweep(bm, [(0.28, 0.08), (0.48, 0.12), (0.62, 0.26)], [0.045, 0.03, 0.022])
	add_torus(bm, 0.1, 0.025, 14, 6, Matrix.Translation((-0.42, 0, 0.12)))
	add_pommel(bm, [(0.1, 0.24), (0.1, 0.27), (0.06, 0.33), (0, 0.35)])
	add_pommel(bm, [(0.06, -0.08), (0.095, -0.06), (0.095, -0.03), (0.06, -0.02)])
	add_pommel(bm, [(0.06, bottom + 0.03), (0.12, bottom), (0.12, bottom - 0.08), (0.06, bottom - 0.12)])
	moon = crescent_shape(0.24, 0.2, 0.09)
	add_plate(bm, moon, None, 0.03, matrix=Matrix.Translation((-0.78, 0, 2.55)))
	for location, size in (((0.95, 0, 1.45), 0.11), ((-0.62, 0, 1.25), 0.09), ((1.42, 0, 2.7), 0.1), ((-0.55, 0, 3.15), 0.08)):
		star = star_shape(5, size, size * 0.45)
		add_plate(bm, star, [point * 0.5 for point in star], 0.012, 0.035, Matrix.Translation(location))
	part(bm, "Gold")

	bm = bmesh.new()
	for y in (-0.17, 0.17):
		add_cabochon(bm, (0, y, 0.1), 0.055, 0.04, direction=(0, 1 if y > 0 else -1, 0))
	part(bm, "Turquoise", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, -0.08, 0.9, 0.07, 0.084, 8)
	part(bm, "DjinnLeather")

	return {
		"blade": "Djinn",
		"outline": outline,
		"edge_glow": ("4FE3FF", 0.07),
		"effects": {
			"Djinn": {
				"gradient": (0.3, 3.6, [(0, "1A0E5A"), (0.5, "3A2AA8"), (1, "7A5AF0")]),
				"patterns": [("nebula", "4FA8FF", 1.8, 0.4), ("nebula", "C24FD8", 2.8, 0.3), ("stars", "FFFFFF", 10, 1)],
			},
		},
	}


DESERT_SWORDS = [
	("CactusSword", "Common", build_cactus_sword),
	("JawboneSword", "Common", build_jawbone_sword),
	("ObeliskSword", "Uncommon", build_obelisk_sword),
	("NomadKhopesh", "Uncommon", build_nomad_khopesh),
	("ScorpionSword", "Rare", build_scorpion_sword),
	("CobraFang", "Rare", build_cobra_fang),
	("MummyBlade", "Epic", build_mummy_blade),
	("PharaohSword", "Epic", build_pharaoh_sword),
	("SandstormSword", "Legendary", build_sandstorm_sword),
	("ScarabSword", "Legendary", build_scarab_sword),
	("SunGodSword", "Mythic", build_sun_god_sword),
	("DjinnKingScimitar", "Exclusive", build_djinn_king_scimitar),
]

WORLDS = {
	"Starter": SWORDS,
	"Desert": DESERT_SWORDS,
}



#// Bake Materials

def create_decal_mask(name, strokes, stroke_width, outline=None, edge_width=None):
	# R: decal strokes, G: their light edge, B: distance from the blade outline for the edge glow.
	points = [Vector(point) for point in (outline or [point for stroke in strokes for point in stroke])]
	min_x = min(point.x for point in points) - 0.1
	min_z = min(point.y for point in points) - 0.1
	width = max(point.x for point in points) + 0.1 - min_x
	height = max(point.y for point in points) + 0.1 - min_z

	pixel_width = int(width * DECAL_RESOLUTION)
	pixel_height = int(height * DECAL_RESOLUTION)
	grid_x, grid_z = numpy.meshgrid(
		min_x + (numpy.arange(pixel_width) + 0.5) / DECAL_RESOLUTION,
		min_z + (numpy.arange(pixel_height) + 0.5) / DECAL_RESOLUTION,
	)

	def segment_distance(start, end):
		edge = end - start
		t = numpy.clip(((grid_x - start[0]) * edge[0] + (grid_z - start[1]) * edge[1]) / max(edge.dot(edge), 1e-9), 0, 1)
		return numpy.hypot(grid_x - start[0] - t * edge[0], grid_z - start[1] - t * edge[1]), t

	def stroke_mask(offset):
		mask = numpy.zeros_like(grid_x)
		for stroke in strokes:
			for i in range(len(stroke) - 1):
				distance, t = segment_distance(numpy.array(stroke[i]) + offset, numpy.array(stroke[i + 1]) + offset)
				taper = 1 - (i + t) / (len(stroke) - 1) * 0.6
				mask = numpy.maximum(mask, numpy.clip((stroke_width * taper - distance) * DECAL_RESOLUTION + 0.5, 0, 1))
		return mask

	main = stroke_mask(numpy.array((0, 0)))
	edge = numpy.clip(stroke_mask(numpy.array((0.008, -0.008))) - main, 0, 1)

	depth = numpy.ones_like(grid_x)
	if outline and edge_width:
		distance = numpy.full_like(grid_x, numpy.inf)
		for i, point in enumerate(outline):
			following = outline[(i + 1) % len(outline)]
			distance = numpy.minimum(distance, segment_distance(numpy.array(point), numpy.array(following))[0])
		depth = numpy.clip(distance / edge_width, 0, 1)

	image = bpy.data.images.new(name + "Decals", pixel_width, pixel_height, float_buffer=True)
	image.colorspace_settings.name = "Non-Color"
	pixels = numpy.stack([main, edge, depth, numpy.ones_like(main)], axis=-1)
	image.pixels.foreach_set(pixels.astype(numpy.float32).ravel())
	image.pack()
	return image, (min_x, min_z, width, height)


def setup_bake_material(material, key, bake_image, bounds, decal=None, effects=None):
	base, shadow, highlight = (to_color(color) for color in PALETTE[key])
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
		if kind == "cells":
			warp = node("ShaderNodeTexNoise", (x - 400, y))
			warp.inputs["Scale"].default_value = scale * 1.5
			links.new(coordinates.outputs["Object"], warp.inputs["Vector"])
			warped = node("ShaderNodeVectorMath", (x - 200, y), operation="MULTIPLY_ADD")
			links.new(warp.outputs["Color"], warped.inputs[0])
			warped.inputs[1].default_value = (0.15, 0.15, 0.15)
			links.new(coordinates.outputs["Object"], warped.inputs[2])
			cells = node("ShaderNodeTexVoronoi", (x, y), feature="DISTANCE_TO_EDGE")
			cells.inputs["Scale"].default_value = scale
			links.new(warped.outputs[0], cells.inputs["Vector"])
			return map_range(cells.outputs["Distance"], 0.06, 0.0, (x + 200, y))

		if kind == "stars":
			cells = node("ShaderNodeTexVoronoi", (x, y))
			cells.inputs["Scale"].default_value = scale
			links.new(coordinates.outputs["Object"], cells.inputs["Vector"])
			sparkle = map_range(cells.outputs["Distance"], 0.24, 0.08, (x + 200, y))
			return math_node("MULTIPLY", sparkle, math_node("GREATER_THAN", cells.outputs["Color"], 0.55, (x + 200, y - 150)), (x + 400, y))

		if kind == "bands":
			bands = node("ShaderNodeTexWave", (x, y), bands_direction="Z")
			bands.inputs["Scale"].default_value = scale
			bands.inputs["Distortion"].default_value = 1.5
			links.new(coordinates.outputs["Object"], bands.inputs["Vector"])
			return map_range(bands.outputs["Fac"], 0.55, 0.62, (x + 200, y))

		if kind == "flames":
			stretched = node("ShaderNodeVectorMath", (x - 200, y), operation="MULTIPLY")
			links.new(coordinates.outputs["Object"], stretched.inputs[0])
			stretched.inputs[1].default_value = (1, 1, 0.3)
			tongues = node("ShaderNodeTexNoise", (x, y))
			tongues.inputs["Scale"].default_value = scale
			tongues.inputs["Detail"].default_value = 3
			tongues.inputs["Distortion"].default_value = 0.6
			links.new(stretched.outputs[0], tongues.inputs["Vector"])
			return map_range(tongues.outputs["Fac"], 0.52, 0.62, (x + 200, y))

		cloud = node("ShaderNodeTexNoise", (x, y))
		cloud.inputs["Scale"].default_value = scale
		cloud.inputs["Detail"].default_value = 4
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
			element.color = to_color(hex_color)
		base = ramp.outputs["Color"]

	bevel = node("ShaderNodeBevel", (-1000, 300), samples=16)
	bevel.inputs["Radius"].default_value = EDGE_BEVEL_RADIUS
	facing = node("ShaderNodeVectorMath", (-800, 300), operation="DOT_PRODUCT")
	links.new(geometry.outputs["Normal"], facing.inputs[0])
	links.new(bevel.outputs["Normal"], facing.inputs[1])
	edge = map_range(facing.outputs["Value"], EDGE_START, EDGE_FULL, (-600, 300))

	occlusion = node("ShaderNodeAmbientOcclusion", (-1000, 0), samples=16, only_local=True)
	occlusion.inputs["Distance"].default_value = CAVITY_DISTANCE
	convex = math_node("MULTIPLY", edge, map_range(occlusion.outputs["AO"], 0.7, 0.92, (-800, 0)), (-400, 200))
	cavity = map_range(occlusion.outputs["AO"], 0.95, 0.35, (-800, -100))

	wear = node("ShaderNodeTexNoise", (-1000, -300))
	wear.inputs["Scale"].default_value = EDGE_WEAR_SCALE
	wear.inputs["Detail"].default_value = 3
	links.new(coordinates.outputs["Object"], wear.inputs["Vector"])
	convex = math_node("MULTIPLY", convex, map_range(wear.outputs["Fac"], 0.35, 0.6, (-800, -300), 0.45, 1), (-200, 200))

	variation = map_range(wear.outputs["Fac"], 0.3, 0.7, (-800, -450))
	light_tone = mix(COLOR_VARIATION, base, highlight, (-400, -400))
	dark_tone = mix(COLOR_VARIATION, base, shadow, (-400, -550))
	color = mix(variation, dark_tone, light_tone, (0, -400))

	bottom, top = bounds
	gradient = map_range(position.outputs["Z"], top, bottom, (-800, -1000), 0, LENGTH_GRADIENT)
	color = mix(gradient, color, shadow, (100, -300))

	flat = None
	channels = None
	if decal is not None:
		normal = node("ShaderNodeSeparateXYZ", (-1000, 500))
		links.new(geometry.outputs["Normal"], normal.inputs[0])
		flat = map_range(math_node("ABSOLUTE", normal.outputs["Y"], 0, (-800, 500)), 0.97, 0.995, (-600, 500))
		chamfer = map_range(flat, 1, 0, (-400, 500), 0, BEVEL_BRIGHTNESS)
		color = mix(chamfer, color, highlight, (150, -150))

		if decal["mask"]:
			image, (min_x, min_z, width, height) = decal["mask"]
			combine = node("ShaderNodeCombineXYZ", (-600, -800))
			links.new(map_range(position.outputs["X"], min_x, min_x + width, (-800, -750)), combine.inputs["X"])
			links.new(map_range(position.outputs["Z"], min_z, min_z + height, (-800, -900)), combine.inputs["Y"])
			mask = node("ShaderNodeTexImage", (-400, -800), image=image, extension="CLIP")
			links.new(combine.outputs[0], mask.inputs["Vector"])
			channels = node("ShaderNodeSeparateColor", (-150, -800))
			links.new(mask.outputs["Color"], channels.inputs[0])

			if decal["edge_glow"]:
				glow_color, _ = decal["edge_glow"]
				glow = math_node("MULTIPLY", map_range(channels.outputs["Blue"], 1, 0, (0, -900)), mask.outputs["Alpha"], (150, -900))
				color = mix(glow, color, to_color(glow_color), (250, -200))

	for index, (kind, hex_color, scale, strength) in enumerate(effects.get("patterns", ())):
		factor = pattern(kind, scale, (-600, -1200 - index * 300))
		color = mix(math_node("MULTIPLY", factor, strength, (0, -1200 - index * 300)), color, to_color(hex_color), (300, -250 - index * 50))

	color = mix(cavity, color, shadow, (400, 0))
	color = mix(convex, color, highlight, (500, 100))

	if channels and decal["strokes"]:
		main_color, edge_color = decal["colors"] or (None, None)
		main_color = to_color(main_color) if main_color else shadow
		edge_color = to_color(edge_color) if edge_color else highlight
		color = mix(math_node("MULTIPLY", channels.outputs["Red"], flat, (100, -700)), color, main_color, (600, -100))
		color = mix(math_node("MULTIPLY", channels.outputs["Green"], flat, (100, -850)), color, edge_color, (800, -100))

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
	shader.inputs["Roughness"].default_value = 0.65
	image_node = material.node_tree.nodes.new("ShaderNodeTexImage")
	image_node.image = texture
	image_node.location = (-400, 300)
	material.node_tree.links.new(image_node.outputs["Color"], shader.inputs["Base Color"])
	return material


def create_outline_material():
	# Black inverted hull. Backface culling hides the shell in the viewport and in Roblox,
	# the backfacing mix does the same for Cycles renders.
	material = bpy.data.materials.new("Outline")
	material.use_nodes = True
	material.use_backface_culling = True
	material.diffuse_color = to_color(OUTLINE_COLOR)
	nodes = material.node_tree.nodes
	links = material.node_tree.links
	nodes.clear()

	geometry = nodes.new("ShaderNodeNewGeometry")
	light_path = nodes.new("ShaderNodeLightPath")
	not_camera = nodes.new("ShaderNodeMath")
	not_camera.operation = "SUBTRACT"
	not_camera.inputs[0].default_value = 1
	links.new(light_path.outputs["Is Camera Ray"], not_camera.inputs[1])
	hide = nodes.new("ShaderNodeMath")
	hide.operation = "MAXIMUM"
	links.new(geometry.outputs["Backfacing"], hide.inputs[0])
	links.new(not_camera.outputs[0], hide.inputs[1])
	color = nodes.new("ShaderNodeEmission")
	color.inputs["Color"].default_value = to_color(OUTLINE_COLOR)
	hidden = nodes.new("ShaderNodeBsdfTransparent")
	shader = nodes.new("ShaderNodeMixShader")
	output = nodes.new("ShaderNodeOutputMaterial")
	links.new(hide.outputs[0], shader.inputs[0])
	links.new(color.outputs[0], shader.inputs[1])
	links.new(hidden.outputs[0], shader.inputs[2])
	links.new(shader.outputs[0], output.inputs["Surface"])
	return material


def create_outline(root, targets, material):
	# Inverted hull kept as its own black object: a Solidify shell with flipped normals,
	# without the original surface, parented to the model.
	bm = bmesh.new()
	for target in targets:
		modifier = target.modifiers.new("Outline", "SOLIDIFY")
		modifier.thickness = OUTLINE_THICKNESS
		modifier.offset = 1
		modifier.use_flip_normals = True
		modifier.use_quality_normals = True
		modifier.use_rim = False
		modifier.material_offset = len(target.data.materials)
		target.data.materials.append(material)

		shell = bpy.data.meshes.new_from_object(target.evaluated_get(bpy.context.evaluated_depsgraph_get()))
		target.modifiers.remove(modifier)
		target.data.materials.pop()
		shell.transform(root.matrix_world.inverted() @ target.matrix_world)
		shell_bm = bmesh.new()
		shell_bm.from_mesh(shell)
		bmesh.ops.delete(shell_bm, geom=[face for face in shell_bm.faces if face.material_index < len(target.data.materials)], context="FACES")
		shell_bm.to_mesh(shell)
		shell_bm.free()
		bm.from_mesh(shell)
		bpy.data.meshes.remove(shell)

	for face in bm.faces:
		face.material_index = 0
	mesh = bpy.data.meshes.new(root.name + "Outline")
	bm.to_mesh(mesh)
	bm.free()
	mesh.materials.append(material)

	outline = bpy.data.objects.new(root.name + "Outline", mesh)
	for collection in root.users_collection:
		collection.objects.link(outline)
	outline.parent = root
	outline.matrix_parent_inverse = Matrix()
	return outline


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


def separate_glow(sword, name):
	glow_parts = []
	for index, material in enumerate(sword.data.materials):
		if material["Key"] not in GLOW_MATERIALS:
			continue

		select_only([sword])
		bpy.ops.object.mode_set(mode="EDIT")
		bm = bmesh.from_edit_mesh(sword.data)
		for face in bm.faces:
			face.select_set(False)
		for face in bm.faces:
			if face.material_index == index:
				face.select_set(True)
		bmesh.update_edit_mesh(sword.data)
		bpy.ops.mesh.separate(type="SELECTED")
		bpy.ops.object.mode_set(mode="OBJECT")

		glow = next(target for target in bpy.context.selected_objects if target != sword)
		glow.name = name + material["Key"]
		glow.data.name = glow.name
		glow_parts.append(glow)
	return glow_parts


def build_sword(name, rarity, build, collection, outline_material):
	parts = []

	def part(bm, key, smooth_angle=SMOOTH_ANGLE):
		material = bpy.data.materials.get(name + key)
		if not material:
			material = bpy.data.materials.new(name + key)
			material.use_nodes = True
			material["Key"] = key
		parts.append(new_part(name + key, bm, material, smooth_angle))

	details = build(part)

	select_only(parts)
	bpy.ops.object.join()
	sword = bpy.context.view_layer.objects.active
	sword.name = name
	sword.data.name = name
	sword["Rarity"] = rarity

	heights = [vertex.co.z for vertex in sword.data.vertices]
	bounds = (min(heights), max(heights))
	texture = bpy.data.images.new(name, TEXTURE_SIZE, TEXTURE_SIZE)
	strokes = details.get("decals", [])
	edge_glow = details.get("edge_glow")
	mask = None
	if strokes or edge_glow:
		mask = create_decal_mask(
			name,
			strokes,
			details.get("decal_width", DECAL_WIDTH),
			details.get("outline") if edge_glow else None,
			edge_glow[1] if edge_glow else None,
		)
	decal = {"mask": mask, "strokes": strokes, "colors": details.get("decal_colors"), "edge_glow": edge_glow}
	effects = details.get("effects", {})
	for material in sword.data.materials:
		key = material["Key"]
		setup_bake_material(material, key, texture, bounds, decal if key == details["blade"] else None, effects.get(key))

	select_only([sword])
	bpy.ops.object.mode_set(mode="EDIT")
	bpy.ops.mesh.select_all(action="SELECT")
	bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=UV_MARGIN, scale_to_bounds=True)
	bpy.ops.object.mode_set(mode="OBJECT")

	bpy.ops.object.bake(type="EMIT")

	final_material = create_final_material(name, texture)
	glow_parts = separate_glow(sword, name)
	for target in [sword] + glow_parts:
		target.data.materials.clear()
		target.data.materials.append(final_material)
		for polygon in target.data.polygons:
			polygon.material_index = 0
		for user_collection in list(target.users_collection):
			user_collection.objects.unlink(target)
		collection.objects.link(target)
		if target != sword:
			target.parent = sword
	create_outline(sword, [sword] + glow_parts, outline_material)

	return sword, texture


def export_sword(sword, texture):
	texture.filepath_raw = os.path.join(EXPORT_FOLDER, sword.name + ".png")
	texture.file_format = "PNG"
	texture.save()

	original_location = sword.location.copy()
	sword.location = (0, 0, 0)

	# The outline is its own <Sword>Outline mesh, set it to black SmoothPlastic in Roblox.
	select_only([sword] + list(sword.children))
	bpy.ops.export_scene.fbx(
		filepath=os.path.join(EXPORT_FOLDER, sword.name + ".fbx"),
		use_selection=True,
		object_types={"MESH"},
		path_mode="COPY",
		embed_textures=True,
	)
	sword.location = original_location


def main():
	clear_scene()
	scene = bpy.context.scene
	scene.render.engine = "CYCLES"
	scene.cycles.device = "CPU"
	scene.cycles.samples = BAKE_SAMPLES
	scene.render.bake.margin = 8

	collection = bpy.data.collections.new(WORLD + "SwordPack")
	scene.collection.children.link(collection)

	outline_material = create_outline_material()
	swords = []
	for index, (name, rarity, build) in enumerate(WORLDS[WORLD]):
		sword, texture = build_sword(name, rarity, build, collection, outline_material)
		sword.location.x = index * PACK_SPACING
		swords.append((sword, texture))

	if EXPORT_FOLDER:
		os.makedirs(EXPORT_FOLDER, exist_ok=True)
		for sword, texture in swords:
			export_sword(sword, texture)

	for _, texture in swords:
		texture.pack()

	return [sword for sword, _ in swords]


if __name__ == "__main__":
	main()
