import os
import importlib
import threading
import time
import socket
import pytest

pytest.importorskip("flask")
pytest.importorskip("requests")
import requests


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_restart_returns_new_model(tmp_path):
    """Start Flask, switch models and verify new name."""
    port = _free_port()
    memory = tmp_path / "mem"
    knowledge = tmp_path / "know"
    memory.mkdir()
    knowledge.mkdir()

    threads: list[threading.Thread] = []
    current_main = [None]

    def wait_ready():
        for _ in range(50):
            try:
                r = requests.get(f"http://127.0.0.1:{port}/model")
                if r.status_code == 200:
                    return
            except Exception:
                time.sleep(0.1)

    def start_server(model: str) -> None:
        def run() -> None:
            os.environ["MODEL_NAME"] = model
            os.environ["FLASK_PORT"] = str(port)
            os.environ["MEMORY_DIR"] = str(memory)
            os.environ["KNOWLEDGE_DIR"] = str(knowledge)
            os.environ["TOKEN_LIFETIME_DAYS"] = "1"
            import main as m
            m = importlib.reload(m)
            current_main[0] = m
            m.AUTH_ENABLED = False
            m.subprocess.Popen = fake_popen
            m.app.run(host="127.0.0.1", port=port, use_reloader=False)

        t = threading.Thread(target=run, daemon=True)
        threads.append(t)
        t.start()
        wait_ready()

    restart_info = {}

    def fake_popen(args, *a, **k):
        new_model = args[-1]
        restart_info["model"] = new_model

        def restart() -> None:
            threads[-1].join()
            start_server(new_model)

        threading.Thread(target=restart, daemon=True).start()

        class D:
            pass

        return D()

    start_server("one")

    res = requests.post(f"http://127.0.0.1:{port}/model", json={"model": "two"})
    assert res.status_code == 200
    for _ in range(50):
        try:
            r = requests.get(f"http://127.0.0.1:{port}/model")
            if r.status_code == 200 and r.json()["model"] == "two":
                break
        except Exception:
            pass
        time.sleep(0.1)

    assert r.json()["model"] == "two"
    assert restart_info["model"] == "two"

    current_main[0].subprocess.Popen = lambda *a, **k: type("D", (), {})()
    requests.post(f"http://127.0.0.1:{port}/model", json={"model": "two"})
    threads[-1].join(timeout=5)

