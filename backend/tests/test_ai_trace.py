from pathlib import Path

from app.services import ai_trace


def test_trace_block_writes_file(tmp_path, monkeypatch):
    log_path = tmp_path / "ai-requests.log"
    monkeypatch.setattr(ai_trace, "LOG_FILE", log_path)
    ai_trace.trace_block("test.event", foo="bar", baz="qux")
    content = log_path.read_text(encoding="utf-8")
    assert "test.event" in content
    assert "--- foo ---" in content
    assert "bar" in content
    assert "--- baz ---" in content
    assert "qux" in content

    ai_trace.trace_block("second")
    content2 = log_path.read_text(encoding="utf-8")
    assert "second" in content2
    assert content2.count("\n=== ") + (1 if content2.startswith("=== ") else 0) >= 2


def test_trace_block_creates_parent_dirs(tmp_path, monkeypatch):
    log_path = tmp_path / "nested" / "ai-requests.log"
    monkeypatch.setattr(ai_trace, "LOG_FILE", log_path)
    ai_trace.trace_block("mkdir.test", note="ok")
    assert log_path.is_file()
    assert "ok" in log_path.read_text(encoding="utf-8")
