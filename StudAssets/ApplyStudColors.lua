--[[
	Run in the Studio Command Bar after importing the FBX files.
	Select the imported models (or a folder containing them) and run.

	Colours every MeshPart by the colour key at the end of its name
	(e.g. "Torso_StoneGrey" -> StoneGrey) and makes "Glow" parts Neon.
]]

--// Services

local Selection = game:GetService("Selection")

--// Constants

local PART_MATERIAL = Enum.Material.SmoothPlastic
local GLOW_MATERIAL = Enum.Material.Neon

local COLORS = {
	LeafGreen = Color3.fromRGB(98, 200, 60),
	LeafDark = Color3.fromRGB(64, 160, 48),
	Grass = Color3.fromRGB(124, 226, 46),
	Trunk = Color3.fromRGB(176, 124, 150),
	Wood = Color3.fromRGB(196, 126, 110),
	WoodLight = Color3.fromRGB(222, 160, 136),
	DeadWood = Color3.fromRGB(140, 92, 92),
	Apple = Color3.fromRGB(206, 30, 40),
	RockBlue = Color3.fromRGB(146, 152, 236),
	RockBlueDark = Color3.fromRGB(112, 116, 206),
	FlowerRed = Color3.fromRGB(230, 40, 50),
	FlowerBlue = Color3.fromRGB(60, 190, 255),
	FlowerPink = Color3.fromRGB(240, 120, 200),
	White = Color3.fromRGB(242, 243, 243),
	Yellow = Color3.fromRGB(245, 205, 48),
	Sand = Color3.fromRGB(232, 184, 132),
	SandDark = Color3.fromRGB(214, 160, 110),
	PyramidPink = Color3.fromRGB(214, 150, 140),
	Bone = Color3.fromRGB(236, 238, 242),
	Cactus = Color3.fromRGB(96, 200, 64),
	Snow = Color3.fromRGB(240, 244, 255),
	SnowShade = Color3.fromRGB(196, 202, 236),
	Ice = Color3.fromRGB(80, 176, 255),
	Coal = Color3.fromRGB(32, 32, 38),
	Carrot = Color3.fromRGB(255, 140, 30),
	StripeRed = Color3.fromRGB(222, 40, 40),
	StripeBlue = Color3.fromRGB(30, 150, 240),
	StripePurple = Color3.fromRGB(140, 60, 220),
	Sakura = Color3.fromRGB(226, 156, 236),
	SakuraDark = Color3.fromRGB(176, 104, 214),
	ToriiRed = Color3.fromRGB(212, 40, 44),
	ToriiBlue = Color3.fromRGB(40, 88, 180),
	Gold = Color3.fromRGB(250, 200, 40),
	Bamboo = Color3.fromRGB(84, 200, 60),
	BambooDark = Color3.fromRGB(52, 150, 46),
	StoneGrey = Color3.fromRGB(163, 162, 165),
	DarkStone = Color3.fromRGB(99, 95, 98),
	DarkBlue = Color3.fromRGB(32, 52, 140),
	ReallyDarkBlue = Color3.fromRGB(20, 28, 88),
	Cobalt = Color3.fromRGB(16, 42, 220),
	BrightBlue = Color3.fromRGB(13, 105, 220),
	LightBlue = Color3.fromRGB(160, 220, 255),
	RoyalPurple = Color3.fromRGB(110, 40, 220),
	BrightViolet = Color3.fromRGB(170, 60, 255),
	LightPurple = Color3.fromRGB(214, 166, 255),
	Moss = Color3.fromRGB(60, 172, 60),
	MossDark = Color3.fromRGB(36, 120, 56),
	Glow = Color3.fromRGB(120, 230, 255),
}

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
		meshPart.Material = if colorKey == "Glow" then GLOW_MATERIAL else PART_MATERIAL
		coloredCount += 1
	end
end

print(`Coloured {coloredCount} MeshParts`)
