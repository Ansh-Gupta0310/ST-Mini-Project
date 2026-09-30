from solution import get_equal

def test_empty_input() -> None:
    assert get_equal([]) == True

def test_single_tuple() -> None:
    assert get_equal([(1, 2, 3)]) == True

def test_all_equal_length() -> None:
    assert get_equal([(1, 2), (3, 4)]) == True

def test_first_tuple_longer() -> None:
    assert get_equal([(1, 2, 3), (4, 5)]) == False

def test_first_tuple_shorter() -> None:
    assert get_equal([(1,), (2, 3)]) == False

def test_mixed_lengths() -> None:
    assert get_equal([(1, 2), (3,), (4, 5)]) == False

def test_all_same_length_three() -> None:
    assert get_equal([(1, 2, 3), (4, 5, 6), (7, 8, 9)]) == True
