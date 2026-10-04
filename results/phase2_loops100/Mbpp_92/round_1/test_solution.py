from solution import is_undulating

def test_undulating_true():
    assert is_undulating(1212121) == True

def test_undulating_false_length_less_than_3():
    assert is_undulating(12) == False

def test_undulating_false_more_than_two_unique_digits():
    assert is_undulating(123123) == False

def test_undulating_false_adjacent_equal_digits():
    assert is_undulating(1221) == False

def test_undulating_loop_body_skipped():
    assert is_undulating(121) == True

def test_undulating_loop_one_iteration():
    assert is_undulating(12121) == True

def test_undulating_loop_two_or_more_iterations():
    assert is_undulating(1212121) == True
