from factory.operations.resources import memory_headroom


def test_cgroup_limit_caps_admission(tmp_path):
    (tmp_path / "memory.max").write_text("8589934592")
    (tmp_path / "memory.current").write_text("8053063680")
    m = memory_headroom(tmp_path)
    assert m["cgroup_limit_bytes"] == 8 * 1024**3
    assert 0 <= m["available_bytes"] <= 512 * 1024**2
    (tmp_path / "memory.current").write_text("8589934593")
    assert memory_headroom(tmp_path)["available_bytes"] == 0


def test_unlimited_and_unmounted_cgroup_fallback(tmp_path):
    assert memory_headroom(tmp_path)["cgroup_limit_bytes"] is None
    (tmp_path / "memory.max").write_text("max")
    assert memory_headroom(tmp_path)["cgroup_limit_bytes"] is None
