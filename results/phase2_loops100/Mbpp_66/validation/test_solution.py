from solution import pos_count

def test_empty_list():
    assert pos_count([]) == 0

def test_all_negative():
    assert pos_count([-1, -2, -3]) == 0

def test_all_positive():
    assert pos_count([1, 2, 3]) == 3

def test_mixed_one_positive():
    assert pos_count([-5, 0, 10]) == 1

def test_mixed_two_positives():
    assert pos_count([2, -3, 4, -1]) == 2

def test_single_positive():
    assert pos_count([42]) == 1

def test_single_negative():
    assert pos_count([-7]) == 0

def test_single_zero():
    assert pos_count([0]) == 0

def test_large_list():
    assert pos_count([1] * 10 + [-1] * 5) == 10
