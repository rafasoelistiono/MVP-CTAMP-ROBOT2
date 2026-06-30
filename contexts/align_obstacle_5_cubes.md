# CONTEXT.MD - 5 Cubes Alignment With Obstacles

## scene
- scene_id: align_obstacle_5_cubes
- variant: ungroup_obs

## table
- x_range: [-0.55, 0.55]
- y_range: [-0.75, 0.75]
- z_top: 0.80
- goal_center: [0.22, -0.06, 0.806]
- goal_area_size_xy: [0.52, 0.40]

## geometry
- cube_size_xyz: [0.066, 0.066, 0.066]
- cylinder_radius: 0.026
- cylinder_height: 0.08

## robot
- id: panda_left
- reach_min_xy: 0.30
- reach_max_xy: 0.82
- base_xy: [-0.4, 0.0]
- capabilities: [pick, place, stack_place]

## objects
- id: cube1
  class: cube
  pose: [-0.20, -0.40, 0.833]
  reachable: true
  near_obstacle: false
- id: cube2
  class: cube
  pose: [0.00, -0.50, 0.833]
  reachable: true
  near_obstacle: false
- id: cube3
  class: cube
  pose: [0.15, -0.35, 0.833]
  reachable: true
  near_obstacle: false
- id: cube4
  class: cube
  pose: [-0.10, 0.20, 0.833]
  reachable: true
  near_obstacle: false
- id: cube5
  class: cube
  pose: [0.20, 0.15, 0.833]
  reachable: true
  near_obstacle: false
- id: circle1
  class: cylinder
  pose: [0.30, -0.30, 0.84]
  reachable: true
  near_obstacle: false
- id: circle2
  class: cylinder
  pose: [-0.15, 0.40, 0.84]
  reachable: true
  near_obstacle: false

## obstacles
- id: obstacle1
  pose: [0.05, -0.30, 0.89]
  fragile: true
  radius: 0.035
  height: short
- id: obstacle2
  pose: [0.30, 0.25, 0.89]
  fragile: true
  radius: 0.035
  height: short

## task
- name: align
- target_objects: [cube1, cube2, cube3, cube4, cube5]
- description: Susun lima cube menjadi satu baris sepanjang sumbu X pada goal area tanpa menggeser obstacle.

## constraints
- preserve_obstacles: true
- max_retries_per_object: 3
- allowed_predicates: [at, on, clear, handempty, holding]
