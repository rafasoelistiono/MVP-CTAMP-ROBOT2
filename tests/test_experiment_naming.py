from telemetry.naming import (
    infer_experiment_label,
    normalize_experiment_label,
    with_experiment_label,
)


def test_label_is_inferred_from_response_or_generated_plan_name():
    assert infer_experiment_label(
        "ungroup_obs_stack_cubes_qwen_3_coder.json",
        scene_id="ungroup_obs_stack_cubes",
        task="stack",
    ) == "qwen_3_coder"
    assert infer_experiment_label(
        "ungroup_obs_stack_cubes_stack_qwen_3_coder.json",
        scene_id="ungroup_obs_stack_cubes",
        task="stack",
    ) == "qwen_3_coder"


def test_label_is_safe_and_optional():
    assert normalize_experiment_label("Sonnet 4.6 Max") == "sonnet_4_6_max"
    assert with_experiment_label("run_123", "Gemini-3.1-Pro") == (
        "run_123_gemini_3_1_pro"
    )
    assert with_experiment_label("run_123", "") == "run_123"
