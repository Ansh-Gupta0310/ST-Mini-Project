from solution import is_woodall

def test_is_woodall_negative() -> None:
    """Check that negative numbers return False."""
    assert is_woodall(-5) is False

def test_is_woodall_zero() -> None:
    """Check that zero returns False."""
    assert is_woodall(0) is False

def test_is_woodall_one() -> None:
    """Check that 1 (n=1) returns True."""
    assert is_woodall(1) is True

def test_is_woodall_three() -> None:
    """Check that 3 (n=2) returns True."""
    assert is_woodall(3) is True

def test_is_woodall_eleven() -> None:
    """Check that 11 (n=3) returns True."""
    assert is_woodall(11) is True

def test_is_woodall_fortytwo() -> None:
    """Check that 42 (n=4) returns True."""
    assert is_woodall(42) is True

def test_is_woodall_383() -> None:
    """Check that 383 (n=5) returns True."""
    assert is_woodall(383) is True

def test_is_woodall_not_woodall() -> None:
    """Check that a non‑Woodall number returns False."""
    assert is_woodall(100) is False
