from solution import is_undulating

def test_undulating_positive() -> None:
    assert is_undulating(1212121) == True

def test_undulating_short_number() -> None:
    assert is_undulating(12) == False

def test_undulating_non_two_unique_digits() -> None:
    assert is_undulating(123123) == False

def test_undulating_adjacent_equal() -> None:
    assert is_undulating(121221) == False

def test_undulating_alternating() -> None:
    assert is_undulating(1212) == False

def test_undulating_single_digit() -> None:
    assert is_undulating(5) == False

def test_undulating_three_digits_valid() -> None:
    assert is_undulating(121) == True
