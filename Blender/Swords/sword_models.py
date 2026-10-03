import bpy
import bmesh
import math
import os
import numpy
import mathutils.bvhtree
from mathutils import Matrix, Vector

# Run inside Blender 4.1+: Scripting tab -> Open -> Run Script.
# Builds a pack of stylized low poly swords for one world, from a common sword up to a Robux exclusive.
# Every sword gets its own hand-painted curvature texture (edge highlights, cavity shadows, wear,
# painted decals) baked into one image, auto smooth shading and an FBX export for Roblox.
# Glowing parts are split into their own mesh named <Sword><Material>, meant to become Neon in Roblox.
# The black inverted hull outline is a separate object named <Sword>Outline, parented to the sword.

WORLD = "Starter"  # which pack to build, see WORLDS: "Starter", "Desert", "Halloween", "Atlantis", "Magma" or "Robux"

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
PLATEAU_SPACING = 0.12  # longest plateau edge before the chamfer gets split
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
	"CandyCorn": ("FFB02E", "A8501E", "FFF4D0"),
	"Wrapper": ("A84AE0", "4A1A7A", "E0B0FF"),
	"CandyStick": ("FFF6E6", "B8A890", "FFFFFF"),
	"CandyWhite": ("FFF6E6", "B8A890", "FFFFFF"),
	"Lollipop": ("FF4FA0", "8A1A50", "FFB8DA"),
	"Straw": ("E8C25A", "8A6A1E", "FFF0A0"),
	"Burlap": ("B08A5A", "5A4028", "E0C090"),
	"GraveStone": ("8A8E9A", "3A3C48", "C8CCD8"),
	"IronBlack": ("3A3A44", "121218", "7A7A8A"),
	"Pumpkin": ("FF8A1F", "A8380E", "FFC06A"),
	"PumpkinGlow": ("FFD23A", "C07A0E", "FFF6C0"),
	"Vine": ("4E9A35", "1E4A1A", "9ADA6A"),
	"Leaf": ("6AB84A", "2A5A1E", "B0E880"),
	"BatWing": ("4A2E6A", "1A0E2A", "9A7AC0"),
	"BatBody": ("2E2238", "0E0812", "6A5A80"),
	"BatEye": ("FF3A3A", "8A0E0E", "FFB0B0"),
	"SpiderBlade": ("2A2630", "0E0C12", "6A6478"),
	"SpiderBody": ("1E1A24", "08060A", "5A5068"),
	"Hourglass": ("E8202E", "6A0810", "FF8A8A"),
	"Web": ("ECECF6", "8A8AA0", "FFFFFF"),
	"Potion": ("6AE05A", "1E7A2E", "D0FFB0"),
	"PotionGlow": ("9CFF5A", "3A9A1E", "E8FFD0"),
	"Cauldron": ("2E2A36", "0E0C12", "6A6478"),
	"WitchPurple": ("6A3AB0", "2A1258", "B08AF0"),
	"ReaperSteel": ("5A6070", "1E2028", "B0B8C8"),
	"ReaperGlow": ("B06AFF", "5A1AB0", "E8D0FF"),
	"ReaperWood": ("3A2E28", "140E0C", "7A6050"),
	"Cloth": ("3A3248", "14101C", "7A6A90"),
	"Ghost": ("E8F4FF", "7A9AC0", "FFFFFF"),
	"GhostGlow": ("8AF0FF", "1E8AB0", "E8FFFF"),
	"Chain": ("6A6E7A", "22242C", "B0B4C0"),
	"Vampire": ("B01E2E", "4A0812", "FF7A7A"),
	"BloodGlow": ("FF2E3A", "8A0612", "FFB0B0"),
	"Rose": ("D81E3A", "5A0814", "FF7A8A"),
	"Horseman": ("2A2230", "0C080E", "6A5A78"),
	"HellFire": ("FF8A2E", "C0380E", "FFE8A0"),
	"NightmareBlade": ("2A1A40", "0A0614", "8A6AD0"),
	"SoulGlow": ("7CFF9A", "1E9A4A", "E0FFE8"),
	"SoulCarve": ("7CFF9A", "1E9A4A", "E0FFE8"),
	"SeaStone": ("6A8A9A", "2A3A4A", "B0C8D8"),
	"Kelp": ("4E9A4A", "1E4A2A", "9AD88A"),
	"KelpDark": ("2E6A3A", "0E2A1A", "6AA86A"),
	"Driftwood": ("9A7A5A", "4A3A2A", "D0B898"),
	"Shell": ("FFE3D6", "B88A7A", "FFFFFF"),
	"Coral": ("FF6F7F", "8A1E3A", "FFC2C8"),
	"CoralDeep": ("E04A6A", "6A1030", "FF9AAA"),
	"Pearl": ("F4F0FF", "9A94B8", "FFFFFF"),
	"ShellPink": ("FFB3C2", "A85A6A", "FFE0E8"),
	"Sea": ("3AA8E0", "0E4A8A", "A8E8FF"),
	"SharkTooth": ("F4F0E6", "9A9480", "FFFFFF"),
	"SharkSkin": ("6A8AA8", "2A3A5A", "B0C8E0"),
	"Abyss": ("1E2A4A", "080C1A", "5A6A9A"),
	"AbyssBody": ("26304E", "0A0E1E", "5A6A9A"),
	"LureGlow": ("9CFFE8", "2AB8A0", "F0FFFA"),
	"Jelly": ("C89AFF", "6A3AB0", "F0E0FF"),
	"JellyBell": ("B07AE8", "5A2A9A", "F0D8FF"),
	"JellyGlow": ("FF8AE0", "B03A9A", "FFE0F6"),
	"AtlantisGlow": ("6AFFF0", "0EA8B8", "E8FFFF"),
	"OceanKing": ("2E7AE0", "0E2A6A", "A8D8FF"),
	"AbyssPurple": ("4A1E6A", "1A0828", "A87AD8"),
	"Octopus": ("B04AA8", "4A0E4A", "F08AE0"),
	"Sucker": ("FFC2E8", "B0709A", "FFF0FA"),
	"Atlantean": ("4FE0D0", "0E6A7A", "D0FFFA"),
	"Marble": ("F2F0EA", "A8A498", "FFFFFF"),
	"Leviathan": ("2E8AA0", "0E3A4A", "8AE0E8"),
	"Fin": ("4FC8D8", "1E6A7A", "B8F4FA"),
	"Kraken": ("3A1A5A", "12061E", "8A5AC0"),
	"KrakenSkin": ("6A2A8A", "240A36", "C08AE8"),
	"KrakenEye": ("FFD23A", "B8700E", "FFF6C0"),
	"PearlGlow": ("F4FAFF", "8AB8E0", "FFFFFF"),
	"Basalt": ("5A5A64", "22222A", "9A9AA8"),
	"BasaltDark": ("3A3A44", "121218", "7A7A88"),
	"Ember": ("4A3A3A", "1A1212", "8A6A6A"),
	"EmberGlow": ("FF8A2E", "C0380E", "FFE0A0"),
	"Obsidian": ("2A2238", "0A0612", "7A6AA0"),
	"VolcanoRock": ("4A3A34", "1A1210", "8A7268"),
	"Salamander": ("FF5A2E", "8A1A0E", "FFB08A"),
	"SalamanderSpot": ("FFD23A", "B8700E", "FFF0A0"),
	"VolcanoDark": ("3A2A24", "140C0A", "7A5A4A"),
	"LavaGlow": ("FF6A1E", "A8200E", "FFD27A"),
	"GolemRock": ("6A5248", "2A1E1A", "A88A7A"),
	"GolemBoulder": ("6A5248", "2A1E1A", "A88A7A"),
	"PhoenixFeather": ("FF7A2E", "B8300E", "FFE07A"),
	"PhoenixWing": ("FF9A3A", "C0400E", "FFE8A0"),
	"PhoenixGlow": ("FFC23A", "D8600E", "FFF6C0"),
	"InfernoSteel": ("3A3440", "121016", "8A8098"),
	"KatanaWrap": ("B01E2E", "4A0812", "F07A7A"),
	"DragonSteel": ("3A2228", "120A0C", "8A5A60"),
	"Dragon": ("B0201E", "4A0808", "FF7A6A"),
	"DragonFire": ("FFA02E", "C8400E", "FFF0A0"),
	"MoltenCore": ("2A2228", "0A0608", "6A5A68"),
	"CoreGlow": ("FFB02E", "C8500E", "FFF0B0"),
	"MagmaTitan": ("1E1A22", "08060A", "5A5068"),
	"TitanGlow": ("FF5A1E", "A8180E", "FFD08A"),
	"Galaxy": ("3A1E8A", "120838", "A88AFF"),
	"GalaxyGlow": ("FF6AE8", "A81A9A", "FFE0FA"),
	"StarCore": ("FFF6A0", "D8A82E", "FFFFFF"),
	"CosmicGlow": ("6AE8FF", "1E8AC8", "E8FFFF"),
	"AbyssMouth": ("4A0E1E", "14040A", "8A2A3A"),
	"AncientBronze": ("4E8A7A", "1E3A34", "A8D8C8"),
	"BronzeShaft": ("4E8A7A", "1E3A34", "A8D8C8"),
	"Barnacle": ("D8D0C0", "6A6458", "FFFFFF"),
	"SickleSteel": ("9AA2AE", "3A3F4A", "E6ECF4"),
	"Crow": ("2E2E3E", "0E0E14", "6E6E8E"),
	"Beak": ("F7A93A", "8A4A0E", "FFE0A0"),
	"Moss": ("6AA84A", "25501E", "B0E07A"),
	"Dirt": ("6E4A30", "2E1C10", "A87A52"),
	"SpiderEye": ("FF2E3A", "8A0612", "FFB0B0"),
	"Spirit": ("F4FAFF", "8AA6C8", "FFFFFF"),
	"Blush": ("FF9AB8", "B8506E", "FFD0E0"),
	"GhostEye": ("2A3050", "0C0E1E", "5A6890"),
	"Cape": ("6A1E2A", "1E060C", "A04A58"),
}

# Materials split into their own mesh so they can be set to Neon in Roblox.
GLOW_MATERIALS = {
	"FireGem", "Flame", "DemonGlow", "DemonEye", "StarGlow", "HaloGlow", "VoidGlow", "VoidCyan",
	"Venom", "CurseGlow", "SandGlow", "SunGlow", "DjinnGlow", "DjinnSmoke",
	"PumpkinGlow", "BatEye", "PotionGlow", "ReaperGlow", "GhostGlow", "BloodGlow", "HellFire", "SoulGlow", "SpiderEye", "SoulCarve",
	"LureGlow", "JellyGlow", "AtlantisGlow", "KrakenEye", "PearlGlow", "EmberGlow", "LavaGlow", "PhoenixGlow",
	"DragonFire", "CoreGlow", "TitanGlow", "GalaxyGlow", "StarCore", "CosmicGlow",
}

# Glow parts carved into a model get no outline, it would poke into the carving.
CARVED_MATERIALS = {"PumpkinGlow", "SoulCarve"}


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
	# Zips the outline to the plateau. Every outline point is matched to where its closest point sits
	# along the plateau, so tight curls, notches and teeth can't make the chamfer fold over itself.
	inner_points = [vert.co.xz for vert in inner]
	lengths = [0]
	for i, point in enumerate(inner_points):
		lengths.append(lengths[-1] + (inner_points[(i + 1) % len(inner)] - point).length)
	total = lengths[-1]

	def project(point):
		best_distance, best_position = math.inf, 0
		for i, start in enumerate(inner_points):
			edge = inner_points[(i + 1) % len(inner)] - start
			t = max(0, min(1, (point - start).dot(edge) / max(edge.length_squared, 1e-12)))
			distance = (start + edge * t - point).length
			if distance < best_distance:
				best_distance, best_position = distance, lengths[i] + t * edge.length
		return best_position

	origin = project(outer[0].co.xz)
	outer_positions = []
	for vert in outer:
		position = (project(vert.co.xz) - origin) % total
		if outer_positions and (position < outer_positions[-1] or position - outer_positions[-1] > total / 2):
			position = outer_positions[-1]
		outer_positions.append(position)

	inner_positions = [(length - origin) % total for length in lengths[:-1]]
	start = min(range(len(inner)), key=lambda j: inner_positions[j])
	inner = inner[start:] + inner[:start]
	inner_positions = inner_positions[start:] + inner_positions[:start]

	def winding(a, b, c):
		a, b, c = a.co.xz, b.co.xz, c.co.xz
		return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)

	points = [vert.co.xz for vert in outer]
	orientation = 1 if sum(a.x * b.y - b.x * a.y for a, b in zip(points, points[1:] + points[:1])) > 0 else -1

	i = j = 0
	while i < len(outer) or j < len(inner):
		next_outer = outer_positions[i + 1] if i + 1 < len(outer) else total
		next_inner = inner_positions[j + 1] if j + 1 < len(inner) else total
		advance_outer = j >= len(inner) or (i < len(outer) and next_outer <= next_inner)
		if i < len(outer) and j < len(inner) and abs(next_outer - next_inner) < 0.2:
			outer_flipped = winding(outer[i], outer[(i + 1) % len(outer)], inner[j]) * orientation < -1e-7
			inner_flipped = winding(outer[i], inner[(j + 1) % len(inner)], inner[j]) * orientation < -1e-7
			if advance_outer and outer_flipped and not inner_flipped:
				advance_outer = False
			elif not advance_outer and inner_flipped and not outer_flipped:
				advance_outer = True
		if advance_outer:
			bm.faces.new((outer[i], outer[(i + 1) % len(outer)], inner[j % len(inner)]))
			i += 1
		else:
			bm.faces.new((outer[i % len(outer)], inner[(j + 1) % len(inner)], inner[j]))
			j += 1


def densify(points, spacing=PLATEAU_SPACING):
	# Extra points along long straight plateau edges give the chamfer zipper close partners everywhere.
	result = []
	for i, point in enumerate(points):
		following = points[(i + 1) % len(points)]
		steps = max(1, math.ceil((following - point).length / spacing))
		result += [point.lerp(following, step / steps) for step in range(steps)]
	return result


def add_plate(bm, outline, plateau=None, edge_thickness=BLADE_EDGE_THICKNESS, center_thickness=BLADE_CENTER_THICKNESS, matrix=Matrix()):
	# Flat shape in the XZ plane. With a plateau the center is raised and the rim becomes a chamfer.
	new_verts = []
	sides = {}
	for side in (-1, 1):
		outer = [bm.verts.new((point.x, side * edge_thickness, point.y)) for point in outline]
		new_verts += outer
		sides[side] = outer
		if plateau:
			inner = [bm.verts.new((point.x, side * center_thickness, point.y)) for point in densify(plateau)]
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

#// Halloween Event

def new_verts_since(bm, before):
	return [vert for vert in bm.verts if vert not in before]


def add_pumpkin(bm, center, radius, height=0.78, ribs=8, sides=16, rings=8):
	before = set(bm.verts)
	profile = [(radius * math.sin(math.pi * i / rings), -radius * height * math.cos(math.pi * i / rings)) for i in range(rings + 1)]
	profile[0] = (0, profile[0][1] + radius * 0.12)
	profile[-1] = (0, profile[-1][1] - radius * 0.12)
	add_lathe(bm, profile, sides)
	for vert in new_verts_since(bm, before):
		angle = math.atan2(vert.co.y, vert.co.x)
		bulge = 1 + 0.08 * math.cos(ribs * angle)
		vert.co.x *= bulge
		vert.co.y *= bulge
		vert.co += Vector(center)


# Jack-o'-lantern face in units of the pumpkin radius: slanted angry eyes, a small nose and a fanged grin.
PUMPKIN_EYE = [(-0.62, 0.36), (-0.12, 0.14), (-0.44, -0.02)]
PUMPKIN_NOSE = [(-0.09, -0.06), (0.09, -0.06), (0.0, 0.1)]
PUMPKIN_MOUTH = [
	(-0.66, -0.1), (-0.48, -0.24), (-0.38, -0.16), (-0.27, -0.3), (-0.15, -0.2), (-0.05, -0.33), (0.05, -0.33), (0.15, -0.2),
	(0.27, -0.3), (0.38, -0.16), (0.48, -0.24), (0.66, -0.1), (0.5, -0.42), (0.36, -0.52), (0.27, -0.4), (0.12, -0.56),
	(0.0, -0.44), (-0.12, -0.56), (-0.27, -0.4), (-0.36, -0.52), (-0.5, -0.42),
]
PUMPKIN_PROBES = [(-0.38, 0.16), (0.38, 0.16), (0.0, 0.0), (0.0, -0.38), (-0.4, -0.3), (0.4, -0.3)]  # points inside the cuts
PUMPKIN_CARVE_DEPTH = 0.22  # how deep the face is cut into the pumpkin, in units of its radius


def merge_into(target, source):
	mesh = bpy.data.meshes.new("Merge")
	source.to_mesh(mesh)
	source.free()
	target.from_mesh(mesh)
	bpy.data.meshes.remove(mesh)


def boolean_difference(target, cutter):
	# Exact boolean on two bmeshes through temporary objects, returns a new bmesh.
	objects = []
	for name, bm in (("BooleanTarget", target), ("BooleanCutter", cutter)):
		bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
		mesh = bpy.data.meshes.new(name)
		bm.to_mesh(mesh)
		objects.append(bpy.data.objects.new(name, mesh))
		bpy.context.scene.collection.objects.link(objects[-1])
	modifier = objects[0].modifiers.new("Carve", "BOOLEAN")
	modifier.operation = "DIFFERENCE"
	modifier.solver = "EXACT"
	modifier.object = objects[1]
	result_mesh = bpy.data.meshes.new_from_object(objects[0].evaluated_get(bpy.context.evaluated_depsgraph_get()))
	result = bmesh.new()
	result.from_mesh(result_mesh)
	bpy.data.meshes.remove(result_mesh)
	for target_object in objects:
		mesh = target_object.data
		bpy.data.objects.remove(target_object)
		bpy.data.meshes.remove(mesh)
	return result


def carve_pockets(solid, cutter):
	# Cuts the cutter out of the solid, returns the remaining shell and the new inner faces as two bmeshes.
	carved = boolean_difference(solid, cutter)
	tree = mathutils.bvhtree.BVHTree.FromBMesh(solid)
	pocket_indices = set()
	for face in carved.faces:
		nearest = tree.find_nearest(face.calc_center_median())
		if nearest[3] is not None and nearest[3] > 0.004:
			pocket_indices.add(face.index)
	solid.free()
	cutter.free()
	pockets = carved.copy()
	bmesh.ops.delete(pockets, geom=[face for face in pockets.faces if face.index not in pocket_indices], context="FACES")
	bmesh.ops.delete(carved, geom=[face for face in carved.faces if face.index in pocket_indices], context="FACES")
	return carved, pockets


def carving_is_clean(carved, pockets, center, radius):
	# Looks into every cut from the front and the back, it has to see a pocket and not the shell.
	carved.faces.ensure_lookup_table()
	tree = mathutils.bvhtree.BVHTree.FromBMesh(carved)
	for x, z in PUMPKIN_PROBES:
		for side in (-1, 1):
			hit = tree.ray_cast(Vector((center.x + x * radius, side * radius * 2, center.z + z * radius)), Vector((0, -side, 0)))
			if hit[2] is None or carved.faces[hit[2]] not in pockets:
				return False
	return True


def add_carved_pumpkin(shell_bm, glow_bm, center, radius, **pumpkin_options):
	# Cuts the face into the pumpkin on the front and back. The pockets go into glow_bm,
	# so their walls and floor become the glowing (Neon) part.
	center = Vector(center)
	pumpkin = bmesh.new()
	add_pumpkin(pumpkin, center, radius, **pumpkin_options)

	# The exact boolean can fail on unlucky alignments, a tiny nudge of the cutters fixes it.
	for attempt in range(12):
		nudge = attempt * 0.0017 * radius
		inner = bmesh.new()
		add_pumpkin(inner, center, radius * (1 - PUMPKIN_CARVE_DEPTH - nudge), **pumpkin_options)
		prisms = bmesh.new()
		shapes = [PUMPKIN_EYE, [(-x, z) for x, z in PUMPKIN_EYE], PUMPKIN_NOSE, PUMPKIN_MOUTH]
		for side in (-1, 1):
			for shape in shapes:
				points = [Vector((center.x + x * radius + nudge, center.z + z * radius + nudge * 0.7)) for x, z in shape]
				add_plate(prisms, points, None, radius * 0.5, matrix=Matrix.Translation((0, side * radius, 0)))
		cutter = boolean_difference(prisms, inner)
		prisms.free()
		inner.free()
		carved = boolean_difference(pumpkin, cutter)
		cutter.free()

		tree = mathutils.bvhtree.BVHTree.FromBMesh(pumpkin)
		pockets = []
		for face in carved.faces:
			nearest = tree.find_nearest(face.calc_center_median())
			if nearest[3] is not None and nearest[3] > radius * 0.02:
				pockets.append(face)
		if carving_is_clean(carved, set(pockets), center, radius) or attempt == 11:
			break
		carved.free()
	pumpkin.free()

	pocket_bm = carved.copy()
	pocket_indices = {face.index for face in pockets}
	bmesh.ops.delete(pocket_bm, geom=[face for face in pocket_bm.faces if face.index not in pocket_indices], context="FACES")
	bmesh.ops.delete(carved, geom=pockets, context="FACES")
	merge_into(shell_bm, carved)
	merge_into(glow_bm, pocket_bm)


