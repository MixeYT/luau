import bpy
import bmesh
import math
import os
import numpy
from mathutils import Matrix, Vector

# Run inside Blender 4.1+: Scripting tab -> Open -> Run Script.
# Builds a pack of cute, smooth low poly Roblox UGC accessories (hats and back items).
# Every accessory gets a baked curvature texture where edges turn a lighter shade of their own
# color, a separate black inverted hull outline object (<Accessory>Outline) and an FBX export.
# The outline UVs point at the black strip on the left edge of the texture, so joining it into the
# accessory (Ctrl+J) gives a single MeshPart with one texture for UGC uploads.
# Hats are built around a head centered at the origin (top of the head at z = 0.6),
# back items around a torso centered at the origin (back surface at y = 0.5). Front is -Y.

TEXTURE_SIZE = 1024
BAKE_SAMPLES = 64
UV_MARGIN = 0.01
OUTLINE_STRIP = 0.03  # left part of the texture painted black for the outline shell
OUTLINE_STRIP_GAP = 0.03  # empty space between the strip and the UV islands, keeps mipmaps from bleeding black
PACK_SPACING = 3.4

SMOOTH_ANGLE = 60  # auto smooth angle, every edge sharper than this stays hard
GEM_SMOOTH_ANGLE = 1

#// Curvature Look

EDGE_BEVEL_RADIUS = 0.03
EDGE_START = 0.996  # dot(normal, bevelNormal) where the highlight starts
EDGE_FULL = 0.94  # dot(normal, bevelNormal) where the highlight is at full strength
EDGE_STRENGTH = 0.9
EDGE_WEAR_SCALE = 6
CAVITY_DISTANCE = 0.16
CAVITY_STRENGTH = 0.75
COLOR_VARIATION = 0.05

HIGHLIGHT_LIGHTEN = 0.32  # highlight = base color mixed this much towards white
SHADOW_DARKEN = 0.45  # shadow = base color darkened this much
SHADOW_TINT = "3B2D6E"  # shadows lean slightly towards this color
SHADOW_TINT_AMOUNT = 0.25

#// Shapes

OUTLINE_SMOOTHNESS = 3
OUTLINE_TOLERANCE = 0.004
PROFILE_SAMPLES_PER_UNIT = 6

#// Outline

OUTLINE_THICKNESS = 0.016
OUTLINE_COLOR = "0B0710"

# Leave empty to skip. Otherwise every accessory is exported as FBX + PNG into this folder.
EXPORT_FOLDER = os.path.join(os.path.dirname(bpy.data.filepath), "Export") if bpy.data.filepath else ""

# Base color of every material, shadows and highlights are derived from it.
PALETTE = {
	"Felt": "5E6678",
	"Band": "26252E",
	"Feather": "E0483A",
	"Helm": "9FB0D6",
	"Trim": "F2B640",
	"Wing": "F4F7FF",
	"Gem": "3F8CFF",
	"Hat": "5A35A8",
	"HatBand": "FF8A2B",
	"Gold": "FFC43A",
	"Velvet": "C42A4A",
	"Ermine": "F7F2EA",
	"Ruby": "F03A55",
	"Sapphire": "3F7BFF",
	"Emerald": "2FCF7A",
	"Frog": "7CCB4F",
	"Eye": "FFFFFF",
	"Pupil": "2A2433",
	"Cheek": "FF8FAE",
	"Mouth": "3B2A35",
	"Headband": "FF8FC0",
	"Fur": "F4EEFF",
	"InnerEar": "FFA3CF",
	"Bow": "FF5C9E",
	"Angel": "F5F7FF",
	"Membrane": "8B5CF0",
	"Bone": "4A2C8F",
	"Heart": "FF6FA8",
}


#// Colors

