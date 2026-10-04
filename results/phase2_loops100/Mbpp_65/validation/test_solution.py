from solution import recursive_list_sum

def test_empty_list():
    assert recursive_list_sum([]) == 0

def test_single_element():
    assert recursive_list_sum([42]) == 42

def test_multiple_elements():
    assert recursive_list_sum([1, 2, 3]) == 6

def test_nested_list():
    assert recursive_list_sum([1, [2, 3], 4]) == 10

def test_deeply_nested():
    assert recursive_list_sum([1, [2, [3, 4]], 5]) == 15

def test_skip_loop_body():
    # Ensure loop body is skipped when list is empty
    assert recursive_list_sum([]) == 0

def test_one_iteration():
    # Loop runs exactly one iteration (no nested lists)
    assert recursive_list_sum([7]) == 7

def test_two_or_more_iterations():
    # Loop runs multiple iterations, including nested list
    assert recursive_list_sum([1, 2, [3, 4]]) == 10

def test_consecutive_decision_outcomes():
    # First element is list, second is not (consecutive outcomes)
    assert recursive_list_sum([[5], 6]) == 11
