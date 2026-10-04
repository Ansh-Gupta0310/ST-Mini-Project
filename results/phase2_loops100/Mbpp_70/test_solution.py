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


def test_first_len_assignment_and_return_true() -> None:
    """Test that first_len assignment and final return True are executed."""
    assert get_equal([(1, 2, 3), (4, 5, 6)]) is True


def test_first_len_assignment_and_loop_one_iteration() -> None:
    """Test first_len assignment with a single tuple (loop runs once)."""
    assert get_equal([(1, 2, 3)]) is True


def test_first_len_assignment_and_loop_two_iterations() -> None:
    """Test first_len assignment with two tuples (loop runs twice)."""
    assert get_equal([(1, 2), (3, 4)]) is True


def test_first_len_assignment_and_loop_three_iterations() -> None:
    """Test first_len assignment with three tuples (loop runs thrice)."""
    assert get_equal([(1, 2), (3, 4), (5, 6)]) is True


def test_first_len_assignment_and_loop_skipped() -> None:
    """Test first_len assignment when input is empty (loop body skipped)."""
    assert get_equal([]) is True


def test_first_len_assignment_and_loop_early_exit_false() -> None:
    """Test first_len assignment with early exit due to mismatch."""
    assert get_equal([(1, 2, 3), (4, 5)]) is False


def test_first_len_assignment_and_loop_early_exit_true() -> None:
    """Test first_len assignment with early exit due to mismatch (second longer)."""
    assert get_equal([(1, 2), (3, 4, 5)]) is False


def test_first_len_assignment_and_loop_mixed_early_exit() -> None:
    """Test first_len assignment with mixed lengths causing early exit."""
    assert get_equal([(1, 2, 3), (4, 5), (6, 7, 8)]) is False
