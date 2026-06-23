# CTAMP Robot Framework

Framework tabletop manipulation untuk Franka Panda dengan pipeline:

```text
CONTEXT.MD -> LLM satu kali -> TaskPlan JSON -> validasi -> binding geometrik
-> Pinocchio/MuJoCo IK -> OMPL -> MuJoCo execution -> observed verification
```

LLM tidak dipanggil saat simulasi berjalan dan tidak pernah menghasilkan joint
angle atau trajectory. TaskPlan wajib melewati validation gates sebelum backend
MuJoCo diimpor.

## Pipeline end-to-end

```mermaid
flowchart TD
    A[Context Markdown dan task intent] --> B[World builder]
    B --> C[WorldState: robot, object, obstacle, region, constraint]

    C --> D{Sumber TaskPlan}
    D -->|Mode LLM| E[LLM goal compiler<br/>dipanggil satu kali sebelum simulasi]
    D -->|Mode offline| F[TaskPlan JSON lokal<br/>response-file]
    E --> G[TaskPlan JSON]
    F --> G

    G --> H[Schema dan field validation]
    H --> I[Object, action, dan predicate whitelist]
    I --> J[Logical action-sequence validation]
    J --> K[Task plugin validation<br/>align, stack, atau plugin baru]
    K --> L{Plan valid?}
    L -->|Tidak| X[Stop sebelum MuJoCo dimuat]

    L -->|Ya| M[Slot allocation dan geometric safety check]
    M --> N[Resolve immutable RuntimeConfig]
    N --> O[Generate scene XML dari model dasar]
    O --> P[Write run manifest dan hash input]
    P --> Q[Import dan inisialisasi backend MuJoCo]

    Q --> R[TaskRunner membaca step berikutnya]
    R --> S[Adaptive hint dan continuous binding]
    S --> T[Primitive pick, place-slot, atau stack-on]
    T --> U[Pinocchio IK candidates]
    U -->|Tidak valid atau gagal| V[MuJoCo damped-least-squares IK]
    U -->|Valid| W[MuJoCo FK dan joint-limit validation]
    V --> W
    W --> Y[Collision policy dan OMPL joint-space planning]
    Y --> Z[Execute trajectory dan gripper command]
    Z --> AA[Observed predicate verification dari live pose]

    AA --> AB{Expected effect tercapai?}
    AB -->|Ya| AI[Task plugin memeriksa seluruh progress]
    AI --> AJ{Stack prefix stabil?}
    AJ -->|Ya, masih ada step| R
    AJ -->|Ya, semua step selesai| AC[Task plugin final-goal verification]
    AJ -->|Tidak| AK[Stage invalid suffix dari atas ke bawah]
    AK --> AL[Rebuild suffix dari bawah ke atas]
    AL --> AI
    AB -->|Tidak| AD[Bounded recovery policy]
    AD -->|Retry atau rebind| R
    AD -->|Fatal atau retry habis| AE[Abort terstruktur]

    AC --> AF{Final goal tercapai?}
    AF -->|Ya| AG[Run sukses]
    AF -->|Tidak| AE
    AG --> AH[Event CSV, summary CSV, dan run manifest]
    AE --> AH
```

LLM hanya menentukan goal dan urutan simbolik. Target pose, grasp candidate,
IK, collision validity, trajectory OMPL, serta keputusan keberhasilan tetap
ditentukan oleh komponen deterministik dan verifier berbasis state MuJoCo.

### Recovery tower stack

Cube diambil dan ditempatkan satu per satu dari bawah ke atas. Setiap cube harus
teramati sudah berada di base atau di atas support yang benar sebelum runner
boleh mengambil cube berikutnya. Jika placement gagal atau cube jatuh, cube
tersebut diambil ulang dan level stack yang invalid langsung dibangun kembali.
Stable prefix dipertahankan. Recovery dibatasi tiga rebuild oleh
`recovery.max_stack_rebuilds`; setelah batas habis run langsung gagal. Obstacle
displacement tetap fatal.

`layer_height_m` pada plan adalah nilai nominal symbolic. Backend MuJoCo
mengikat target Z menggunakan vertical half-extent live dari support dan cube
yang dipegang. Karena itu cube yang berubah orientasi tidak dipaksa masuk ke
support berdasarkan tinggi nominal yang sudah stale.
Semua world memakai cube seragam `6.6 x 6.6 x 6.6 cm`, sehingga penampang grip
dan kontak antar-layer lebih besar tanpa melampaui bukaan gripper Panda.
Orientation dan velocity direkam sebagai diagnostic, tetapi belum menjadi hard
gate sampai primitive place mengontrol orientasi object secara eksplisit.

