# Stud Assets

Blocky stud-style assets for Roblox Studio (old-Roblox style, flat colours, no 3D studs; the stud texture is added in Roblox).

| Biome | Assets |
|---|---|
| Forest | GrassBlockSmall / GrassBlock / GrassBlockLarge, AppleTree, PineTree, Bush, Rock, RockSpire, Log, LogPile, Stump, Mushroom, FlowerPatch, Fence, Pebbles |
| Desert | StepPyramid, DeadTree, Cactus, RibBones, SandRock, BonePile |
| Snow | SnowTree, FrostTree, SnowPine, Snowman, IceCrystal, SnowRock, SnowLog |
| Market | MarketStallRed / Blue / Purple, Crate, Signboard |
| Sakura | CherryTree, Torii, GongGate, Bamboo, StoneLantern |
| Halloween | Ghost, Tombstone, Pumpkin, JackOLantern |
| Props | StoneDoor, SpinWheel, PortalArch |
| Boss | CrystalGolem (~22 studs tall, split into Head / Torso / LeftArm / RightArm / LeftLeg / RightLeg) |

Previews are in `Previews/` (rendered with a stud texture only to show the final look).

## Files

- `Export/<Biome>/<Asset>.fbx` - ready for import into Roblox
- `StudAssets.blend` - every asset in one file for editing in Blender (one collection per biome)
- `generate_assets.py` - generator; change sizes or colours and run it again
- `ApplyStudColors.lua` - colours the MeshParts in Studio (generated from `PALETTE`)

## Import into Roblox

1. Avatar / Home -> **Import 3D** -> pick an `.fbx` file from `Export/`.
2. In the importer set **File Dimensions = Studs** (1 Blender unit = 1 stud).
3. Each asset arrives as a Model with one MeshPart per colour (e.g. `Torso_StoneGrey`).
4. Select the imported models, paste `ApplyStudColors.lua` into the **Command Bar** and run it. It sets the colours and makes every `*Glow` part Neon (golem eyes, pumpkin faces, portal, lantern).
5. Add your stud texture. UVs are in stud units (1 UV unit = 1 stud), so the texture tiles once per stud on every face. Use a texture that repeats in the 0-1 UV range (e.g. a `SurfaceAppearance` / `MaterialVariant` with a grayscale stud). The part `Color` tints it.

## Regenerating

```bash
pip install bpy            # or run inside Blender: blender -b -P generate_assets.py
python3 generate_assets.py           # FBX + .blend
python3 generate_assets.py --render  # also preview renders
```

Colours are in `PALETTE` at the top of the script. `ApplyStudColors.lua` is regenerated from it on every run.
