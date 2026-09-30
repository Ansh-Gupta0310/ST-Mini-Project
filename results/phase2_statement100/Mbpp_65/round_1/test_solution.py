from solution import recursive_list_sum

def test_flat_list_sum():
    assert recursive_list_sum([1, 2, 3, 4, 5]) == 15

def test_nested_list_sum():
    assert recursive_list_sum([1, 2, [3, 4], [5, 6]]) == 21

def test_deeply_nested_list_sum():
    assert recursive_list_sum([1, [2, [3, [4]]]]) == 10

def test_empty_list():
    assert recursive_list_sum([]) == 0

def test_single_element():
    assert recursive_list_sum([42]) == 42

def test_mixed_types_with_nested_lists():
    assert recursive_list_sum([1, [2, 3], 4, [5, [6, 7]]]) == 28