## Benchmark TaskPlan empat LLM

Visualisasi berikut membandingkan DeepSeek V4 Flash, Qwen3 Coder, MiniMax M3,
dan GPT-OSS pada context `align` dan `stack`. Satu data point adalah **run
terbaru** untuk pasangan task dan model. Karena saat ini hanya ada satu run per
pasangan yang dipilih, hasil ini merupakan perbandingan run, bukan estimasi
statistik atau rata-rata keberhasilan model. Untuk Qwen3 Coder `stack`, run
terbaru yang dipakai adalah `20260622_224529_qwen3coder`.

TaskPlan pembanding adalah
`task_plans/examples/ungroup_obs_align_cubes.json` dan
`task_plans/examples/ungroup_obs_stack_cubes.json`. Arti metrik pada kedua
gambar:

- **Summary completion**: nilai `completion_percent` yang ditulis summary CSV.
- **Verified placements**: persentase target unik dengan event `STEP=OK` untuk
  `place` atau `stack_place`; placement recovery tetap dihitung.
- **Final goal reached**: hasil verifier final yang direkam sebagai `success`.
- **Planned steps OK**: step ID asli TaskPlan yang pernah menghasilkan
  `STEP=OK`, dibagi jumlah step asli. Step recovery tambahan tidak masuk
  denominator.
- **Failed STEP attempts**: seluruh attempt berstatus `FAILED`, termasuk retry.
- **Plan structure match**: kecocokan per posisi untuk tuple `action`, `object`,
  `slot`, dan `on_top_of` terhadap TaskPlan pembanding.
- **Goal predicate match**: Jaccard similarity antara himpunan predicate plan
  kandidat dan plan pembanding. Predicate tambahan ikut menurunkan skor.
- **Slot geometry deviation**: selisih absolut field geometri terhadap plan
  pembanding dalam milimeter. Ini mengukur perbedaan plan, bukan otomatis
  kesalahan fisik, karena backend masih melakukan geometric binding dari state
  MuJoCo.
- **Runtime**: `duration_ms` summary yang dikonversi ke detik.

### Align

![Perbandingan performa dan goal state align empat LLM](docs/images/llm_align_benchmark.png)

| Model | Summary | Placement terverifikasi | Final goal | Runtime | Failed attempt | Struktur plan |
|---|---:|---:|:---:|---:|---:|---:|
| DeepSeek V4 Flash | 50% | 50% (2/4) | gagal | 67.119 s | 5 | 100% |
| Qwen3 Coder | 50% | 0% (0/4) | gagal | 37.162 s | 13 | 50% |
| MiniMax M3 | 50% | 0% (0/4) | gagal | 34.834 s | 13 | 50% |
| GPT-OSS | 50% | 0% (0/4) | gagal | 33.841 s | 13 | 50% |

Tidak ada run `align` yang mencapai final goal. DeepSeek memakai nama slot
`slot_0` sampai `slot_3` sesuai kontrak dan berhasil menempatkan dua cube.
Qwen3 Coder, MiniMax M3, dan GPT-OSS memakai `slot0` sampai `slot3` pada steps;
masing-masing menghasilkan delapan attempt `missing_place_target` dan tidak
memiliki placement valid. Karena itu nilai summary 50% pada tiga run tersebut
tidak boleh ditafsirkan sebagai 2/4 cube sudah berada di goal. Runtime yang lebih
pendek juga bukan performa lebih baik karena run berhenti lebih awal dalam
kondisi gagal.

### Stack

![Perbandingan performa dan goal state stack empat LLM](docs/images/llm_stack_benchmark.png)

| Model | Summary | Placement terverifikasi | Final goal | Runtime | Failed attempt | Rebuild |
|---|---:|---:|:---:|---:|---:|---:|
| DeepSeek V4 Flash | 100% | 100% (4/4) | berhasil | 119.417 s | 2 | 1 |
| Qwen3 Coder | 100% | 100% (4/4) | berhasil | 119.114 s | 2 | 1 |
| MiniMax M3 | 100% | 100% (4/4) | berhasil | 114.563 s | 2 | 1 |
| GPT-OSS | 100% | 100% (4/4) | berhasil | 113.451 s | 2 | 1 |

