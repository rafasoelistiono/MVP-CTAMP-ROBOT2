# CONTEXT.MD - Ungrouped Cubes Alignment With Obstacles

## scene
- scene_id: ungroup_obs_align_cubes
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
  pose: [-0.16, -0.42, 0.833]
  reachable: true
  near_obstacle: false
- id: circle1
  class: cylinder
  pose: [0.00, -0.54, 0.84]
  reachable: true
  near_obstacle: false
- id: cube2
  class: cube
  pose: [0.10, -0.54, 0.833]
  reachable: true
  near_obstacle: false
- id: circle2
  class: cylinder
  pose: [0.28, -0.48, 0.84]
  reachable: true
  near_obstacle: false
- id: cube3
  class: cube
  pose: [-0.10, 0.28, 0.833]
  reachable: true
  near_obstacle: false
- id: circle3
  class: cylinder
  pose: [0.06, 0.40, 0.84]
  reachable: true
  near_obstacle: false
- id: cube4
  class: cube
  pose: [0.12, 0.20, 0.833]
  reachable: true
  near_obstacle: false
- id: circle4
  class: cylinder
  pose: [0.28, 0.42, 0.84]
  reachable: true
  near_obstacle: false

## obstacles
- id: obstacle1
  pose: [0.11, -0.30, 0.89]
  fragile: true
  radius: 0.035
  height: short
- id: obstacle2
  pose: [0.35, 0.27, 0.89]
  fragile: true
  radius: 0.035
  height: short

## task
- name: align
- target_objects: [cube1, cube2, cube3, cube4]
- description: Susun empat cube yang bercampur dengan cylinder menjadi satu baris sepanjang sumbu X pada goal area tanpa menggeser obstacle.

## constraints
- preserve_obstacles: true
- max_retries_per_object: 3
- allowed_predicates: [at, on, clear, handempty, holding, aligned-row]

## task_plan_contract
- schema_version: ctamp-plan/v1
- output_format: Satu JSON object valid saja tanpa Markdown, code fence, komentar, atau penjelasan.
- task: align
- slot_type: line
- slot_axis: x
- geometry_rule: Hitung sendiri spacing_m, row_y, base_z, dan center_x dari jumlah target, goal area, permukaan meja, serta dimensi object pada environment. Semua cube harus muat, tidak overlap, dan tetap di goal area.
- target_rule: Gunakan seluruh target_objects dan pertahankan urutan yang dinyatakan task saat menentukan slot_0 sampai slot terakhir.
- step_rule: Setiap target harus memiliki tepat satu pasangan pick lalu place. Tentukan sendiri pemetaan object ke slot yang konsisten dengan urutan target. Jangan menambahkan stack_place, retry, atau recovery step ke TaskPlan.
- predicate_rule: goal_predicates memakai object dengan field name dan args. Preconditions dan effects harus dihilangkan. Jika benar-benar disertakan, keduanya wajib array string seperti clear(cube1), holding(cube1), dan handempty; jangan memakai object predicate.
- constraints_rule: constraints output cukup preserve_obstacles dan move_order.

## task_plan_shape_hint

Hint berikut sengaja tidak lengkap, tidak berurutan, dan bukan JSON final yang
valid. Jangan menyalinnya secara literal. Ganti seluruh placeholder, tentukan
pemetaan object ke slot dari task, lalu beri step_id integer berurutan mulai 0.

~~~text
{
  "schema_version": "ctamp-plan/v1",
  "task": "align",
  "scene_id": "<scene_id dari context>",
  "target_objects": ["<semua target dalam urutan task>"],
  "goal_predicates": [
    {"name": "aligned-row", "args": ["<semua target>"]},
    {"name": "at", "args": ["<cube>", "<slot yang sesuai>"]},
    "<lengkapi predicate at untuk seluruh cube; urutan contoh ini diacak>"
  ],
  "slot_config": {
    "type": "line",
    "axis": "x",
    "spacing_m": "<hitung dari environment>",
    "row_y": "<hitung dari environment>",
    "base_z": "<hitung dari environment>",
    "center_x": "<hitung dari environment>"
  },
  "steps": [
    {"step_id": "*", "action": "place", "object": "<cube>", "slot": "<slot>"},
    {"step_id": "*", "action": "pick", "object": "<cube>"},
    "<lengkapi dan urutkan semua pasangan pick/place yang valid>"
  ],
  "constraints": {
    "preserve_obstacles": true,
    "move_order": ["<urutkan semua target>"]
  }
}
~~~

Output final wajib mengganti `*` dengan integer, mengganti semua placeholder
dengan nilai konkret dari context, memakai tipe data yang benar, dan memenuhi
urutan pick lalu place untuk setiap cube.
