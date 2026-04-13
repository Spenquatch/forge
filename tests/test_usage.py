from anvil.usage import TokenUsage, estimate_cost_usd, extract_token_usage


def test_extract_token_usage_from_dict_prompt_completion() -> None:
    usage = extract_token_usage({"prompt_tokens": 10, "completion_tokens": 5})
    assert usage == TokenUsage(input_tokens=10, output_tokens=5)
    assert usage.total_tokens == 15


def test_extract_token_usage_from_response_metadata_token_usage() -> None:
    class Resp:
        response_metadata = {
            "token_usage": {"prompt_tokens": 7, "completion_tokens": 3}
        }

    usage = extract_token_usage(Resp())
    assert usage == TokenUsage(input_tokens=7, output_tokens=3)


def test_estimate_cost_usd_known_model() -> None:
    cost = estimate_cost_usd(
        "gpt-4o-mini", TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    )
    assert cost == 0.75


def test_estimate_cost_usd_unknown_model_is_none() -> None:
    assert (
        estimate_cost_usd(
            "some-unknown-model", TokenUsage(input_tokens=10, output_tokens=10)
        )
        is None
    )
