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