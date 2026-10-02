import bpy
import bmesh
import math
import os
import numpy
from mathutils import Matrix, Vector

# Run inside Blender 4.1+: Scripting tab -> Open -> Run Script.
# Builds a stylized low poly sword, bakes a hand-painted curvature texture
# (edge highlights, cavity shadows, face cracks) into one image and exports it for Roblox.

SWORD_NAME = "CleaverSword"

TEXTURE_SIZE = 1024
BAKE_SAMPLES = 64
UV_MARGIN = 0.008

SMOOTH_ANGLE = 22

#// Curvature Look

EDGE_BEVEL_RADIUS = 0.035
EDGE_START = 0.996  # dot(normal, bevelNormal) where the highlight starts
EDGE_FULL = 0.94  # dot(normal, bevelNormal) where the highlight is at full strength
EDGE_WEAR_SCALE = 7
CAVITY_DISTANCE = 0.22
COLOR_VARIATION = 0.07
BEVEL_BRIGHTNESS = 0.45  # how much lighter the blade chamfer is than its flat center
LENGTH_GRADIENT = 0.25  # darkens the sword towards the pommel
SWORD_BOTTOM = -0.9
SWORD_TOP = 3.95

#// Blade Shape

BLADE_EDGE_THICKNESS = 0.02
BLADE_CENTER_THICKNESS = 0.11
OUTLINE_SMOOTHNESS = 3
OUTLINE_TOLERANCE = 0.006  # points closer than this to a straight line are removed

# Leave empty to skip. Otherwise the FBX and texture are written into this folder.
EXPORT_FOLDER = os.path.join(os.path.dirname(bpy.data.filepath), "Export") if bpy.data.filepath else ""

# Base, shadow and highlight color of every material.
PALETTE = {
	"Steel": ("8A9CB0", "2C3850", "EEF5FF"),
	"Gold": ("E9A73B", "7A3A14", "FFE7A1"),
	"Leather": ("70432A", "2A150E", "B07A52"),
	"Gem": ("E8384F", "5E0E2A", "FFC2CC"),
}

# Outer blade outline, counter clockwise. Every list is one smooth curve, corners sit between lists.
BLADE_OUTLINE = [
	[(0.30, 0.90), (0.40, 1.04), (0.40, 2.20), (0.41, 3.12), (0.47, 3.42), (0.64, 3.62)],
	[(0.64, 3.62), (0.50, 3.80), (0.18, 3.92), (-0.18, 3.93), (-0.46, 3.84), (-0.66, 3.68)],
	[(-0.66, 3.68), (-0.48, 3.50), (-0.42, 3.20), (-0.40, 2.20), (-0.40, 1.04), (-0.30, 0.90)],
	[(-0.30, 0.90), (0.30, 0.90)],
]

# Raised flat center of the blade, the space between both outlines becomes the chamfer.
BLADE_PLATEAU = [
	[(0.20, 0.97), (0.28, 1.10), (0.28, 2.20), (0.29, 3.12), (0.34, 3.40), (0.44, 3.57)],
	[(0.44, 3.57), (0.36, 3.70), (0.15, 3.78), (-0.15, 3.79), (-0.36, 3.73), (-0.46, 3.62)],
	[(-0.46, 3.62), (-0.34, 3.47), (-0.30, 3.20), (-0.28, 2.20), (-0.28, 1.10), (-0.20, 0.97)],
	[(-0.20, 0.97), (0.20, 0.97)],
]

# Chips cut into the blade edge: position, width, depth, skew along the edge.
BLADE_NOTCHES = [
	((0.40, 2.75), 0.11, 0.09, 0.25),
	((0.40, 1.38), 0.07, 0.05, -0.2),
	((-0.40, 1.55), 0.15, 0.11, 0.3),
	((-0.40, 2.40), 0.06, 0.05, 0),
	((-0.44, 3.32), 0.07, 0.05, -0.3),
	((0.30, 3.89), 0.08, 0.06, 0.2),
	((0.55, 3.53), 0.06, 0.04, 0),
]

