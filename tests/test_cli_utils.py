from anvil.cli_utils import (
    build_state_pipeline,
    format_mapping_diff,
    format_pipeline_map,
    normalize_requested_pipeline,
    provider_selection_status,
)
from anvil.orchestration.nodes.review import _parse_review_pass


def test_normalize_requested_pipeline_fills_all_roles() -> None:
    pipeline = normalize_requested_pipeline("auto", {"execute": "openai"})
    assert pipeline["execute"] == "openai"
    assert pipeline["critique"] == "auto"
    assert pipeline["reflect"] == "auto"


def test_build_state_pipeline_omits_auto_base_provider() -> None:
    pipeline = build_state_pipeline(
        base_provider="auto", role_providers={"execute": "openai"}
    )
    assert pipeline == {"execute": "openai"}


def test_build_state_pipeline_applies_base_and_overrides() -> None:
    pipeline = build_state_pipeline(
        base_provider="openai", role_providers={"critique": "anthropic"}
    )
    assert pipeline["execute"] == "openai"
    assert pipeline["critique"] == "anthropic"


def test_provider_selection_status() -> None:
    assert (
        provider_selection_status(
            base_provider="auto",
            enable_leadership=True,
            role_providers={"execute": "openai"},
        )
        == "skipped (role overrides provided)"
    )
    assert (
        provider_selection_status(
            base_provider="openai", enable_leadership=True, role_providers=None
        )
        == "skipped (base provider specified)"
    )
    assert (
        provider_selection_status(
            base_provider="auto", enable_leadership=False, role_providers=None
        )
        == "disabled"
    )
    assert (
        provider_selection_status(
            base_provider="auto", enable_leadership=True, role_providers=None
        )
        == "active"
    )


def test_format_pipeline_map_is_ordered_and_readable() -> None:
    pipeline = normalize_requested_pipeline("openai", {"critique": "anthropic"})
    text = format_pipeline_map(pipeline)
    assert text.startswith(
        "execute=openai, critique=anthropic, refine=openai, review=openai,"
    )


def test_format_mapping_diff_reports_changed_keys() -> None:
    before = {"temperature": 0.7, "max_tokens": 512}
    after = {"temperature": 0.5, "max_tokens": 512, "top_p": 1.0}
    diff = format_mapping_diff(before, after)
    assert "temperature 0.7 → 0.5" in diff
    assert "top_p None → 1.0" in diff


def test_review_pass_parsing_ignores_think_block() -> None:
    text = "<think>reasoning...</think>\n[PASS] Looks good"
    assert _parse_review_pass(text) is True


def test_review_fail_parsing_ignores_think_block() -> None:
    text = "<think>reasoning...</think>\n[FAIL] Needs work"
    assert _parse_review_pass(text) is False