def bat_wing_outline(scale=1.0):
	elbow = Vector((0.85, 0.55))
	top = [(0, 0.08), (0.4, 0.38), (0.85, 0.55), (1.35, 0.62), (1.6, 0.45)]
	fingers = [Vector(point) for point in ((1.6, 0.45), (1.3, -0.1), (0.85, -0.38), (0.4, -0.3), (0, -0.1))]
	outline = catmull_rom(top, 4)
	for start, end in zip(fingers, fingers[1:]):
		control = ((start + end) / 2).lerp(elbow, 0.45)
		for step in range(5):
			t = step / 5
			outline.append((1 - t) ** 2 * start + 2 * (1 - t) * t * control + t ** 2 * end)
	outline = [point * scale for point in simplify(outline)]
	bones = [[Vector(point) * scale for point in top]] + [[elbow * scale, elbow.lerp(finger, 0.5) * scale, finger * scale] for finger in fingers[1:4]]
	return outline, bones


def ghost_outline(radius, height, waves=3):
	top = [Vector((math.cos(angle), math.sin(angle))) * radius for angle in numpy.linspace(0, math.pi, 9)]
	bottom = []
	for i in range(waves * 2 + 1):
		x = -radius + 2 * radius * i / (waves * 2)
		bottom.append(Vector((x, -height + (0.12 * radius if i % 2 else 0))))
	return simplify([Vector((radius, 0))] + top[1:-1] + [Vector((-radius, 0))] + bottom)


def web_strokes(center, radius, spokes=7, rings=3, start=0.0, sweep=math.tau):
	center = Vector(center)
	directions = [Vector((math.cos(start + sweep * i / spokes), math.sin(start + sweep * i / spokes))) for i in range(spokes + (0 if sweep >= math.tau else 1))]
	strokes = [[center, center + direction * radius] for direction in directions]
	for ring in range(1, rings + 1):
		distance = radius * ring / (rings + 0.4)
		loop = []
		for index, direction in enumerate(directions):
			loop.append(center + direction * distance)
			following = directions[(index + 1) % len(directions)]
			if index < len(directions) - 1 or sweep >= math.tau:
				loop.append(center + (direction + following).normalized() * distance * 0.86)
		if sweep >= math.tau:
			loop.append(loop[0])
		strokes.append(loop)
	return strokes


def add_flame(bm, root, direction, length, width, side=1, matrix=Matrix()):
	direction = Vector(direction).normalized()
	bend = Vector((-direction.y, direction.x)) * side * length * 0.2
	spine = [Vector(root), Vector(root) + direction * length * 0.5 + bend, Vector(root) + direction * length]
	flame, flame_plateau = profile_shape(spine, [(0, width * 0.35), (0.3, width), (0.55, width * 0.65), (0.72, width * 0.78), (1, 0)], chamfer=width * 0.4)
	add_plate(bm, flame, flame_plateau, 0.008, 0.03, matrix)


#// Halloween 01 Candy Corn Sword (Common)

def add_candy_fan(bm, root, direction, length, radius, pleats=8):
	# Twisted end of a candy wrapper that opens up into a pleated fan.
	before = set(bm.verts)
	add_lathe(bm, [(radius * 0.3, 0), (radius * 0.22, length * 0.25), (radius * 0.75, length * 0.75), (radius, length), (0, length * 0.92)], pleats * 2)
	for vert in new_verts_since(bm, before):
		if vert.co.z > length * 0.4:
			pleat = 1 + 0.2 * math.cos(pleats * math.atan2(vert.co.y, vert.co.x))
			vert.co.x *= pleat
			vert.co.y *= pleat
	bmesh.ops.transform(bm, matrix=oriented(root, direction), verts=new_verts_since(bm, before))


def build_candy_corn_sword(part):
	blade_base = 0.16
	length = 2.15
	tiers = (0.39, 0.735)
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.27), (0.06, 0.31), (0.5, 0.23), (0.85, 0.14), (1, 0.09)],
		tip="round",
		chamfer=0.1,
		plateau_ratio=0.4,
		features=[(t, side, 0.08, 0.035, 0) for t in tiers for side in (-1, 1)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.06, 0.12)
	part(bm, "CandyCorn")

	bm = bmesh.new()
	add_ball(bm, (0, 0, 0.08), 0.15, (1.45, 1.0, 0.95))
	for side in (-1, 1):
		add_candy_fan(bm, (side * 0.18, 0, 0.08), (side, 0, 0.18), 0.26, 0.17)
	part(bm, "Wrapper")

	bottom = -0.84
	bm = bmesh.new()
	add_lathe(bm, [(0.07, -0.02), (0.08, -0.06), (0.08, bottom + 0.04), (0.07, bottom)], 10)
	add_lathe(bm, [(0.04, bottom + 0.02), (0.04, bottom - 0.16)], 8)
	part(bm, "CandyStick")

	stripe = [(math.cos(angle) * 0.108, math.sin(angle) * 0.108, -0.07 + (bottom + 0.1) * angle / (math.tau * 3)) for angle in numpy.linspace(0, math.tau * 3, 25)]
	lolly_center = Vector((0, 0, bottom - 0.34))
	bm = bmesh.new()
	add_sweep(bm, stripe, [0.022] * 25, sides=4, smoothness=2)
	for side in (-1, 1):
		swirl = []
		for angle in numpy.linspace(0, math.tau * 2, 17):
			radius = 0.025 + 0.14 * angle / (math.tau * 2)
			swirl.append(lolly_center + Vector((math.cos(angle) * radius * side, side * (0.068 - radius * 0.06), math.sin(angle) * radius)))
		add_sweep(bm, swirl, [0.02] * 17, sides=4, flatten=0.6, smoothness=2)
	part(bm, "Lollipop")

	bm = bmesh.new()
	add_lathe(bm, [(0, -0.07), (0.17, -0.06), (0.2, 0.0), (0.17, 0.06), (0, 0.07)], 16, oriented(lolly_center, (0, 1, 0)))
	part(bm, "CandyWhite")

	tier_heights = [blade_base + t * length for t in tiers]
	shine = [
		[(-0.15, blade_base + 0.18), (-0.13, tier_heights[0] - 0.12)],
		[(-0.12, tier_heights[0] + 0.12), (-0.1, tier_heights[1] - 0.12)],
		[(-0.075, tier_heights[1] + 0.1), (-0.06, tier_heights[1] + 0.35)],
		[(0.16, blade_base + 0.25), (0.15, blade_base + 0.38)],
	]
	return {
		"blade": "CandyCorn",
		"decals": shine,
		"decal_width": 0.022,
		"decal_colors": ("FFFDF6", "FFFFFF"),
		"effects": {
			"CandyCorn": {
				"gradient": (blade_base, blade_base + length + 0.1, [
					(0, "FFC21F"), (0.36, "FFC21F"), (0.385, "FF7A1F"), (0.69, "FF7A1F"), (0.715, "FFF6E6"), (1, "FFF6E6"),
				]),
				"patterns": [("stars", "FFFFFF", 12, 0.45)],
			},
			"Wrapper": {"gradient": (-0.2, 0.4, [(0, "7A2AB8"), (1, "C07AF0")]), "patterns": [("stars", "FFFFFF", 9, 0.8)]},
		},
	}


#// Halloween 02 Scarecrow Sickle (Common)

def build_scarecrow_sickle(part):
	spine = [(0, 0.34), (0.02, 0.8), (0.16, 1.28), (0.46, 1.62), (0.86, 1.74), (1.22, 1.62), (1.42, 1.38)]
	stations = [(0, 0.065, 0.065), (0.12, 0.075, 0.075), (0.35, 0.17, 0.11), (0.6, 0.18, 0.1), (0.82, 0.12, 0.06), (1, 0, 0)]
	serration = [(t, 1, 0.045, -0.03, 0.7) for t in (0.42, 0.48, 0.54, 0.6, 0.66, 0.72, 0.78)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.08, features=serration)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.018, 0.07)
	part(bm, "SickleSteel")

	bm = bmesh.new()
	add_lathe(bm, [(0.1, 0.12), (0.115, 0.16), (0.115, 0.36), (0.09, 0.42)], 8)
	for y in (-0.115, 0.115):
		add_ball(bm, (0, y, 0.27), 0.03)
	part(bm, "IronBlack")

	bottom = 0.12 - 1.0
	bm = bmesh.new()
	add_grip(bm, 0.12, 1.0, 0.062, 0.068, 8)
	part(bm, "Wood")

	bm = bmesh.new()
	for height in (0.06, -0.01, bottom - 0.01):
		add_torus(bm, 0.098, 0.024, 12, 5, Matrix.Translation((0, 0, height)) @ Matrix.Rotation(math.radians(90), 4, "X"))
	part(bm, "Rope")

	bm = bmesh.new()
	for index in range(12):
		angle = math.tau * index / 12
		direction = Vector((math.cos(angle) * 0.8, math.sin(angle) * 0.8, 0.9 if index % 2 else 0.5))
		add_spike(bm, (math.cos(angle) * 0.08, math.sin(angle) * 0.08, 0.36), direction, 0.24 if index % 3 else 0.18, 0.03, sides=4)
	for index in range(10):
		angle = math.tau * index / 10 + 0.3
		direction = Vector((math.cos(angle), math.sin(angle), 0.25 if index % 2 else -0.1))
		add_spike(bm, (math.cos(angle) * 0.08, math.sin(angle) * 0.08, bottom - 0.03), direction, 0.2 if index % 3 else 0.15, 0.028, sides=4)
	part(bm, "Straw")

	head = Vector((0, 0, bottom - 0.25))
	bm = bmesh.new()
	add_ball(bm, head, 0.22, (1, 0.95, 1.05))
	add_box(bm, (0.1, 0.03, 0.09), head + Vector((0.12, -0.17, 0.07)), 0.012)
	part(bm, "Burlap")

	bm = bmesh.new()
	for side in (-1, 1):
		add_cabochon(bm, head + Vector((side * 0.085, -0.19, 0.05)), 0.045, 0.03, direction=(0, -1, 0))
	smile = [head + Vector((x, -0.205 + abs(x) * 0.35, -0.07 + x * x * 2.4)) for x in (-0.11, -0.055, 0, 0.055, 0.11)]
	add_sweep(bm, smile, [0.011] * 5, sides=4, smoothness=2)
	for x in (-0.08, -0.027, 0.027, 0.08):
		stitch = head + Vector((x, -0.205 + abs(x) * 0.35, -0.07 + x * x * 2.4))
		add_sweep(bm, [stitch + Vector((0, 0, -0.03)), stitch + Vector((0, 0, 0.03))], [0.008, 0.008], sides=4)
	part(bm, "Socket")

	crow = Vector((0.64, 0, 1.88))
	crow_scale = Matrix.Translation(crow) @ Matrix.Scale(1.35, 4) @ Matrix.Translation(-crow)
	bm = bmesh.new()
	add_ball(bm, crow + Vector((0, 0, 0.1)), 0.11, (1.25, 0.85, 0.9))
	add_ball(bm, crow + Vector((0.13, 0, 0.2)), 0.072)
	add_plate(bm, [Vector(point) for point in ((-0.08, 0.1), (-0.3, 0.04), (-0.33, 0.1), (-0.31, 0.15), (-0.1, 0.16))], None, 0.02, matrix=Matrix.Translation(crow))
	for y in (-0.085, 0.085):
		wing = [Vector(point) for point in ((0.08, 0.15), (-0.05, 0.19), (-0.2, 0.13), (-0.25, 0.06), (-0.1, 0.06), (0.05, 0.07))]
		add_plate(bm, wing, None, 0.012, matrix=Matrix.Translation(crow + Vector((0, y, 0))))
	bmesh.ops.transform(bm, matrix=crow_scale, verts=bm.verts)
	part(bm, "Crow")

	bm = bmesh.new()
	add_spike(bm, crow + Vector((0.19, 0, 0.2)), (1, 0, -0.25), 0.1, 0.03, sides=4)
	for y in (-0.035, 0.035):
		add_sweep(bm, [crow + Vector((0.02, y, 0.04)), crow + Vector((0.03, y, -0.03))], [0.012, 0.01], sides=4)
		add_ball(bm, crow + Vector((0.16, y * 1.6, 0.23)), 0.016)
	bmesh.ops.transform(bm, matrix=crow_scale, verts=bm.verts)
	part(bm, "Beak")

	return {
		"blade": "SickleSteel",
		"outline": outline,
		"edge_glow": ("F2F6FA", 0.03),
		"effects": {
			"SickleSteel": {"gradient": (0.3, 1.95, [(0, "6E747E"), (1, "B8C0CA")]), "patterns": [("nebula", "A0603A", 4, 0.55)]},
			"Burlap": {"patterns": [("bands", "8A6A3E", 22, 0.35)]},
			"Crow": {"patterns": [("cells", "5A5A80", 9, 0.35)]},
		},
	}


#// Halloween 03 Tombstone Sword (Uncommon)

LETTER_R = [[(-1, -1), (-1, 1), (0.5, 1), (0.9, 0.55), (0.5, 0.05), (-1, 0.05)], [(0.0, 0.05), (0.9, -1)]]
LETTER_I = [[(0, 1), (0, -1)]]
LETTER_P = [[(-1, -1), (-1, 1), (0.5, 1), (0.9, 0.55), (0.5, 0.05), (-1, 0.05)]]


def build_tombstone_sword(part):
	blade_base = 0.22
	length = 1.95
	top = blade_base + length
	outline, plateau = profile_shape(
		[(0, blade_base), (0, top)],
		[(0, 0.28), (1, 0.3)],
		tip="round",
		chamfer=0.08,
		features=[(0.38, 1, 0.1, 0.06, 0.3), (0.72, -1, 0.12, 0.07, -0.2), (0.9, 1, 0.08, 0.05, 0)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.05, 0.13)
	part(bm, "GraveStone")

	bm = bmesh.new()
	for x, z, radius in ((-0.2, blade_base + 0.18, 0.085), (0.21, blade_base + 0.14, 0.07), (0.29, top - 0.5, 0.06), (-0.3, blade_base + 0.85, 0.055), (-0.26, top - 0.12, 0.05)):
		add_ball(bm, (x, 0, z), radius, (1.1, 1.95, 0.8))
	for location in ((-0.25, 0, blade_base + 0.4), (0.24, 0, blade_base + 0.3)):
		add_ball(bm, location, 0.04, (1, 3.5, 0.9))
	part(bm, "Moss")

	bm = bmesh.new()
	add_lathe(bm, [(0.48, -0.03), (0.44, 0.1), (0.33, 0.22), (0.16, 0.3), (0, 0.32)], 14, Matrix.Diagonal((1, 0.52, 1, 1)))
	part(bm, "Dirt")

	bm = bmesh.new()
	for index in range(11):
		x = -0.36 + index * 0.072
		height = 0.12 + 0.17 * math.sqrt(max(0, 1 - (x / 0.46) ** 2))
		for y in (-0.17, 0.17):
			if abs(x) < 0.32:
				add_spike(bm, (x, y * (1 - abs(x) / 0.6), height - 0.04), (x * 0.6 + (0.15 if index % 2 else -0.15), y * 2, 1), 0.12 if index % 3 else 0.09, 0.025, sides=3)
	part(bm, "Leaf")

	bm = bmesh.new()
	add_box(bm, (1.12, 0.06, 0.06), (0, 0.08, 0.32), 0.015)
	for x in (-0.52, -0.36, 0.36, 0.52):
		add_box(bm, (0.05, 0.05, 0.36), (x, 0.08, 0.2), 0.012)
		add_spike(bm, (x, 0.08, 0.38), (0, 0, 1), 0.15, 0.045, sides=4)
		for side in (-1, 1):
			add_sweep(bm, [(x, 0.08, 0.34), (x + side * 0.06, 0.08, 0.39), (x + side * 0.05, 0.08, 0.45)], [0.013, 0.011, 0.0], sides=4)
	bottom = -0.04 - 0.72
	add_box(bm, (0.24, 0.24, 0.05), (0, 0, bottom - 0.02), 0.012)
	add_box(bm, (0.24, 0.24, 0.05), (0, 0, bottom - 0.32), 0.012)
	for x in (-0.1, 0.1):
		for y in (-0.1, 0.1):
			add_box(bm, (0.03, 0.03, 0.3), (x, y, bottom - 0.17), 0.006)
	add_lathe(bm, [(0.17, bottom - 0.34), (0, bottom - 0.47)], 4, Matrix.Rotation(math.radians(45), 4, "Z"))
	add_torus(bm, 0.05, 0.016, 10, 4, Matrix.Translation((0, 0, bottom - 0.52)))
	part(bm, "IronBlack")

	bm = bmesh.new()
	add_lathe(bm, [(0, bottom - 0.28), (0.07, bottom - 0.24), (0.07, bottom - 0.12), (0, bottom - 0.06)], 6)
	part(bm, "PumpkinGlow", CRYSTAL_SMOOTH_ANGLE)

	hand = Vector((0.24, -0.16, 0.2))
	bm = bmesh.new()
	add_ball(bm, hand, 0.05, (1.1, 0.7, 1.2))
	for index, x in enumerate((-0.035, -0.012, 0.012, 0.035)):
		reach = 0.11 + (0.02 if index in (1, 2) else 0)
		add_sweep(bm, [hand + Vector((x, 0, 0.03)), hand + Vector((x * 1.3, -0.01, reach * 0.65)), hand + Vector((x * 1.4, -0.05, reach))], [0.013, 0.011, 0.009], sides=4, smoothness=2)
	add_sweep(bm, [hand + Vector((0.04, 0, 0)), hand + Vector((0.08, -0.02, 0.04)), hand + Vector((0.09, -0.05, 0.08))], [0.013, 0.011, 0.009], sides=4, smoothness=2)
	bmesh.ops.transform(bm, matrix=Matrix.Translation(hand) @ Matrix.Scale(1.6, 4) @ Matrix.Translation(-hand), verts=bm.verts)
	part(bm, "Bone")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.72, 0.064, 0.077, 7)
	part(bm, "DarkLeather")

	letters = glyph_strokes([LETTER_R, LETTER_I, LETTER_P], [(-0.16, top - 0.25), (0, top - 0.25), (0.15, top - 0.25)], 0.055)
	cross = [[(0, top - 0.95), (0, top - 0.5)], [(-0.12, top - 0.62), (0.12, top - 0.62)]]
	cracks = [[(0.14, blade_base + 0.65), (0.08, blade_base + 0.6), (0.12, blade_base + 0.52), (0.05, blade_base + 0.45)], [(-0.15, top - 1.15), (-0.08, top - 1.2), (-0.12, top - 1.3)]]
	return {
		"blade": "GraveStone",
		"decals": letters + cross + cracks,
		"decal_width": 0.018,
		"decal_colors": ("33353F", "E2E6F0"),
		"effects": {
			"GraveStone": {
				"gradient": (0.2, 2.4, [(0, "6A6E7A"), (1, "AEB2BE")]),
				"patterns": [("nebula", "5E9A45", 2.5, 0.45), ("cells", "4A4C58", 3, 0.25)],
			},
			"Moss": {"patterns": [("nebula", "9AD86A", 5, 0.5)]},
			"Dirt": {"patterns": [("cells", "4A3020", 6, 0.4), ("stars", "A87A52", 12, 0.6)]},
		},
	}


#// Halloween 04 Pumpkin Sword (Uncommon)

