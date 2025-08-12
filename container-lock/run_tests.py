#!/usr/bin/env python3
"""
Simple test runner for the container-lock module.
This script runs tests without requiring pytest installation.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up environment variables for testing
os.environ['DOCKER_HOST'] = 'tcp://test:2376'
os.environ['DOCKER_TLS_VERIFY'] = '1'
os.environ['DOCKER_CERT_PATH'] = '/test/certs'

def run_basic_tests():
    """Run basic functionality tests"""
    print("Running basic functionality tests...")
    
    try:
        # Test imports
        from container_lock.lock import get_redis_client, get_docker_client
        print("✓ Imports successful")
        
        # Test Redis client creation
        with patch('container_lock.lock.Redis') as mock_redis:
            mock_redis.from_url.return_value = Mock()
            client = get_redis_client("redis://test:6379/0")
            print("✓ Redis client creation successful")
        
        # Test Docker client creation (local)
        with patch.dict(os.environ, {}, clear=True):
            with patch('container_lock.lock.docker') as mock_docker:
                mock_docker.from_env.return_value = Mock()
                client = get_docker_client()
                print("✓ Local Docker client creation successful")
        
        # Test Docker client creation (remote TLS)
        with patch.dict(os.environ, {
            'DOCKER_HOST': 'tcp://remote:2376',
            'DOCKER_TLS_VERIFY': '1',
            'DOCKER_CERT_PATH': '/certs'
        }):
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = True
                with patch('container_lock.lock.docker') as mock_docker:
                    mock_tls_config = Mock()
                    mock_docker.tls.TLSConfig.return_value = mock_tls_config
                    mock_docker.DockerClient.return_value = Mock()
                    
                    client = get_docker_client()
                    print("✓ Remote TLS Docker client creation successful")
        
        print("\n🎉 All basic tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def run_advanced_tests():
    """Run more advanced tests with mocking"""
    print("\nRunning advanced tests...")
    
    try:
        from container_lock.lock import (
            acquire_lock, release_lock, is_managed_container,
            get_locked_container, get_active_containers
        )
        from fastapi import HTTPException
        
        # Test parameter validation
        try:
            acquire_lock("", "container123")
            print("❌ Should have failed with empty IP")
            return False
        except HTTPException as e:
            if e.status_code == 400:
                print("✓ Parameter validation working")
            else:
                print(f"❌ Wrong error code: {e.status_code}")
                return False
        
        # Test Redis operations
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.scan_iter.return_value = []
        mock_redis.setex.return_value = True
        mock_redis.sadd.return_value = 1
        
        with patch('container_lock.lock.is_managed_container', return_value=True):
            result = acquire_lock("192.168.1.1", "container123", mock_redis)
            if result:
                print("✓ Lock acquisition working")
            else:
                print("❌ Lock acquisition failed")
                return False
        
        print("🎉 All advanced tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Advanced test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test runner"""
    print("🧪 Container Lock Test Runner")
    print("=" * 40)
    
    # Run basic tests
    basic_success = run_basic_tests()
    
    # Run advanced tests
    advanced_success = run_advanced_tests()
    
    print("\n" + "=" * 40)
    if basic_success and advanced_success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 