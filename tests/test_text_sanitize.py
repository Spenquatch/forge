from anvil.text_sanitize import extract_final, strip_think


def test_strip_think_removes_leading_closed_block(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_STRIP_THINK", "1")
    text = "<think>secret</think>\nFinal answer"
    assert strip_think(text) == "Final answer"


def test_strip_think_removes_multiple_leading_blocks(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_STRIP_THINK", "1")
    text = "<think>a</think>\n<think>b</think>\nOK"
    assert strip_think(text) == "OK"


def test_strip_think_strict_drops_unclosed_think(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_STRIP_THINK", "1")
    monkeypatch.setenv("FORGE_STRIP_THINK_STRICT", "1")
    text = "<think>this never closes\nstill thinking..."
    assert strip_think(text) == ""


def test_strip_think_non_strict_keeps_text_without_tag(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_STRIP_THINK", "1")
    monkeypatch.setenv("FORGE_STRIP_THINK_STRICT", "0")
    text = "<think>still thinking..."
    assert strip_think(text) == "still thinking..."


def test_extract_final_prefers_final_marker(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_FINAL_ONLY", "1")
    text = "<think>thoughts</think>\nFINAL:\nHello"
    assert extract_final(text) == "Hello"


def test_extract_final_falls_back_to_after_think_close(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_FINAL_ONLY", "1")
    text = "<think>thoughts</think>\nHello"
    assert extract_final(text) == "Hello"


def test_extract_final_ignores_template_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_FINAL_ONLY", "1")
    text = "Real content\n\nFINAL:\n<your improved solution>"
    assert extract_final(text) == "Real content"


def test_extract_final_uses_last_non_placeholder_final_block(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_FINAL_ONLY", "1")
    text = "FINAL:\nGood answer\n\nFINAL:\n<your answer>"
    assert extract_final(text) == "Good answer"