def build_pumpkin_sword(part):
	blade_base = 0.3
	length = 2.55
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.2), (0.08, 0.26), (0.7, 0.25), (0.9, 0.17), (1, 0)],
		chamfer=0.1,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	pumpkin_center = (0, 0, 0.14)
	glow = bmesh.new()
	add_carved_pumpkin(bm, glow, pumpkin_center, 0.27)
	bottom = -0.1 - 0.72
	add_pumpkin(bm, (0, 0, bottom - 0.1), 0.12, ribs=6, sides=12, rings=6)
	part(bm, "Pumpkin")
	part(glow, "PumpkinGlow", CRYSTAL_SMOOTH_ANGLE)

	path = []
	for step in range(16):
		t = step / 15
		angle = t * math.tau * 1.75
		path.append((math.cos(angle) * 0.27, math.sin(angle) * 0.13, blade_base + 0.1 + t * 1.9))
	bm = bmesh.new()
	add_sweep(bm, path, [0.022] * 12 + [0.018, 0.014, 0.01, 0.0], sides=5, smoothness=3)
	add_sweep(bm, [(0, 0, 0.32), (0.04, 0, 0.42), (0.1, 0, 0.44)], [0.04, 0.035, 0.03])
	tendril = [(path[-1][0] + 0.05 * math.cos(a) * (1 - a / 9), 0, path[-1][2] + 0.05 * math.sin(a) * (1 - a / 9)) for a in numpy.linspace(0, 9, 10)]
	add_sweep(bm, tendril, [0.012] * 9 + [0.0], sides=4, smoothness=2)
	add_sweep(bm, [(0, 0, bottom), (0.03, 0, bottom + 0.06)], [0.025, 0.02])
	part(bm, "Vine")

	bm = bmesh.new()
	for index in (3, 7, 11):
		x, y, z = path[index]
		leaf, leaf_plateau = profile_shape([(0, 0), (0.08, 0.1), (0.1, 0.22)], [(0, 0.03), (0.4, 0.08), (1, 0)], chamfer=0.03)
		side = 1 if x > 0 else -1
		add_plate(bm, leaf, leaf_plateau, 0.006, 0.02, Matrix.Translation((x, y - 0.03 * side, z)) @ Matrix.Rotation(math.radians(-side * 50), 4, "Y"))
	part(bm, "Leaf")

	bm = bmesh.new()
	add_grip(bm, -0.1, 0.72, 0.064, 0.077, 7)
	part(bm, "DarkLeather")

	ribs = [[(x, blade_base + 0.25), (x * 1.08, blade_base + 1.2), (x, blade_base + 2.2)] for x in (-0.13, 0, 0.13)]
	return {
		"blade": "Pumpkin",
		"decals": ribs,
		"decal_width": 0.014,
		"decal_colors": ("B8480E", "FFC07A"),
		"effects": {"Pumpkin": {"gradient": (-1.0, 2.9, [(0, "E06A14"), (1, "FFA43A")])}},
	}


#// Halloween 05 Bat Wing Sword (Rare)

def build_bat_wing_sword(part):
	left = [Vector((-0.09, 0.25)), Vector((-0.1, 1.0)), Vector((-0.07, 2.0)), Vector((0.0, 3.0))]
	fingers = [Vector((0.0, 3.0)), Vector((0.36, 2.3)), Vector((0.44, 1.6)), Vector((0.38, 0.9)), Vector((0.16, 0.25))]
	outline = list(left)
	for start, end in zip(fingers, fingers[1:]):
		control = ((start + end) / 2).lerp(Vector((0.0, (start.y + end.y) / 2)), 0.45)
		for step in range(1, 6):
			t = step / 6
			outline.append((1 - t) ** 2 * start + 2 * (1 - t) * t * control + t ** 2 * end)
		outline.append(end)
	outline = simplify(outline)
	bm = bmesh.new()
	add_plate(bm, outline, None, 0.035)
	part(bm, "BatWing")

	bm = bmesh.new()
	add_sweep(bm, [(point.x, point.y) for point in left], [0.05, 0.045, 0.035, 0.0], sides=6)
	for finger in fingers[1:4]:
		root = Vector((-0.08, finger.y - 0.35))
		add_sweep(bm, [root, root.lerp(finger, 0.5), finger], [0.032, 0.025, 0.012], sides=5)
		add_spike(bm, (finger.x, 0, finger.y), (1, 0, 0.3), 0.09, 0.02, sides=4)
	add_ball(bm, (0, 0.04, 0.14), 0.16, (1.1, 0.85, 1.15))
	add_ball(bm, (0, -0.06, 0.3), 0.11, (1.1, 0.95, 0.95))
	for side in (-1, 1):
		add_spike(bm, (side * 0.07, -0.05, 0.37), (side * 0.4, 0, 1), 0.16, 0.05, sides=4)
		wing, bones = bat_wing_outline(0.32)
		wing_matrix = Matrix.Translation((side * 0.12, 0.02, 0.06)) @ Matrix.Diagonal((side, 1, 1, 1))
		add_plate(bm, wing, None, 0.02, matrix=wing_matrix)
		for bone in bones:
			add_sweep(bm, [(point.x, point.y) for point in bone], [0.018] * (len(bone) - 1) + [0.006], sides=4, matrix=wing_matrix)
	bottom = -0.04 - 0.75
	add_grip(bm, -0.04, 0.75, 0.064, 0.077, 7)
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.03), (0.1, bottom - 0.08), (0.06, bottom - 0.11)])
	add_spike(bm, (0, 0, bottom - 0.1), (0, 0, -1), 0.2, 0.06)
	part(bm, "BatBody")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (side * 0.045, -0.155, 0.32), 0.026, (1, 0.6, 1))
	part(bm, "BatEye")

	bm = bmesh.new()
	for side in (-1, 1):
		add_spike(bm, (side * 0.025, -0.15, 0.25), (0, -0.1, -1), 0.06, 0.012, sides=4)
	part(bm, "Tooth")

	return {
		"blade": "BatWing",
		"effects": {
			"BatWing": {"gradient": (0.2, 3.0, [(0, "2A1A40"), (1, "7A52B0")]), "patterns": [("cells", "9A72D0", 2.2, 0.3)]},
			"BatBody": {"gradient": (-0.9, 0.5, [(0, "1A1222"), (1, "3E2E50")])},
		},
	}


#// Halloween 06 Spider Sword (Rare)

def build_spider_sword(part):
	blade_base = 0.42
	spine = [(0, blade_base), (0, blade_base + 2.0), (0.06, blade_base + 2.65), (0.2, blade_base + 3.0)]
	stations = [(0, 0.17), (0.08, 0.24), (0.3, 0.21), (0.33, 0.16), (0.36, 0.22), (0.62, 0.2), (0.65, 0.15), (0.68, 0.19), (0.88, 0.14), (1, 0)]
	spurs = [(t, side, 0.08, -0.09, 0.8) for t in (0.34, 0.66) for side in (-1, 1)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.09, features=spurs)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "SpiderBlade")

	abdomen = Vector((0, 0, 0.02))
	thorax = Vector((0, 0, 0.3))
	bm = bmesh.new()
	add_ball(bm, abdomen, 0.2, (1, 0.85, 1.2))
	add_ball(bm, thorax, 0.13, (1.05, 0.9, 1))
	legs = [
		((0.08, 0.36), (0.3, 0.62), (0.27, 0.98)),
		((0.1, 0.32), (0.42, 0.48), (0.62, 0.62)),
		((0.1, 0.27), (0.42, 0.26), (0.64, 0.1)),
		((0.08, 0.22), (0.34, 0.08), (0.46, -0.24)),
	]
	for side in (-1, 1):
		for root, knee, tip in legs:
			add_sweep(bm, [(side * root[0], 0, root[1]), (side * knee[0], 0, knee[1]), (side * tip[0], 0, tip[1])], [0.03, 0.026, 0.0], sides=5)
			add_ball(bm, (side * knee[0], 0, knee[1]), 0.04)
	add_grip(bm, -0.2, 0.75, 0.064, 0.077, 7)
	hanger = Vector((0.46, 0, -0.84))
	add_ball(bm, hanger, 0.055, (1, 0.9, 1.15))
	add_ball(bm, hanger + Vector((0, 0, 0.07)), 0.035)
	for side in (-1, 1):
		for lift in (0.06, 0.0, -0.06):
			add_sweep(bm, [hanger + Vector((side * 0.03, 0, lift)), hanger + Vector((side * 0.1, 0, lift + 0.05)), hanger + Vector((side * 0.13, 0, lift - 0.03))], [0.012, 0.01, 0.0], sides=4)
	part(bm, "SpiderBody")

	bm = bmesh.new()
	upper = [Vector((-0.08, 0.1)), Vector((0.08, 0.1)), Vector((0.0, 0.008))]
	lower = [Vector((0.0, -0.008)), Vector((0.08, -0.1)), Vector((-0.08, -0.1))]
	for shape in (upper, lower):
		add_plate(bm, shape, None, 0.115, matrix=Matrix.Translation((0, 0, blade_base + 1.3)))
		add_plate(bm, [point * 0.75 for point in shape], None, 0.172, matrix=Matrix.Translation(abdomen))
	part(bm, "Hourglass")

	bm = bmesh.new()
	for y in (-0.105, 0.105):
		for x, z, radius in ((0.04, 0.35, 0.034), (0.085, 0.32, 0.024), (0.07, 0.39, 0.022), (0.022, 0.405, 0.019)):
			for side in (-1, 1):
				add_ball(bm, (side * x, y, z), radius)
	add_ball(bm, hanger + Vector((0, 0, 0.075)), 0.02, (1.8, 2.2, 1))
	part(bm, "SpiderEye")

	bottom = -0.2 - 0.75
	sac = Vector((0, 0, bottom - 0.15))
	bm = bmesh.new()
	add_ball(bm, sac, 0.15, (0.9, 0.9, 1.15))
	wrap = [sac + Vector((math.cos(angle) * 0.145, math.sin(angle) * 0.145, 0.12 - 0.24 * angle / (math.tau * 2))) for angle in numpy.linspace(0, math.tau * 2, 13)]
	add_sweep(bm, wrap, [0.008] * 13, sides=4, smoothness=2)
	add_sweep(bm, [(0.46, 0, -0.24), (0.46, 0, -0.5), (0.46, 0, -0.75)], [0.006, 0.006, 0.006], sides=4)
	part(bm, "Web")

	webs = web_strokes((0, blade_base + 2.3), 0.22, spokes=8, rings=3) + web_strokes((-0.21, blade_base + 0.06), 0.4, spokes=4, rings=3, start=0, sweep=math.pi / 2)
	return {
		"blade": "SpiderBlade",
		"outline": outline,
		"edge_glow": ("C0182A", 0.05),
		"decals": webs,
		"decal_width": 0.008,
		"decal_colors": ("ECECF6", "FFFFFF"),
		"effects": {
			"SpiderBlade": {"gradient": (0.4, 3.4, [(0, "141218"), (1, "3A3448")]), "patterns": [("cells", "4A2A3A", 3, 0.4)]},
			"SpiderBody": {"patterns": [("stars", "6A5A80", 14, 0.6)]},
		},
	}


#// Halloween 07 Witch Cauldron Blade (Epic)

def build_witch_cauldron_blade(part):
	blade_base = 0.38
	length = 2.75
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.2), (0.1, 0.28), (0.5, 0.25), (0.8, 0.22), (0.92, 0.14), (1, 0)],
		chamfer=0.15,
		plateau_ratio=0.12,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.015, 0.12)
	part(bm, "Potion")

	bm = bmesh.new()
	add_lathe(bm, [(0, -0.2), (0.2, -0.18), (0.35, -0.04), (0.38, 0.12), (0.32, 0.28), (0.29, 0.32)], 20, Matrix.Translation((0, 0, 0.1)))
	add_torus(bm, 0.3, 0.04, 22, 6, Matrix.Translation((0, 0, 0.43)) @ Matrix.Rotation(math.radians(90), 4, "X"))
	for side in (-1, 1):
		add_torus(bm, 0.08, 0.022, 10, 5, Matrix.Translation((side * 0.4, 0, 0.3)) @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "X"))
	for index in range(3):
		angle = math.tau * index / 3 + math.pi / 2
		add_spike(bm, (math.cos(angle) * 0.2, math.sin(angle) * 0.2, -0.08), (math.cos(angle) * 0.3, math.sin(angle) * 0.3, -1), 0.14, 0.045, sides=5)
	part(bm, "Cauldron")

	bm = bmesh.new()
	add_lathe(bm, [(0, 0.38), (0.3, 0.38), (0.3, 0.4), (0, 0.42)], 20)
	for location, radius in (((0.15, -0.08, 0.44), 0.07), ((-0.14, 0.08, 0.45), 0.06), ((0.06, 0.15, 0.43), 0.045), ((-0.22, -0.12, 0.42), 0.04), ((0.2, 0.1, 0.42), 0.035)):
		add_ball(bm, location, radius)
	for location, radius in (((0.32, 0, 0.75), 0.045), ((-0.34, 0, 1.15), 0.035), ((0.3, 0, 1.7), 0.03), ((-0.28, 0, 2.2), 0.04), ((0.25, 0, 2.65), 0.025)):
		add_ball(bm, location, radius)
	bottom = -0.04 - 0.72
	flask = Vector((0, 0, bottom - 0.24))
	add_ball(bm, flask, 0.15, (1, 1, 0.95))
	part(bm, "PotionGlow")

	bm = bmesh.new()
	add_lathe(bm, [(0.06, bottom - 0.12), (0.07, bottom - 0.08), (0.05, bottom - 0.02), (0.05, bottom + 0.01)], 10)
	add_grip(bm, -0.04, 0.72, 0.064, 0.077, 7)
	part(bm, "WitchPurple")

	bm = bmesh.new()
	add_lathe(bm, [(0.05, bottom - 0.02), (0.065, bottom + 0.0), (0.065, bottom + 0.05), (0.05, bottom + 0.06)], 10)
	add_pommel(bm, [(0.06, -0.06), (0.095, -0.04), (0.095, -0.01), (0.06, 0.0)])
	part(bm, "DesertWood")

	return {
		"blade": "Potion",
		"outline": outline,
		"edge_glow": ("C8FF7A", 0.06),
		"effects": {
			"Potion": {
				"gradient": (0.3, 3.1, [(0, "1E6A2E"), (0.5, "4EC04A"), (1, "B8FF7A")]),
				"patterns": [("stars", "E8FFD0", 7, 0.9), ("nebula", "8AF07A", 3, 0.35)],
			},
			"WitchPurple": {"patterns": [("bands", "4A2280", 10, 0.5)]},
		},
	}


#// Halloween 08 Reaper Scythe (Epic)

def build_reaper_scythe(part):
	head = Vector((0, 0, 2.36))
	spine = [(0.02, 2.36), (0.5, 2.48), (1.0, 2.49), (1.45, 2.36), (1.78, 2.07), (1.9, 1.73), (1.8, 1.45)]
	stations = [(0, 0.09, 0.2), (0.2, 0.09, 0.26), (0.5, 0.08, 0.22), (0.78, 0.06, 0.13), (1, 0, 0)]
	back_spikes = [(t, -1, 0.11, -0.08, 0.7) for t in (0.28, 0.42, 0.56)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.07, features=back_spikes)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.018, 0.08)
	add_spike(bm, head + Vector((-0.08, 0, 0.02)), (-1, 0, 0.3), 0.42, 0.07, sides=4)
	for height in (2.12, 1.98):
		add_lathe(bm, [(0.085, height - 0.035), (0.1, height - 0.015), (0.1, height + 0.015), (0.085, height + 0.035)], 8)
	add_torus(bm, 0.085, 0.026, 10, 5, Matrix.Translation((-0.02, 0, 1.08)) @ Matrix.Rotation(math.radians(90), 4, "Z"))
	add_lathe(bm, [(0.075, -0.95), (0, -1.18)], 8)
	part(bm, "ReaperSteel")

	rim, rim_plateau = profile_shape(spine, [(t, left + 0.012, right + 0.045) for t, left, right in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.014)
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.075, -0.17, 0.04)), 0.036)
	part(bm, "ReaperGlow")

	bm = bmesh.new()
	add_lathe(bm, [(0.065, -0.95), (0.07, 0.0), (0.065, 2.0), (0.06, 2.25)], 8)
	add_sweep(bm, [(-0.02, 0, 1.1), (-0.2, -0.02, 1.06), (-0.3, -0.04, 0.98)], [0.04, 0.038, 0.034], sides=6)
	add_ball(bm, (-0.31, -0.04, 0.97), 0.06)
	part(bm, "ReaperWood")

	bm = bmesh.new()
	add_grip(bm, -0.06, 0.85, 0.07, 0.08, 7)
	part(bm, "DarkLeather")

	bm = bmesh.new()
	add_ball(bm, head, 0.21, (1, 0.95, 1.05))
	add_ball(bm, head + Vector((0, -0.05, -0.16)), 0.125, (0.85, 0.8, 0.55))
	part(bm, "Bone")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.075, -0.155, 0.04)), 0.058, (1, 0.5, 1.15))
	add_ball(bm, head + Vector((0, -0.19, -0.05)), 0.027, (1, 0.5, 1))
	for x in (-0.05, 0.0, 0.05):
		add_box(bm, (0.014, 0.03, 0.05), head + Vector((x, -0.145, -0.16)), 0.004)
	part(bm, "Socket")

	bm = bmesh.new()
	for index, (x, length) in enumerate(((-0.1, 0.7), (0.0, 0.85), (0.1, 0.6))):
		rag = [Vector((x - 0.06, 0)), Vector((x + 0.06, 0)), Vector((x + 0.07, -length * 0.5)), Vector((x + 0.04, -length * 0.8)), Vector((x + 0.02, -length * 0.7)), Vector((x, -length)), Vector((x - 0.03, -length * 0.75)), Vector((x - 0.07, -length * 0.85)), Vector((x - 0.06, -length * 0.4))]
		add_plate(bm, rag, None, 0.012, matrix=Matrix.Translation((0, 0.08 + index * 0.012, 2.05)) @ Matrix.Rotation(math.radians(index * 6 - 6), 4, "Y"))
	add_torus(bm, 0.09, 0.03, 12, 5, Matrix.Translation((0, 0, 2.05)) @ Matrix.Rotation(math.radians(90), 4, "X"))
	part(bm, "Cloth")

	runes = []
	for index in range(4):
		center = point_on_path(catmull_rom(spine, 8) + [Vector(spine[-1])], 0.16 + index * 0.17)
		runes.append([center + Vector((0, -0.09)) + Vector(point) * 0.05 for point in VOID_RUNES[(index * 2) % len(VOID_RUNES)]])
	return {
		"blade": "ReaperSteel",
		"outline": outline,
		"edge_glow": ("C08AFF", 0.05),
		"decals": runes,
		"decal_width": 0.014,
		"decal_colors": ("C08AFF", "F0E0FF"),
		"effects": {
			"ReaperSteel": {"gradient": (1.6, 2.6, [(0, "2E3240"), (1, "8A92A8")]), "patterns": [("nebula", "6A4A9A", 3, 0.35)]},
			"Cloth": {"gradient": (1.1, 2.1, [(0, "1A1424"), (1, "4A3E5E")])},
		},
	}


#// Halloween 09 Ghost Sword (Legendary)

