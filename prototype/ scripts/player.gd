extends CharacterBody3D

@export var walk_speed: float = 13.0
@export var sprint_multiplier: float = 2.0
@export var speed_mode_multiplier: float = 4.0
@export var acceleration: float = 30.0
@export var rotation_speed: float = 9.0
@export var stamina_max: float = 5.0
@export var stamina_drain_per_second: float = 1.5
@export var stamina_recover_per_second: float = 1.0
@export var base_fov: float = 75.0
@export var max_fov_bonus: float = 30.0
@export var gravity: float = 30.0
@export var camera_look_at_offset: Vector3 = Vector3(0.0, 1.1, 0.0)
@export var camera_near_distance: float = 6.5
@export var camera_far_distance: float = 9.5
@export var camera_height: float = 3.0
@export var camera_lerp_speed: float = 7.5
@export var trail_min_speed: float = 14.0
@export var trail_max_scale: float = 1.45
@export var trail_strength_in_speed_mode: float = 1.0

var stamina: float = stamina_max

@onready var camera: Camera3D = $Camera3D
@onready var stamina_bar: ProgressBar = $CanvasLayer/StaminaBar
@onready var speed_trail: MeshInstance3D = $VisualRoot/SpeedTrail
@onready var accent_meshes: Array[MeshInstance3D] = [
	$VisualRoot/LeftLegAccent,
	$VisualRoot/RightLegAccent,
	$VisualRoot/ChestAccent,
	$VisualRoot/VisorAccent
]

func _ready() -> void:
	camera.top_level = true
	stamina_bar.max_value = stamina_max
	stamina_bar.value = stamina
	_update_camera_follow(0.0)
	_update_camera_fov()

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= gravity * delta
	else:
		velocity.y = 0.0

	var speed_mode_active := Input.is_action_pressed("speed_mode") and stamina > 0.0
	_update_stamina(delta, speed_mode_active)

	var input_dir := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var move_direction := _get_camera_relative_direction(input_dir)

	var speed_multiplier := 1.0
	if Input.is_action_pressed("sprint"):
		speed_multiplier *= sprint_multiplier
	if speed_mode_active:
		speed_multiplier *= speed_mode_multiplier

	var target_velocity := move_direction * walk_speed * speed_multiplier
	velocity.x = move_toward(velocity.x, target_velocity.x, acceleration * delta)
	velocity.z = move_toward(velocity.z, target_velocity.z, acceleration * delta)

	if move_direction.length_squared() > 0.0001:
		var target_yaw := atan2(move_direction.x, move_direction.z)
		rotation.y = lerp_angle(rotation.y, target_yaw, rotation_speed * delta)

	move_and_slide()

	var horizontal_speed := Vector2(velocity.x, velocity.z).length()
	_update_camera_follow(delta)
	_update_camera_fov()
	_update_speed_effects(horizontal_speed, speed_mode_active)
	stamina_bar.value = stamina

func _get_camera_relative_direction(input_dir: Vector2) -> Vector3:
	if input_dir.length_squared() == 0.0:
		return Vector3.ZERO

	var camera_forward := -camera.global_transform.basis.z
	var camera_right := camera.global_transform.basis.x
	camera_forward.y = 0.0
	camera_right.y = 0.0

	camera_forward = camera_forward.normalized()
	camera_right = camera_right.normalized()

	return (camera_right * input_dir.x + camera_forward * input_dir.y).normalized()

func _update_stamina(delta: float, speed_mode_active: bool) -> void:
	if speed_mode_active:
		stamina = max(stamina - stamina_drain_per_second * delta, 0.0)
	else:
		stamina = min(stamina + stamina_recover_per_second * delta, stamina_max)

func _update_camera_follow(delta: float) -> void:
	var horizontal_speed := Vector2(velocity.x, velocity.z).length()
	var max_speed := walk_speed * sprint_multiplier * speed_mode_multiplier
	var speed_ratio := clamp(horizontal_speed / max_speed, 0.0, 1.0)
	var distance := lerp(camera_near_distance, camera_far_distance, speed_ratio)
	var offset := Vector3(0.0, camera_height, distance)
	var target_camera_position := global_position + offset
	if delta <= 0.0:
		camera.global_position = target_camera_position
	else:
		camera.global_position = camera.global_position.lerp(target_camera_position, clamp(camera_lerp_speed * delta, 0.0, 1.0))
	camera.look_at(global_position + camera_look_at_offset, Vector3.UP)

func _update_camera_fov() -> void:
	var current_speed := Vector2(velocity.x, velocity.z).length()
	var max_speed := walk_speed * sprint_multiplier * speed_mode_multiplier
	var speed_ratio := clamp(current_speed / max_speed, 0.0, 1.0)
	camera.fov = lerp(base_fov, base_fov + max_fov_bonus, speed_ratio)

func _update_speed_effects(horizontal_speed: float, speed_mode_active: bool) -> void:
	var max_speed := walk_speed * sprint_multiplier * speed_mode_multiplier
	var speed_ratio := clamp(horizontal_speed / max_speed, 0.0, 1.0)
	var fast_enough := horizontal_speed > trail_min_speed
	var mode_boost := trail_strength_in_speed_mode if speed_mode_active else 0.0
	var trail_intensity := clamp(speed_ratio + mode_boost, 0.0, 1.0)

	speed_trail.visible = fast_enough or speed_mode_active
	speed_trail.scale.x = lerp(0.25, trail_max_scale, trail_intensity)
	speed_trail.scale.y = lerp(0.2, 0.7, trail_intensity)

	for accent in accent_meshes:
		var material := accent.material_override as StandardMaterial3D
		if material:
			material.emission_energy_multiplier = lerp(0.35, 2.4, trail_intensity)
