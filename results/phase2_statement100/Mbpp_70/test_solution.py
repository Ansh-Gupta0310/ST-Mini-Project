from solution import get_equal

def test_empty_input():
    assert get_equal([]) == True

def test_single_tuple():
    assert get_equal([(1, 2, 3)]) == True

def test_all_equal_lengths():
    assert get_equal([(1, 2), (3, 4), (5, 6)]) == True

def test_first_tuple_longer():
    assert get_equal([(1, 2, 3), (4, 5)]) == False

def test_middle_tuple_longer():
    assert get_equal([(1,), (2, 3), (4,)]) == False

def test_last_tuple_longer():
    assert get_equal([(1,), (2,), (3, 4)]) == False

def test_all_different_lengths():
    assert get_equal([(1,), (2, 3), (4, 5, 6)]) == False

def test_nested_tuples():
    assert get_equal([((1, 2),), ((3, 4),)]) == True

def test_mixed_types():
    assert get_equal([(1, 2, 3), (4.5, 6.7, 8.9)]) == True