def build_ghost_sword(part):
	blade_base = 0.42
	spine = [(0, blade_base), (0, 1.4), (0.08, 2.2), (-0.04, 2.9), (0.08, 3.35), (0.26, 3.62)]
	stations = [(0, 0.12), (0.1, 0.24), (0.5, 0.3), (0.75, 0.25), (0.9, 0.15), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.11)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Ghost")

	rim, rim_plateau = profile_shape(spine, [(t, width + 0.05) for t, width in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	bottom = -0.22 - 0.75
	wisp = [(0, 0, bottom - 0.02), (0.1, 0, bottom - 0.15), (-0.05, 0, bottom - 0.3), (0.06, 0, bottom - 0.42)]
	add_sweep(bm, wisp, [0.06, 0.05, 0.03, 0.0], sides=6)
	part(bm, "GhostGlow")

	ghost_center = Vector((0, 0, 0.22))
	body = ghost_outline(0.34, 0.52, waves=3)
	bm = bmesh.new()
	add_plate(bm, body, [point * 0.65 for point in body], 0.05, 0.15, Matrix.Translation(ghost_center))
	for side in (-1, 1):
		add_sweep(bm, [(side * 0.28, 0.2), (side * 0.43, 0.3), (side * 0.5, 0.45)], [0.05, 0.045, 0.04])
		add_ball(bm, (side * 0.51, 0, 0.49), 0.065)
	part(bm, "Spirit")

	bm = bmesh.new()
	for y in (-0.155, 0.155):
		for side in (-1, 1):
			add_ball(bm, ghost_center + Vector((side * 0.1, y, 0.08)), 0.055, (1, 0.5, 1.35))
		add_ball(bm, ghost_center + Vector((0, y, -0.07)), 0.045, (1, 0.5, 1.2))
	part(bm, "GhostEye")

	bm = bmesh.new()
	for y in (-0.175, 0.175):
		for side in (-1, 1):
			add_ball(bm, ghost_center + Vector((side * 0.1 - 0.018, y, 0.12)), 0.018, (1, 0.6, 1))
	part(bm, "Spirit")

	bm = bmesh.new()
	for y in (-0.14, 0.14):
		for side in (-1, 1):
			add_ball(bm, ghost_center + Vector((side * 0.19, y, -0.02)), 0.04, (1.3, 0.4, 0.8))
	part(bm, "Blush")

	bm = bmesh.new()
	for side in (-1, 1):
		for index in range(3):
			rotation = Matrix.Rotation(math.radians(90 if index % 2 else 0), 4, "Z")
			add_torus(bm, 0.045, 0.015, 10, 5, Matrix.Translation((side * 0.51, 0, 0.4 - index * 0.085)) @ rotation)
		add_ball(bm, (side * 0.51, 0, 0.1), 0.07)
	add_pommel(bm, [(0.06, bottom - 0.02), (0.095, bottom + 0.0), (0.095, bottom + 0.03), (0.06, bottom + 0.05)])
	add_grip(bm, -0.22, 0.75, 0.064, 0.077, 7)
	part(bm, "Chain")

	tiny = []
	for center, size in (((-0.04, 1.45), 0.1), ((0.1, 2.35), 0.085), ((-0.06, 3.0), 0.07)):
		loop = [Vector(center) + point for point in ghost_outline(size, size * 1.5, waves=2)]
		tiny.append(loop + [loop[0]])
		for side in (-1, 1):
			eye = Vector(center) + Vector((side * size * 0.35, size * 0.05))
			tiny.append([eye, eye + Vector((0, size * 0.25))])
	return {
		"blade": "Ghost",
		"outline": outline,
		"edge_glow": ("8AF0FF", 0.07),
		"decals": tiny,
		"decal_width": 0.016,
		"decal_colors": ("5A7AA8", "FFFFFF"),
		"effects": {
			"Ghost": {"gradient": (0.4, 3.6, [(0, "8ACAE8"), (0.6, "D8F0FF"), (1, "FFFFFF")]), "patterns": [("nebula", "FFFFFF", 2.5, 0.4), ("stars", "FFFFFF", 9, 0.6)]},
			"Spirit": {"gradient": (-0.3, 0.6, [(0, "B8D8F0"), (1, "FFFFFF")])},
		},
	}


#// Halloween 10 Vampire Sword (Legendary)

def build_vampire_sword(part):
	blade_base = 0.26
	spine = [(0, blade_base), (0, blade_base + 3.2)]
	stations = [(0, 0.16), (0.08, 0.21), (0.6, 0.18), (0.8, 0.25), (0.9, 0.19), (1, 0)]
	gothic = [(t, side, 0.12, -0.09, 0.8) for t, side in ((0.3, 1), (0.3, -1), (0.55, 1), (0.55, -1), (0.78, 1), (0.78, -1))]
	outline, plateau = profile_shape(spine, stations, chamfer=0.09, features=gothic)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.018, 0.09)
	part(bm, "Vampire")

	bm = bmesh.new()
	for side in (-1, 1):
		curl = [(side * 0.08, 0.14), (side * 0.3, 0.1), (side * 0.42, 0.2), (side * 0.38, 0.32), (side * 0.3, 0.27)]
		add_sweep(bm, curl, [0.05, 0.045, 0.035, 0.025, 0.0])
		add_sweep(bm, [(side * 0.1, 0.1), (side * 0.22, -0.05), (side * 0.18, -0.14)], [0.035, 0.03, 0.0])
	add_box(bm, (0.26, 0.22, 0.3), (0, 0, 0.14), 0.06)
	bottom = -0.04 - 0.78
	for height in (-0.04, -0.42, bottom + 0.02):
		add_pommel(bm, [(0.06, height - 0.02), (0.095, height - 0.01), (0.095, height + 0.02), (0.06, height + 0.03)])
	coffin = [Vector((0, 0.0)), Vector((0.1, -0.05)), Vector((0.08, -0.32)), Vector((0, -0.36)), Vector((-0.08, -0.32)), Vector((-0.1, -0.05))]
	coffin = [Vector((point.x * 1.2, point.y + 0.04)) for point in [Vector((-0.06, 0.04)), Vector((0.06, 0.04))]] + coffin[1:]
	add_plate(bm, coffin, [point * 0.6 + Vector((0, -0.07)) for point in coffin], 0.035, 0.07, Matrix.Translation((0, 0, bottom - 0.02)))
	part(bm, "Gold")

	bm = bmesh.new()
	for side in (-1, 1):
		wing, bones = bat_wing_outline(0.36)
		wing_matrix = Matrix.Translation((side * 0.16, 0.03, 0.06)) @ Matrix.Diagonal((side, 1, 1, 1)) @ Matrix.Rotation(math.radians(-8), 4, "Y")
		add_plate(bm, wing, None, 0.02, matrix=wing_matrix)
		for bone in bones:
			add_sweep(bm, [(point.x, point.y) for point in bone], [0.018] * (len(bone) - 1) + [0.006], sides=4, matrix=wing_matrix)
	add_grip(bm, -0.04, 0.78, 0.064, 0.077, 7)
	part(bm, "BatBody")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.16), 0.085, 0.16)
	add_cabochon(bm, (0, 0, bottom - 0.16), 0.045, 0.1)
	part(bm, "BloodGlow")

	bm = bmesh.new()
	for side in (-1, 1):
		for y in (-0.11, 0.11):
			add_spike(bm, (side * 0.07, y, 0.02), (0, 0, -1), 0.12, 0.022, sides=5)
	part(bm, "Tooth")

	bm = bmesh.new()
	rose_center = Vector((0, -0.13, 0.32))
	for index in range(7):
		angle = index * 2.4
		distance = 0.02 + index * 0.012
		add_ball(bm, rose_center + Vector((math.cos(angle) * distance, -0.01 * index, math.sin(angle) * distance)), 0.045 + index * 0.004, (1, 0.6, 1))
	part(bm, "Rose")

	drips = [[(0, blade_base + 0.2), (0, blade_base + 2.7)]]
	for x, length in ((-0.1, 0.55), (-0.05, 0.9), (0.06, 1.15), (0.11, 0.45), (-0.12, 1.6), (0.1, 1.9)):
		top = blade_base + 2.75
		drips.append([(x, top - 0.25), (x, top - 0.25 - length)])
	return {
		"blade": "Vampire",
		"outline": outline,
		"edge_glow": ("FF4A5A", 0.05),
		"decals": drips,
		"decal_width": 0.022,
		"decal_colors": ("4A0610", "FF8A8A"),
		"effects": {"Vampire": {"gradient": (0.26, 3.5, [(0, "3A0610"), (0.6, "9A1428"), (1, "E0404E")]), "patterns": [("nebula", "5A0A18", 3, 0.35)]}},
	}


#// Halloween 11 Headless Horseman Blade (Mythic)

def build_headless_horseman_blade(part):
	blade_base = 0.5
	spine = [(0, blade_base), (0.02, 1.5), (0.16, 2.5), (0.42, 3.3), (0.6, 3.62)]
	stations = [(0, 0.2), (0.08, 0.25), (0.7, 0.24), (0.88, 0.2, 0.15), (1, 0, 0)]
	licks = [(t, 1, 0.2, -0.1, 0.9) for t in (0.3, 0.44, 0.58, 0.72)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1, features=licks)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Horseman")

	pumpkin_center = (0, 0, 0.24)
	rim, rim_plateau = profile_shape(spine, [station[:1] + tuple(width + 0.035 for width in station[1:]) for station in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	shell = bmesh.new()
	carving = bmesh.new()
	add_carved_pumpkin(shell, carving, pumpkin_center, 0.32)
	for side in (-1, 1):
		add_flame(bm, Vector((side * 0.18, 0.46)), (side * 0.35, 1), 0.6, 0.11, side)
		add_flame(bm, Vector((side * 0.28, 0.36)), (side * 0.8, 1), 0.42, 0.08, side)
		add_flame(bm, Vector((side * 0.1, 0.5)), (side * 0.1, 1), 0.7, 0.09, -side)
	bottom = -0.06 - 0.82
	add_flame(bm, Vector((0, bottom - 0.33)), (0, 1), 0.2, 0.06)
	part(bm, "HellFire")
	part(shell, "Pumpkin")
	part(carving, "PumpkinGlow", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	knuckle_bow = [(0.24, 0.12), (0.42, -0.12), (0.42, -0.52), (0.26, -0.84), (0.06, -0.95)]
	add_sweep(bm, knuckle_bow, [0.045, 0.04, 0.035, 0.035, 0.04])
	add_sweep(bm, [(-0.26, 0.14), (-0.44, 0.06), (-0.52, 0.16), (-0.47, 0.26), (-0.41, 0.22)], [0.045, 0.04, 0.032, 0.022, 0.0])
	add_pommel(bm, [(0.06, -0.1), (0.1, -0.08), (0.1, -0.03), (0.06, -0.01)])
	add_pommel(bm, [(0.05, bottom + 0.01), (0.1, bottom - 0.02), (0.1, bottom - 0.06), (0.05, bottom - 0.08)])
	shoe = [(math.cos(angle) * 0.15, bottom - 0.24 + math.sin(angle) * 0.17) for angle in numpy.linspace(math.radians(-35), math.radians(215), 9)]
	add_sweep(bm, shoe, [0.038] * 9, sides=4, smoothness=3)
	part(bm, "IronBlack")

	bm = bmesh.new()
	for angle in numpy.linspace(math.radians(10), math.radians(170), 5):
		if abs(angle - math.pi / 2) > 0.2:
			for y in (-0.055, 0.055):
				add_ball(bm, (math.cos(angle) * 0.15, y, bottom - 0.24 + math.sin(angle) * 0.17), 0.016)
	part(bm, "Gold")

	bm = bmesh.new()
	add_grip(bm, -0.06, 0.82, 0.064, 0.077, 7)
	part(bm, "DarkLeather")

	bm = bmesh.new()
	for index, (length, tilt) in enumerate(((0.75, 28), (0.6, 40))):
		rag = [Vector((-0.06, 0)), Vector((0.06, 0)), Vector((0.08, -length * 0.5)), Vector((0.05, -length * 0.85)), Vector((0.02, -length * 0.72)), Vector((0, -length)), Vector((-0.03, -length * 0.78)), Vector((-0.08, -length * 0.88)), Vector((-0.07, -length * 0.4))]
		add_plate(bm, rag, None, 0.014, matrix=Matrix.Translation((-0.2, 0.1 + index * 0.02, 0.02)) @ Matrix.Rotation(math.radians(-tilt), 4, "Y"))
	part(bm, "Cape")

	cracks = [
		[(0.0, blade_base + 0.1), (0.05, blade_base + 0.45), (-0.03, blade_base + 0.85), (0.03, blade_base + 1.25)],
		[(0.05, blade_base + 0.45), (0.13, blade_base + 0.65)],
		[(-0.03, blade_base + 0.85), (-0.12, blade_base + 1.05)],
	]
	return {
		"blade": "Horseman",
		"outline": outline,
		"edge_glow": ("FF8A2E", 0.06),
		"decals": cracks,
		"decal_width": 0.02,
		"decal_colors": ("FF7A1F", "FFE08A"),
		"effects": {
			"Horseman": {"gradient": (0.5, 3.7, [(0, "5A2414"), (0.3, "241A20"), (1, "2E2636")]), "patterns": [("flames", "FF7A1F", 3.5, 0.5)]},
			"HellFire": {"gradient": (0.0, 1.2, [(0, "FF5A1A"), (1, "FFE07A")])},
			"Cape": {"gradient": (-0.6, 0.0, [(0, "2A0A10"), (1, "6A1E2A")])},
		},
	}


#// Halloween 12 Nightmare King Blade (Exclusive)

def build_nightmare_king_blade(part):
	blade_base = 0.66
	spine = [(0, blade_base), (0, blade_base + 2.2), (0.06, blade_base + 3.3), (0.22, blade_base + 4.0)]
	stations = [(0, 0.3), (0.06, 0.4), (0.5, 0.46), (0.78, 0.4), (0.9, 0.28), (1, 0)]
	features = []
	for side in (-1, 1):
		features += [(t, side, 0.5, 0.08, 0) for t in (0.3, 0.5, 0.7)]
		features += [(t, side, 0.1, -0.1, 0.8) for t in (0.2, 0.4, 0.6, 0.8)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.13, features=features)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.022, 0.12)
	part(bm, "NightmareBlade")

	pumpkin_center = Vector((0, 0, 0.34))
	rim, rim_plateau = profile_shape(spine, [(t, width + 0.08) for t, width in stations], chamfer=0.04, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, rim, rim_plateau, 0.006, 0.016)
	shell = bmesh.new()
	carving = bmesh.new()
	add_carved_pumpkin(shell, carving, pumpkin_center, 0.38)
	for side in (-1, 1):
		add_flame(bm, Vector((side * 0.28, 0.6)), (side * 0.3, 1), 0.62, 0.12, side)
		add_flame(bm, Vector((side * 0.38, 0.46)), (side * 0.9, 1), 0.46, 0.09, side)
	bottom = -0.06 - 0.95
	pommel_center = Vector((0, 0, bottom - 0.12))
	add_carved_pumpkin(shell, carving, pommel_center, 0.15, ribs=6, sides=12, rings=6)
	part(bm, "SoulGlow")
	part(shell, "Pumpkin")
	part(carving, "SoulCarve", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	crown_base = pumpkin_center.z + 0.27
	add_lathe(bm, [(0.21, crown_base), (0.23, crown_base), (0.24, crown_base + 0.08), (0.22, crown_base + 0.08)], 16, closed=True)
	for index in range(5):
		angle = math.tau * index / 5 - math.pi / 2
		direction = Vector((math.cos(angle) * 0.25, math.sin(angle) * 0.25, 1))
		root = Vector((math.cos(angle) * 0.23, math.sin(angle) * 0.23, crown_base + 0.06))
		add_spike(bm, root, direction, 0.2, 0.05, sides=4)
		add_ball(bm, root + direction.normalized() * 0.21, 0.03)
	for height in (-0.06, -0.5, bottom + 0.02):
		add_pommel(bm, [(0.06, height - 0.03), (0.095, height - 0.015), (0.095, height + 0.015), (0.06, height + 0.03)])
	add_plate(bm, crescent_shape(0.22, 0.18, 0.08), None, 0.145, matrix=Matrix.Translation((0, 0, blade_base + 2.75)))
	part(bm, "Gold")

	bm = bmesh.new()
	for index in range(5):
		angle = math.tau * index / 5 - math.pi / 2 + math.pi / 5
		add_cabochon(bm, (math.cos(angle) * 0.24, math.sin(angle) * 0.24, crown_base + 0.04), 0.03, 0.02, direction=(math.cos(angle), math.sin(angle), 0))
	part(bm, "Ruby", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	for side in (-1, 1):
		wing, bones = bat_wing_outline(0.62)
		wing_matrix = Matrix.Translation((side * 0.26, 0.1, 0.26)) @ Matrix.Diagonal((side, 1, 1, 1)) @ Matrix.Rotation(math.radians(-6), 4, "Y")
		add_plate(bm, wing, None, 0.025, matrix=wing_matrix)
		for bone in bones:
			add_sweep(bm, [(point.x, point.y) for point in bone], [0.026] * (len(bone) - 1) + [0.008], sides=4, smoothness=3, matrix=wing_matrix)
	add_grip(bm, -0.06, 0.95, 0.07, 0.084, 8)
	add_sweep(bm, [(0, 0, bottom - 0.02), (0.03, 0, bottom + 0.04)], [0.03, 0.025])
	part(bm, "BatBody")

	runes = []
	for index in range(6):
		center = Vector((0, blade_base + 0.42 + index * 0.4))
		runes.append([center + Vector(point) * 0.075 for point in VOID_RUNES[(index + 3) % len(VOID_RUNES)]])
	return {
		"blade": "NightmareBlade",
		"outline": outline,
		"edge_glow": ("7CFF9A", 0.08),
		"decals": runes,
		"decal_width": 0.016,
		"decal_colors": ("7CFF9A", "E0FFE8"),
		"effects": {
			"NightmareBlade": {
				"gradient": (0.6, 4.7, [(0, "0E0818"), (0.5, "2A1A40"), (1, "5A3A8A")]),
				"patterns": [("nebula", "3E7A5A", 2, 0.35), ("cells", "7CFF9A", 2.4, 0.3), ("stars", "FFFFFF", 10, 0.8)],
			},
		},
	}


HALLOWEEN_SWORDS = [
	("CandyCornSword", "Common", build_candy_corn_sword),
	("ScarecrowSickle", "Common", build_scarecrow_sickle),
	("TombstoneSword", "Uncommon", build_tombstone_sword),
	("PumpkinSword", "Uncommon", build_pumpkin_sword),
	("BatWingSword", "Rare", build_bat_wing_sword),
	("SpiderSword", "Rare", build_spider_sword),
	("WitchCauldronBlade", "Epic", build_witch_cauldron_blade),
	("ReaperScythe", "Epic", build_reaper_scythe),
	("GhostSword", "Legendary", build_ghost_sword),
	("VampireSword", "Legendary", build_vampire_sword),
	("HeadlessHorsemanBlade", "Mythic", build_headless_horseman_blade),
	("NightmareKingBlade", "Exclusive", build_nightmare_king_blade),
]


#// Atlantis World

def spiral_path(radius_x, radius_y, start, end, turns, steps, phase=0.0):
	# Helix around the blade, used for kelp, tentacles and serpent bodies.
	path = []
	for step in range(steps):
		t = step / (steps - 1)
		angle = phase + t * math.tau * turns
		path.append((math.cos(angle) * radius_x, math.sin(angle) * radius_y, start + (end - start) * t))
	return path


def add_tentacle(bm, sucker_bm, points, base_radius, suckers=True):
	# Tapered tube with a row of suckers along its inner side.
	count = len(points)
	radii = [base_radius * (1 - index / (count - 1)) ** 0.8 for index in range(count - 1)] + [0.0]
	add_sweep(bm, points, radii, sides=6, smoothness=3)
	if suckers and sucker_bm is not None:
		path = catmull_rom([Vector(point) if len(point) == 3 else Vector((point[0], 0, point[1])) for point in points], 3)
		for index in range(1, len(path) - 3, 2):
			t = index / len(path)
			offset = Vector((0, -1, 0)) * base_radius * GUARD_THICKNESS * (1 - t) * 0.85
			add_ball(sucker_bm, path[index] + offset, base_radius * 0.55 * (1 - t) + 0.008, (1, 0.5, 1))


def add_wave_curl(bm, side, root, size, height=0.0):
	# Golden wave crest that rolls over itself, used as crossguards.
	curl = []
	for step in range(9):
		t = step / 8
		angle = math.pi * 0.9 * t * 2.2
		radius = size * (1 - t * 0.7)
		curl.append((root[0] + side * (size * 1.4 * t + math.sin(angle) * radius * 0.6), root[1] + height + (1 - math.cos(angle)) * radius * 0.6))
	add_sweep(bm, curl, [size * 0.22 * (1 - index / 10) for index in range(8)] + [0.0], sides=6, smoothness=3)


#// Atlantis 01 Kelp Blade (Common)

def build_kelp_blade(part):
	blade_base = 0.16
	length = 2.3
	spine = [(0, blade_base), (0.05, blade_base + 0.8), (-0.04, blade_base + 1.6), (0.03, blade_base + length)]
	outline, plateau = profile_shape(
		spine,
		[(0, 0.2), (0.08, 0.25), (0.75, 0.22), (0.92, 0.14), (1, 0)],
		chamfer=0.09,
		features=[(0.4, 1, 0.1, 0.05, 0.3), (0.62, -1, 0.12, 0.05, -0.3)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "SeaStone")

	bm = bmesh.new()
	for phase in (0, math.pi):
		path = spiral_path(0.27, 0.12, blade_base + 0.05, blade_base + 1.75, 1.3, 14, phase)
		add_sweep(bm, path, [0.03] * 11 + [0.024, 0.016, 0.0], sides=5, smoothness=3)
		for index in (3, 6, 9, 12):
			x, y, z = path[index]
			side = 1 if x > 0 else -1
			leaf, leaf_plateau = profile_shape([(0, 0), (0.1 * side, 0.12), (0.14 * side, 0.3)], [(0, 0.03), (0.4, 0.07), (1, 0)], chamfer=0.025)
			add_plate(bm, leaf, leaf_plateau, 0.006, 0.018, Matrix.Translation((x, y, z)))
	part(bm, "Kelp")

	bm = bmesh.new()
	add_sweep(bm, [(-0.42, 0.02), (-0.2, 0.1), (0, 0.11), (0.2, 0.1), (0.42, 0.02)], [0.05, 0.065, 0.075, 0.065, 0.05], sides=7)
	for side in (-1, 1):
		add_ball(bm, (side * 0.45, 0, 0.0), 0.08, (1, 0.9, 1))
	add_pommel(bm, [(0.06, -0.06), (0.085, -0.03), (0.085, 0.02), (0.06, 0.05)])
	part(bm, "Driftwood")

	bottom = -0.06 - 0.74
	bm = bmesh.new()
	add_grip(bm, -0.06, 0.74, 0.062, 0.074, 7)
	part(bm, "KelpDark")

	bm = bmesh.new()
	add_ball(bm, (0, 0, bottom - 0.12), 0.14, (1, 0.9, 1.05))
	for x, z in ((-0.1, blade_base + 0.35), (0.12, blade_base + 0.7), (-0.08, blade_base + 1.25)):
		add_lathe(bm, [(0.05, -0.07), (0.035, 0.0), (0.045, 0.07)], 6, oriented((x, 0, z), (0, 1, 0)))
	part(bm, "Shell")

	return {
		"blade": "SeaStone",
		"effects": {
			"SeaStone": {"gradient": (0.1, 2.5, [(0, "4E6A7A"), (1, "A8C8D4")]), "patterns": [("cells", "3E5A6A", 3, 0.35), ("nebula", "6AB89A", 2.5, 0.3)]},
			"KelpDark": {"patterns": [("bands", "4E8A4A", 10, 0.5)]},
		},
	}


#// Atlantis 02 Coral Sword (Common)

def build_coral_sword(part):
	blade_base = 0.18
	length = 2.4
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.18), (0.08, 0.23), (0.7, 0.2), (0.9, 0.13), (1, 0)],
		chamfer=0.09,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Coral")

	bm = bmesh.new()
	for side, z, length_scale in ((1, 0.55, 1.0), (-1, 0.95, 0.9), (1, 1.45, 0.8), (-1, 1.9, 0.65)):
		root = Vector((side * 0.19, blade_base + z))
		branch = [root, root + Vector((side * 0.16, 0.1)) * length_scale, root + Vector((side * 0.22, 0.28)) * length_scale]
		add_sweep(bm, branch, [0.04, 0.035, 0.03], sides=6)
		add_ball(bm, (branch[-1].x, 0, branch[-1].y), 0.045)
		twig = [branch[1], branch[1] + Vector((side * 0.14, 0.02)) * length_scale]
		add_sweep(bm, twig, [0.03, 0.026], sides=6)
		add_ball(bm, (twig[-1].x, 0, twig[-1].y), 0.038)
	for side in (-1, 1):
		for angle, reach in ((15, 0.42), (50, 0.34), (-20, 0.3)):
			direction = Vector((side * math.cos(math.radians(angle)), math.sin(math.radians(angle))))
			end = Vector((side * 0.08, 0.1)) + direction * reach
			add_sweep(bm, [(side * 0.06, 0.1), ((side * 0.08 + end.x) / 2, 0.14 + (end.y - 0.1) / 2), (end.x, end.y)], [0.06, 0.05, 0.04], sides=6)
			add_ball(bm, (end.x, 0, end.y), 0.06)
	part(bm, "CoralDeep")

	bottom = -0.04 - 0.74
	bm = bmesh.new()
	add_grip(bm, -0.04, 0.74, 0.062, 0.074, 7)
	part(bm, "Driftwood")

	bm = bmesh.new()
	star = star_shape(5, 0.17, 0.07)
	add_plate(bm, star, [point * 0.45 for point in star], 0.03, 0.07, Matrix.Translation((0, 0, bottom - 0.14)))
	part(bm, "Shell")

	return {
		"blade": "Coral",
		"effects": {
			"Coral": {"gradient": (0.2, 2.6, [(0, "E0506A"), (1, "FFB0B8")]), "patterns": [("stars", "FFE0E6", 7, 0.8), ("cells", "C83A5A", 3, 0.3)]},
			"CoralDeep": {"patterns": [("stars", "FFC2CC", 10, 0.7)]},
			"Shell": {"patterns": [("stars", "FF8A5A", 12, 0.7)]},
		},
	}


#// Atlantis 03 Shell Sword (Uncommon)

def build_shell_sword(part):
	blade_base = 0.32
	length = 2.5
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.17), (0.1, 0.24), (0.55, 0.26), (0.85, 0.17), (1, 0)],
		chamfer=0.1,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Pearl")

	fan = []
	for step in range(15):
		angle = math.pi * step / 14
		radius = 0.46 + (0.035 if step % 2 else 0)
		fan.append(Vector((math.cos(angle) * radius, 0.06 + math.sin(angle) * radius * 0.82)))
	fan += [Vector((-0.08, -0.02)), Vector((0.08, -0.02))]
	bm = bmesh.new()
	add_plate(bm, fan, [Vector((point.x * 0.6, 0.06 + (point.y - 0.06) * 0.6)) for point in fan], 0.03, 0.09)
	part(bm, "ShellPink")

	bm = bmesh.new()
	for step in range(1, 14, 2):
		angle = math.pi * step / 14
		tip = Vector((math.cos(angle) * 0.47, 0.06 + math.sin(angle) * 0.47 * 0.82))
		for y in (-0.085, 0.085):
			add_sweep(bm, [(0, y, 0.0), (tip.x * 0.55, y, tip.y * 0.55), (tip.x * 0.98, y, tip.y * 0.98)], [0.02, 0.022, 0.016], sides=5)
	add_box(bm, (0.22, 0.2, 0.12), (0, 0, -0.02), 0.04)
	add_pommel(bm, [(0.055, -0.08), (0.08, -0.06), (0.08, -0.03), (0.055, -0.02)])
	part(bm, "Shell")

	bottom = -0.08 - 0.74
	bm = bmesh.new()
	add_grip(bm, -0.08, 0.74, 0.062, 0.074, 7)
	part(bm, "Sea")

	bm = bmesh.new()
	add_ball(bm, (0, 0, bottom - 0.13), 0.14)
	add_ball(bm, (0, -0.1, 0.12), 0.07)
	add_ball(bm, (0, 0.1, 0.12), 0.07)
	part(bm, "Pearl")

	return {
		"blade": "Pearl",
		"outline": outline,
		"edge_glow": ("FFD6EA", 0.06),
		"effects": {
			"Pearl": {"gradient": (0.3, 2.8, [(0, "F0A0C8"), (0.35, "F4ECFF"), (0.7, "A8E0FF"), (1, "E0C8FF")]), "patterns": [("nebula", "FFD0EA", 2.5, 0.5), ("nebula", "B8F0FF", 4, 0.4), ("stars", "FFFFFF", 9, 0.7)]},
			"ShellPink": {"gradient": (-0.1, 0.5, [(0, "F08AA0"), (1, "FFD6E0")])},
			"Sea": {"patterns": [("bands", "1E6AA8", 10, 0.5)]},
		},
	}


#// Atlantis 04 Shark Tooth Sword (Uncommon)

def build_shark_tooth_sword(part):
	blade_base = 0.2
	length = 2.35
	serration = [(t, side, 0.07, -0.035, 0.6) for t in (0.18, 0.28, 0.38, 0.48, 0.58, 0.68, 0.78) for side in (-1, 1)]
	outline, plateau = profile_shape(
		[(0, blade_base), (0.04, blade_base + length * 0.6), (0.12, blade_base + length)],
		[(0, 0.36), (0.1, 0.38), (0.6, 0.22), (1, 0)],
		chamfer=0.12,
		features=serration,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.02, 0.12)
	part(bm, "SharkTooth")

	bm = bmesh.new()
	for side in (-1, 1):
		fin = [Vector((side * 0.12, -0.02)), Vector((side * 0.6, 0.02)), Vector((side * 0.52, 0.16)), Vector((side * 0.22, 0.2))]
		add_plate(bm, fin if side > 0 else fin[::-1], None, 0.045)
	add_box(bm, (0.36, 0.2, 0.22), (0, 0, 0.08), 0.06)
	bottom = -0.04 - 0.74
	tail = [Vector((0, 0)), Vector((0.2, -0.22)), Vector((0.08, -0.16)), Vector((0, -0.12)), Vector((-0.08, -0.16)), Vector((-0.2, -0.22))]
	add_plate(bm, tail, None, 0.04, matrix=Matrix.Translation((0, 0, bottom + 0.02)))
	part(bm, "SharkSkin")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.74, 0.062, 0.074, 7)
	part(bm, "Rope")

	return {
		"blade": "SharkTooth",
		"effects": {
			"SharkTooth": {"gradient": (0.2, 2.6, [(0, "C9B89A"), (0.25, "F4F0E6"), (1, "FFFFFF")]), "patterns": [("nebula", "E8E0D0", 3, 0.4)]},
			"SharkSkin": {"gradient": (-0.8, 0.3, [(0, "4A6A8A"), (1, "8AAAC8")])},
		},
	}


