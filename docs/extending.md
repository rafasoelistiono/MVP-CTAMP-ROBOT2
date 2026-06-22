# Mengembangkan Framework

## Menambah task

Buat module `<name>_task.py` di package plugin tepercaya:

```python
class SortTaskPlugin:
    api_version = "ctamp-task/v2"
    name = "sort"
    supported_actions = {"pick", "place"}

    def validate_plan(self, plan, world): ...
    def make_slot_config(self, plan, world): ...
    def configure_runtime(self, plan, world, config): ...
    def assess_progress(self, plan, verifier, slots, completed_objects): ...
    def verify_goal(self, plan, world, verifier, slots): ...

PLUGIN = SortTaskPlugin()
```

Jika module ditaruh di `plugins`, plugin ditemukan otomatis. Package
eksternal dapat dipilih menggunakan `--plugin-package my_robot.tasks`. Tidak
perlu mengedit registry atau TaskRunner.

## Menambah runtime profile

Untuk perubahan nilai saja, buat TOML:

```toml
extends = "conservative"
name = "experiment_b"

[motion]
time_limit_s = 7.0

[grasp]
pick_grip_sequence = [0.020, 0.017, 0.014]
```

Untuk profile code, buat immutable `RuntimeConfig` dengan `dataclasses.replace`
dan register pada `RuntimeProfileRegistry`.

## Menambah parameter tuning

1. Tambahkan field pada dataclass section yang tepat di `configuration/types.py`.
2. Tambahkan validation invariant pada `RuntimeConfig.validate()`.
3. Konsumsi field melalui injected/active RuntimeConfig.
4. Tambahkan contoh TOML dan test type/limit.
5. Pastikan parameter safety tidak dapat diubah HintCache.

Jangan membaca parameter baru langsung dari environment.

## Mengganti model

Salin `configuration/profiles/models/panda.toml`, ubah XML dan pose model, lalu gunakan sebagai
runtime config. Base XML harus menyediakan contract body/joint/actuator yang
dipahami backend MuJoCo saat ini. Backend robot dengan contract berbeda harus
dibuat sebagai backend package baru, bukan ditambahkan sebagai kondisi acak di
task plugin.

## Menambah backend

Implementasikan contract `PrimitiveExecutor`:

- `execute(step, target, hints)`;
- `object_pose(object_id)`;
- `all_object_poses()`;
- `held_object_name()`.
- `object_orientation(object_id)` untuk stability verification;
- `object_velocity(object_id)` untuk memastikan object sudah settle.

Backend lama yang belum menyediakan orientation/velocity tetap dapat berjalan
dengan pose-only fallback, tetapi tidak memperoleh validasi tilt dan velocity.

TaskRunner, TaskPlan, plugin, dan verifier tidak boleh bergantung pada internal
backend. Backend baru bertanggung jawab atas lifecycle simulator/controller,
IK, collision, trajectory, dan shutdown.
