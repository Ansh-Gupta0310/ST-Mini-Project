from solution import get_equal

def test_empty_input() -> None:
    """Test empty list returns True, loop body not executed."""
    assert get_equal([]) is True

def test_single_tuple() -> None:
    """Test single tuple, loop runs exactly one iteration."""
    assert get_equal([(1, 2, 3)]) is True

def test_two_equal_length_tuples() -> None:
    """Test two tuples with equal length, loop runs two iterations."""
    assert get_equal([(1, 2), (3, 4)]) is True

def test_three_equal_length_tuples() -> None:
    """Test three tuples with equal length, loop runs three iterations."""
    assert get_equal([(1,), (2,), (3,)]) is True

def test_first_tuple_longer() -> None:
    """Test first tuple longer than second, loop exits early."""
    assert get_equal([(1, 2, 3), (4, 5)]) is False

def test_second_tuple_longer() -> None:
    """Test second tuple longer than first, loop exits early."""
    assert get_equal([(1, 2), (3, 4, 5)]) is False

def test_mixed_lengths() -> None:
    """Test mixed lengths, loop exits early at first mismatch."""
    assert get_equal([(1, 2, 3), (4, 5), (6, 7, 8)]) is False

def test_all_same_length_three_tuples() -> None:
    """Test three tuples all same length, loop runs three iterations."""
    assert get_equal([(1, 2), (3, 4), (5, 6)]) is True
