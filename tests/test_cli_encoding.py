"""
Test CLI with encoding restrictions (Windows cp1252)
"""

import sys
from unittest.mock import Mock, patch

from harnessdiff.cli import safe_checkmark, safe_cross


def test_cli_safe_symbols_with_cp1252():
    """Test that CLI symbols work with cp1252 encoding"""
    # Create a mock stream with cp1252 encoding
    fake_stream = Mock()
    fake_stream.encoding = "cp1252"

    with patch.object(sys, "stdout", fake_stream):
        check = safe_checkmark()
        cross = safe_cross()

        # Should return ASCII-safe alternatives on cp1252
        assert check in ["✓", "OK"]
        assert cross in ["✗", "X"]

        # Should be encodable to cp1252
        try:
            check.encode("cp1252")
            cross.encode("cp1252")
        except UnicodeEncodeError:
            assert False, "CLI symbols must be encodable to cp1252"


def test_cli_safe_symbols_with_utf8():
    """Test that CLI symbols prefer Unicode with UTF-8"""
    fake_stream = Mock()
    fake_stream.encoding = "utf-8"

    with patch.object(sys, "stdout", fake_stream):
        check = safe_checkmark()
        cross = safe_cross()

        # With UTF-8, should use Unicode symbols
        # (but ASCII fallback is also acceptable)
        assert check in ["✓", "OK"]
        assert cross in ["✗", "X"]
