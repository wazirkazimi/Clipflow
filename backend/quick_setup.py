#!/usr/bin/env python3
"""
Quick Test & Demo Script for Instagram Reel Batch Generation
Run this to test if everything is working correctly
"""

import subprocess
import time
import requests
import sys

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*70}")
    print(f"  {description}")
    print(f"{'='*70}")
    print(f"Command: {cmd}")
    print()
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    return result.returncode == 0

def test_api_endpoints():
    """Test if API is running and endpoints work"""
    print(f"\n{'='*70}")
    print(f"  Testing API Endpoints")
    print(f"{'='*70}\n")
    
    base_url = "http://localhost:8001"
    endpoints = [
        ("GET", "/", "Health Check"),
        ("GET", "/api/instagram/health", "Instagram Health"),
        ("GET", "/api/instagram/gameplay/available", "List Gameplay Videos"),
    ]
    
    for method, endpoint, desc in endpoints:
        try:
            url = base_url + endpoint
            if method == "GET":
                resp = requests.get(url, timeout=5)
            
            if resp.status_code == 200:
                print(f"✓ {desc}: {endpoint}")
            else:
                print(f"✗ {desc}: Status {resp.status_code}")
        except Exception as e:
            print(f"✗ {desc}: {str(e)}")

def main():
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║      Clipflow Instagram - Quick Test & Setup Guide                ║")
    print("╚════════════════════════════════════════════════════════════════════╝\n")
    
    print("This script will help you set up and test the Instagram reel backend.\n")
    
    # Step 1: Download gameplay videos
    print("STEP 1: Download Gameplay Videos")
    print("-" * 70)
    response = input("Download gameplay videos from YouTube? (y/n): ").strip().lower()
    if response == 'y':
        if run_command("python setup_gameplay_videos.py", "Downloading Gameplay Videos"):
            print("✓ Gameplay videos downloaded successfully")
        else:
            print("✗ Gameplay video download failed")
            print("\nYou can try again later by running: python setup_gameplay_videos.py")
    
    # Step 2: Start the backend
    print("\n\nSTEP 2: Start the Instagram Backend API")
    print("-" * 70)
    print("Command: python -m uvicorn instagram_main:app --port 8001")
    print("\nRunning in a new terminal window...")
    
    if sys.platform == "win32":
        subprocess.Popen("start cmd /k python -m uvicorn instagram_main:app --port 8001", shell=True)
    else:
        subprocess.Popen("python -m uvicorn instagram_main:app --port 8001", shell=True)
    
    print("Waiting for API to start...")
    time.sleep(5)
    
    # Step 3: Test API
    print("\n\nSTEP 3: Test API Endpoints")
    test_api_endpoints()
    
    # Step 4: Show example usage
    print("\n\n" + "="*70)
    print("  SETUP COMPLETE!")
    print("="*70)
    
    print("\n📋 Next Steps:\n")
    print("1. Keep the API running (don't close the terminal)")
    print("2. Run the batch generation example:")
    print("   python example_batch_generation.py")
    print("\n3. Or use curl to interact directly:")
    print("   curl -X POST http://localhost:8001/api/instagram/process \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"url": "https://www.instagram.com/reel/DSlAOH0k0NG/"}\'\n')
    
    print("📚 API Endpoints Available:\n")
    print("  Process Reel:")
    print("    POST   /api/instagram/process")
    print("    GET    /api/instagram/projects/{id}\n")
    print("  Generate Composites:")
    print("    POST   /api/instagram/composite/generate")
    print("    POST   /api/instagram/composite/batch")
    print("    GET    /api/instagram/composites/{id}")
    print("    GET    /api/instagram/batches/{id}\n")
    print("  Utilities:")
    print("    GET    /api/instagram/gameplay/available")
    print("    GET    /api/instagram/health\n")
    
    print("For detailed examples, check: example_batch_generation.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