def to_srgb(hex_color):
	return [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def to_linear(channels):
	return tuple(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels) + (1,)


def to_color(hex_color):
	return to_linear(to_srgb(hex_color))


def material_colors(key):
	base = to_srgb(PALETTE[key])
	tint = to_srgb(SHADOW_TINT)
	highlight = [channel + (1 - channel) * HIGHLIGHT_LIGHTEN for channel in base]
	shadow = [channel * (1 - SHADOW_DARKEN) * (1 - SHADOW_TINT_AMOUNT) + tinted * SHADOW_TINT_AMOUNT for channel, tinted in zip(base, tint)]
	return to_linear(base), to_linear(shadow), to_linear(highlight)


#// Math Helpers

def clamp(value, low=0.0, high=1.0):
	return max(low, min(high, value))


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


def oriented(location, direction, scale=(1, 1, 1)):
	rotation = Vector((0, 0, 1)).rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()
	return Matrix.Translation(Vector(location)) @ rotation @ Matrix.Diagonal(Vector(scale)).to_4x4()


def profile_shape(spine, stations, chamfer=0.05, plateau_ratio=0.3, tip="point"):
	# spine: centerline control points (x, z). stations: (t, halfWidth) along it.
	# tip: "point" ends in a sharp point, "round" closes the end with a half circle.
	path = catmull_rom(spine, 8) + [Vector(spine[-1])]
	lengths = [0]
	for start, end in zip(path, path[1:]):
		lengths.append(lengths[-1] + (end - start).length)
	total = lengths[-1]

	def frame(t):
		distance = t * total
		for i in range(len(path) - 1):
			if lengths[i + 1] >= distance or i == len(path) - 2:
				local = (distance - lengths[i]) / max(lengths[i + 1] - lengths[i], 1e-6)
				tangent = (path[i + 1] - path[i]).normalized()
				return path[i].lerp(path[i + 1], local), Vector((-tangent.y, tangent.x))

	def width(t):
		for start, end in zip(stations, stations[1:]):
			if start[0] <= t <= end[0]:
				return start[1] + (end[1] - start[1]) * (t - start[0]) / max(end[0] - start[0], 1e-6)
		return stations[-1][1]

	count = max(2, math.ceil(total * PROFILE_SAMPLES_PER_UNIT))
	samples = sorted({round(i / count, 4) for i in range(count + 1)} | {station[0] for station in stations})

	def edges(t_values, inset=0):
		right, left = [], []
		for t in t_values:
			center, normal = frame(t)
			half = width(t)
			if inset:
				half = max(half - inset, half * plateau_ratio)
			right.append(center - normal * half)
			left.append(center + normal * half)
		return right, left

	def cap(inset=0):
		center, normal = frame(1)
		tangent = Vector((normal.y, -normal.x))
		radius = width(1)
		radius = max(radius - inset, radius * plateau_ratio) if inset else radius
		return [center + (-normal * math.cos(angle) + tangent * math.sin(angle)) * radius for angle in (math.pi * i / 6 for i in range(1, 6))]

	plateau_start = chamfer * 0.3 / total
	if tip == "round":
		right, left = edges(samples)
		outline = simplify(right + cap() + left[::-1])
		right, left = edges([plateau_start] + [t for t in samples if t > plateau_start], chamfer)
		plateau = simplify(right + cap(chamfer) + left[::-1])
		return outline, plateau

	right, left = edges([t for t in samples if t < 1])
	outline = simplify(right + [frame(1)[0]] + left[::-1])
	plateau_end = 1 - chamfer * 2.2 / total
	right, left = edges([plateau_start] + [t for t in samples if plateau_start < t < plateau_end], chamfer)
	plateau = simplify(right + [frame(plateau_end)[0]] + left[::-1])
	return outline, plateau


def star_shape(points, outer_radius, inner_radius):
	outline = []
	for i in range(points * 2):
		angle = math.pi / 2 + math.pi * i / points
		radius = outer_radius if i % 2 == 0 else inner_radius
		outline.append(Vector((math.cos(angle) * radius, math.sin(angle) * radius)))
	return outline


def heart_shape(size, steps=20):
	outline = []
	for i in range(steps):
		t = math.tau * i / steps
		x = 16 * math.sin(t) ** 3
		z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
		outline.append(Vector((x, z)) * size / 16)
	return outline[::-1]


#// Mesh Helpers

def deform(bm, function):
	for vert in bm.verts:
		vert.co = function(vert.co.copy())


def oval(depth):
	def stretch(co):
		co.y *= depth
		return co
	return stretch


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


def add_plate(bm, outline, plateau=None, edge_thickness=0.01, center_thickness=0.03, matrix=Matrix()):
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
	return new_verts


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


def add_sweep(bm, points, radii, sides=6, flatten=1.0, smoothness=4, matrix=Matrix()):
	# Tube along a path given as (x, z) or (x, y, z) points. A radius of 0 ends the tube in a point.
	points = [Vector((point[0], 0, point[1])) if len(point) == 2 else Vector(point) for point in points]
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


def add_ball(bm, location, radius, scale=(1, 1, 1), segments=10, rings=6):
	bmesh.ops.create_uvsphere(
		bm,
		u_segments=segments,
		v_segments=rings,
		radius=radius,
		matrix=Matrix.LocRotScale(Vector(location), None, Vector(scale)),
	)


def add_spike(bm, base, direction, length, radius, sides=6):
	add_lathe(bm, [(radius, 0), (radius * 0.8, length * 0.3), (0, length)], sides, oriented(base, direction))


def add_cabochon(bm, center, radius, depth, direction=(0, 1, 0), sides=8):
	profile = [(0, -depth), (radius * 0.7, -depth * 0.8), (radius, -depth * 0.35), (radius, depth * 0.35), (radius * 0.7, depth * 0.8), (0, depth)]
	add_lathe(bm, profile, sides, oriented(center, direction))


def add_feather(bm, spine, width, matrix):
	outline, plateau = profile_shape(spine, [(0, width * 0.5), (0.35, width), (1, width * 0.7)], chamfer=width * 0.35, tip="round")
	add_plate(bm, outline, plateau, 0.01, 0.03, matrix)


def wing_outline(top, tips, bulge, steps=5):
	# Top edge as a smooth curve, bottom edge made of rounded feather tips.
	outline = catmull_rom(top, 4)
	center = sum((Vector(point) for point in top + tips), Vector((0, 0))) / len(top + tips)
	for start, end in zip(tips, tips[1:]):
		start, end = Vector(start), Vector(end)
		middle = (start + end) / 2
		control = middle + (middle - center).normalized() * bulge
		for step in range(steps):
			t = step / steps
			outline.append((1 - t) ** 2 * start + 2 * (1 - t) * t * control + t ** 2 * end)
	return simplify(outline)


def curve_back(bend, start):
	# Bends wings backwards the further they reach from the spine.
	def bend_wing(co):
		co.y += bend * max(0, abs(co.x) - start) ** 2
		return co
	return bend_wing


#// 01 Classic Fedora

def build_classic_fedora(part):
	bm = bmesh.new()
	add_lathe(bm, [(0.6, 0.42), (0.615, 0.62), (0.59, 0.84), (0.52, 0.98), (0.34, 1.05), (0, 1.06)], 24)

	def shape_crown(co):
		height = clamp((co.z - 0.55) / 0.5)
		co.y *= 1.12
		front = max(0, -co.y / 0.7)
		co.x *= 1 - 0.18 * front ** 2 * height
		co.z -= 0.05 * math.exp(-(co.x / 0.3) ** 2) * height ** 2
		return co

	deform(bm, shape_crown)

	brim = bmesh.new()
	add_lathe(brim, [(0.56, 0.4), (0.98, 0.395), (1.05, 0.41), (1.03, 0.435), (0.96, 0.445), (0.56, 0.44)], 32, closed=True)

	def shape_brim(co):
		radius = max(co.xy.length, 1e-6)
		edge = clamp((radius - 0.62) / 0.43)
		side = (co.x / radius) ** 2
		co.y *= 1.1
		co.z += 0.17 * side * edge ** 2 - 0.05 * (1 - side) * edge
		return co

	deform(brim, shape_brim)
	part(bm, "Felt")
	part(brim, "Felt")

	bm = bmesh.new()
	add_lathe(bm, [(0.6, 0.43), (0.635, 0.44), (0.64, 0.56), (0.605, 0.57)], 24, closed=True)
	deform(bm, oval(1.12))
	add_ball(bm, (-0.66, 0.1, 0.5), 0.07, (0.6, 1.3, 1))
	part(bm, "Band")

	bm = bmesh.new()
	feather_matrix = Matrix.Translation((-0.64, 0.14, 0.47)) @ Matrix.Rotation(math.radians(125), 4, "Z")
	add_feather(bm, [(0, 0), (0.1, 0.3), (0.3, 0.6)], 0.12, feather_matrix)
	part(bm, "Feather", subdivide=1)

	bm = bmesh.new()
	shaft = [feather_matrix @ Vector((x, -0.035, z)) for x, z in ((0, -0.04), (0.1, 0.3), (0.27, 0.55))]
	add_sweep(bm, shaft, [0.014, 0.011, 0.0], sides=5)
	part(bm, "Band")

	return {
		"attachment": "Hat",
		"effects": {
			"Felt": {"gradient": (0.35, 1.05, [(0, "4E5566"), (1, "727B8F")]), "patterns": [("nebula", "6A7387", 6, 0.3)]},
			"Feather": {"gradient": (0.45, 1.0, [(0, "B8322A"), (1, "FF7A5C")])},
		},
	}


#// 02 Sky Valkyrie Helm

def build_sky_valkyrie_helm(part):
	profile = [(0.66, 0.0), (0.69, 0.22), (0.66, 0.46), (0.56, 0.68), (0.36, 0.84), (0, 0.9)]
	bm = bmesh.new()
	add_lathe(bm, profile, 24)
	deform(bm, oval(1.08))
	part(bm, "Helm")

	bm = bmesh.new()
	add_lathe(bm, [(0.66, -0.02), (0.75, -0.01), (0.77, 0.07), (0.7, 0.13)], 24, closed=True)
	deform(bm, oval(1.08))
	crest = [(0, -radius * 1.08, height) for radius, height in profile[1:-1]]
	crest = crest + [(0, 0, profile[-1][1])] + [(0, -y, z) for _, y, z in crest[::-1]]
	add_sweep(bm, crest, [0.045, 0.06, 0.065, 0.07, 0.07, 0.065, 0.06, 0.045, 0.045][:len(crest)], smoothness=2)
	for side in (-1, 1):
		add_ball(bm, (side * 0.72, 0.05, 0.38), 0.085)
	part(bm, "Trim")

	bm = bmesh.new()
	add_cabochon(bm, (0, -0.73, 0.34), 0.085, 0.07, direction=(0, -1, 0))
	part(bm, "Gem", GEM_SMOOTH_ANGLE)

	top = [(0, 0), (0.02, 0.4), (0.22, 0.8), (0.55, 1.02)]
	tips = [(0.55, 1.02), (0.68, 0.78), (0.68, 0.54), (0.58, 0.32), (0.4, 0.14), (0.16, 0.0), (0, 0)]
	outline = wing_outline(top, tips, 0.1, steps=4)
	bm = bmesh.new()
	for side in (-1, 1):
		wing_matrix = Matrix.Translation((side * 0.74, 0.05, 0.36)) @ Matrix.Rotation(math.radians(90 - side * 15), 4, "Z")
		for scale, depth in ((1, 0), (0.62, 0.05)):
			layer = [point * scale for point in outline]
			add_plate(bm, layer, None, 0.014, matrix=wing_matrix @ Matrix.Translation((0, -side * depth, 0)))
	part(bm, "Wing")

	return {
		"attachment": "Hat",
		"effects": {
			"Helm": {"gradient": (0, 0.9, [(0, "7F90BE"), (1, "C3D0F0")])},
			"Wing": {"gradient": (0.35, 1.35, [(0, "B9CCFF"), (1, "FFFFFF")])},
		},
	}


#// 03 Starry Witch Hat

def build_starry_witch_hat(part):
	bm = bmesh.new()
	add_lathe(bm, [(0.55, 0.38), (1.1, 0.375), (1.2, 0.395), (1.17, 0.42), (1.08, 0.425), (0.55, 0.42)], 32, closed=True)

	def shape_brim(co):
		radius = max(co.xy.length, 1e-6)
		angle = math.atan2(co.y, co.x)
		edge = clamp((radius - 0.6) / 0.6)
		co.z += 0.05 * math.sin(angle * 3) * edge ** 2 - 0.06 * edge ** 2 * max(0, -co.y / radius)
		return co

	deform(bm, shape_brim)
	part(bm, "Hat")

	pivot = Vector((0, 0, 1.0))

	def shape_cone(co):
		wrinkle = 1 + 0.022 * math.sin(co.z * 14) * clamp((co.z - 0.6) / 0.4)
		co.x *= wrinkle
		co.y *= wrinkle
		if co.z > pivot.z:
			bend = math.radians(66) * ((co.z - pivot.z) / 1.1) ** 1.8
			co = pivot + Matrix.Rotation(bend, 3, "Y") @ (co - pivot)
		return co

	bm = bmesh.new()
	cone = [(0.6, 0.4), (0.6, 0.6), (0.53, 0.82), (0.45, 1.02), (0.38, 1.2), (0.31, 1.36), (0.25, 1.52), (0.19, 1.66), (0.13, 1.8), (0.08, 1.93), (0.04, 2.03), (0, 2.1)]
	add_lathe(bm, cone, 18)
	deform(bm, shape_cone)
	part(bm, "Hat")

	bm = bmesh.new()
	add_lathe(bm, [(0.6, 0.42), (0.64, 0.43), (0.64, 0.6), (0.6, 0.61)], 20, closed=True)
	part(bm, "HatBand")

	bm = bmesh.new()
	for size, location in (
		((0.22, 0.04, 0.045), (0, -0.66, 0.6)),
		((0.22, 0.04, 0.045), (0, -0.66, 0.43)),
		((0.045, 0.04, 0.2), (-0.09, -0.66, 0.515)),
		((0.045, 0.04, 0.2), (0.09, -0.66, 0.515)),
	):
		add_box(bm, size, location, 0.012)
	star = star_shape(5, 0.14, 0.065)
	tip = shape_cone(Vector((0, 0, 2.1)))
	add_plate(bm, star, [point * 0.55 for point in star], 0.015, 0.04, Matrix.Translation(tip + Vector((0.04, 0, -0.04))))
	part(bm, "Gold")

	return {
		"attachment": "Hat",
		"effects": {
			"Hat": {"gradient": (0.4, 2.0, [(0, "45278A"), (1, "8E62EE")]), "patterns": [("stars", "FFD84A", 7, 1)]},
		},
	}


#// 04 Royal Crown

def build_royal_crown(part):
	points = 5
	phase = math.pi / 2

	def shape_crown(co):
		angle = math.atan2(co.y, co.x)
		rise = clamp((co.z - 0.5) / 0.24)
		spike = (0.5 + 0.5 * math.cos(points * (angle + phase))) ** 2
		co.z += 0.32 * spike * rise ** 1.5
		co.y *= 1.05
		return co

	bm = bmesh.new()
	profile = [(0.6, 0.44), (0.66, 0.44), (0.665, 0.5), (0.67, 0.58), (0.675, 0.66), (0.68, 0.74), (0.62, 0.74), (0.615, 0.66), (0.61, 0.58), (0.605, 0.5)]
	add_lathe(bm, profile, 30, closed=True)
	deform(bm, shape_crown)
	for index in range(points):
		angle = -phase + math.tau * index / points
		add_ball(bm, (math.cos(angle) * 0.68, math.sin(angle) * 0.68 * 1.05, 1.08), 0.055, segments=8, rings=5)
	part(bm, "Gold")

	gems = {"Ruby": bmesh.new(), "Sapphire": bmesh.new(), "Emerald": bmesh.new()}
	for index in range(points):
		angle = -phase + math.tau * index / points
		direction = Vector((math.cos(angle), math.sin(angle), 0))
		center = Vector((direction.x * 0.69, direction.y * 0.69 * 1.05, 0.6))
		add_cabochon(gems[list(gems)[index % 3]], center, 0.065, 0.05, direction)
	for key, gem in gems.items():
		part(gem, key, GEM_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_lathe(bm, [(0.6, 0.5), (0.58, 0.7), (0.5, 0.86), (0.3, 0.96), (0, 0.98)], 24)
	deform(bm, oval(1.05))
	part(bm, "Velvet")

	bm = bmesh.new()
	trim = [(0.69 + math.cos(math.tau * i / 6) * 0.065, 0.45 + math.sin(math.tau * i / 6) * 0.065) for i in range(6)]
	add_lathe(bm, trim, 24, closed=True)
	deform(bm, oval(1.05))
	part(bm, "Ermine")

	return {
		"attachment": "Hat",
		"effects": {
			"Gold": {"gradient": (0.44, 1.1, [(0, "E09A20"), (1, "FFD86A")])},
			"Ermine": {"patterns": [("stars", "2B2530", 9, 1)]},
			"Velvet": {"gradient": (0.5, 0.98, [(0, "9C1E38"), (1, "E0405E")])},
		},
	}


#// 05 Frog Bucket Hat

def build_frog_bucket_hat(part):
	bm = bmesh.new()
	add_lathe(bm, [(0.62, 0.38), (0.64, 0.55), (0.61, 0.74), (0.5, 0.88), (0.28, 0.96), (0, 0.975)], 24)
	deform(bm, oval(1.08))
	brim = bmesh.new()
	add_lathe(brim, [(0.6, 0.43), (0.88, 0.3), (0.95, 0.26), (0.93, 0.235), (0.86, 0.255), (0.6, 0.39)], 24, closed=True)
	deform(brim, oval(1.08))
	for side in (-1, 1):
		add_ball(bm, (side * 0.25, -0.2, 0.86), 0.21, segments=12, rings=8)
	part(bm, "Frog")
	part(brim, "Frog")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.25, -0.33, 0.89), 0.14, segments=12, rings=8)
		add_ball(bm, (side * 0.25 + 0.035, -0.5, 0.93), 0.024, segments=6, rings=4)
	part(bm, "Eye")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.25, -0.46, 0.9), 0.065, (1, 0.5, 1), segments=10, rings=6)
	part(bm, "Pupil")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.4, -0.555, 0.56), 0.075, (1, 0.45, 0.75), segments=10, rings=6)
	part(bm, "Cheek")

	bm = bmesh.new()
	add_sweep(bm, [(-0.12, -0.672, 0.63), (0, -0.69, 0.585), (0.12, -0.672, 0.63)], [0.011, 0.013, 0.011])
	part(bm, "Mouth")

	return {
		"attachment": "Hat",
		"effects": {
			"Frog": {"gradient": (0.25, 1.05, [(0, "5FAE3E"), (1, "A2E36E")]), "patterns": [("stars", "B2E886", 4, 0.8)]},
		},
	}


