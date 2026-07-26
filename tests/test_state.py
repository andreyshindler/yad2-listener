import os

from yad2_listener.state import SeenStore


def test_seen_store_roundtrip(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    store = SeenStore(path)
    assert "a" not in store

    store.add("a")
    store.add("b")
    store.save()

    reloaded = SeenStore(path)
    assert "a" in reloaded
    assert "b" in reloaded
    assert len(reloaded) == 2


def test_seen_store_handles_missing_file(tmp_path):
    store = SeenStore(os.path.join(tmp_path, "does-not-exist.json"))
    assert len(store) == 0


def test_seen_store_handles_corrupt_file(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not valid json")
    store = SeenStore(path)
    assert len(store) == 0
