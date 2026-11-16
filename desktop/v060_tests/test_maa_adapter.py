from fgoauto_v060.maa_adapter import MaaFrameworkAdapter


def test_adapter_starts_uninitialized():
    adapter = MaaFrameworkAdapter()
    assert adapter.status.initialized is False
    assert "尚未初始化" in adapter.status.message


def test_initialize_requires_controller(tmp_path):
    adapter = MaaFrameworkAdapter()
    status = adapter.initialize(None, tmp_path)
    assert status.initialized is False
    assert "尚未提供裝置控制器" in status.message


def test_initialize_requires_existing_resource_directory(tmp_path):
    adapter = MaaFrameworkAdapter()
    status = adapter.initialize(object(), tmp_path / "missing")
    assert status.initialized is False
    assert "找不到 Maa 資源資料夾" in status.message


def test_close_is_safe_before_initialization():
    adapter = MaaFrameworkAdapter()
    adapter.close()
    assert adapter.status.initialized is False