# Cracks painted on the flat of the blade, as polylines in blade space.
BLADE_CRACKS = [
	[(0.24, 3.16), (0.16, 3.09), (0.22, 3.03), (0.12, 2.95)],
	[(-0.26, 3.44), (-0.17, 3.37), (-0.23, 3.31), (-0.15, 3.25)],
	[(0.25, 2.76), (0.15, 2.72), (0.19, 2.64)],
	[(-0.25, 1.66), (-0.15, 1.60), (-0.21, 1.53), (-0.11, 1.46)],
	[(0.25, 1.42), (0.16, 1.38), (0.19, 1.30)],
	[(-0.08, 3.74), (-0.03, 3.66), (-0.09, 3.60)],
	[(-0.25, 2.44), (-0.16, 2.38), (-0.19, 2.32)],
]
CRACK_WIDTH = 0.02
CRACK_MASK_RESOLUTION = 400  # pixels per unit

#// Guard, Grip and Pommel

RING_CENTER = 0.48
RING_RADIUS = 0.26
RING_THICKNESS = 0.06
SPIKE_ANGLE = 22
SPIKE_LENGTH = 0.3

GRIP_TOP = 0.11
GRIP_RADIUS = 0.064
GRIP_WRAP_RADIUS = 0.078
GRIP_WRAPS = 7
GRIP_WRAP_LENGTH = 0.1


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


def build_outline(curves):
	outline = []
	for curve in curves:
		outline += catmull_rom(curve, OUTLINE_SMOOTHNESS)

	removed = True
	while removed:
		removed = False
		for i in range(len(outline)):
			previous, current, following = outline[i - 1], outline[i], outline[(i + 1) % len(outline)]
			edge = following - previous
			distance = abs(edge.x * (current.y - previous.y) - edge.y * (current.x - previous.x)) / edge.length
			if distance < OUTLINE_TOLERANCE:
				outline.pop(i)
				removed = True
				break
	return outline


def point_at_distance(outline, lengths, distance):
	for i in range(len(outline)):
		if lengths[i + 1] >= distance:
			t = (distance - lengths[i]) / max(lengths[i + 1] - lengths[i], 1e-6)
			start = outline[i]
			end = outline[(i + 1) % len(outline)]
			return start.lerp(end, t), (end - start).normalized()
	return outline[0], (outline[1] - outline[0]).normalized()


def cut_notch(outline, position, width, depth, skew):
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


#// Mesh Helpers

def new_part(name, bm, material, smooth_angle=SMOOTH_ANGLE):
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


def add_box(bm, size, location, bevel):
	result = bmesh.ops.create_cube(bm, size=1, matrix=Matrix.LocRotScale(Vector(location), None, Vector(size)))
	edges = list({edge for vert in result["verts"] for edge in vert.link_edges})
	bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=1, affect="EDGES", profile=0.5)


#// Blade

def build_blade(material):
	outline = build_outline(BLADE_OUTLINE)
	for position, width, depth, skew in BLADE_NOTCHES:
		outline = cut_notch(outline, position, width, depth, skew)
	plateau = build_outline(BLADE_PLATEAU)

	bm = bmesh.new()
	sides = {}
	for side in (-1, 1):
		outer = [bm.verts.new((point.x, side * BLADE_EDGE_THICKNESS, point.y)) for point in outline]
		inner = [bm.verts.new((point.x, side * BLADE_CENTER_THICKNESS, point.y)) for point in plateau]
		bridge_loops(bm, outer, inner)
		bm.faces.new(inner)
		sides[side] = outer

	front, back = sides[-1], sides[1]
	for i in range(len(outline)):
		bm.faces.new((front[i - 1], front[i], back[i], back[i - 1]))

	bm.normal_update()
	bmesh.ops.triangulate(bm, faces=[face for face in bm.faces if len(face.verts) > 4], ngon_method="BEAUTY")
	return new_part("Blade", bm, material)


