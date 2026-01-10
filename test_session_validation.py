"""Quick test to verify session ID validation fix"""
import sys

sys.path.insert(0, 'src')

from src.utils.security import validate_request_data

# Test cases
test_cases = [
    ("08sssadb1-1ec5-47fd-8af6-6a5926b91a0d", True, "User's session ID"),
    ("550e8400-e29b-41d4-a716-446655440000", True, "Standard UUID"),
    ("test-session-123", True, "Simple session ID"),
    ("abc", False, "Too short (< 8 chars)"),
    ("a" * 51, False, "Too long (> 50 chars)"),
    ("test@session", False, "Invalid character @"),
    ("test session", False, "Invalid character (space)"),
    (None, True, "None (should be accepted)"),
]

print("="*70)
print("SESSION ID VALIDATION TEST")
print("="*70)

passed = 0
failed = 0

for session_id, should_pass, description in test_cases:
    try:
        result = validate_request_data({"message": "test", "session_id": session_id})
        if should_pass:
            print(f"✅ PASS: {description}")
            print(f"   Input: {session_id}")
            print(f"   Result: Accepted\n")
            passed += 1
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Input: {session_id}")
            print(f"   Expected: Rejection, Got: Accepted\n")
            failed += 1
    except ValueError as e:
        if not should_pass:
            print(f"✅ PASS: {description}")
            print(f"   Input: {session_id}")
            print(f"   Result: Correctly rejected ({str(e)})\n")
            passed += 1
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Input: {session_id}")
            print(f"   Expected: Acceptance, Got: {str(e)}\n")
            failed += 1

print("="*70)
print(f"RESULTS: {passed}/{len(test_cases)} passed, {failed}/{len(test_cases)} failed")
print("="*70)

if failed == 0:
    print("\n🎉 All validation tests passed! Session ID validation is working correctly.")
    sys.exit(0)
else:
    print(f"\n❌ {failed} test(s) failed. Please review the validation logic.")
    sys.exit(1)