#// 06 Cat Ears Headband

def build_cat_ears_headband(part):
	bm = bmesh.new()
	arc = [(math.cos(math.radians(angle)) * 0.64, 0, 0.02 + math.sin(math.radians(angle)) * 0.66) for angle in range(10, 171, 20)]
	add_sweep(bm, arc, [0.035] * len(arc), sides=8, flatten=2.4)
	part(bm, "Headband")

	ears = bmesh.new()
	inner = bmesh.new()
	for side in (-1, 1):
		angle = math.radians(55)
		base = Vector((side * math.cos(angle) * 0.64, 0, 0.02 + math.sin(angle) * 0.66 - 0.03))
		tilt = Matrix.Translation(base) @ Matrix.Rotation(math.radians(side * 28), 4, "Y")
		outline, plateau = profile_shape([(0, 0), (0.03, 0.22), (0, 0.42)], [(0, 0.2), (0.55, 0.12), (1, 0)], chamfer=0.05)
		ear_verts = add_plate(ears, outline, plateau, 0.02, 0.06)
		outline, plateau = profile_shape([(0, 0.06), (0.02, 0.22), (0, 0.36)], [(0, 0.12), (0.55, 0.075), (1, 0)], chamfer=0.03)
		inner_verts = add_plate(inner, outline, plateau, 0.01, 0.03, Matrix.Translation((0, -0.05, 0)))
		for target, verts in ((ears, ear_verts), (inner, inner_verts)):
			for vert in verts:
				vert.co.y -= 2.4 * vert.co.x ** 2
			bmesh.ops.transform(target, matrix=tilt, verts=verts)
	part(ears, "Fur", subdivide=1)
	part(inner, "InnerEar", subdivide=1)

	bm = bmesh.new()
	bow = Vector((-0.45, -0.07, 0.47))
	add_ball(bm, bow, 0.045)
	for side in (-1, 1):
		add_ball(bm, bow + Vector((side * 0.085, 0.01, 0.01)), 0.065, (1.3, 0.55, 0.9))
	part(bm, "Bow")

	return {
		"attachment": "Hat",
		"effects": {
			"Fur": {"gradient": (0.5, 1.0, [(0, "FFFFFF"), (1, "D9C8FF")])},
		},
	}


