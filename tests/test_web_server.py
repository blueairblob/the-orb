from fastapi.testclient import TestClient

from engine.scenario import build_cell_and_guard
from experiments.web.server import create_app
from tests.test_loop import StubLLM


def test_state_and_reply_protocol(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="Hmph. Fine.")
    app = create_app(llm, scenario, tmp_path / "save.json")
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        state = ws.receive_json()
        assert state["type"] == "state"
        assert state["mood"] == 40
        assert "intro" in state

        ws.send_json({"type": "utterance", "text": "please, my friend"})

        thinking = ws.receive_json()
        assert thinking == {"type": "thinking"}

        reply = ws.receive_json()
        assert reply["type"] == "reply"
        assert reply["text"] == "Hmph. Fine."
        assert reply["mood"] > 40
        assert reply["outcome"] is None

    assert (tmp_path / "save.json").is_file()


def test_empty_and_malformed_messages_are_ignored(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM()
    app = create_app(llm, scenario, tmp_path / "save.json")
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # initial state

        ws.send_text("not json")
        ws.send_json({"type": "utterance", "text": "   "})
        ws.send_json({"type": "unrelated"})
        ws.send_json({"type": "utterance", "text": "hello"})

        thinking = ws.receive_json()
        assert thinking == {"type": "thinking"}
        reply = ws.receive_json()
        assert reply["type"] == "reply"

    assert len(llm.calls) == 1


def test_static_index_is_served(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM()
    app = create_app(llm, scenario, tmp_path / "save.json")
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "orb-canvas" in response.text

    orb_js = client.get("/orb.js")
    assert orb_js.status_code == 200
    assert "WebSocket" in orb_js.text