#// Atlantis 05 Angler Blade (Rare)

def build_angler_blade(part):
	blade_base = 0.42
	spine = [(0, blade_base), (0.02, blade_base + 1.4), (0.1, blade_base + 2.3), (0.24, blade_base + 2.75)]
	stations = [(0, 0.2), (0.1, 0.25), (0.6, 0.24), (0.85, 0.17), (1, 0)]
	teeth = [(t, 1, 0.1, -0.08, 0.7) for t in (0.3, 0.42, 0.54, 0.66)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1, features=teeth)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Abyss")

	head = Vector((0, 0, 0.2))
	mouth_center = head + Vector((0, 0, -0.04))
	skull = bmesh.new()
	profile = [(0.3 * math.sin(math.pi * ring / 8), -0.3 * math.cos(math.pi * ring / 8)) for ring in range(9)]
	add_lathe(skull, profile, 16, Matrix.LocRotScale(head + Vector((0, 0, 0.04)), None, Vector((1.25, 0.85, 0.95))))
	mouth = [Vector((mouth_center.x + math.cos(angle) * 0.26, mouth_center.z + math.sin(angle) * 0.13)) for angle in numpy.linspace(0, math.tau, 17)[:-1]]
	cutter = bmesh.new()
	for side in (-1, 1):
		add_plate(cutter, mouth, None, 0.15, matrix=Matrix.Translation((0, side * 0.28, 0)))
	bm, inside = carve_pockets(skull, cutter)
	part(inside, "AbyssMouth")
	for side in (-1, 1):
		fin = [Vector((side * 0.3, 0.1)), Vector((side * 0.62, 0.28)), Vector((side * 0.56, 0.08)), Vector((side * 0.62, -0.08)), Vector((side * 0.32, 0.0))]
		add_plate(bm, fin if side > 0 else fin[::-1], None, 0.025)
	antenna = [(-0.05, -0.05, 0.42), (-0.2, -0.12, 0.85), (-0.42, -0.2, 1.05), (-0.58, -0.22, 0.95)]
	add_sweep(bm, antenna, [0.025, 0.02, 0.016, 0.012], sides=5)
	add_grip(bm, -0.1, 0.74, 0.062, 0.074, 7)
	add_pommel(bm, [(0.05, -0.85), (0.09, -0.88), (0.09, -0.93), (0.05, -0.97)])
	part(bm, "AbyssBody")

	bm = bmesh.new()
	for side in (-1, 1):
		for index, x in enumerate(numpy.linspace(-0.2, 0.2, 7)):
			half_height = 0.13 * math.sqrt(max(0.0, 1 - (x / 0.26) ** 2))
			add_spike(bm, (x, side * 0.19, mouth_center.z + half_height + 0.02), (0, side * 0.2, -1), half_height * (1.15 if index % 2 else 0.85), 0.024, sides=4)
			if index < 6:
				lower_x = x + 0.033
				lower_height = 0.13 * math.sqrt(max(0.0, 1 - (lower_x / 0.26) ** 2))
				add_spike(bm, (lower_x, side * 0.19, mouth_center.z - lower_height - 0.02), (0, side * 0.2, 1), lower_height * 0.9, 0.022, sides=4)
	part(bm, "Tooth")

	bm = bmesh.new()
	add_ball(bm, (-0.6, -0.22, 0.88), 0.09)
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.16, -0.22, 0.14)), 0.045)
	for x, z in ((-0.1, blade_base + 0.6), (0.08, blade_base + 1.2), (-0.06, blade_base + 1.8)):
		for y in (-0.095, 0.095):
			add_ball(bm, (x, y, z), 0.035, (1, 0.4, 1))
	part(bm, "LureGlow")

	return {
		"blade": "Abyss",
		"outline": outline,
		"edge_glow": ("4FFFE0", 0.05),
		"effects": {
			"Abyss": {"gradient": (0.4, 3.2, [(0, "0A1024"), (1, "26406A")]), "patterns": [("stars", "6AFFE0", 9, 0.9), ("nebula", "1E5A6A", 2.5, 0.4)]},
			"AbyssBody": {"patterns": [("stars", "4FE0C8", 8, 0.6)]},
		},
	}


#// Atlantis 06 Jellyfish Sword (Rare)

def build_jellyfish_sword(part):
	blade_base = 0.42
	length = 2.6
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.17), (0.1, 0.23), (0.5, 0.26), (0.8, 0.2), (0.93, 0.12), (1, 0)],
		chamfer=0.11,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Jelly")

	bell_profile = [(0.42, 0.06), (0.44, 0.14), (0.38, 0.3), (0.26, 0.42), (0.12, 0.48), (0, 0.5)]
	bm = bmesh.new()
	add_lathe(bm, bell_profile, 16, Matrix.Diagonal((1, 0.75, 1, 1)))
	add_grip(bm, -0.04, 0.74, 0.062, 0.074, 7)
	part(bm, "JellyBell")

	bm = bmesh.new()
	for index in range(8):
		angle = math.tau * index / 8 + 0.2
		root = Vector((math.cos(angle) * 0.36, math.sin(angle) * 0.26, 0.08))
		length = 0.75 + 0.25 * (index % 3) / 2
		points = [root]
		for step in range(1, 6):
			t = step / 5
			sway = math.sin(t * math.pi * 2 + index) * 0.07
			points.append(root * (1 - 0.35 * t) + Vector((sway, sway * 0.5, -length * t)))
		add_sweep(bm, points, [0.03, 0.026, 0.022, 0.018, 0.012, 0.0], sides=5, smoothness=3)
	for x, z in ((-0.08, blade_base + 0.5), (0.1, blade_base + 0.95), (-0.06, blade_base + 1.5), (0.07, blade_base + 2.0)):
		for y in (-0.105, 0.105):
			add_ball(bm, (x, y, z), 0.04, (1, 0.4, 1))
	part(bm, "JellyGlow")

	bottom = -0.04 - 0.74
	bm = bmesh.new()
	add_lathe(bm, [(0.16, bottom - 0.02), (0.15, bottom - 0.08), (0.1, bottom - 0.16), (0, bottom - 0.2)], 12)
	add_ball(bm, (0, 0, 0.5), 0.06)
	part(bm, "Pearl")

	return {
		"blade": "Jelly",
		"outline": outline,
		"edge_glow": ("FF8AE0", 0.07),
		"effects": {
			"Jelly": {"gradient": (0.4, 3.0, [(0, "8A5AE0"), (0.6, "D89AFF"), (1, "FFD6F6")]), "patterns": [("nebula", "FFFFFF", 2.5, 0.35), ("stars", "FFE0FA", 9, 0.7)]},
			"JellyBell": {"gradient": (-0.8, 0.5, [(0, "8A4AC8"), (1, "E0A8FF")]), "patterns": [("stars", "FFE0FA", 7, 0.6)]},
		},
	}


#// Atlantis 07 Poseidon Trident (Epic)

def barbed_prong(base, top, shaft_width, head_width, head_length, barb):
	# Straight prong with an arrow head whose barbs hang down, returns the outline and its plateau.
	head_base = top - head_length
	right = [Vector((shaft_width, base)), Vector((shaft_width, head_base)), Vector((head_width, head_base - barb))]
	outline = right + [Vector((0, top))] + [Vector((-point.x, point.y)) for point in right[::-1]]
	inner = [Vector((shaft_width * 0.6, base + 0.04)), Vector((shaft_width * 0.6, head_base)), Vector((head_width * 0.5, head_base - barb * 0.3))]
	plateau = inner + [Vector((0, top - 0.1))] + [Vector((-point.x, point.y)) for point in inner[::-1]]
	return outline, plateau


def add_barnacle(bm, center, direction, size):
	add_lathe(bm, [(size, -size * 0.3), (size * 0.9, size * 0.3), (size * 0.55, size * 0.75), (size * 0.38, size * 0.62), (0, size * 0.35)], 8, oriented(center, direction))


def build_poseidon_trident(part):
	hub = 1.05
	bm = bmesh.new()
	outline, plateau = barbed_prong(hub - 0.1, hub + 2.2, 0.1, 0.27, 0.5, 0.17)
	add_plate(bm, outline, plateau, 0.045, 0.11)
	for side in (-1, 1):
		arm, arm_plateau = profile_shape([(side * 0.04, hub - 0.08), (side * 0.3, hub + 0.0), (side * 0.52, hub + 0.2), (side * 0.56, hub + 0.48)], [(0, 0.13), (1, 0.1)], tip="flat", chamfer=0.05)
		add_plate(bm, arm, arm_plateau, 0.045, 0.11)
		prong, prong_plateau = barbed_prong(hub + 0.4, hub + 1.8, 0.095, 0.24, 0.45, 0.15)
		add_plate(bm, prong, prong_plateau, 0.045, 0.11, Matrix.Translation((side * 0.56, 0, 0)) @ Matrix.Rotation(math.radians(-side * 4), 4, "Y"))
	part(bm, "AncientBronze")

	bm = bmesh.new()
	add_ball(bm, (0, 0, hub - 0.05), 0.2, (1.15, 0.9, 1.0))
	for height, radius in ((hub - 0.28, 0.11), (hub - 0.42, 0.105)):
		add_lathe(bm, [(0.08, height - 0.05), (radius, height - 0.03), (radius, height + 0.03), (0.08, height + 0.05)], 10)
	add_lathe(bm, [(0.075, hub - 0.2), (0.08, -0.4), (0.075, -1.3)], 10)
	add_lathe(bm, [(0.09, -1.28), (0.11, -1.33), (0.08, -1.42), (0, -1.45)], 10)
	part(bm, "BronzeShaft")

	bm = bmesh.new()
	generator = numpy.random.default_rng(5)
	clusters = [((0.14, hub - 0.02), 4), ((-0.18, hub + 0.06), 3), ((0.5, hub + 0.28), 3), ((-0.54, hub + 0.48), 2), ((0.05, hub + 0.98), 2), ((-0.6, hub + 1.25), 2), ((0.0, hub - 0.48), 3)]
	for (x, z), count in clusters:
		for _ in range(count):
			for y_side in (-1, 1):
				offset = Vector((generator.uniform(-0.08, 0.08), 0, generator.uniform(-0.08, 0.08)))
				center = Vector((x, y_side * 0.09, z)) + offset
				add_barnacle(bm, center, (generator.uniform(-0.3, 0.3), y_side, generator.uniform(-0.2, 0.4)), generator.uniform(0.05, 0.08))
	part(bm, "Barnacle")

	runes = glyph_strokes([[ATLANTIS_GLYPHS[index]] for index in (0, 3, 1)], [(0, hub + 0.5), (0, hub + 1.0), (0, hub + 1.45)], 0.065)
	runes += glyph_strokes([[ATLANTIS_GLYPHS[2]], [ATLANTIS_GLYPHS[4]]], [(-0.56, hub + 0.95), (0.56, hub + 0.95)], 0.06)
	cracks = [
		[(0.03, hub + 0.1), (-0.02, hub + 0.22), (0.02, hub + 0.32)],
		[(0.02, hub + 1.2), (-0.03, hub + 1.3), (0.01, hub + 1.38)],
		[(-0.58, hub + 0.6), (-0.54, hub + 0.72), (-0.58, hub + 0.82)],
		[(0.55, hub + 1.3), (0.6, hub + 1.42)],
	]
	return {
		"blade": "AncientBronze",
		"outline": outline,
		"edge_glow": ("2AD8C8", 0.025),
		"decals": runes + cracks,
		"decal_width": 0.022,
		"decal_colors": ("4FFFF0", "D8FFFF"),
		"effects": {
			"AncientBronze": {"gradient": (0.8, 3.3, [(0, "2E5A50"), (1, "5A9A88")]), "patterns": [("nebula", "A0683A", 3.5, 0.7), ("cells", "1E3A34", 3, 0.4), ("stars", "A8E8D8", 9, 0.4)]},
			"BronzeShaft": {"gradient": (-1.4, 1.2, [(0, "24443C"), (1, "4E8A7A")]), "patterns": [("nebula", "8A5A34", 4, 0.55), ("cells", "1E3A34", 4, 0.3)]},
			"Barnacle": {"gradient": (-0.6, 2.6, [(0, "9A9080"), (1, "D8D0C0")]), "patterns": [("nebula", "7A7060", 6, 0.5)]},
		},
	}