#// 07 Angel Wings

def build_angel_wings(part):
	top = [(0, 0.05), (0.5, 0.45), (1.1, 0.7), (1.6, 0.62)]
	tips = [(1.6, 0.62), (1.56, 0.26), (1.38, -0.06), (1.14, -0.32), (0.86, -0.5), (0.57, -0.56), (0.3, -0.5), (0.06, -0.3), (0, 0.05)]
	outline = wing_outline(top, tips, 0.13)
	root = Vector((0, 0.05))

	bm = bmesh.new()
	for side in (-1, 1):
		wing_matrix = Matrix.Translation((side * 0.2, 0.54, 0.5)) @ Matrix.Diagonal((side, 1, 1, 1)) @ Matrix.Rotation(math.radians(12), 4, "Z")
		for scale, depth in ((1, 0), (0.68, 0.05), (0.4, 0.1)):
			layer_outline = [root + (point - root) * scale for point in outline]
			add_plate(bm, layer_outline, None, 0.014, matrix=wing_matrix @ Matrix.Translation((0, depth, 0)))
		add_ball(bm, (side * 0.2, 0.56, 0.53), 0.1, (1, 1.1, 1.2))
	deform(bm, curve_back(0.22, 0.3))
	part(bm, "Angel")

	return {
		"attachment": "Back",
		"effects": {
			"Angel": {"gradient": (0.0, 1.3, [(0, "FFD98A"), (0.35, "FFF4DA"), (1, "FFFFFF")])},
		},
	}


