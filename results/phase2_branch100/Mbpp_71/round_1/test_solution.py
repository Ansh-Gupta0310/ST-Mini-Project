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

def test_comb_sort_gap_reduction_true():
    # Ensure gap reduction path is exercised by using a list that requires multiple passes
    result = comb_sort([5, 15, 37, 25, 79])
    assert result == [5, 15, 25, 37, 79]

def test_comb_sort_sorted_flag_false():
    # Trigger the sorted_flag = False branch by providing an unsorted list
    result = comb_sort([10, 3, 7, 1, 9])
    assert result == [1, 3, 7, 9, 10]
