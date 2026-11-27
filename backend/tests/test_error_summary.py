from types import SimpleNamespace

from app.rag.generator import _safe_error_summary


class FakeErr(Exception):
    status_code = 404
    body = {"error": {"code": 404, "status": "NOT_FOUND", "message": "SECRET-PROMPT-TEXT"}}
    response = SimpleNamespace(
        request=SimpleNamespace(
            url=SimpleNamespace(host="example.test", path="/v1beta/openai/chat/completions")
        )
    )


def test_summary_has_allowlisted_fields_only():
    out = _safe_error_summary(FakeErr("Bearer abc SECRET-PROMPT-TEXT"), "m1")
    assert "status=404" in out and "code=404" in out and "status=NOT_FOUND" in out
    assert "host=example.test" in out and "path=/v1beta/openai/chat/completions" in out
    assert "SECRET" not in out and "Bearer" not in out


def test_summary_without_body():
    assert "body=none" in _safe_error_summary(ValueError("x"), "m1")
