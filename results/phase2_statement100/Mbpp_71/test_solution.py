from solution import comb_sort

def test_comb_sort_already_sorted():
    assert comb_sort([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]

def test_comb_sort_reverse_sorted():
    assert comb_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]

def test_comb_sort_with_duplicates():
    assert comb_sort([3, 1, 2, 1, 3]) == [1, 1, 2, 3, 3]

def test_comb_sort_single_element():
    assert comb_sort([42]) == [42]

def test_comb_sort_empty_list():
    assert comb_sort([]) == []

def test_comb_sort_random_order():
    assert comb_sort([5, 15, 37, 25, 79]) == [5, 15, 25, 37, 79]