#// 08 Cute Bat Wings

def build_cute_bat_wings(part):
	elbow = Vector((0.85, 0.55))
	top = [(0, 0.08), (0.4, 0.38), (0.85, 0.55), (1.35, 0.62), (1.6, 0.45)]
	fingers = [Vector(point) for point in ((1.6, 0.45), (1.3, -0.1), (0.85, -0.38), (0.4, -0.3), (0, -0.1))]

	outline = catmull_rom(top, 4)
	for start, end in zip(fingers, fingers[1:]):
		control = (start + end) / 2
		control = control.lerp(elbow, 0.45)
		for step in range(5):
			t = step / 5
			outline.append((1 - t) ** 2 * start + 2 * (1 - t) * t * control + t ** 2 * end)
	outline = simplify(outline)

	membrane = bmesh.new()
	bones = bmesh.new()
	for side in (-1, 1):
		wing_matrix = Matrix.Translation((side * 0.22, 0.54, 0.6)) @ Matrix.Diagonal((side, 1, 1, 1)) @ Matrix.Rotation(math.radians(12), 4, "Z")
		add_plate(membrane, outline, None, 0.014, matrix=wing_matrix)
		add_sweep(bones, top, [0.07, 0.06, 0.055, 0.04, 0.02], sides=5, smoothness=3, matrix=wing_matrix)
		for finger in fingers[1:4]:
			add_sweep(bones, [elbow, elbow.lerp(finger, 0.5), finger], [0.045, 0.035, 0.015], sides=5, smoothness=2, matrix=wing_matrix)
		claw_base = wing_matrix @ Vector((elbow.x, 0, elbow.y + 0.04))
		claw_direction = wing_matrix.to_3x3() @ Vector((0.25, 0, 1))
		add_spike(bones, claw_base, claw_direction, 0.16, 0.04)
	for side in (-1, 1):
		add_ball(bones, (side * 0.22, 0.53, 0.66), 0.08, (1, 0.7, 1.1))
	deform(membrane, curve_back(0.22, 0.3))
	deform(bones, curve_back(0.22, 0.3))
	part(membrane, "Membrane")
	part(bones, "Bone")

	bm = bmesh.new()
	heart = heart_shape(0.2, steps=28)
	add_plate(bm, heart, [point * 0.6 for point in heart], 0.03, 0.06, Matrix.Translation((0, 0.56, 0.62)))
	part(bm, "Heart")

	return {
		"attachment": "Back",
		"effects": {
			"Membrane": {"gradient": (0.1, 1.3, [(0, "C2A2FF"), (1, "7A4BE0")])},
		},
	}


