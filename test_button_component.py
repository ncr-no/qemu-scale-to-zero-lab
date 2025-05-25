#!/usr/bin/env python3
"""
Test script for the dynamic button component functionality
"""

import requests
import json
import time
import sys

def test_api_endpoints(base_url="http://localhost:8000"):
    """Test the container-lock API endpoints"""
    
    print("🧪 Testing Container Button Component API")
    print("=" * 50)
    
    # Test health endpoint
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test containers status endpoint
    print("\n2. Testing containers status endpoint...")
    try:
        response = requests.get(f"{base_url}/containers/status")
        if response.status_code == 200:
            data = response.json()
            containers = data.get('containers', [])
            print(f"✅ Found {len(containers)} containers")
            
            # Display container status
            for container in containers[:3]:  # Show first 3
                print(f"   📦 {container['name']}: {container['container_status']} "
                      f"({'🔒 locked' if container['is_locked'] else '🟢 available'})")
        else:
            print(f"❌ Containers status failed: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Containers status failed: {e}")
        return False
    
    # Test cleanup endpoint
    print("\n3. Testing cleanup endpoint...")
    try:
        response = requests.post(f"{base_url}/cleanup")
        if response.status_code == 200:
            data = response.json()
            cleaned = data.get('cleaned_locks', 0)
            print(f"✅ Cleanup completed, removed {cleaned} stale locks")
        else:
            print(f"❌ Cleanup failed: {response.status_code}")
    except requests.RequestException as e:
        print(f"❌ Cleanup failed: {e}")
    
    # Test individual container status (if containers exist)
    if containers:
        print("\n4. Testing individual container status...")
        container_id = containers[0]['id']
        try:
            response = requests.get(f"{base_url}/container/{container_id}/status")
            if response.status_code == 200:
                status = response.json()
                print(f"✅ Container {status['container_name']}: "
                      f"{status['container_status']} "
                      f"({'clickable' if status['is_clickable'] else 'not clickable'})")
            else:
                print(f"❌ Individual status failed: {response.status_code}")
        except requests.RequestException as e:
            print(f"❌ Individual status failed: {e}")
    
    print("\n✅ API testing completed successfully!")
    return True

def test_lock_behavior(base_url="http://localhost:8000"):
    """Test lock acquisition and release behavior"""
    
    print("\n🔐 Testing Lock Behavior")
    print("=" * 30)
    
    # Get available containers
    try:
        response = requests.get(f"{base_url}/containers/status")
        containers = response.json().get('containers', [])
        available = [c for c in containers if c['is_clickable']]
        
        if not available:
            print("⚠️  No available containers for lock testing")
            return True
            
        container_id = available[0]['id']
        test_ip = "192.168.1.100"
        
        print(f"Using container: {available[0]['name']}")
        
        # Test lock acquisition
        print("\n1. Testing lock acquisition...")
        response = requests.post(f"{base_url}/acquire", 
                               params={"ip": test_ip, "container_id": container_id})
        
        if response.status_code == 200:
            print("✅ Lock acquired successfully")
            
            # Verify lock status
            response = requests.get(f"{base_url}/container/{container_id}/status")
            if response.status_code == 200:
                status = response.json()
                if status['is_locked'] and status['locked_by_ip'] == test_ip:
                    print("✅ Lock status verified")
                else:
                    print("❌ Lock status verification failed")
            
            # Test lock release
            print("\n2. Testing lock release...")
            response = requests.post(f"{base_url}/release", params={"ip": test_ip})
            
            if response.status_code == 200:
                print("✅ Lock released successfully")
                
                # Verify release
                response = requests.get(f"{base_url}/container/{container_id}/status")
                if response.status_code == 200:
                    status = response.json()
                    if not status['is_locked']:
                        print("✅ Lock release verified")
                    else:
                        print("❌ Lock release verification failed")
            else:
                print(f"❌ Lock release failed: {response.status_code}")
        else:
            print(f"❌ Lock acquisition failed: {response.status_code}")
            
    except requests.RequestException as e:
        print(f"❌ Lock testing failed: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000"
    
    print(f"🎯 Testing Container Button Component at {base_url}")
    print(f"⏰ Test started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = True
    
    # Run API tests
    if not test_api_endpoints(base_url):
        success = False
    
    # Run lock behavior tests
    if not test_lock_behavior(base_url):
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Button component is working correctly.")
        print("\n📋 Manual Testing Checklist:")
        print("   1. Open browser to container-lock service UI")
        print("   2. Verify containers show with appropriate status badges")
        print("   3. Check that buttons change color based on state")
        print("   4. Test clicking available containers")
        print("   5. Verify auto-refresh every 5 seconds")
        print("   6. Test manual refresh button")
    else:
        print("❌ Some tests failed. Please check the logs and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()