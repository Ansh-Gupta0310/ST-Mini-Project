from solution import pos_count

def test_pos_count_all_positive():
    assert pos_count([1, 2, 3]) == 3

def test_pos_count_all_negative():
    assert pos_count([-1, -2, -3]) == 0

def test_pos_count_mixed():
    assert pos_count([1, -2, 3, -4, 5]) == 3

def test_pos_count_empty():
    assert pos_count([]) == 0

def test_pos_count_single_positive():
    assert pos_count([42]) == 1

def test_pos_count_single_negative():
    assert pos_count([-42]) == 0

def test_pos_count_zero():
    assert pos_count([0, 0, 0]) == 0