ACCESSORIES = [
	("ClassicFedora", build_classic_fedora),
	("SkyValkyrieHelm", build_sky_valkyrie_helm),
	("StarryWitchHat", build_starry_witch_hat),
	("RoyalCrown", build_royal_crown),
	("FrogBucketHat", build_frog_bucket_hat),
	("CatEarsHeadband", build_cat_ears_headband),
	("AngelWings", build_angel_wings),
	("CuteBatWings", build_cute_bat_wings),
]


#// Materials

def setup_bake_material(material, key, bake_image, effects=None):
	base, shadow, highlight = material_colors(key)
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
		if kind == "stars":
			cells = node("ShaderNodeTexVoronoi", (x, y))
			cells.inputs["Scale"].default_value = scale
			links.new(coordinates.outputs["Object"], cells.inputs["Vector"])
			dot = map_range(cells.outputs["Distance"], 0.24, 0.12, (x + 200, y))
			return math_node("MULTIPLY", dot, math_node("GREATER_THAN", cells.outputs["Color"], 0.5, (x + 200, y - 150)), (x + 400, y))

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
			element.color = to_color(hex_color)
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

	wear = node("ShaderNodeTexNoise", (-1000, -300))
	wear.inputs["Scale"].default_value = EDGE_WEAR_SCALE
	wear.inputs["Detail"].default_value = 3
	links.new(coordinates.outputs["Object"], wear.inputs["Vector"])
	convex = math_node("MULTIPLY", convex, map_range(wear.outputs["Fac"], 0.35, 0.6, (-800, -300), 0.6, 1), (-200, 200))

	variation = map_range(wear.outputs["Fac"], 0.3, 0.7, (-800, -450))
	light_tone = mix(COLOR_VARIATION, base, highlight, (-400, -400))
	dark_tone = mix(COLOR_VARIATION, base, shadow, (-400, -550))
	color = mix(variation, dark_tone, light_tone, (0, -400))

	for index, (kind, hex_color, scale, strength) in enumerate(effects.get("patterns", ())):
		factor = pattern(kind, scale, (-600, -1200 - index * 300))
		color = mix(math_node("MULTIPLY", factor, strength, (0, -1200 - index * 300)), color, to_color(hex_color), (200, -250 - index * 50))

	color = mix(cavity, color, shadow, (400, 0))
	color = mix(convex, color, highlight, (500, 100))

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