def build_collar(material):
	bm = bmesh.new()
	add_box(bm, (0.70, 0.24, 0.13), (0, 0, 0.87), 0.03)
	add_box(bm, (0.50, 0.21, 0.08), (0, 0, 0.77), 0.025)
	return new_part("Collar", bm, material)


#// Guard

def build_guard(gold, steel, gem):
	bm = bmesh.new()
	add_torus(bm, RING_RADIUS, RING_THICKNESS, 18, 8, Matrix.Translation((0, 0, RING_CENTER)))
	add_box(bm, (0.15, 0.18, 0.12), (0, 0, RING_CENTER - RING_RADIUS - 0.02), 0.02)

	spike_roots = []
	for side in (-1, 1):
		angle = math.radians(SPIKE_ANGLE)
		root = Vector((side * math.cos(angle) * RING_RADIUS, 0, RING_CENTER + math.sin(angle) * RING_RADIUS))
		bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.075, matrix=Matrix.Translation(root))
		spike_roots.append((root, Vector((side * math.cos(angle * 1.6), 0, math.sin(angle * 1.6)))))
	guard = new_part("Guard", bm, gold)

	bm = bmesh.new()
	for root, direction in spike_roots:
		rotation = Vector((0, 0, 1)).rotation_difference(direction).to_matrix().to_4x4()
		matrix = Matrix.Translation(root + direction * 0.04) @ rotation
		add_lathe(bm, [(0.055, 0), (0.05, 0.06), (0, SPIKE_LENGTH)], 6, matrix)
	spikes = new_part("Spikes", bm, steel)

	bm = bmesh.new()
	profile = [(0, -0.17), (0.07, -0.07), (0.085, 0), (0.07, 0.07), (0, 0.17)]
	add_lathe(bm, profile, 6, Matrix.LocRotScale(Vector((0, 0, RING_CENTER)), None, Vector((1, 0.6, 1))))
	gem_part = new_part("Gem", bm, gem, smooth_angle=1)

	return [guard, spikes, gem_part]


#// Grip and Pommel

def build_grip(leather, gold):
	bm = bmesh.new()
	height = GRIP_TOP
	profile = [(GRIP_RADIUS, height + 0.02)]
	for _ in range(GRIP_WRAPS):
		profile += [
			(GRIP_RADIUS, height),
			(GRIP_WRAP_RADIUS, height - GRIP_WRAP_LENGTH * 0.2),
			(GRIP_WRAP_RADIUS, height - GRIP_WRAP_LENGTH * 0.7),
			(GRIP_RADIUS, height - GRIP_WRAP_LENGTH * 0.9),
		]
		height -= GRIP_WRAP_LENGTH
	profile.append((GRIP_RADIUS, height - 0.02))
	add_lathe(bm, profile, 8)
	grip = new_part("Grip", bm, leather)

	bm = bmesh.new()
	add_lathe(bm, [(0.06, GRIP_TOP - 0.03), (0.095, GRIP_TOP - 0.01), (0.095, GRIP_TOP + 0.04), (0.05, GRIP_TOP + 0.07)], 8)
	bottom = height
	add_lathe(bm, [
		(0.05, bottom + 0.02),
		(0.095, bottom - 0.01),
		(0.095, bottom - 0.05),
		(0.05, bottom - 0.08),
		(0.068, bottom - 0.12),
		(0.05, bottom - 0.17),
		(0, bottom - 0.19),
	], 8)
	add_torus(bm, 0.055, 0.018, 10, 6, Matrix.Translation((0, 0, bottom - 0.24)))
	pommel = new_part("Pommel", bm, gold)

	return [grip, pommel]


#// Bake Materials

