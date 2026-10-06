--[[
	Run in the Studio Command Bar.
	Select the map (models / folders) first - with nothing selected the whole Workspace is used.

	Recolours green (grass, leaves) and brown (dirt, mountains) to a Halloween palette.
	Keeps the light / dark variation of the original colours. Ctrl+Z undoes it.
]]

--// Services

local ChangeHistoryService = game:GetService("ChangeHistoryService")
local Selection = game:GetService("Selection")

--// Constants

-- Hue ranges are 0-1 (Color3:ToHSV). Each rule: source hue range -> target hue, saturation and brightness multiplier
local RECOLOR_RULES = {
	Green = {
		MinHue = 0.17,
		MaxHue = 0.47,
		TargetHue = 0.78,
		TargetSaturation = 0.65,
		BrightnessMultiplier = 0.7,
	},

	Brown = {
		MinHue = 0.0,
		MaxHue = 0.12,
		TargetHue = 0.72,
		TargetSaturation = 0.3,
		BrightnessMultiplier = 0.45,
	},
}

local MIN_SATURATION = 0.2
local BROWN_MAX_BRIGHTNESS = 0.92

local TERRAIN_MATERIALS = {
	Enum.Material.Grass,
	Enum.Material.LeafyGrass,
	Enum.Material.Ground,
	Enum.Material.Mud,
	Enum.Material.Rock,
	Enum.Material.Slate,
	Enum.Material.Sandstone,
	Enum.Material.Basalt,
	Enum.Material.CrackedLava,
}

--// Functions

local function getRecoloredColor(color: Color3): Color3?
	local hue, saturation, brightness = color:ToHSV()
	if saturation < MIN_SATURATION then
		return nil
	end

	for ruleName, rule in RECOLOR_RULES do
		if hue < rule.MinHue or hue > rule.MaxHue then
			continue
		end

		-- Pure orange / red is not dirt, leave pumpkins and lava alone
		if ruleName == "Brown" and brightness > BROWN_MAX_BRIGHTNESS then
			return nil
		end

		return Color3.fromHSV(rule.TargetHue, rule.TargetSaturation, brightness * rule.BrightnessMultiplier)
	end

	return nil
end

--// Recolor

local recordingId = ChangeHistoryService:TryBeginRecording("HalloweenRecolor")

local roots = Selection:Get()
if #roots == 0 then
	roots = { workspace }
end

local recoloredCount = 0
local skippedSurfaceAppearances = 0

for _, root in roots do
	local instances = root:GetDescendants()
	table.insert(instances, root)

	for _, instance in instances do
		if instance:IsA("BasePart") then
			local newColor = getRecoloredColor(instance.Color)
			if newColor then
				instance.Color = newColor
				recoloredCount += 1
			end
		elseif instance:IsA("Texture") or instance:IsA("Decal") then
			local newColor = getRecoloredColor(instance.Color3)
			if newColor then
				instance.Color3 = newColor
				recoloredCount += 1
			end
		elseif instance:IsA("SurfaceAppearance") then
			skippedSurfaceAppearances += 1
		end
	end
end

local terrain = workspace.Terrain
for _, material in TERRAIN_MATERIALS do
	local newColor = getRecoloredColor(terrain:GetMaterialColor(material))
	if newColor then
		terrain:SetMaterialColor(material, newColor)
		recoloredCount += 1
	end
end

if recordingId then
	ChangeHistoryService:FinishRecording(recordingId, Enum.FinishRecordingOperation.Commit)
end

print(`Halloween recolor: {recoloredCount} changed`)
if skippedSurfaceAppearances > 0 then
	warn(`{skippedSurfaceAppearances} SurfaceAppearance textures have baked colours and were not changed`)
end