def new_part(name, bm, material, smooth_angle, subdivide):
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
	mesh = bpy.data.meshes.new(name)
	bm.to_mesh(mesh)
	bm.free()
	mesh.materials.append(material)

	part = bpy.data.objects.new(name, mesh)
	bpy.context.scene.collection.objects.link(part)

	if subdivide:
		modifier = part.modifiers.new("Subdivision", "SUBSURF")
		modifier.levels = subdivide
		smooth_mesh = bpy.data.meshes.new_from_object(part.evaluated_get(bpy.context.evaluated_depsgraph_get()))
		part.modifiers.clear()
		part.data = smooth_mesh
		bpy.data.meshes.remove(mesh)

	bm = bmesh.new()
	bm.from_mesh(part.data)
	for face in bm.faces:
		face.smooth = True
	for edge in bm.edges:
		edge.smooth = not (len(edge.link_faces) == 2 and edge.calc_face_angle(0) > math.radians(smooth_angle))
	bm.to_mesh(part.data)
	bm.free()
	return part


def create_outline(root, material):
	# Inverted hull kept as its own black object: a Solidify shell with flipped normals,
	# without the original surface, parented to the model. Its UVs point at the black strip,
	# so joining it into the accessory later still renders black with the accessory texture.
	modifier = root.modifiers.new("Outline", "SOLIDIFY")
	modifier.thickness = OUTLINE_THICKNESS
	modifier.offset = 1
	modifier.use_flip_normals = True
	modifier.use_quality_normals = True
	modifier.use_rim = False
	modifier.material_offset = len(root.data.materials)
	root.data.materials.append(material)

	mesh = bpy.data.meshes.new_from_object(root.evaluated_get(bpy.context.evaluated_depsgraph_get()))
	root.modifiers.remove(modifier)
	root.data.materials.pop()
	bm = bmesh.new()
	bm.from_mesh(mesh)
	bmesh.ops.delete(bm, geom=[face for face in bm.faces if face.material_index < len(root.data.materials)], context="FACES")
	uv_layer = bm.loops.layers.uv.active
	for face in bm.faces:
		face.material_index = 0
		for loop in face.loops:
			loop[uv_layer].uv = (OUTLINE_STRIP / 2, 0.5)
	bm.to_mesh(mesh)
	bm.free()
	mesh.name = root.name + "Outline"
	mesh.materials.clear()
	mesh.materials.append(material)

	outline = bpy.data.objects.new(root.name + "Outline", mesh)
	for collection in root.users_collection:
		collection.objects.link(outline)
	outline.parent = root
	outline.matrix_parent_inverse = Matrix()
	return outline


