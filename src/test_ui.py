#!/usr/bin/env python3
"""
Test script to verify the Knowledge Repository API and Web UI are working correctly.
"""

import requests
import json
import time
import sys

API_BASE = "http://localhost:8000"

def test_health():
    """Test the health endpoint"""
    print("🔍 Testing API health endpoint...")
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"✅ API is healthy: {health['status']}")
            print(f"   - Ollama: {health['ollama']}")
            print(f"   - Vault: {health['vault_path']}")
            print(f"   - ChromaDB: {health['chroma_db']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server. Is it running on port 8000?")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_capture():
    """Test the capture endpoint"""
    print("\n🔍 Testing URL capture endpoint...")
    test_url = "https://httpbin.org/json"

    try:
        headers = {
            "Content-Type": "application/json"
        }
        data = {"url": test_url, "method": "auto"}

        response = requests.post(f"{API_BASE}/capture", headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ URL capture successful")
            print(f"   - File: {result['file_path']}")
            print(f"   - Title: {result['title']}")
            return True
        else:
            print(f"❌ URL capture failed: {response.status_code}")
            print(f"   - Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ URL capture error: {e}")
        return False

def test_query():
    """Test the query endpoint"""
    print("\n🔍 Testing query endpoint...")

    try:
        headers = {
            "Content-Type": "application/json"
        }
        data = {"query": "test", "top_k": 3}

        response = requests.post(f"{API_BASE}/query", headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Query successful")
            print(f"   - Answer: {result['answer']}")
            print(f"   - Sources found: {len(result['sources'])}")
            return True
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(f"   - Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Query error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Knowledge Repository API")
    print("=" * 50)

    # Test health first
    if not test_health():
        print("\n❌ API server is not responding. Please start it with:")
        print("   python3 main.py")
        sys.exit(1)

    # Test other endpoints
    test_capture()
    test_query()

    print("\n" + "=" * 50)
    print("🎉 API tests completed!")
    print("\n📝 Next steps:")
    print("1. Open your web browser and go to: http://10.243.15.166:7860/simple_ui.html")
    print("2. The connection status indicator should show '🟢 API 연결됨'")
    print("3. Try capturing a URL or searching your knowledge base")

if __name__ == "__main__":
    main()