#// Atlantis 08 Octopus Blade (Epic)

def build_octopus_blade(part):
	blade_base = 0.44
	spine = [(0, blade_base), (0, blade_base + 2.0), (-0.06, blade_base + 2.85)]
	stations = [(0, 0.2), (0.08, 0.26), (0.65, 0.24), (0.88, 0.16), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1, features=[(0.35, 1, 0.14, 0.06, 0), (0.55, -1, 0.14, 0.06, 0)])
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "AbyssPurple")

	head = Vector((0, 0, 0.28))
	bm = bmesh.new()
	suckers = bmesh.new()
	add_ball(bm, head + Vector((0, 0.02, 0.06)), 0.27, (1.1, 0.95, 1.15))
	for phase in (0.3, 0.3 + math.pi):
		add_tentacle(bm, suckers, spiral_path(0.26, 0.13, 0.45, blade_base + 1.6, 1.1, 9, phase), 0.06)
	for side in (-1, 1):
		curl = [(side * 0.2, -0.05, 0.12), (side * 0.48, -0.06, 0.05), (side * 0.66, -0.04, 0.2), (side * 0.6, -0.02, 0.38), (side * 0.48, 0.0, 0.32)]
		add_tentacle(bm, suckers, curl, 0.065)
		droop = [(side * 0.12, -0.05, 0.05), (side * 0.3, -0.06, -0.2), (side * 0.26, -0.04, -0.45), (side * 0.36, -0.02, -0.6)]
		add_tentacle(bm, suckers, droop, 0.05)
	add_grip(bm, -0.06, 0.78, 0.062, 0.074, 7)
	part(bm, "Octopus")
	part(suckers, "Sucker")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.13, -0.22, 0.12)), 0.075, (1, 0.6, 1.1))
	bottom = -0.06 - 0.78
	add_ball(bm, (0, 0, bottom - 0.1), 0.12)
	part(bm, "Pearl")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.13, -0.26, 0.11)), 0.04, (1, 0.5, 1.2))
	part(bm, "Socket")

	return {
		"blade": "AbyssPurple",
		"outline": outline,
		"edge_glow": ("E08AFF", 0.05),
		"effects": {
			"AbyssPurple": {"gradient": (0.4, 3.3, [(0, "2A0E3A"), (1, "7A3AA0")]), "patterns": [("cells", "B05AD8", 2.6, 0.35), ("stars", "FFC2F6", 9, 0.7)]},
			"Octopus": {"gradient": (-0.8, 1.8, [(0, "7A2A70"), (1, "D86AC8")]), "patterns": [("stars", "FFB0E8", 7, 0.6)]},
		},
	}


#// Atlantis 09 Atlantean Blade (Legendary)

ATLANTIS_GLYPHS = [
	[(-1, -1), (0, 1), (1, -1), (-1, 0.2), (1, 0.2)],
	[(-1, 1), (1, 1), (0, 1), (0, -1)],
	[(-1, -1), (-1, 1), (1, 0), (-1, -1)],
	[(0, -1), (0, 1), (-1, 0), (1, 0)],
	[(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 0)],
]


def build_atlantean_blade(part):
	blade_base = 0.34
	length = 3.0
	spine = [(0, blade_base), (0, blade_base + length)]
	stations = [(0, 0.2), (0.08, 0.27), (0.45, 0.24), (0.7, 0.29), (0.85, 0.2), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.12)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.02, 0.11)
	part(bm, "Atlantean", CRYSTAL_SMOOTH_ANGLE)

	trim, trim_plateau = profile_shape(spine, [(t, width + 0.05) for t, width in stations], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, trim, trim_plateau, 0.008, 0.016)
	add_torus(bm, 0.2, 0.04, 18, 6, Matrix.Translation((0, 0, 0.18)))
	for side in (-1, 1):
		for height in (0.0, 0.36):
			add_box(bm, (0.2, 0.2, 0.06), (side * 0.52, 0, height), 0.02)
		add_sweep(bm, [(side * 0.18, 0.18), (side * 0.32, 0.22), (side * 0.44, 0.38)], [0.035, 0.03, 0.025], sides=5)
	bottom = -0.04 - 0.8
	add_pommel(bm, [(0.06, -0.04), (0.09, -0.02), (0.09, 0.02), (0.06, 0.04)])
	add_pommel(bm, [(0.06, bottom + 0.02), (0.1, bottom - 0.02), (0.1, bottom - 0.06), (0.06, bottom - 0.08)])
	part(bm, "Gold")

	bm = bmesh.new()
	for side in (-1, 1):
		profile = [(0.075 + (0.012 if step % 2 else 0), 0.03 + step * 0.03) for step in range(10)]
		add_lathe(bm, [(0.075, 0.03)] + profile + [(0.075, 0.33)], 10, Matrix.Translation((side * 0.52, 0, 0)))
	add_lathe(bm, [(0, bottom - 0.08), (0.12, bottom - 0.1), (0.14, bottom - 0.18), (0.08, bottom - 0.26), (0, bottom - 0.28)], 10)
	part(bm, "Marble")

	bm = bmesh.new()
	add_ball(bm, (0, 0, 0.18), 0.14)
	add_gem(bm, (0, 0, bottom - 0.18), 0.07, 0.1)
	part(bm, "AtlantisGlow", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.8, 0.062, 0.074, 7)
	part(bm, "OceanKing")

	centers = [(0, blade_base + 0.45 + index * 0.42) for index in range(6)]
	return {
		"blade": "Atlantean",
		"outline": outline,
		"edge_glow": ("8AFFF6", 0.08),
		"decals": glyph_strokes([[ATLANTIS_GLYPHS[index % len(ATLANTIS_GLYPHS)]] for index in range(6)], centers, 0.07),
		"decal_width": 0.016,
		"decal_colors": ("E0FFFF", "FFFFFF"),
		"effects": {
			"Atlantean": {"gradient": (0.3, 3.4, [(0, "0E8A9A"), (0.5, "4FE0D0"), (1, "C8FFF6")]), "patterns": [("cells", "A8FFF6", 2.5, 0.45), ("stars", "FFFFFF", 9, 0.8)]},
			"Marble": {"patterns": [("nebula", "C8C4B8", 4, 0.35)]},
		},
	}


#// Atlantis 10 Leviathan Fang (Legendary)

def build_leviathan_fang(part):
	blade_base = 0.5
	spine = [(0, blade_base), (0.04, blade_base + 1.5), (0.18, blade_base + 2.6), (0.36, blade_base + 3.05)]
	stations = [(0, 0.2, 0.2), (0.1, 0.25, 0.24), (0.7, 0.24, 0.22), (0.88, 0.18, 0.14), (1, 0, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Leviathan")

	bm = bmesh.new()
	path = catmull_rom([Vector(point) for point in spine], 8) + [Vector(spine[-1])]
	for t in (0.18, 0.36, 0.54, 0.72):
		center = point_on_path(path, t)
		root = center + Vector((-0.22, 0))
		fin = [root + Vector((0.02, -0.1)), root + Vector((-0.3, 0.06)), root + Vector((-0.2, 0.12)), root + Vector((0.02, 0.12))]
		add_plate(bm, fin, None, 0.02)
	tail = [Vector((0, 0)), Vector((0.28, -0.2)), Vector((0.14, -0.04)), Vector((0.24, 0.12)), Vector((0, 0.02)), Vector((-0.24, 0.12)), Vector((-0.14, -0.04)), Vector((-0.28, -0.2))]
	bottom = -0.1 - 0.8
	add_plate(bm, tail[::-1], None, 0.03, matrix=Matrix.Translation((0, 0, bottom - 0.2)))
	part(bm, "Fin")

	head = Vector((0, -0.02, 0.26))
	bm = bmesh.new()
	add_ball(bm, head, 0.28, (1.15, 0.95, 1.0))
	add_ball(bm, head + Vector((0, -0.12, -0.1)), 0.2, (1.0, 1.0, 0.6))
	coil = spiral_path(0.13, 0.13, -0.05, bottom - 0.05, 2.2, 16)
	add_sweep(bm, coil, [0.065] * 12 + [0.055, 0.045, 0.035, 0.03], sides=6, smoothness=3)
	add_grip(bm, -0.1, 0.8, 0.055, 0.06, 6)
	part(bm, "Leviathan")

	bm = bmesh.new()
	for side in (-1, 1):
		add_spike(bm, head + Vector((side * 0.2, 0.08, 0.16)), (side * 0.7, 0.4, 0.9), 0.36, 0.06, sides=5)
		add_spike(bm, head + Vector((side * 0.12, -0.28, -0.04)), (side * 0.1, -0.2, -1), 0.14, 0.03, sides=4)
		add_spike(bm, head + Vector((side * 0.06, -0.3, -0.04)), (0, -0.2, -1), 0.1, 0.025, sides=4)
	part(bm, "Tooth")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.17, -0.2, 0.09)), 0.05, (1.2, 0.6, 0.8))
	part(bm, "AtlantisGlow")

	return {
		"blade": "Leviathan",
		"outline": outline,
		"edge_glow": ("6AFFF0", 0.06),
		"effects": {
			"Leviathan": {"gradient": (0.4, 3.6, [(0, "0E3A5A"), (0.6, "2E8AA0"), (1, "8AE8E8")]), "patterns": [("cells", "6AD8E0", 9, 0.45)]},
			"Fin": {"gradient": (0.0, 3.0, [(0, "2E8AB0"), (1, "B8F4FA")])},
		},
	}


#// Atlantis 11 Kraken Sword (Mythic)

def build_kraken_sword(part):
	blade_base = 0.5
	spine = [(0, blade_base), (0, blade_base + 2.2), (0.08, blade_base + 3.3)]
	stations = [(0, 0.24), (0.07, 0.32), (0.4, 0.3), (0.62, 0.36), (0.84, 0.26), (1, 0)]
	teeth = [(t, side, 0.16, -0.12, 0.75) for t, side in ((0.3, 1), (0.36, -1), (0.52, 1), (0.58, -1), (0.74, 1), (0.8, -1))]
	outline, plateau = profile_shape(spine, stations, chamfer=0.12, features=teeth)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.02, 0.11)
	part(bm, "Kraken")

	bm = bmesh.new()
	suckers = bmesh.new()
	add_ball(bm, (0, 0.04, 0.3), 0.32, (1.15, 0.95, 1.1))
	add_tentacle(bm, suckers, spiral_path(0.34, 0.15, 0.4, blade_base + 2.3, 1.4, 12, 0.6), 0.08)
	for side in (-1, 1):
		curl = [(side * 0.25, -0.04, 0.3), (side * 0.6, -0.06, 0.4), (side * 0.85, -0.04, 0.7), (side * 0.8, -0.02, 1.0), (side * 0.62, 0.0, 1.05), (side * 0.6, 0.0, 0.9)]
		add_tentacle(bm, suckers, curl, 0.08)
		droop = [(side * 0.2, -0.04, 0.08), (side * 0.48, -0.06, -0.1), (side * 0.5, -0.04, -0.45), (side * 0.36, -0.02, -0.7), (side * 0.42, 0.0, -0.85)]
		add_tentacle(bm, suckers, droop, 0.065)
	bottom = -0.08 - 0.85
	add_grip(bm, -0.08, 0.85, 0.064, 0.077, 8)
	part(bm, "KrakenSkin")
	part(suckers, "Sucker")

	bm = bmesh.new()
	add_ball(bm, (0, -0.2, 0.34), 0.16, (1.3, 0.6, 1.0))
	add_ball(bm, (0, 0, bottom - 0.12), 0.14)
	part(bm, "KrakenEye")

	bm = bmesh.new()
	add_box(bm, (0.05, 0.08, 0.22), (0, -0.28, 0.34), 0.02)
	part(bm, "Socket")

	runes = []
	for index in range(6):
		center = Vector((0, blade_base + 0.5 + index * 0.4))
		runes.append([center + Vector(point) * 0.07 for point in VOID_RUNES[(index * 3) % len(VOID_RUNES)]])
	return {
		"blade": "Kraken",
		"outline": outline,
		"edge_glow": ("C26AFF", 0.07),
		"decals": runes,
		"decal_width": 0.016,
		"decal_colors": ("FFD23A", "FFF6C0"),
		"effects": {
			"Kraken": {"gradient": (0.5, 3.8, [(0, "12061E"), (0.5, "3A1A5A"), (1, "7A4AB0")]), "patterns": [("nebula", "2A6A8A", 2.2, 0.35), ("cells", "C26AFF", 2.6, 0.35)]},
			"KrakenSkin": {"gradient": (-0.9, 1.3, [(0, "3A1450"), (1, "8A4AB0")]), "patterns": [("stars", "E0A8FF", 7, 0.5)]},
		},
	}


#// Atlantis 12 Ocean King Blade (Exclusive)

def build_ocean_king_blade(part):
	blade_base = 0.6
	spine = [(0, blade_base), (0, blade_base + 3.9)]
	stations = [(0, 0.3), (0.06, 0.4), (0.45, 0.38), (0.72, 0.44), (0.88, 0.3), (1, 0)]
	crests = [(t, side, 0.3, 0.07, 0.6 * side) for t in (0.25, 0.42, 0.59) for side in (-1, 1)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.13, features=crests)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.022, 0.12)
	part(bm, "OceanKing")

	trim, trim_plateau = profile_shape(spine, [(t, width + 0.07) for t, width in stations], chamfer=0.04, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, trim, trim_plateau, 0.008, 0.016)
	for side in (-1, 1):
		add_wave_curl(bm, side, (0.2, 0.22), 0.42)
		add_wave_curl(bm, side, (0.16, 0.02), 0.28, -0.02)
	crown_base = 0.5
	add_lathe(bm, [(0.2, crown_base), (0.22, crown_base), (0.23, crown_base + 0.08), (0.21, crown_base + 0.08)], 16, closed=True)
	for index in range(5):
		angle = math.tau * index / 5 - math.pi / 2
		direction = Vector((math.cos(angle) * 0.2, math.sin(angle) * 0.2, 1))
		root = Vector((math.cos(angle) * 0.22, math.sin(angle) * 0.22, crown_base + 0.06))
		add_spike(bm, root, direction, 0.22, 0.05, sides=4)
	fan = []
	for step in range(17):
		angle = math.pi * step / 16
		radius = 0.62 + (0.045 if step % 2 else 0)
		fan.append(Vector((math.cos(angle) * radius, 0.1 + math.sin(angle) * radius * 0.78)))
	fan += [Vector((-0.12, 0.0)), Vector((0.12, 0.0))]
	add_plate(bm, fan, [Vector((point.x * 0.62, 0.1 + (point.y - 0.1) * 0.62)) for point in fan], 0.035, 0.1)
	for step in range(1, 16, 2):
		angle = math.pi * step / 16
		tip = Vector((math.cos(angle) * 0.6, 0.1 + math.sin(angle) * 0.6 * 0.78))
		for y in (-0.11, 0.11):
			add_sweep(bm, [(0, y, 0.06), (tip.x * 0.55, y, tip.y * 0.55), (tip.x * 0.97, y, tip.y * 0.97)], [0.022, 0.025, 0.018], sides=5)
	bottom = -0.08 - 0.95
	for height in (-0.08, -0.52, bottom + 0.02):
		add_pommel(bm, [(0.06, height - 0.03), (0.095, height - 0.015), (0.095, height + 0.015), (0.06, height + 0.03)])
	conch = []
	for step in range(9):
		t = step / 8
		conch.append((0.15 * (1 - t) + 0.015 + (0.02 if step % 2 else 0), bottom - 0.05 - 0.38 * t))
	conch.append((0, bottom - 0.46))
	add_lathe(bm, conch, 10)
	part(bm, "Gold")

	bm = bmesh.new()
	add_ball(bm, (0, 0, 0.26), 0.2, (1, 1.15, 1))
	for x, z in ((-0.14, blade_base + 0.9), (0.12, blade_base + 1.6), (-0.1, blade_base + 2.4), (0.11, blade_base + 3.1)):
		for y in (-0.115, 0.115):
			add_ball(bm, (x, y, z), 0.045, (1, 0.4, 1))
	part(bm, "PearlGlow")

	bm = bmesh.new()
	for index in range(5):
		angle = math.tau * index / 5 - math.pi / 2 + math.pi / 5
		add_cabochon(bm, (math.cos(angle) * 0.22, math.sin(angle) * 0.22, crown_base + 0.04), 0.03, 0.02, direction=(math.cos(angle), math.sin(angle), 0))
	part(bm, "Sapphire", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, -0.08, 0.95, 0.07, 0.084, 8)
	part(bm, "Sea")

	waves = []
	for index in range(7):
		z = blade_base + 0.4 + index * 0.45
		waves.append([(-0.16, z), (-0.1, z + 0.06), (-0.04, z), (0.02, z + 0.06), (0.08, z), (0.14, z + 0.06)])
	return {
		"blade": "OceanKing",
		"outline": outline,
		"edge_glow": ("8AF0FF", 0.08),
		"decals": waves,
		"decal_width": 0.02,
		"decal_colors": ("B8F4FF", "FFFFFF"),
		"effects": {
			"OceanKing": {"gradient": (0.6, 4.5, [(0, "0A1E5A"), (0.45, "1E5AC8"), (1, "6AD8FF")]), "patterns": [("nebula", "4FB8FF", 2, 0.4), ("stars", "FFFFFF", 10, 0.8)]},
			"Sea": {"patterns": [("bands", "0E3A8A", 10, 0.5)]},
		},
	}


ATLANTIS_SWORDS = [
	("KelpBlade", "Common", build_kelp_blade),
	("CoralSword", "Common", build_coral_sword),
	("ShellSword", "Uncommon", build_shell_sword),
	("SharkToothSword", "Uncommon", build_shark_tooth_sword),
	("AnglerBlade", "Rare", build_angler_blade),
	("JellyfishSword", "Rare", build_jellyfish_sword),
	("PoseidonTrident", "Epic", build_poseidon_trident),
	("OctopusBlade", "Epic", build_octopus_blade),
	("AtlanteanBlade", "Legendary", build_atlantean_blade),
	("LeviathanFang", "Legendary", build_leviathan_fang),
	("KrakenSword", "Mythic", build_kraken_sword),
	("OceanKingBlade", "Exclusive", build_ocean_king_blade),
]


#// Magma World

def lava_cracks(start, end, width, count, seed):
	# Zigzag cracks running up the blade, painted as glowing decals.
	generator = numpy.random.default_rng(seed)
	cracks = []
	for index in range(count):
		z = start + (end - start) * (index + 0.5) / count
		x = generator.uniform(-width, width) * 0.5
		crack = [(x, z - 0.12)]
		for _ in range(3):
			x = max(-width, min(width, x + generator.uniform(-0.07, 0.07)))
			crack.append((x, crack[-1][1] + 0.09))
		cracks.append(crack)
		cracks.append([crack[1], (crack[1][0] + generator.choice((-1, 1)) * 0.08, crack[1][1] + 0.05)])
	return cracks


def add_rock_chunk(bm, center, size, seed):
	# Lumpy low poly rock, an icosphere with every vertex pushed in or out a bit.
	generator = numpy.random.default_rng(seed)
	before = set(bm.verts)
	add_ball(bm, (0, 0, 0), 1)
	for vert in new_verts_since(bm, before):
		vert.co = Vector((vert.co.x * size[0], vert.co.y * size[1], vert.co.z * size[2])) * generator.uniform(0.82, 1.12) + Vector(center)


#// Magma 01 Basalt Sword (Common)

