from solution import is_sublist

def test_empty_sublist():
    assert is_sublist([1, 2, 3], []) == True

def test_sublist_at_start():
    assert is_sublist([1, 2, 3, 4], [1, 2]) == True

def test_sublist_at_end():
    assert is_sublist([1, 2, 3, 4], [3, 4]) == True

def test_sublist_in_middle():
    assert is_sublist([1, 2, 3, 4, 5], [2, 3]) == True

def test_sublist_not_present():
    assert is_sublist([1, 2, 3, 4], [5, 6]) == False

def test_sublist_wrong_order():
    assert is_sublist([1, 2, 3, 4], [4, 3]) == False

def test_sublist_longer_than_list():
    assert is_sublist([1, 2], [1, 2, 3]) == False

def test_single_element_sublist_present():
    assert is_sublist([1, 2, 3], [2]) == True

def test_single_element_sublist_not_present():
    assert is_sublist([1, 2, 3], [4]) == False
