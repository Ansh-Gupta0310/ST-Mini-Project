from solution import is_sublist

def test_empty_sublist():
    assert is_sublist([1, 2, 3], []) == True

def test_sublist_at_start():
    assert is_sublist([3, 7, 1, 2], [3, 7]) == True

def test_sublist_at_end():
    assert is_sublist([1, 2, 3, 7], [3, 7]) == True

def test_sublist_middle():
    assert is_sublist([1, 2, 3, 7, 8], [3, 7]) == True

def test_sublist_not_present():
    assert is_sublist([2, 4, 3, 5, 7], [3, 7]) == False

def test_sublist_exact_match():
    assert is_sublist([3, 7], [3, 7]) == True

def test_sublist_longer_than_list():
    assert is_sublist([1, 2], [1, 2, 3]) == False
