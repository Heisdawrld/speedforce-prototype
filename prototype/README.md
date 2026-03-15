# Godot 4 Speed Prototype - Stylized City Slice

A compact third-person speedster prototype in a stylized fantasy city block.
The scope stays focused on movement feel, camera readability, and lightweight presentation.

## Folder structure

```text
prototype/
├── project.godot
├── README.md
├── scenes/
│   ├── Main.tscn
│   └── Player.tscn
└── scripts/
    └── player.gd
```

## What's new in this upgrade

- Stylized hero placeholder made from primitive meshes:
  - red suit body
  - gold/yellow accents
  - simple speed trail mesh
- Small city block test space:
  - road lane
  - left/right sidewalks
  - varied-height buildings on both sides
  - props (street lights, barriers, crates)
- Visual speed fantasy:
  - trail scales up with speed
  - accent emissive glow intensifies as speed rises
  - speed mode strengthens the effect
- Improved follow camera feel:
  - camera distance expands at higher speed
  - FOV still scales with actual movement speed
- Checkpoint marker:
  - glowing target marker to run toward

## Scene setup

### `scenes/Main.tscn`
- `Main (Node3D)`
- `Sun (DirectionalLight3D)`
- `Road`, `SidewalkLeft`, `SidewalkRight` (`StaticBody3D`)
- `BuildingRow` with 6 varied-height building blocks
- `StreetProps` with lights/barriers/crates
- `CheckpointMarker` (glow sphere + light)
- `Player` instance from `Player.tscn`

### `scenes/Player.tscn`
- `Player (CharacterBody3D)` with `scripts/player.gd`
- `CollisionShape3D` (capsule)
- `VisualRoot` with stylized body/accent meshes
- `SpeedTrail` mesh for lightweight streak effect
- `Camera3D` (third-person follow)
- `CanvasLayer/StaminaBar`

## Controls

- `WASD`: camera-relative movement
- `Shift`: sprint
- `E` (hold): speed mode while stamina > 0

## How to run

1. Open **Godot 4.x**.
2. Import `prototype/project.godot`.
3. Run project (main scene is `scenes/Main.tscn`).
4. Run toward the glowing checkpoint to evaluate speed feel and readability.

## Tuning variables (`scripts/player.gd`)

### Movement
- `walk_speed`
- `sprint_multiplier`
- `speed_mode_multiplier`
- `acceleration`
- `rotation_speed`

### Stamina
- `stamina_max`
- `stamina_drain_per_second`
- `stamina_recover_per_second`

### Camera
- `base_fov`
- `max_fov_bonus`
- `camera_look_at_offset`
- `camera_near_distance`
- `camera_far_distance`
- `camera_height`
- `camera_lerp_speed`

### Speed effects
- `trail_min_speed`
- `trail_max_scale`
- `trail_strength_in_speed_mode`
