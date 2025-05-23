import pytest
from container_lock.lock import acquire_lock, release_lock, get_locked_container, get_active_containers
from container_lock.mock_redis import MockRedis

@pytest.fixture
def redis_client():
    return MockRedis()

def test_acquire_and_release_lock(redis_client):
    ip = "1.2.3.4"
    container_id = "cont-123"
    # Acquire lock
    assert acquire_lock(ip, container_id, redis_client=redis_client) is True
    # Can't acquire again for same IP
    assert acquire_lock(ip, "cont-456", redis_client=redis_client) is False
    # Check locked container
    assert get_locked_container(ip, redis_client=redis_client) == container_id
    # Active containers
    assert get_active_containers(redis_client=redis_client) == [container_id]
    # Release lock
    assert release_lock(ip, redis_client=redis_client) is True
    # Lock is gone
    assert get_locked_container(ip, redis_client=redis_client) is None
    assert get_active_containers(redis_client=redis_client) == []
    # Release again returns False
    assert release_lock(ip, redis_client=redis_client) is False

def test_multiple_ips(redis_client):
    ip1, ip2 = "1.1.1.1", "2.2.2.2"
    c1, c2 = "c1", "c2"
    assert acquire_lock(ip1, c1, redis_client=redis_client)
    assert acquire_lock(ip2, c2, redis_client=redis_client)
    assert set(get_active_containers(redis_client=redis_client)) == {c1, c2}
    assert release_lock(ip1, redis_client=redis_client)
    assert get_locked_container(ip1, redis_client=redis_client) is None
    assert get_locked_container(ip2, redis_client=redis_client) == c2
    assert get_active_containers(redis_client=redis_client) == [c2]

def test_ui_route(monkeypatch):
    from fastapi.testclient import TestClient
    from container_lock.main import app
    # Patch docker.from_env
    class MockContainer:
        def __init__(self, id, name, status, group_label):
            self.id = id
            self.name = name
            self.status = status
            self.labels = {"sablier.group": "qemu-lab"}
    class MockDockerClient:
        class containers:
            @staticmethod
            def list(all=True):
                return [
                    MockContainer("id1", "cont1", "running", "qemu-lab"),
                    MockContainer("id2", "cont2", "exited", "qemu-lab"),
                ]
    monkeypatch.setattr("docker.from_env", lambda: MockDockerClient())
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Container Sessions" in response.text

def test_ui_dynamic_containers(monkeypatch, redis_client):
    from fastapi.testclient import TestClient
    from container_lock.main import app
    # Patch docker.from_env
    class MockContainer:
        def __init__(self, id, name, status, group_label):
            self.id = id
            self.name = name
            self.status = status
            self.labels = {"sablier.group": "qemu-lab"}
    class MockDockerClient:
        class containers:
            @staticmethod
            def list(all=True):
                return [
                    MockContainer("c1", "cont1", "running", "qemu-lab"),
                    MockContainer("c2", "cont2", "running", "qemu-lab"),
                ]
    monkeypatch.setattr("docker.from_env", lambda: MockDockerClient())
    monkeypatch.setattr("container_lock.main.get_active_containers", lambda: ["c1", "c2"])
    # Patch get_redis_client to use test redis_client
    monkeypatch.setattr("container_lock.lock.get_redis_client", lambda *args, **kwargs: redis_client)
    redis_client.setex("lock:1.2.3.4", 300, "c1")
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "Container c1" in html or "cont1" in html
    assert "Container c2" in html or "cont2" in html
    assert 'disabled' in html or 'cursor-not-allowed' in html

def test_list_all_containers_with_locks(monkeypatch, redis_client):
    # Mock docker client and containers
    class MockContainer:
        def __init__(self, id, name, status, group_label):
            self.id = id
            self.name = name
            self.status = status
            self.labels = {"sablier.group": group_label}
    class MockDockerClient:
        class containers:
            @staticmethod
            def list(all=True):
                return [
                    MockContainer("id1", "cont1", "running", "qemu-lab"),
                    MockContainer("id2", "cont2", "exited", "qemu-lab"),
                    MockContainer("id3", "cont3", "running", "other-group"),
                ]
    monkeypatch.setattr("docker.from_env", lambda: MockDockerClient())
    # Patch get_redis_client to use test redis_client
    monkeypatch.setattr("container_lock.lock.get_redis_client", lambda *args, **kwargs: redis_client)
    # Lock id1 to ip1
    redis_client.setex("lock:ip1", 300, "id1")
    from container_lock.lock import list_all_containers_with_locks
    containers = list_all_containers_with_locks(redis_client=redis_client)
    active = [c for c in containers if c["status"] == "running" and c["locked_by_ip"]]
    available = [c for c in containers if not c["locked_by_ip"] or c["status"] != "running"]
    # id1 should be active, locked by ip1
    assert any(c["id"] == "id1" and c["locked_by_ip"] == "ip1" for c in active)
    # id2 should be available (not running)
    assert any(c["id"] == "id2" for c in available)
    # id3 should not be present (wrong group)
    assert all(c["id"] != "id3" for c in containers)

def always_true(*args, **kwargs):
    return True

# Patch is_managed_container for all tests
import container_lock.lock
import pytest
@pytest.fixture(autouse=True)
def patch_is_managed_container(monkeypatch):
    monkeypatch.setattr(container_lock.lock, "is_managed_container", always_true) 