def build_accessory(name, build, collection, outline_material):
	parts = []

	def part(bm, key, smooth_angle=SMOOTH_ANGLE, subdivide=0):
		material = bpy.data.materials.get(name + key)
		if not material:
			material = bpy.data.materials.new(name + key)
			material.use_nodes = True
			material["Key"] = key
		parts.append(new_part(name + key, bm, material, smooth_angle, subdivide))

	details = build(part)

	select_only(parts)
	bpy.ops.object.join()
	accessory = bpy.context.view_layer.objects.active
	accessory.name = name
	accessory.data.name = name
	accessory["Attachment"] = details["attachment"]

	texture = bpy.data.images.new(name, TEXTURE_SIZE, TEXTURE_SIZE)
	effects = details.get("effects", {})
	for material in accessory.data.materials:
		setup_bake_material(material, material["Key"], texture, effects.get(material["Key"]))

	select_only([accessory])
	bpy.ops.object.mode_set(mode="EDIT")
	bpy.ops.mesh.select_all(action="SELECT")
	bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=UV_MARGIN, scale_to_bounds=True)
	bpy.ops.object.mode_set(mode="OBJECT")
	for loop in accessory.data.uv_layers.active.data:
		loop.uv.x = OUTLINE_STRIP + OUTLINE_STRIP_GAP + loop.uv.x * (1 - OUTLINE_STRIP - OUTLINE_STRIP_GAP)

	bpy.ops.object.bake(type="EMIT")

	pixels = numpy.empty(TEXTURE_SIZE * TEXTURE_SIZE * 4, dtype=numpy.float32)
	texture.pixels.foreach_get(pixels)
	pixels = pixels.reshape(TEXTURE_SIZE, TEXTURE_SIZE, 4)
	pixels[:, :math.ceil(TEXTURE_SIZE * OUTLINE_STRIP)] = to_srgb(OUTLINE_COLOR) + [1]
	texture.pixels.foreach_set(pixels.ravel())

	accessory.data.materials.clear()
	accessory.data.materials.append(create_final_material(name, texture))
	for polygon in accessory.data.polygons:
		polygon.material_index = 0
	for user_collection in list(accessory.users_collection):
		user_collection.objects.unlink(accessory)
	collection.objects.link(accessory)
	create_outline(accessory, outline_material)

	return accessory, texture


def export_accessory(accessory, texture):
	texture.filepath_raw = os.path.join(EXPORT_FOLDER, accessory.name + ".png")
	texture.file_format = "PNG"
	texture.save()

	original_location = accessory.location.copy()
	accessory.location = (0, 0, 0)

	# The outline is its own <Accessory>Outline mesh next to the accessory mesh.
	select_only([accessory] + list(accessory.children))
	bpy.ops.export_scene.fbx(
		filepath=os.path.join(EXPORT_FOLDER, accessory.name + ".fbx"),
		use_selection=True,
		object_types={"MESH"},
		axis_forward="Z",
		axis_up="Y",
		path_mode="COPY",
		embed_textures=True,
	)
	accessory.location = original_location


def main():
	clear_scene()
	scene = bpy.context.scene
	scene.render.engine = "CYCLES"
	scene.cycles.device = "CPU"
	scene.cycles.samples = BAKE_SAMPLES
	scene.render.bake.margin = 8

	collection = bpy.data.collections.new("UGCPack")
	scene.collection.children.link(collection)
	outline_material = create_outline_material()

	accessories = []
	for index, (name, build) in enumerate(ACCESSORIES):
		accessory, texture = build_accessory(name, build, collection, outline_material)
		accessory.location.x = index * PACK_SPACING
		accessories.append((accessory, texture))

	if EXPORT_FOLDER:
		os.makedirs(EXPORT_FOLDER, exist_ok=True)
		for accessory, texture in accessories:
			export_accessory(accessory, texture)

	for _, texture in accessories:
		texture.pack()

	return [accessory for accessory, _ in accessories]


if __name__ == "__main__":
	main()
