import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import docker
from fastapi import HTTPException

# Import after setting up environment
os.environ['DOCKER_HOST'] = 'tcp://test:2376'
os.environ['DOCKER_TLS_VERIFY'] = '1'
os.environ['DOCKER_CERT_PATH'] = '/test/certs'

from container_lock.lock import (
    get_redis_client, get_docker_client, test_docker_connection,
    is_managed_container, acquire_lock, release_lock, get_locked_container,
    get_active_containers, get_user_active_container,
    list_all_containers_with_locks, list_all_containers,
    cleanup_exited_containers, get_container_lock_status
)
from container_lock.config import config


class TestRedisClient:
    def test_get_redis_client_with_custom_url(self):
        with patch('container_lock.lock.Redis') as mock_redis:
            mock_redis.from_url.return_value = Mock()
            client = get_redis_client("redis://custom:6379/0")
            mock_redis.from_url.assert_called_once_with("redis://custom:6379/0")

    def test_get_redis_client_default(self):
        with patch('container_lock.lock.Redis') as mock_redis:
            mock_redis.from_url.return_value = Mock()
            client = get_redis_client()
            mock_redis.from_url.assert_called_once_with(config.REDIS_URL)


class TestDockerClient:
    @patch.dict(os.environ, {}, clear=True)
    def test_get_docker_client_local(self):
        """Test local Docker socket when no environment variables set"""
        with patch('container_lock.lock.docker') as mock_docker:
            mock_docker.from_env.return_value = Mock()
            client = get_docker_client()
            mock_docker.from_env.assert_called_once()

    @patch.dict(os.environ, {
        'DOCKER_HOST': 'tcp://remote:2376',
        'DOCKER_TLS_VERIFY': '1',
        'DOCKER_CERT_PATH': '/certs'
    })
    @patch('os.path.exists')
    def test_get_docker_client_remote_tls(self, mock_exists):
        """Test remote Docker with TLS"""
        mock_exists.return_value = True
        
        with patch('container_lock.lock.docker') as mock_docker:
            mock_tls_config = Mock()
            mock_docker.tls.TLSConfig.return_value = mock_tls_config
            mock_docker.DockerClient.return_value = Mock()
            
            client = get_docker_client()
            
            mock_docker.tls.TLSConfig.assert_called_once()
            mock_docker.DockerClient.assert_called_once()

    @patch.dict(os.environ, {
        'DOCKER_HOST': 'tcp://remote:2376',
        'DOCKER_TLS_VERIFY': '1',
        'DOCKER_CERT_PATH': '/certs'
    })
    @patch('os.path.exists')
    def test_get_docker_client_missing_certs(self, mock_exists):
        """Test error when TLS certificates are missing"""
        mock_exists.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            get_docker_client()
        assert exc_info.value.status_code == 500

    @patch.dict(os.environ, {
        'DOCKER_HOST': 'tcp://remote:2376',
        'DOCKER_TLS_VERIFY': '0'
    })
    def test_get_docker_client_remote_no_tls(self):
        """Test remote Docker without TLS (insecure)"""
        with patch('container_lock.lock.docker') as mock_docker:
            mock_docker.DockerClient.return_value = Mock()
            
            client = get_docker_client()
            mock_docker.DockerClient.assert_called_once()


class TestDockerConnection:
    def test_test_docker_connection_success(self):
        """Test successful Docker connection"""
        mock_info = {
            'ServerVersion': '20.10.0',
            'Containers': 5,
            'Images': 10
        }
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.info.return_value = mock_info
            mock_get_client.return_value = mock_client
            
            result = test_docker_connection()
            
            assert result['status'] == 'connected'
            assert result['docker_version'] == '20.10.0'
            assert result['containers_count'] == 5

    def test_test_docker_connection_failure(self):
        """Test Docker connection failure"""
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_get_client.side_effect = Exception("Connection failed")
            
            result = test_docker_connection()
            
            assert result['status'] == 'failed'
            assert 'Connection failed' in result['error']


class TestManagedContainer:
    def test_is_managed_container_true(self):
        mock_container = Mock()
        mock_container.labels = {"sablier.group": config.GROUP_LABEL}
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_get_client.return_value = mock_client
            
            result = is_managed_container("container123")
            assert result is True

    def test_is_managed_container_false(self):
        mock_container = Mock()
        mock_container.labels = {"sablier.group": "other-group"}
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_get_client.return_value = mock_client
            
            result = is_managed_container("container123")
            assert result is False

    def test_is_managed_container_not_found(self):
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.side_effect = docker.errors.NotFound("Container not found")
            mock_get_client.return_value = mock_client
            
            result = is_managed_container("container123")
            assert result is False

    def test_is_managed_container_docker_error(self):
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.side_effect = Exception("Docker error")
            mock_get_client.return_value = mock_client
            
            result = is_managed_container("container123")
            assert result is False


