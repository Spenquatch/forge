from anvil.cli import _should_print_stream_event


def test_stream_filter_hides_chat_model_stream_by_default() -> None:
    event = {"event": "on_chat_model_stream", "node": "ChatOpenAI"}
    assert _should_print_stream_event(event, verbose=False) is False


def test_stream_filter_shows_node_chain_transitions_by_default() -> None:
    assert (
        _should_print_stream_event(
            {"event": "on_chain_start", "node": "execute"}, verbose=False
        )
        is True
    )
    assert (
        _should_print_stream_event(
            {"event": "on_chain_end", "node": "execute"}, verbose=False
        )
        is True
    )


def test_stream_filter_hides_chain_stream_by_default() -> None:
    event = {"event": "on_chain_stream", "node": "execute"}
    assert _should_print_stream_event(event, verbose=False) is False


def test_stream_filter_verbose_shows_everything() -> None:
    event = {"event": "on_chat_model_stream", "node": "ChatOpenAI"}
    assert _should_print_stream_event(event, verbose=True) is True
