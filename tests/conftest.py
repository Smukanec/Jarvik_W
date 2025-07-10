import pytest

@pytest.fixture
def reload_spy():
    called = []

    def fake_reload():
        called.append(True)

    return called, fake_reload
