import pytest
from sources.common import decode_html


def test_no_guess_and_no_conflicting_encodings():
    with pytest.raises(ValueError):
        decode_html(b"<html>unknown</html>", {})
    with pytest.raises(ValueError):
        decode_html(b'<meta charset="Shift_JIS">', {"Content-Type": "text/html;charset=utf-8"})


def test_invalid_bytes_fail():
    with pytest.raises(UnicodeDecodeError):
        decode_html(b'<meta charset="Shift_JIS">\x81', {})
