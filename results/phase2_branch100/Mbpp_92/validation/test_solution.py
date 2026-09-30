from solution import is_undulating

def test_undulating_true():
    assert is_undulating(1212121) == True

def test_undulating_false_length_less_than_3():
    assert is_undulating(12) == False

def test_undulating_false_more_than_two_unique_digits():
    assert is_undulating(123123) == False

def test_undulating_false_adjacent_equal_digits():
    assert is_undulating(121121) == False

def test_undulating_false_single_digit():
    assert is_undulating(5) == False

def test_undulating_false_all_same_digits():
    assert is_undulating(111) == False

def test_undulating_true_minimal():
    assert is_undulating(121) == True

def test_undulating_false_three_digits_adjacent_equal():
    assert is_undulating(112) == False
