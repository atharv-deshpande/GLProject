import httpx

from app.modules.rag.answer_service import OllamaAnswerService


def test_answer_uses_only_supplied_source_context(monkeypatch):
    captured = {}
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"message": {"content": "Follow the approved process [S1]."}}

    def fake_post(url, json, timeout):
        captured.update(url=url, payload=json)
        return Response()

    monkeypatch.setattr("app.modules.rag.answer_service.httpx.post", fake_post)
    answer = OllamaAnswerService("http://ollama", "llama-test").answer(
        "What is the process?",
        [{
            "source_id": "S1",
            "document_name": "policy.pdf",
            "page_number": 4,
            "section_title": "Payments",
            "content": "Use the approved payment workflow.",
        }],
    )
    assert answer.endswith("[S1].")
    user_prompt = captured["payload"]["messages"][1]["content"]
    assert "Use the approved payment workflow." in user_prompt
    assert "Do not invent citations" in user_prompt