def create_crack_mask():
	points = [point for curve in BLADE_OUTLINE for point in curve]
	min_x = min(point[0] for point in points)
	min_z = min(point[1] for point in points)
	width = max(point[0] for point in points) - min_x
	height = max(point[1] for point in points) - min_z

	pixel_width = int(width * CRACK_MASK_RESOLUTION)
	pixel_height = int(height * CRACK_MASK_RESOLUTION)
	x = min_x + (numpy.arange(pixel_width) + 0.5) / CRACK_MASK_RESOLUTION
	z = min_z + (numpy.arange(pixel_height) + 0.5) / CRACK_MASK_RESOLUTION
	grid_x, grid_z = numpy.meshgrid(x, z)

	def stroke_mask(offset):
		mask = numpy.zeros_like(grid_x)
		for crack in BLADE_CRACKS:
			for i in range(len(crack) - 1):
				start = numpy.array(crack[i]) + offset
				end = numpy.array(crack[i + 1]) + offset
				edge = end - start
				t = numpy.clip(((grid_x - start[0]) * edge[0] + (grid_z - start[1]) * edge[1]) / edge.dot(edge), 0, 1)
				distance = numpy.hypot(grid_x - start[0] - t * edge[0], grid_z - start[1] - t * edge[1])
				taper = 1 - (i + t) / (len(crack) - 1) * 0.6
				pixel = 1 / CRACK_MASK_RESOLUTION
				mask = numpy.maximum(mask, numpy.clip((CRACK_WIDTH * taper - distance) / pixel + 0.5, 0, 1))
		return mask

	dark = stroke_mask(numpy.array((0, 0)))
	light = numpy.clip(stroke_mask(numpy.array((0.008, -0.008))) - dark, 0, 1)

	image = bpy.data.images.get("CrackMask") or bpy.data.images.new("CrackMask", pixel_width, pixel_height)
	image.scale(pixel_width, pixel_height)
	pixels = numpy.stack([dark, light, numpy.zeros_like(dark), numpy.ones_like(dark)], axis=-1)
	image.pixels.foreach_set(pixels.astype(numpy.float32).ravel())
	image.pack()
	return image, (min_x, min_z, width, height)


def create_bake_material(name, bake_image, crack_mask=None):
	base, shadow, highlight = (to_color(color) for color in PALETTE[name])
	material = bpy.data.materials.new(name)
	material.use_nodes = True
	nodes = material.node_tree.nodes
	links = material.node_tree.links
	nodes.clear()

	def node(node_type, location, **properties):
		new_node = nodes.new(node_type)
		new_node.location = location
		for key, property_value in properties.items():
			setattr(new_node, key, property_value)
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

	separate = node("ShaderNodeSeparateXYZ", (-1000, -800))
	links.new(coordinates.outputs["Object"], separate.inputs[0])
	gradient = map_range(separate.outputs["Z"], SWORD_TOP, SWORD_BOTTOM, (-800, -1000), 0, LENGTH_GRADIENT)
	color = mix(gradient, color, shadow, (100, -300))

	if crack_mask:
		normal = node("ShaderNodeSeparateXYZ", (-1000, 500))
		links.new(geometry.outputs["Normal"], normal.inputs[0])
		flat = map_range(math_node("ABSOLUTE", normal.outputs["Y"], 0, (-800, 500)), 0.97, 0.995, (-600, 500))
		chamfer = map_range(flat, 1, 0, (-400, 500), 0, BEVEL_BRIGHTNESS)
		color = mix(chamfer, color, highlight, (150, -150))

	color = mix(cavity, color, shadow, (200, 0))
	color = mix(convex, color, highlight, (400, 100))

	if crack_mask:
		image, (min_x, min_z, width, height) = crack_mask
		combine = node("ShaderNodeCombineXYZ", (-600, -800))
		links.new(map_range(separate.outputs["X"], min_x, min_x + width, (-800, -750)), combine.inputs["X"])
		links.new(map_range(separate.outputs["Z"], min_z, min_z + height, (-800, -900)), combine.inputs["Y"])
		mask = node("ShaderNodeTexImage", (-400, -800), image=image, extension="CLIP")
		links.new(combine.outputs[0], mask.inputs["Vector"])
		channels = node("ShaderNodeSeparateColor", (-150, -800))
		links.new(mask.outputs["Color"], channels.inputs[0])

		color = mix(math_node("MULTIPLY", channels.outputs["Red"], flat, (100, -700)), color, shadow, (600, -100))
		color = mix(math_node("MULTIPLY", channels.outputs["Green"], flat, (100, -850)), color, highlight, (800, -100))

	emission = node("ShaderNodeEmission", (1000, 0))
	links.new(color, emission.inputs["Color"])
	output = node("ShaderNodeOutputMaterial", (1200, 0))
	links.new(emission.outputs[0], output.inputs["Surface"])

	target = node("ShaderNodeTexImage", (1000, 300), image=bake_image)
	nodes.active = target
	return material


