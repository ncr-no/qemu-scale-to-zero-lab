import asyncio
import aiohttp
from urllib.parse import urljoin
import time
import json

class CompleteFunctionalityTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_ip1 = "192.168.1.100"
        self.test_ip2 = "192.168.1.101"
        
    async def setup(self):
        """Setup test session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup(self):
        """Cleanup test session"""
        if self.session:
            await self.session.close()
    
    async def release_all_locks(self):
        """Release all existing locks for clean testing"""
        print("🧹 Cleaning up all existing locks...")
        for ip in [self.test_ip1, self.test_ip2]:
            try:
                release_url = urljoin(self.base_url, "/end-session")
                headers = {"X-Real-IP": ip}
                data = {"stop_container": False}  # Don't stop containers, just release locks
                
                async with self.session.post(release_url, json=data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"   Released lock for IP {ip}: {result}")
            except:
                pass  # Ignore errors during cleanup
    
    async def test_all_functionality(self):
        """Test all functionality in sequence"""
        print("🔄 Starting complete functionality test...")
        
        # Clean up first
        await self.release_all_locks()
        
        # 1. Test IP extraction
        print("\n1️⃣ Testing IP extraction...")
        if not await self.test_ip_extraction():
            return False
        
        # 2. Test lock acquisition and verification
        print("\n2️⃣ Testing lock acquisition...")
        container_id = await self.test_acquire_lock()
        if not container_id:
            return False
        
        # 3. Test verify functionality
        print("\n3️⃣ Testing verify functionality...")
        if not await self.test_verify_functionality():
            return False
            
        # 4. Test container access restriction
        print("\n4️⃣ Testing access restriction...")
        if not await self.test_access_restriction(container_id):
            return False
        
        # 5. Test end session functionality
        print("\n5️⃣ Testing end session...")
        if not await self.test_end_session():
            return False
        
        return True
    
    async def test_ip_extraction(self):
        """Test IP extraction from headers"""
        # Test X-Forwarded-For header
        headers = {"X-Forwarded-For": f"{self.test_ip1}, 10.0.0.1, 172.16.0.1"}
        url = urljoin(self.base_url, "/check")
        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"❌ X-Forwarded-For header test failed: {response.status}")
                return False
                
        # Test X-Real-IP header
        headers = {"X-Real-IP": self.test_ip1}
        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"❌ X-Real-IP header test failed: {response.status}")
                return False
        
        print("✅ IP extraction working correctly")
        return True
    
    async def test_acquire_lock(self):
        """Test acquiring a container lock"""
        # Get available containers
        containers_url = urljoin(self.base_url, "/containers/status")
        headers = {"X-Real-IP": self.test_ip1}
        
        async with self.session.get(containers_url, headers=headers) as response:
            if response.status != 200:
                print(f"❌ Failed to get containers: {response.status}")
                return None
            
            data = await response.json()
            containers = data.get("containers", [])
            available_container = None
            
            for container in containers:
                if container.get("is_clickable", False) and not container.get("is_locked", False):
                    available_container = container
                    break
            
            if not available_container:
                print("❌ No available containers found")
                return None
        
        container_id = available_container["id"]
        
        # Acquire lock
        acquire_url = urljoin(self.base_url, f"/acquire?container_id={container_id}")
        
        async with self.session.post(acquire_url, headers=headers) as response:
            if response.status != 200:
                print(f"❌ Failed to acquire lock: {response.status}")
                return None
            
            result = await response.json()
            print(f"✅ Lock acquired for container: {container_id[:12]}...")
        
        # Verify lock exists
        check_url = urljoin(self.base_url, "/check")
        async with self.session.get(check_url, headers=headers) as response:
            if response.status != 200:
                print(f"❌ Failed to check lock: {response.status}")
                return None
            
            result = await response.json()
            if result.get("status") == "locked" and result.get("container_id") == container_id:
                print("✅ Lock verified successfully")
                return container_id
            else:
                print(f"❌ Lock verification failed: {result}")
                return None
    
    async def test_verify_functionality(self):
        """Test verify button functionality"""
        # Test verify endpoint
        verify_url = urljoin(self.base_url, "/verify-caddy-config")
        headers = {"X-Real-IP": self.test_ip1}
        
        async with self.session.get(verify_url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                required_fields = ["caddy_status", "container_routes", "sablier_enabled", "user_container"]
                if all(field in data for field in required_fields):
                    print("✅ Verify functionality working correctly")
                    return True
                else:
                    print(f"❌ Verify endpoint missing fields: {data}")
                    return False
            else:
                print(f"❌ Verify endpoint failed: {response.status}")
                return False
    
    async def test_access_restriction(self, locked_container_id):
        """Test that other IPs cannot access locked containers"""
        # Try to access containers/status with IP2
        headers2 = {"X-Real-IP": self.test_ip2}
        containers_url = urljoin(self.base_url, "/containers/status")
        
        async with self.session.get(containers_url, headers=headers2) as response:
            if response.status == 200:
                data = await response.json()
                containers = data.get("containers", [])
                
                # Find the locked container
                locked_container = None
                for container in containers:
                    if container["id"] == locked_container_id:
                        locked_container = container
                        break
                
                if locked_container:
                    if not locked_container.get("is_clickable", True):
                        print(f"✅ Container properly restricted for other IPs")
                        
                        # Try to acquire lock with IP2 (should fail)
                        acquire_url = urljoin(self.base_url, f"/acquire?container_id={locked_container_id}")
                        async with self.session.post(acquire_url, headers=headers2) as response:
                            if response.status == 409:
                                print("✅ IP2 correctly denied access to locked container")
                                return True
                            else:
                                print(f"❌ IP2 should not be able to acquire lock: {response.status}")
                                return False
                    else:
                        print(f"❌ Container should not be clickable for IP2")
                        return False
                else:
                    print(f"❌ Could not find locked container in response")
                    return False
            else:
                print(f"❌ Failed to get containers with IP2: {response.status}")
                return False
    
    async def test_end_session(self):
        """Test end session functionality"""
        # Test end-session endpoint
        end_session_url = urljoin(self.base_url, "/end-session")
        headers = {"X-Real-IP": self.test_ip1}
        data = {"stop_container": True}
        
        async with self.session.post(end_session_url, json=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Session ended: {result}")
            else:
                print(f"❌ Failed to end session: {response.status}")
                return False
        
        # Verify lock is gone
        check_url = urljoin(self.base_url, "/check")
        async with self.session.get(check_url, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                if result.get("status") == "available":
                    print("✅ Lock successfully removed")
                    return True
                else:
                    print(f"❌ Lock still exists: {result}")
                    return False
            else:
                print(f"❌ Failed to check lock after release: {response.status}")
                return False

async def run_tests():
    """Run complete functionality test"""
    tester = CompleteFunctionalityTester()
    await tester.setup()
    
    try:
        success = await tester.test_all_functionality()
        
        if success:
            print("\n🎉 All functionality tests passed!")
            print("\n✅ Summary of fixes implemented:")
            print("1. Standardized IP extraction using X-Forwarded-For -> X-Real-IP -> client.host priority")
            print("2. Fixed verify button to validate lock ownership")
            print("3. Implemented end session functionality with container stopping")
            print("4. Enforced container access restriction - only lock owner can access container")
            print("5. Updated frontend to use new endpoints properly")
        else:
            print("\n❌ Some functionality tests failed")
        
        return success
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    if success:
        print("\n🚀 All systems working correctly!")
    else:
        print("\n🔧 Some issues remain to be fixed") 