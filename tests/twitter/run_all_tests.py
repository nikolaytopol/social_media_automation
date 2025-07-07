#!/usr/bin/env python3
"""
Twitter API Test Suite Runner
Runs all Twitter tests in sequence to verify functionality.
"""

import os
import sys
import subprocess
import datetime
import time

def run_test(test_name, test_file):
    """Run a single test and return success status"""
    print(f"\n{'='*60}")
    print(f"🧪 Running {test_name}")
    print(f"{'='*60}")
    
    try:
        # Run the test script
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, 
                              text=True, 
                              timeout=300)  # 5 minute timeout
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {test_name} PASSED")
            return True
        else:
            print(f"❌ {test_name} FAILED (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_name} TIMED OUT (5 minutes)")
        return False
    except Exception as e:
        print(f"💥 {test_name} ERROR: {e}")
        return False

def main():
    print("🚀 Twitter API Test Suite")
    print(f"Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Define tests in order of complexity
    tests = [
        ("Text-Only Tweet", "test_text_only.py"),
        ("Text + Media Tweet", "test_text_media.py"),
        ("Media-Only Tweet", "test_media_only.py"),
        ("Text + Video Tweet", "test_text_video.py"),
    ]
    
    # Get the directory where this script is located
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if we're in the right directory
    if not os.path.exists(os.path.join(test_dir, "test_text_only.py")):
        print("❌ Error: Test files not found. Make sure you're running this from the tests/twitter directory.")
        sys.exit(1)
    
    # Check for test files
    print(f"\n📁 Test directory: {test_dir}")
    print("🔍 Checking for test files...")
    
    missing_tests = []
    for test_name, test_file in tests:
        test_path = os.path.join(test_dir, test_file)
        if os.path.exists(test_path):
            print(f"  ✅ {test_file}")
        else:
            print(f"  ❌ {test_file} (missing)")
            missing_tests.append(test_file)
    
    if missing_tests:
        print(f"\n❌ Missing test files: {missing_tests}")
        print("Please ensure all test files are present before running the test suite.")
        sys.exit(1)
    
    # Run tests
    print(f"\n🎯 Running {len(tests)} tests...")
    results = []
    
    for test_name, test_file in tests:
        test_path = os.path.join(test_dir, test_file)
        success = run_test(test_name, test_path)
        results.append((test_name, success))
        
        # Add a small delay between tests
        if test_name != tests[-1][0]:  # Not the last test
            print("\n⏳ Waiting 3 seconds before next test...")
            time.sleep(3)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your Twitter API setup is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1) 