def build_basalt_sword(part):
	blade_base = 0.16
	length = 2.2
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.24), (0.08, 0.28), (0.85, 0.27), (1, 0.2)],
		tip=[(1, 0.0), (0.4, 0.14), (-0.5, 0.1), (-1, 0.0)],
		chamfer=0.1,
		features=[(0.3, 1, 0.12, 0.06, 0.2), (0.62, -1, 0.14, 0.07, -0.2), (0.82, 1, 0.1, 0.05, 0)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.04, 0.13)
	part(bm, "Basalt")

	bm = bmesh.new()
	for x, seed in ((-0.36, 1), (0.36, 2), (0.0, 3)):
		add_rock_chunk(bm, (x, 0, 0.06), (0.17 if x else 0.2, 0.15, 0.13), seed)
	bottom = -0.06 - 0.72
	add_rock_chunk(bm, (0, 0, bottom - 0.1), (0.15, 0.14, 0.14), 4)
	part(bm, "BasaltDark")

	bm = bmesh.new()
	add_grip(bm, -0.06, 0.72, 0.062, 0.074, 7)
	part(bm, "DarkLeather")

	return {
		"blade": "Basalt",
		"effects": {
			"Basalt": {"gradient": (0.1, 2.5, [(0, "3E3E48"), (1, "7A7A88")]), "patterns": [("cells", "2A2A34", 6, 0.6)]},
			"BasaltDark": {"patterns": [("cells", "22222A", 8, 0.5)]},
		},
	}


#// Magma 02 Ember Blade (Common)

def build_ember_blade(part):
	blade_base = 0.2
	length = 2.4
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.17), (0.08, 0.21), (0.75, 0.19), (0.9, 0.13), (1, 0)],
		chamfer=0.09,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Ember")

	bm = bmesh.new()
	arm = [(0.1, 0.1), (0.3, 0.08), (0.4, 0.14)]
	add_sweep(bm, arm, [0.06, 0.055, 0.045])
	add_sweep(bm, mirror(arm), [0.06, 0.055, 0.045])
	add_box(bm, (0.3, 0.2, 0.22), (0, 0, 0.1), 0.05)
	bottom = -0.04 - 0.74
	add_pommel(bm, [(0.05, bottom + 0.02), (0.09, bottom - 0.02), (0.09, bottom - 0.08), (0.05, bottom - 0.12)])
	part(bm, "IronBlack")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.1), 0.06, 0.13)
	add_gem(bm, (0, 0, bottom - 0.16), 0.06, 0.08)
	part(bm, "EmberGlow", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.74, 0.062, 0.074, 7)
	part(bm, "DarkLeather")

	return {
		"blade": "Ember",
		"outline": outline,
		"edge_glow": ("FF7A2E", 0.06),
		"effects": {"Ember": {"gradient": (0.2, 2.7, [(0, "2A1E1E"), (1, "5A4444")]), "patterns": [("stars", "FFA040", 9, 0.9)]}},
	}


#// Magma 03 Obsidian Shard (Uncommon)

def build_obsidian_shard(part):
	blade_base = 0.24
	length = 2.5
	jagged = [(t, side, 0.12, -0.07 * (1 + (index % 2)), 0.7) for index, (t, side) in enumerate(((0.2, 1), (0.32, -1), (0.45, 1), (0.58, -1), (0.7, 1), (0.8, -1)))]
	outline, plateau = profile_shape(
		[(0, blade_base), (0, blade_base + length)],
		[(0, 0.18), (0.1, 0.25), (0.5, 0.22), (0.85, 0.15), (1, 0)],
		chamfer=0.14,
		plateau_ratio=0.15,
		features=jagged,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.015, 0.12)
	part(bm, "Obsidian", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	for side in (-1, 1):
		for angle, length_scale in ((15, 0.38), (45, 0.28), (-20, 0.22)):
			direction = (side * math.cos(math.radians(angle)), 0, math.sin(math.radians(angle)))
			add_crystal(bm, (side * 0.12, 0, 0.1), direction, length_scale, 0.07)
	bottom = -0.04 - 0.74
	add_crystal(bm, (0, 0, bottom - 0.02), (0, 0, -1), 0.3, 0.08)
	part(bm, "Obsidian", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_box(bm, (0.3, 0.2, 0.18), (0, 0, 0.08), 0.05)
	add_pommel(bm, [(0.06, bottom + 0.04), (0.09, bottom + 0.02), (0.09, bottom - 0.02), (0.06, bottom - 0.04)])
	part(bm, "BasaltDark")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.74, 0.062, 0.074, 7)
	part(bm, "DarkLeather")

	return {
		"blade": "Obsidian",
		"outline": outline,
		"edge_glow": ("B07AFF", 0.04),
		"effects": {"Obsidian": {"gradient": (-0.8, 2.8, [(0, "120A1E"), (0.6, "2E2244"), (1, "5A4A80")]), "patterns": [("nebula", "6A4AA0", 3, 0.45), ("stars", "E0D0FF", 8, 0.6)]}},
	}


#// Magma 04 Lava Cleaver (Uncommon)

def build_lava_cleaver(part):
	blade_base = 0.22
	spine = [(0.08, blade_base), (0.08, blade_base + 2.2)]
	outline, plateau = profile_shape(
		spine,
		[(0, 0.16, 0.2), (0.12, 0.24, 0.34), (0.9, 0.24, 0.38), (1, 0.24, 0.38)],
		tip=[(1, 0.0), (0.6, 0.1), (-1, 0.1)],
		chamfer=0.1,
		features=[(0.45, -1, 0.14, 0.07, 0), (0.7, 1, 0.16, 0.06, 0.4)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.03, 0.12)
	add_lathe(bm, [(0.07, -0.05), (0.07, 0.05)], 10, oriented((-0.04, 0, blade_base + 1.9), (0, 1, 0)))
	part(bm, "VolcanoRock")

	bm = bmesh.new()
	add_box(bm, (0.5, 0.22, 0.2), (0.06, 0, 0.1), 0.06)
	bottom = -0.04 - 0.76
	add_pommel(bm, [(0.05, bottom + 0.02), (0.1, bottom - 0.02), (0.1, bottom - 0.08), (0.05, bottom - 0.1)])
	part(bm, "IronBlack")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.76, 0.062, 0.074, 7)
	part(bm, "DarkLeather")

	return {
		"blade": "VolcanoRock",
		"outline": outline,
		"edge_glow": ("FF6A1E", 0.06),
		"decals": lava_cracks(blade_base + 0.3, blade_base + 2.0, 0.22, 6, 11),
		"decal_width": 0.025,
		"decal_colors": ("FF6A1E", "FFD27A"),
		"effects": {"VolcanoRock": {"gradient": (0.2, 2.5, [(0, "241818"), (1, "4A3A34")]), "patterns": [("cells", "FF5A1E", 3, 0.25)]}},
	}


#// Magma 05 Salamander Sword (Rare)

def build_salamander_sword(part):
	blade_base = 0.3
	spine = [(0, blade_base), (0.02, blade_base + 1.5), (0.14, blade_base + 2.5), (0.3, blade_base + 2.8)]
	outline, plateau = profile_shape(spine, [(0, 0.18), (0.08, 0.23), (0.7, 0.22), (0.9, 0.15), (1, 0)], chamfer=0.09)
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "Ember")

	body = [(-0.55, -0.02, 0.18), (-0.3, -0.06, 0.12), (0.0, -0.08, 0.14), (0.3, -0.06, 0.12), (0.5, -0.02, 0.16)]
	bm = bmesh.new()
	add_sweep(bm, body, [0.08, 0.1, 0.11, 0.1, 0.07], sides=8)
	add_ball(bm, (0.58, -0.02, 0.18), 0.12, (1.25, 1, 0.85))
	tail = spiral_path(0.12, 0.12, 0.05, -0.75, 1.6, 12, math.pi)
	add_sweep(bm, [(-0.55, -0.02, 0.18), (-0.5, 0.0, 0.05), (-0.25, 0.08, -0.02)] + tail[1:], [0.08, 0.07, 0.06] + [0.05] * 6 + [0.04, 0.03, 0.02, 0.012, 0.0], sides=6, smoothness=3)
	for x in (-0.32, 0.32):
		for y in (-0.12, 0.12):
			add_sweep(bm, [(x, -0.06, 0.1), (x + 0.04, y * 1.2 - 0.06, 0.0), (x + 0.08, y * 1.3 - 0.06, -0.06)], [0.035, 0.03, 0.025], sides=5)
	part(bm, "Salamander")

	bm = bmesh.new()
	for x in (-0.4, -0.15, 0.1, 0.32):
		add_ball(bm, (x, -0.13, 0.2), 0.04, (1, 0.5, 1))
	part(bm, "SalamanderSpot")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, (0.66, side * 0.09 - 0.02, 0.24), 0.035)
	part(bm, "EmberGlow")

	bm = bmesh.new()
	add_grip(bm, -0.02, 0.74, 0.056, 0.066, 7)
	add_pommel(bm, [(0.05, -0.78), (0.09, -0.81), (0.09, -0.86), (0.05, -0.9)])
	part(bm, "DarkLeather")

	return {
		"blade": "Ember",
		"outline": outline,
		"edge_glow": ("FF8A3A", 0.05),
		"effects": {
			"Ember": {"gradient": (0.3, 3.1, [(0, "5A1E10"), (0.6, "C0401E"), (1, "FF9A4A")]), "patterns": [("flames", "FFB347", 4, 0.35)]},
			"Salamander": {"gradient": (-0.8, 0.3, [(0, "C0300E"), (1, "FF7A3A")]), "patterns": [("cells", "8A1A0E", 9, 0.4)]},
		},
	}


#// Magma 06 Volcano Sword (Rare)

def build_volcano_sword(part):
	blade_base = 0.2
	length = 2.6
	spine = [(0, blade_base), (0, blade_base + length)]
	stations = [(0, 0.2), (0.08, 0.26), (0.7, 0.24), (0.88, 0.16), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1, features=[(0.4, 1, 0.12, 0.05, 0.3), (0.62, -1, 0.14, 0.05, -0.3)])
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "VolcanoRock")

	river, river_plateau = profile_shape([(0, blade_base + 0.05), (0.03, blade_base + 0.8), (-0.03, blade_base + 1.5), (0, blade_base + 2.1)], [(0, 0.07), (0.5, 0.05), (1, 0)], chamfer=0.02, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, river, river_plateau, 0.105, 0.11)
	generator = numpy.random.default_rng(3)
	for index in range(7):
		angle = generator.uniform(0, math.tau)
		x = math.cos(angle) * 0.36
		drip = [(x, -0.06, 0.06), (x * 1.02, -0.07, -0.04), (x * 0.98, -0.06, -0.14 - generator.uniform(0, 0.12))]
		add_sweep(bm, drip, [0.03, 0.026, 0.0], sides=5)
	add_ball(bm, (0, -0.15, 0.12), 0.07, (1, 0.5, 1))
	bottom = 0.0 - 0.76
	add_ball(bm, (0, 0, bottom - 0.14), 0.07)
	part(bm, "LavaGlow")

	bm = bmesh.new()
	for x, seed, size in ((-0.36, 61, 0.15), (-0.16, 62, 0.17), (0.16, 63, 0.17), (0.36, 64, 0.15), (0.0, 65, 0.18)):
		add_rock_chunk(bm, (x, 0, 0.1), (size, 0.15, 0.13), seed)
	add_rock_chunk(bm, (0, 0, bottom - 0.12), (0.15, 0.14, 0.15), 66)
	part(bm, "VolcanoDark")

	bm = bmesh.new()
	add_grip(bm, 0.0, 0.76, 0.062, 0.074, 7)
	part(bm, "DarkLeather")

	return {
		"blade": "VolcanoRock",
		"outline": outline,
		"edge_glow": ("FF5A1E", 0.05),
		"decals": lava_cracks(blade_base + 0.3, blade_base + 2.2, 0.2, 6, 21),
		"decal_width": 0.022,
		"decal_colors": ("FF6A1E", "FFD27A"),
		"effects": {
			"VolcanoRock": {"gradient": (0.2, 2.8, [(0, "3A1E14"), (1, "5A4A44")]), "patterns": [("cells", "2A1E1A", 4, 0.4), ("stars", "FF8A3A", 9, 0.5)]},
			"VolcanoDark": {"gradient": (-0.9, 0.3, [(0, "2A1E1A"), (1, "5A3A2E")]), "patterns": [("cells", "FF6A1E", 4, 0.45)]},
			"LavaGlow": {"gradient": (-0.9, 2.3, [(0, "FF4A0E"), (1, "FFD23A")])},
		},
	}


#// Magma 07 Magma Golem Blade (Epic)

def build_magma_golem_blade(part):
	blade_base = 0.42
	length = 2.9
	spine = [(0, blade_base), (0, blade_base + length)]
	outline, plateau = profile_shape(
		spine,
		[(0, 0.26), (0.08, 0.32), (0.75, 0.3), (0.9, 0.22), (1, 0.12)],
		tip=[(1, 0.0), (0.5, 0.1), (-0.3, 0.16), (-1, 0.0)],
		chamfer=0.12,
		features=[(0.3, 1, 0.16, 0.06, 0.2), (0.55, -1, 0.18, 0.07, -0.2), (0.78, 1, 0.14, 0.05, 0)],
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.04, 0.14)
	part(bm, "GolemRock")

	path = catmull_rom([Vector(point) for point in spine], 8) + [Vector(spine[-1])]
	bm = bmesh.new()
	for index, (t, side) in enumerate(((0.12, 1), (0.22, -1), (0.42, 1), (0.48, -1), (0.66, -1), (0.7, 1))):
		center = point_on_path(path, t)
		add_rock_chunk(bm, (center.x + side * 0.3, 0, center.y), (0.13, 0.17, 0.16), 70 + index)
	head = Vector((0, 0, 0.22))
	add_rock_chunk(bm, head, (0.34, 0.26, 0.26), 80)
	for side in (-1, 1):
		add_rock_chunk(bm, (side * 0.46, 0, 0.3), (0.2, 0.2, 0.2), 81 + side)
		add_rock_chunk(bm, (side * 0.56, -0.02, 0.05), (0.15, 0.15, 0.17), 84 + side)
	bottom = 0.0 - 0.8
	add_rock_chunk(bm, (0, 0, bottom - 0.12), (0.17, 0.16, 0.16), 88)
	part(bm, "GolemBoulder")

	bm = bmesh.new()
	for y in (-1, 1):
		for side in (-1, 1):
			add_box(bm, (0.12, 0.08, 0.06), head + Vector((side * 0.13, y * 0.22, 0.06)), 0.02)
		add_box(bm, (0.24, 0.08, 0.05), head + Vector((0, y * 0.21, -0.1)), 0.02)
	for side in (-1, 1):
		add_box(bm, (0.04, 0.3, 0.2), (side * 0.46, 0, 0.3), 0.01)
	add_box(bm, (0.05, 0.26, 0.16), (0, 0, bottom - 0.12), 0.01)
	part(bm, "LavaGlow")

	bm = bmesh.new()
	add_grip(bm, 0.0, 0.8, 0.064, 0.077, 7)
	part(bm, "DarkLeather")

	return {
		"blade": "GolemRock",
		"outline": outline,
		"edge_glow": ("FF6A1E", 0.06),
		"decals": lava_cracks(blade_base + 0.3, blade_base + 2.6, 0.24, 7, 51),
		"decal_width": 0.026,
		"decal_colors": ("FF6A1E", "FFE07A"),
		"effects": {
			"GolemRock": {"gradient": (0.4, 3.3, [(0, "3A2A24"), (1, "6A5248")]), "patterns": [("cells", "2A1E1A", 4, 0.45)]},
			"GolemBoulder": {"gradient": (-1.0, 3.0, [(0, "2A1E1A"), (1, "7A6052")]), "patterns": [("cells", "FF6A1E", 3.5, 0.4)]},
			"LavaGlow": {"gradient": (-1.0, 0.5, [(0, "FF4A0E"), (1, "FFD23A")])},
		},
	}


#// Magma 08 Phoenix Feather (Epic)

def build_phoenix_feather(part):
	blade_base = 0.2
	spine = [(0, blade_base), (0.04, blade_base + 1.4), (0.16, blade_base + 2.5), (0.3, blade_base + 2.95)]
	stations = [(0, 0.16), (0.08, 0.24), (0.5, 0.29), (0.8, 0.22), (0.94, 0.1), (1, 0)]
	notches = [(t, side, 0.1, 0.07, 0.8 * side) for t, side in ((0.35, 1), (0.48, -1), (0.6, 1), (0.72, -1), (0.82, 1))]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1, features=notches)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.016, 0.08)
	part(bm, "PhoenixFeather")

	bm = bmesh.new()
	for side in (-1, 1):
		root = Vector((side * 0.16, 0.12))
		for angle, length, width in ((10, 0.62, 0.09), (32, 0.52, 0.085), (55, 0.4, 0.075), (-10, 0.4, 0.07)):
			direction = Vector((side * math.cos(math.radians(angle)), math.sin(math.radians(angle))))
			feather_spine = [root, root + direction * length * 0.5 + Vector((0, 0.05)), root + direction * length]
			feather, feather_plateau = profile_shape(feather_spine, [(0, width * 0.5), (0.35, width), (0.8, width * 0.8), (1, 0)], chamfer=width * 0.4)
			add_plate(bm, feather, feather_plateau, 0.008, 0.028)
	part(bm, "PhoenixWing")

	bm = bmesh.new()
	add_box(bm, (0.3, 0.22, 0.24), (0, 0, 0.12), 0.06)
	bottom = -0.04 - 0.76
	add_pommel(bm, [(0.06, -0.04), (0.09, -0.02), (0.09, 0.02), (0.06, 0.04)])
	add_pommel(bm, [(0.05, bottom + 0.02), (0.09, bottom - 0.02), (0.09, bottom - 0.06), (0.05, bottom - 0.08)])
	part(bm, "Gold")

	bm = bmesh.new()
	add_cabochon(bm, (0, 0, 0.12), 0.07, 0.14)
	add_flame(bm, Vector((0, bottom - 0.08)), (0, -1), 0.32, 0.09)
	for side in (-1, 1):
		add_flame(bm, Vector((side * 0.1, 0.32)), (side * 0.4, 1), 0.45, 0.09, side)
	part(bm, "PhoenixGlow")

	bm = bmesh.new()
	add_grip(bm, -0.04, 0.76, 0.062, 0.074, 7)
	part(bm, "RedCloth")

	vane = [[(-0.02, blade_base + 0.1), (0.02, blade_base + 1.4), (0.13, blade_base + 2.45)]]
	for index in range(8):
		z = blade_base + 0.35 + index * 0.27
		x = 0.02 + 0.13 * max(0, (z - blade_base - 1.4) / 1.05)
		vane.append([(x, z), (x - 0.14, z + 0.12)])
		vane.append([(x, z), (x + 0.14, z + 0.12)])
	return {
		"blade": "PhoenixFeather",
		"outline": outline,
		"edge_glow": ("FFE07A", 0.06),
		"decals": vane,
		"decal_width": 0.014,
		"decal_colors": ("A8200E", "FFE07A"),
		"effects": {
			"PhoenixFeather": {"gradient": (0.3, 3.3, [(0, "B8200E"), (0.45, "FF6A1E"), (0.8, "FFB03A"), (1, "FFF0A0")])},
			"PhoenixWing": {"gradient": (0.0, 0.8, [(0, "D8300E"), (1, "FFC23A")])},
		},
	}


#// Magma 09 Inferno Katana (Legendary)