class TestAcquireLock:
    def test_acquire_lock_success(self):
        mock_redis = Mock()
        mock_redis.get.return_value = None  # No existing lock
        mock_redis.scan_iter.return_value = []  # No other locks
        mock_redis.setex.return_value = True
        mock_redis.sadd.return_value = 1
        
        with patch('container_lock.lock.is_managed_container', return_value=True):
            result = acquire_lock("192.168.1.1", "container123", mock_redis)
            assert result is True
            mock_redis.setex.assert_called_once()
            mock_redis.sadd.assert_called_once()

    def test_acquire_lock_missing_params(self):
        """Test validation of required parameters"""
        with pytest.raises(HTTPException) as exc_info:
            acquire_lock("", "container123")
        assert exc_info.value.status_code == 400
        
        with pytest.raises(HTTPException) as exc_info:
            acquire_lock("192.168.1.1", "")
        assert exc_info.value.status_code == 400

    def test_acquire_lock_container_not_managed(self):
        with patch('container_lock.lock.is_managed_container', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                acquire_lock("192.168.1.1", "container123")
            assert exc_info.value.status_code == 403

    def test_acquire_lock_ip_already_has_container(self):
        mock_redis = Mock()
        mock_redis.get.return_value = b"existing_container"
        
        with patch('container_lock.lock.is_managed_container', return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                acquire_lock("192.168.1.1", "container123", mock_redis)
            assert exc_info.value.status_code == 409

    def test_acquire_lock_container_already_locked(self):
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.scan_iter.return_value = [b"lock:192.168.1.2"]
        mock_redis.get.side_effect = [b"container123", b"container123"]
        
        with patch('container_lock.lock.is_managed_container', return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                acquire_lock("192.168.1.1", "container123", mock_redis)
            assert exc_info.value.status_code == 409

    def test_acquire_lock_redis_error(self):
        mock_redis = Mock()
        mock_redis.get.side_effect = Exception("Redis error")
        
        with patch('container_lock.lock.is_managed_container', return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                acquire_lock("192.168.1.1", "container123", mock_redis)
            assert exc_info.value.status_code == 500


class TestReleaseLock:
    def test_release_lock_success(self):
        mock_redis = Mock()
        mock_redis.get.return_value = b"container123"
        mock_redis.delete.return_value = 1
        mock_redis.srem.return_value = 1
        
        with patch('container_lock.lock.is_managed_container', return_value=True):
            result = release_lock("192.168.1.1", mock_redis)
            assert result is True
            mock_redis.delete.assert_called_once()
            mock_redis.srem.assert_called_once()

    def test_release_lock_no_lock_exists(self):
        mock_redis = Mock()
        mock_redis.get.return_value = None
        
        result = release_lock("192.168.1.1", mock_redis)
        assert result is False

    def test_release_lock_container_not_managed(self):
        mock_redis = Mock()
        mock_redis.get.return_value = b"container123"
        
        with patch('container_lock.lock.is_managed_container', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                release_lock("192.168.1.1", mock_redis)
            assert exc_info.value.status_code == 403

    def test_release_lock_redis_error(self):
        mock_redis = Mock()
        mock_redis.get.side_effect = Exception("Redis error")
        
        with pytest.raises(HTTPException) as exc_info:
            release_lock("192.168.1.1", mock_redis)
        assert exc_info.value.status_code == 500


class TestGetLockedContainer:
    def test_get_locked_container_exists(self):
        mock_redis = Mock()
        mock_redis.get.return_value = b"container123"
        
        with patch('container_lock.lock.is_managed_container', return_value=True):
            result = get_locked_container("192.168.1.1", mock_redis)
            assert result == "container123"

    def test_get_locked_container_not_exists(self):
        mock_redis = Mock()
        mock_redis.get.return_value = None
        
        result = get_locked_container("192.168.1.1", mock_redis)
        assert result is None

    def test_get_locked_container_not_managed(self):
        mock_redis = Mock()
        mock_redis.get.return_value = b"container123"
        
        with patch('container_lock.lock.is_managed_container', return_value=False):
            result = get_locked_container("192.168.1.1", mock_redis)
            assert result is None


class TestActiveContainers:
    def test_get_active_containers_success(self):
        mock_redis = Mock()
        mock_redis.smembers.return_value = [b"container1", b"container2"]
        
        result = get_active_containers(mock_redis)
        assert result == ["container1", "container2"]

    def test_get_active_containers_redis_error(self):
        mock_redis = Mock()
        mock_redis.smembers.side_effect = Exception("Redis error")
        
        with pytest.raises(HTTPException) as exc_info:
            get_active_containers(mock_redis)
        assert exc_info.value.status_code == 500


class TestUserActiveContainer:
    def test_get_user_active_container_exists(self):
        mock_redis = Mock()
        mock_redis.get.return_value = b"container123"
        
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.status = "running"
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_get_client.return_value = mock_client
            
            result = get_user_active_container("192.168.1.1", mock_redis)
            assert result["container_id"] == "container123"
            assert result["container_name"] == "test-container"
            assert result["container_status"] == "running"

    def test_get_user_active_container_not_exists(self):
        mock_redis = Mock()
        mock_redis.get.return_value = None
        
        result = get_user_active_container("192.168.1.1", mock_redis)
        assert result is None

    def test_get_user_active_container_not_found(self):
        mock_redis = Mock()
        mock_redis.get.return_value = b"container123"
        mock_redis.delete.return_value = 1
        mock_redis.srem.return_value = 1
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.side_effect = docker.errors.NotFound("Container not found")
            mock_get_client.return_value = mock_client
            
            result = get_user_active_container("192.168.1.1", mock_redis)
            assert result is None
            mock_redis.delete.assert_called_once()
            mock_redis.srem.assert_called_once()


class TestContainerListing:
    def test_list_all_containers_success(self):
        mock_container1 = Mock()
        mock_container1.id = "container1"
        mock_container1.name = "test1"
        mock_container1.status = "running"
        
        mock_container2 = Mock()
        mock_container2.id = "container2"
        mock_container2.name = "test2"
        mock_container2.status = "exited"
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.list.return_value = [mock_container1, mock_container2]
            mock_get_client.return_value = mock_client
            
            result = list_all_containers()
            assert len(result) == 2
            assert result[0]["id"] == "container1"
            assert result[1]["id"] == "container2"

    def test_list_all_containers_docker_error(self):
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.list.side_effect = Exception("Docker error")
            mock_get_client.return_value = mock_client
            
            with pytest.raises(HTTPException) as exc_info:
                list_all_containers()
            assert exc_info.value.status_code == 500


class TestCleanup:
    def test_cleanup_exited_containers(self):
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = [b"lock:192.168.1.1"]
        mock_redis.get.return_value = b"container123"
        mock_redis.delete.return_value = 1
        mock_redis.srem.return_value = 1
        
        mock_container = Mock()
        mock_container.id = "container123"
        mock_container.status = "exited"
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.list.return_value = [mock_container]
            mock_get_client.return_value = mock_client
            
            result = cleanup_exited_containers(mock_redis)
            assert result == 1
            mock_redis.delete.assert_called_once()
            mock_redis.srem.assert_called_once()


class TestContainerStatus:
    def test_get_container_lock_status_not_locked(self):
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []
        
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.status = "running"
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_get_client.return_value = mock_client
            
            result = get_container_lock_status("container123", mock_redis)
            assert result["is_locked"] is False
            assert result["is_clickable"] is True

    def test_get_container_lock_status_locked(self):
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = [b"lock:192.168.1.1"]
        mock_redis.get.return_value = b"container123"
        
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.status = "running"
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.return_value = mock_container
            mock_get_client.return_value = mock_client
            
            result = get_container_lock_status("container123", mock_redis)
            assert result["is_locked"] is True
            assert result["locked_by_ip"] == "192.168.1.1"
            assert result["is_clickable"] is False

    def test_get_container_lock_status_not_found(self):
        mock_redis = Mock()
        
        with patch('container_lock.lock.get_docker_client') as mock_get_client:
            mock_client = Mock()
            mock_client.containers.get.side_effect = docker.errors.NotFound("Container not found")
            mock_get_client.return_value = mock_client
            
            result = get_container_lock_status("container123", mock_redis)
            assert result["container_status"] == "not_found"
            assert result["is_locked"] is False 