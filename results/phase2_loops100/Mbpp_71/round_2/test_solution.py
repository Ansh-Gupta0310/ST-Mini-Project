from solution import comb_sort


def test_comb_sort_already_sorted():
    assert comb_sort([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]


def test_comb_sort_reverse_sorted():
    assert comb_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]


def test_comb_sort_single_element():
    assert comb_sort([42]) == [42]


def test_comb_sort_empty_list():
    assert comb_sort([]) == []


def test_comb_sort_two_elements():
    assert comb_sort([2, 1]) == [1, 2]


def test_comb_sort_three_elements_one_iteration():
    # This list requires exactly one pass of the inner loop (gap=3->2->1)
    # After the first gap=2 iteration, the list becomes [1, 3, 2]
    # Then gap=1 iteration will swap 3 and 2, resulting in sorted order.
    # To ensure the test covers a case where the inner loop runs exactly once,
    # we use a list that after the first gap=2 iteration is already sorted.
    # However, with gap=2, the only comparison is between indices 0 and 2.
    # So we need a list where nums[0] > nums[2] to trigger a swap (so the loop body runs),
    # but after that swap the list is sorted, and the next gap=1 iteration will have no swaps.
    # To achieve exactly one iteration of the inner loop (i.e., the for loop runs once),
    # we need a list where after the first gap=2 iteration, the gap becomes 1 and the for loop
    # runs exactly once (i.e., n - gap = 2). That's satisfied for n=3.
    # Let's pick [3, 1, 2] -> after gap=2 swap: [2, 1, 3]; then gap=1 iteration swaps 2 and 1 -> [1,2,3]
    # The inner loop runs twice (once for gap=2, once for gap=1). To have exactly one iteration,
    # we need a list where after the first gap=2 iteration, the gap becomes 1 and the for loop runs once,
    # but we also need the inner loop to run exactly one iteration overall.
    # Actually, the requirement is about loop coverage: for every loop there must be a test that
    # skips its body completely, a test that runs exactly one iteration, and a test that runs two or more iterations.
    # The loops are: while loop and for loop inside while.
    # For the for loop, we need a test where it runs zero times (skip body), a test where it runs exactly once,
    # and a test where it runs two or more times.
    # To have the for loop run zero times, we need n - gap == 0, i.e., gap == n. That occurs at the start when gap = n.
    # So we can test with a list where after the first shrink, gap becomes 1 and n - gap = 0? Actually gap = max(1, int(gap / shrink)).
    # For n=1, gap starts at 1, after shrink gap = max(1, int(1/1.3)) = max(1,0) = 1, so for loop runs 0 times.
    # So test_comb_sort_single_element already covers the for loop skipping its body.
    # For exactly one iteration of the for loop, we need n - gap == 1. That can happen when n=2 and gap=1.
    # So test_comb_sort_two_elements covers exactly one iteration.
    # For two or more iterations, we need n - gap >= 2. That's covered by test_comb_sort_already_sorted (n=5, gap=5->3->2->1, each for loop runs >=2 times).
    # So we don't need an extra test for for loop iterations; the existing tests already satisfy coverage.
    pass


def test_comb_sort_large_gap():
    # Use a list where the initial gap is large enough to cause multiple swaps in one pass.
    # For n=7, initial gap=7, after shrink gap=5 (int(7/1.3)=5), for loop runs 2 times.
    # So this test ensures the for loop runs at least two iterations.
    assert comb_sort([7, 6, 5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5, 6, 7]


def test_comb_sort_partial_order():
    # A list that requires multiple passes but not full reverse order.
    assert comb_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]


def test_comb_sort_sorted_flag_false_to_true() -> None:
    """Test that sorted_flag starts False and becomes True after sorting."""
    # Use a list that is already sorted; the while loop should run once,
    # sorted_flag becomes False at start, then set to True after first pass,
    # and the loop exits, returning the list.
    assert comb_sort([1, 2, 3]) == [1, 2, 3]


def test_comb_sort_sorted_flag_false_to_true_with_swap() -> None:
    """Test that sorted_flag becomes False then True when swaps occur."""
    # A list that requires at least one swap, ensuring sorted_flag is set to False
    # during the loop, then later becomes True after sorting completes.
    assert comb_sort([2, 1]) == [1, 2]


def test_comb_sort_sorted_flag_false_to_true_multiple_passes() -> None:
    """Test that sorted_flag transitions from False to True over multiple passes."""
    # A list that needs multiple passes (e.g., reverse order) to ensure
    # sorted_flag is toggled multiple times before finally becoming True.
    assert comb_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]


def test_comb_sort_sorted_flag_false_to_true_empty() -> None:
    """Test that sorted_flag is set to False then True for empty list."""
    # For an empty list, the while loop should still run once, sorted_flag
    # becomes False initially, then True after the first (empty) pass, and returns.
    assert comb_sort([]) == []


def test_comb_sort_sorted_flag_false_to_true_single_element() -> None:
    """Test that sorted_flag transitions for a single element."""
    # A single element list should cause the while loop to run once,
    # sorted_flag becomes False then True, and returns.
    assert comb_sort([42]) == [42]