def create_final_material(texture):
	material = bpy.data.materials.new(SWORD_NAME)
	material.use_nodes = True
	shader = material.node_tree.nodes["Principled BSDF"]
	shader.inputs["Roughness"].default_value = 0.65
	image_node = material.node_tree.nodes.new("ShaderNodeTexImage")
	image_node.image = texture
	image_node.location = (-400, 300)
	material.node_tree.links.new(image_node.outputs["Color"], shader.inputs["Base Color"])
	return material


#// Build

def clear_scene():
	for collection in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images):
		for block in list(collection):
			if block.name != "Render Result":
				collection.remove(block)


def join_parts(parts):
	bpy.ops.object.select_all(action="DESELECT")
	for part in parts:
		part.select_set(True)
	bpy.context.view_layer.objects.active = parts[0]
	bpy.ops.object.join()

	sword = bpy.context.view_layer.objects.active
	sword.name = SWORD_NAME
	sword.data.name = SWORD_NAME
	return sword


def unwrap(sword):
	bpy.ops.object.mode_set(mode="EDIT")
	bpy.ops.mesh.select_all(action="SELECT")
	bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=UV_MARGIN, scale_to_bounds=True)
	bpy.ops.object.mode_set(mode="OBJECT")


def bake(sword, image):
	scene = bpy.context.scene
	scene.render.engine = "CYCLES"
	scene.cycles.device = "CPU"
	scene.cycles.samples = BAKE_SAMPLES
	scene.render.bake.margin = 8

	bpy.ops.object.select_all(action="DESELECT")
	sword.select_set(True)
	bpy.context.view_layer.objects.active = sword
	bpy.ops.object.bake(type="EMIT")


def main():
	clear_scene()
	bake_image = bpy.data.images.new(SWORD_NAME + "Texture", TEXTURE_SIZE, TEXTURE_SIZE)
	crack_mask = create_crack_mask()

	steel = create_bake_material("Steel", bake_image, crack_mask)
	gold = create_bake_material("Gold", bake_image)
	leather = create_bake_material("Leather", bake_image)
	gem = create_bake_material("Gem", bake_image)

	parts = [build_blade(steel), build_collar(gold)]
	parts += build_guard(gold, steel, gem)
	parts += build_grip(leather, gold)

	sword = join_parts(parts)
	unwrap(sword)
	bake(sword, bake_image)

	sword.data.materials.clear()
	sword.data.materials.append(create_final_material(bake_image))
	for polygon in sword.data.polygons:
		polygon.material_index = 0

	if EXPORT_FOLDER:
		os.makedirs(EXPORT_FOLDER, exist_ok=True)
		bake_image.filepath_raw = os.path.join(EXPORT_FOLDER, SWORD_NAME + ".png")
		bake_image.file_format = "PNG"
		bake_image.save()

		bpy.ops.export_scene.fbx(
			filepath=os.path.join(EXPORT_FOLDER, SWORD_NAME + ".fbx"),
			use_selection=True,
			object_types={"MESH"},
			path_mode="COPY",
			embed_textures=True,
		)

	return sword


if __name__ == "__main__":
	main()