def build_inferno_katana(part):
	blade_base = 0.22
	spine = [(0, blade_base), (0.03, blade_base + 1.5), (0.14, blade_base + 2.7), (0.26, blade_base + 3.2)]
	outline, plateau = profile_shape(
		spine,
		[(0, 0.13, 0.13), (0.1, 0.14, 0.14), (0.85, 0.12, 0.12), (0.95, 0.1, 0.06), (1, 0, 0)],
		chamfer=0.07,
	)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.014, 0.07)
	part(bm, "InfernoSteel")

	bm = bmesh.new()
	tsuba = []
	for step in range(16):
		angle = math.tau * step / 16
		radius = 0.3 if step % 4 else 0.34
		tsuba.append(Vector((math.cos(angle) * radius, math.sin(angle) * radius * 0.8)))
	add_plate(bm, tsuba, [point * 0.7 for point in tsuba], 0.035, 0.05, Matrix.Translation((0, 0, 0.12)) @ Matrix.Rotation(math.radians(90), 4, "X"))
	add_box(bm, (0.16, 0.14, 0.12), (0, 0, 0.2), 0.03)
	bottom = 0.1 - 1.0
	add_pommel(bm, [(0.055, bottom + 0.02), (0.075, bottom), (0.075, bottom - 0.05), (0.05, bottom - 0.07)])
	part(bm, "IronBlack")

	bm = bmesh.new()
	for side in (-1, 1):
		add_flame(bm, Vector((side * 0.12, 0.12)), (side * 1, 0.4), 0.3, 0.07, side)
	part(bm, "EmberGlow")

	bm = bmesh.new()
	add_grip(bm, 0.1, 1.0, 0.058, 0.07, 9)
	part(bm, "KatanaWrap")

	bm = bmesh.new()
	for index in range(9):
		z = 0.06 - index * 0.111
		add_box(bm, (0.04, 0.2, 0.04), (0, 0, z), 0.01)
	part(bm, "Gold")

	hamon = []
	path = catmull_rom([Vector(point) for point in spine], 8) + [Vector(spine[-1])]
	previous = None
	for step in range(26):
		t = 0.05 + step * 0.034
		center = point_on_path(path, t)
		point = (center.x - 0.05 + (0.035 if step % 2 else 0), center.y)
		if previous:
			hamon.append([previous, point])
		previous = point
	return {
		"blade": "InfernoSteel",
		"outline": outline,
		"edge_glow": ("FF6A1E", 0.06),
		"decals": hamon,
		"decal_width": 0.02,
		"decal_colors": ("FF8A2E", "FFE07A"),
		"effects": {
			"InfernoSteel": {"gradient": (0.2, 3.4, [(0, "2A2228"), (1, "6A6070")]), "patterns": [("flames", "FF5A1E", 5, 0.45)]},
			"KatanaWrap": {"patterns": [("bands", "4A0812", 12, 0.6)]},
		},
	}


#// Magma 10 Dragonfire Sword (Legendary)

def build_dragonfire_sword(part):
	blade_base = 0.42
	length = 2.9
	spine = [(0, blade_base), (0, blade_base + length)]
	stations = [(0, 0.2), (0.08, 0.27), (0.6, 0.25), (0.82, 0.3), (0.9, 0.2), (1, 0)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.1, features=[(0.82, side, 0.14, -0.1, 0.7) for side in (-1, 1)])
	bm = bmesh.new()
	add_plate(bm, outline, plateau)
	part(bm, "DragonSteel")

	head = Vector((0, -0.02, 0.32))
	bm = bmesh.new()
	add_ball(bm, head, 0.26, (1.1, 1.0, 1.0))
	add_box(bm, (0.3, 0.42, 0.18), head + Vector((0, -0.26, -0.06)), 0.07)
	add_box(bm, (0.26, 0.36, 0.08), head + Vector((0, -0.2, -0.22)), 0.03)
	for side in (-1, 1):
		wing, bones = bat_wing_outline(0.42)
		wing_matrix = Matrix.Translation((side * 0.2, 0.12, 0.24)) @ Matrix.Diagonal((side, 1, 1, 1)) @ Matrix.Rotation(math.radians(-10), 4, "Y")
		add_plate(bm, wing, None, 0.02, matrix=wing_matrix)
		for bone in bones:
			add_sweep(bm, [(point.x, point.y) for point in bone], [0.02] * (len(bone) - 1) + [0.006], sides=4, matrix=wing_matrix)
	bottom = 0.1 - 0.9
	add_grip(bm, 0.1, 0.9, 0.064, 0.077, 8)
	part(bm, "Dragon")

	bm = bmesh.new()
	for side in (-1, 1):
		add_sweep(bm, [head + Vector((side * 0.15, 0.1, 0.12)), head + Vector((side * 0.32, 0.22, 0.3)), head + Vector((side * 0.36, 0.38, 0.5))], [0.055, 0.04, 0.0], sides=6)
		add_spike(bm, head + Vector((side * 0.08, -0.4, -0.12)), (0, -0.3, -1), 0.1, 0.025, sides=4)
	add_pommel(bm, [(0.06, bottom + 0.02), (0.1, bottom - 0.02), (0.1, bottom - 0.06), (0.06, bottom - 0.08)])
	add_spike(bm, (0, 0, bottom - 0.07), (0, 0, -1), 0.24, 0.07, sides=5)
	part(bm, "Bone")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.13, -0.2, 0.1)), 0.04, (1.3, 0.6, 0.8))
		add_flame(bm, Vector((side * 0.2, 0.42)), (side * 0.3, 1), 0.95, 0.16, side)
		add_flame(bm, Vector((side * 0.24, 0.36)), (side * 0.9, 1), 0.6, 0.12, -side)
	part(bm, "DragonFire")

	return {
		"blade": "DragonSteel",
		"outline": outline,
		"edge_glow": ("FF8A2E", 0.06),
		"effects": {
			"DragonSteel": {"gradient": (0.5, 3.5, [(0, "A8301E"), (0.3, "3A2228"), (1, "5A4A58")]), "patterns": [("cells", "C0401E", 8, 0.45), ("flames", "FF8A2E", 4, 0.25)]},
			"Dragon": {"gradient": (-0.9, 0.7, [(0, "5A0E0E"), (1, "C0301E")]), "patterns": [("cells", "3A0808", 10, 0.4)]},
		},
	}


#// Magma 11 Molten Core Blade (Mythic)

def build_molten_core_blade(part):
	blade_base = 0.34
	length = 3.2
	spine = [(0, blade_base), (0, blade_base + length)]
	stations = [(0, 0.24), (0.07, 0.32), (0.62, 0.3), (0.84, 0.22), (1, 0)]
	teeth = [(t, side, 0.14, -0.1, 0.7) for t in (0.3, 0.5, 0.7) for side in (-1, 1)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.11, features=teeth)
	core, core_plateau = profile_shape([(0, blade_base + 0.25), (0, blade_base + 2.5)], [(0, 0.04), (0.15, 0.09), (0.85, 0.08), (1, 0)], chamfer=0.03, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.02, 0.1)
	part(bm, "MoltenCore")

	bm = bmesh.new()
	add_plate(bm, core, core_plateau, 0.11, 0.12)
	add_ball(bm, (0, 0, 0.2), 0.15)
	part(bm, "CoreGlow")

	bm = bmesh.new()
	for side in (-1, 1):
		add_sweep(bm, [(side * 0.14, 0.12), (side * 0.38, 0.06), (side * 0.56, 0.2), (side * 0.62, 0.42)], [0.07, 0.065, 0.05, 0.0], sides=6)
		add_spike(bm, (side * 0.3, 0, 0.1), (side * 0.3, 0, -1), 0.3, 0.06, sides=5)
	add_torus(bm, 0.22, 0.05, 16, 6, Matrix.Translation((0, 0, 0.2)))
	bottom = 0.0 - 0.95
	for height in (0.0, -0.45, bottom + 0.02):
		add_pommel(bm, [(0.06, height - 0.03), (0.095, height - 0.015), (0.095, height + 0.015), (0.06, height + 0.03)])
	add_spike(bm, (0, 0, bottom - 0.02), (0, 0, -1), 0.3, 0.08, sides=5)
	part(bm, "IronBlack")

	bm = bmesh.new()
	for index in range(-3, 4):
		if index == 0:
			continue
		rotation = Matrix.Rotation(math.radians(90 if index % 2 else 0), 4, "X")
		add_torus(bm, 0.05, 0.016, 10, 5, Matrix.Translation((index * 0.085, -0.05, 0.02 - abs(index) * 0.03)) @ rotation)
	part(bm, "Chain")

	bm = bmesh.new()
	add_grip(bm, 0.0, 0.95, 0.064, 0.077, 8)
	part(bm, "DarkLeather")

	return {
		"blade": "MoltenCore",
		"outline": outline,
		"edge_glow": ("FF6A1E", 0.07),
		"decals": lava_cracks(blade_base + 0.3, blade_base + 2.6, 0.26, 6, 31),
		"decal_width": 0.022,
		"decal_colors": ("FF6A1E", "FFD27A"),
		"effects": {
			"MoltenCore": {"gradient": (0.4, 3.7, [(0, "120A0E"), (1, "3A2A34")]), "patterns": [("cells", "FF5A1E", 2.8, 0.45)]},
			"CoreGlow": {"gradient": (0.4, 3.0, [(0, "FF4A0E"), (0.5, "FF9A2E"), (1, "FFE07A")])},
		},
	}


#// Magma 12 Magma Titan Blade (Exclusive)

def build_magma_titan_blade(part):
	blade_base = 0.42
	spine = [(0, blade_base), (0, blade_base + 2.4), (0.08, blade_base + 3.6), (0.24, blade_base + 4.1)]
	stations = [(0, 0.32), (0.06, 0.42), (0.5, 0.44), (0.76, 0.38), (0.9, 0.26), (1, 0)]
	features = []
	for side in (-1, 1):
		features += [(t, side, 0.2, -0.15, 0.75) for t in (0.24, 0.42, 0.6, 0.78)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.14, features=features)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.024, 0.13)
	part(bm, "MagmaTitan")

	trim, trim_plateau = profile_shape(spine, [(t, width + 0.08) for t, width in stations], chamfer=0.04, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, trim, trim_plateau, 0.008, 0.018)
	path = catmull_rom([Vector(point) for point in spine], 8) + [Vector(spine[-1])]
	for t, side in ((0.15, 1), (0.33, -1), (0.51, 1), (0.69, -1)):
		center = point_on_path(path, t)
		add_crystal(bm, (center.x + side * 0.3, 0, center.y), (side * 0.8, 0, 0.6), 0.32, 0.08)
	add_cabochon(bm, (0, 0, 0.3), 0.15, 0.2, sides=10)
	for side in (-1, 1):
		add_flame(bm, Vector((side * 0.26, 0.4)), (side * 0.3, 1), 0.75, 0.13, side)
		add_flame(bm, Vector((side * 0.33, 0.36)), (side * 0.9, 1), 0.5, 0.1, side)
	bottom = 0.16 - 1.05
	add_crystal(bm, (0, 0, bottom - 0.04), (0, 0, -1), 0.36, 0.1)
	part(bm, "TitanGlow", CRYSTAL_SMOOTH_ANGLE)

	bm = bmesh.new()
	add_box(bm, (0.7, 0.32, 0.36), (0, 0, 0.3), 0.1)
	for side in (-1, 1):
		horn = [(side * 0.3, 0.42), (side * 0.62, 0.52), (side * 0.82, 0.8), (side * 0.8, 1.15)]
		add_sweep(bm, horn, [0.1, 0.085, 0.06, 0.0], sides=7)
		add_sweep(bm, [(side * 0.32, 0.2), (side * 0.6, 0.06), (side * 0.72, -0.18)], [0.08, 0.06, 0.0], sides=6)
	for height in (0.16, -0.38, bottom + 0.02):
		add_pommel(bm, [(0.065, height - 0.035), (0.1, height - 0.015), (0.1, height + 0.015), (0.065, height + 0.035)])
	part(bm, "IronBlack")

	bm = bmesh.new()
	add_grip(bm, 0.16, 1.05, 0.07, 0.084, 8)
	part(bm, "DarkLeather")

	return {
		"blade": "MagmaTitan",
		"outline": outline,
		"edge_glow": ("FF6A1E", 0.09),
		"decals": lava_cracks(blade_base + 0.3, blade_base + 3.4, 0.34, 9, 41),
		"decal_width": 0.028,
		"decal_colors": ("FF6A1E", "FFE07A"),
		"effects": {
			"MagmaTitan": {
				"gradient": (0.6, 4.8, [(0, "FF4A0E"), (0.12, "3A141A"), (0.6, "1E1622"), (1, "4A3A58")]),
				"patterns": [("cells", "FF5A1E", 2.4, 0.55), ("stars", "FFC23A", 9, 0.6)],
			},
			"TitanGlow": {"gradient": (-1.2, 4.0, [(0, "FF5A1E"), (1, "FFE07A")])},
		},
	}


MAGMA_SWORDS = [
	("BasaltSword", "Common", build_basalt_sword),
	("EmberBlade", "Common", build_ember_blade),
	("ObsidianShard", "Uncommon", build_obsidian_shard),
	("LavaCleaver", "Uncommon", build_lava_cleaver),
	("SalamanderSword", "Rare", build_salamander_sword),
	("VolcanoSword", "Rare", build_volcano_sword),
	("MagmaGolemBlade", "Epic", build_magma_golem_blade),
	("PhoenixFeather", "Epic", build_phoenix_feather),
	("InfernoKatana", "Legendary", build_inferno_katana),
	("DragonfireSword", "Legendary", build_dragonfire_sword),
	("MoltenCoreBlade", "Mythic", build_molten_core_blade),
	("MagmaTitanBlade", "Exclusive", build_magma_titan_blade),
]


#// Robux Exclusive Galaxy Dragon Greatsword

def build_galaxy_dragon_greatsword(part):
	blade_base = 0.8
	spine = [(0, blade_base), (0, blade_base + 2.8), (0.06, blade_base + 4.2), (0.2, blade_base + 4.7)]
	stations = [(0, 0.34), (0.05, 0.46), (0.35, 0.42), (0.6, 0.5), (0.8, 0.42), (0.92, 0.28), (1, 0)]
	features = []
	for side in (-1, 1):
		features += [(t, side, 0.28, 0.08, 0) for t in (0.22, 0.47)]
		features += [(t, side, 0.12, -0.12, 0.8) for t in (0.33, 0.58, 0.72)]
	outline, plateau = profile_shape(spine, stations, chamfer=0.16, features=features)
	bm = bmesh.new()
	add_plate(bm, outline, plateau, 0.026, 0.14)
	part(bm, "Galaxy")

	trim, trim_plateau = profile_shape(spine, [(t, width + 0.07) for t, width in stations], chamfer=0.04, plateau_ratio=0.5)
	bm = bmesh.new()
	add_plate(bm, trim, trim_plateau, 0.008, 0.02)
	star = star_shape(4, 0.42, 0.13)
	add_plate(bm, star, [point * 0.45 for point in star], 0.06, 0.17, Matrix.Translation((0, 0, blade_base + 2.6)))
	for side in (-1, 1):
		wing, bones = bat_wing_outline(1.05)
		wing_matrix = Matrix.Translation((side * 0.3, 0.12, 0.42)) @ Matrix.Diagonal((side, 1, 1, 1)) @ Matrix.Rotation(math.radians(-14), 4, "Y")
		add_plate(bm, wing, None, 0.026, matrix=wing_matrix)
	path = catmull_rom([Vector(point) for point in spine], 8) + [Vector(spine[-1])]
	for t, side in ((0.12, 1), (0.12, -1), (0.4, 1), (0.4, -1), (0.66, 1), (0.66, -1)):
		center = point_on_path(path, t)
		add_crystal(bm, (center.x + side * 0.42, 0, center.y), (side * 0.85, 0, 0.55), 0.38, 0.085)
	bottom = 0.06 - 1.05
	add_crystal(bm, (0, 0, bottom - 0.06), (0, 0, -1), 0.42, 0.11)
	part(bm, "GalaxyGlow", CRYSTAL_SMOOTH_ANGLE)

	head = Vector((0, -0.06, 0.5))
	scale = 1.5
	bm = bmesh.new()
	for side in (-1, 1):
		wing, bones = bat_wing_outline(1.05)
		wing_matrix = Matrix.Translation((side * 0.3, 0.12, 0.42)) @ Matrix.Diagonal((side, 1, 1, 1)) @ Matrix.Rotation(math.radians(-14), 4, "Y")
		for bone in bones:
			add_sweep(bm, [(point.x, point.y) for point in bone], [0.034] * (len(bone) - 1) + [0.01], sides=5, smoothness=3, matrix=wing_matrix)
		horn = [head + Vector((side * 0.16, -0.06, 0.14)) * scale, head + Vector((side * 0.34, -0.14, 0.34)) * scale, head + Vector((side * 0.46, -0.18, 0.62)) * scale, head + Vector((side * 0.42, -0.14, 0.86)) * scale]
		add_sweep(bm, horn, [0.1, 0.085, 0.055, 0.0], sides=7)
	add_ball(bm, head + Vector((0, 0.06, 0.04)) * scale, 0.27 * scale, (1.1, 1.0, 0.95))
	add_box(bm, (0.32 * scale, 0.4 * scale, 0.2 * scale), head + Vector((0, -0.28, -0.06)) * scale, 0.1)
	add_box(bm, (0.28 * scale, 0.34 * scale, 0.08 * scale), head + Vector((0, -0.22, -0.22)) * scale, 0.04)
	for height in (0.06, -0.48, bottom + 0.02):
		add_pommel(bm, [(0.07, height - 0.035), (0.105, height - 0.015), (0.105, height + 0.015), (0.07, height + 0.035)])
	add_lathe(bm, [(0.14, bottom - 0.04), (0.18, bottom - 0.08), (0.16, bottom - 0.14), (0.1, bottom - 0.14)], 10)
	part(bm, "Gold")

	bm = bmesh.new()
	for side in (-1, 1):
		add_ball(bm, head + Vector((side * 0.13, -0.2, 0.12)) * scale, 0.045 * scale, (1.3, 0.6, 0.8))
		add_spike(bm, head + Vector((side * 0.09, -0.44, -0.12)) * scale, (0, -0.3, -1), 0.11 * scale, 0.026 * scale, sides=4)
	part(bm, "StarCore")

	bm = bmesh.new()
	for phase in (0, math.pi):
		ribbon = spiral_path(0.66, 0.12, 0.55, blade_base + 3.2, 1.75, 22, phase)
		add_sweep(bm, ribbon, [0.035] * 18 + [0.03, 0.022, 0.012, 0.0], sides=6, flatten=0.5, smoothness=3)
		for index in range(3, 20, 4):
			add_ball(bm, ribbon[index], 0.06)
	add_torus(bm, 0.62, 0.035, 32, 6, Matrix.Translation((0, 0, blade_base + 1.2)) @ Matrix.Rotation(math.radians(70), 4, "X") @ Matrix.Rotation(math.radians(-12), 4, "Y"))
	part(bm, "CosmicGlow")

	bm = bmesh.new()
	add_grip(bm, 0.06, 1.05, 0.072, 0.086, 9)
	part(bm, "VoidLeather")

	constellations = [
		[(-0.18, blade_base + 0.6), (-0.06, blade_base + 0.85), (0.1, blade_base + 0.75), (0.2, blade_base + 1.05)],
		[(0.16, blade_base + 1.6), (0.02, blade_base + 1.85), (-0.14, blade_base + 1.75), (-0.2, blade_base + 2.05)],
		[(-0.12, blade_base + 3.1), (0.04, blade_base + 3.3), (0.18, blade_base + 3.2), (0.1, blade_base + 3.55), (-0.02, blade_base + 3.7)],
	]
	for constellation in list(constellations):
		for x, z in constellation:
			constellations.append([(x - 0.035, z), (x + 0.035, z)])
			constellations.append([(x, z - 0.035), (x, z + 0.035)])
	return {
		"blade": "Galaxy",
		"outline": outline,
		"edge_glow": ("FF8AF0", 0.1),
		"decals": constellations,
		"decal_width": 0.014,
		"decal_colors": ("E0F4FF", "FFFFFF"),
		"effects": {
			"Galaxy": {
				"gradient": (0.8, 5.5, [(0, "120838"), (0.4, "3A1E8A"), (0.75, "8A2AB0"), (1, "FF6AE8")]),
				"patterns": [("nebula", "2AB8FF", 1.6, 0.45), ("nebula", "FF4FD8", 2.6, 0.35), ("stars", "FFFFFF", 12, 1)],
			},
			"GalaxyGlow": {"gradient": (-1.3, 4.0, [(0, "8A4AFF"), (0.5, "FF6AE8"), (1, "FFE0FA")]), "patterns": [("stars", "FFFFFF", 9, 0.8)]},
		},
	}


ROBUX_SWORDS = [
	("GalaxyDragonGreatsword", "Exclusive", build_galaxy_dragon_greatsword),
]


WORLDS = {
	"Starter": SWORDS,
	"Desert": DESERT_SWORDS,
	"Halloween": HALLOWEEN_SWORDS,
	"Atlantis": ATLANTIS_SWORDS,
	"Magma": MAGMA_SWORDS,
	"Robux": ROBUX_SWORDS,
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

	if key not in GLOW_MATERIALS:
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
	create_outline(sword, [sword] + [glow for glow in glow_parts if glow.name[len(name):] not in CARVED_MATERIALS], outline_material)

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
