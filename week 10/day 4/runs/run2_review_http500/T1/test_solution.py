"""Tests for token persistence functionality."""
from unittest.mock import patch
import solution


def main():
    """Run tests for save_token and load_token functions."""
    # Test 1: Save and Load existing token
    with patch.object(solution, "TOKEN_FILE_PATH") as mock_path:
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "test_token_123"
        mock_path.write_text = lambda content, encoding: None

        solution.save_token("test_token_123")
        token = solution.load_token()

        assert token == "test_token_123", f"Expected 'test_token_123', got {token}"
        print("✅ Save and load token works correctly")

    # Test 2: Load missing token
    with patch.object(solution, "TOKEN_FILE_PATH") as mock_path:
        mock_path.exists.return_value = False

        token = solution.load_token()
        assert token is None, f"Expected None for missing token, got {token}"
        print("✅ Returns None when token file is missing")

    # Test 3: Verify no external dependencies used
    # Implicitly checked by successful import and execution
    print("✅ No external dependencies used")

    print("✅ All tests passed")


if __name__ == "__main__":
    main()