Semua run `stack` mencapai tower 4/4. Setiap run memiliki dua failed attempt
dan satu `STACK_REBUILD`; akibatnya hanya 7 dari 8 step ID asli yang pernah
berstatus OK (87.5%, dibulatkan 88% pada gambar), tetapi placement recovery
cube3 membuat final goal tetap 100%. GPT-OSS memiliki runtime terpendek pada
sampel ini. Seluruh plan cocok 100% pada struktur action. Skor predicate
DeepSeek 67% berasal dari dua goal tambahan (`clear(cube4)` dan `handempty`)
dibanding empat predicate referensi, bukan dari kegagalan eksekusi.

Gambar dapat dibuat ulang setelah log baru ditambahkan:

```bash
python -m pip install -e ".[viz]"
python -m telemetry.visualize_llm_benchmarks
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -e ".[test]"
cp .env.example .env           # Windows: copy .env.example .env
pytest -q
```

Package framework berada langsung di root repository. Editable install tetap
disarankan agar entrypoint tersedia dari directory mana pun. Python minimum
adalah 3.10.

Validasi dua plan obstacle tanpa memanggil LLM:

```bash
python -m cli.generate_plan \
  --context contexts/examples/ungroup_obs_align_cubes.md \
  --task align \
  --response-file task_plans/examples/ungroup_obs_align_cubes.json \
  --output task_plans/generated

python -m cli.generate_plan \
  --context contexts/examples/ungroup_obs_stack_cubes.md \
  --task stack \
  --response-file task_plans/examples/ungroup_obs_stack_cubes.json \
  --output task_plans/generated
```

Kedua file pada `task_plans/examples/` sudah merupakan TaskPlan siap eksekusi.
Jalankan align obstacle dengan viewer:

```bash
python -m cli.run_simulation \
  --plan task_plans/examples/ungroup_obs_align_cubes.json \
  --context contexts/examples/ungroup_obs_align_cubes.md \
  --scene ungroup_obs \
  --runtime-config configuration/profiles/runtime/obstacle.toml \
  --viewer
```

Jalankan stack obstacle dengan viewer:

```bash
python -m cli.run_simulation \
  --plan task_plans/examples/ungroup_obs_stack_cubes.json \
  --context contexts/examples/ungroup_obs_stack_cubes.md \
  --scene ungroup_obs \
  --runtime-config configuration/profiles/runtime/obstacle.toml \
  --viewer
```

## Struktur utama

```text
MVP-CTAMP-ROBOT2/
|-- assets/                 # mesh visual/collision Panda; wajib runtime
|-- models/
|   |-- panda.xml           # base model source
|   `-- generated/          # scene XML runtime; ignored Git
|-- configuration/
|   |-- defaults.py         # built-in defaults dan profile registry
|   |-- loader.py           # validasi dan TOML overlay
|   |-- runtime.py          # resolved active configuration
|   |-- types.py            # immutable typed configuration schema
|   `-- profiles/
|       |-- models/         # override model dan reference pose
|       `-- runtime/        # profile fine-tuning TOML
|-- contexts/examples/      # context align dan stack obstacle siap pakai
|-- task_plans/examples/    # contoh artefak TaskPlan
|-- adaptive/               # hint dari event historis
|-- backends/mujoco/        # MuJoCo, Pinocchio, OMPL, collision, trace
|-- cli/                    # generate plan dan run simulation
|-- execution/              # generic runner, primitives, recovery, verifier
|-- task_planning/          # TaskPlan types, loader, generator, validator
|-- plugins/                # task plugins dan deterministic discovery
|-- scene/                  # scene variants dan XML generation
|-- telemetry/              # summary dan reproducible run manifest
|-- world/                  # Context parser, WorldState, slot allocation
`-- tests/                  # unit dan integration tests tanpa viewer
```

Environment hanya digunakan untuk credential dan endpoint provider LLM.
Parameter model, IK, OMPL, grasp, collision, verifier, adaptive hints, dan
telemetry berada pada typed code profile atau TOML.

## Dokumentasi

- [Arsitektur](docs/architecture.md)
- [Cara penggunaan](docs/usage.md)
- [Fungsi setiap file](docs/file-reference.md)
- [Menambah task, profile, dan model](docs/extending.md)

## Status validasi

```text
62 passed
```

Test suite memvalidasi contracts, plan gates, context parsing, slot allocation,
plugin discovery, runtime configuration, recovery, verifier, scene generation,
manifest, dan generic task runner. Pengujian motion native tetap membutuhkan
binding MuJoCo/OMPL sesuai platform.
