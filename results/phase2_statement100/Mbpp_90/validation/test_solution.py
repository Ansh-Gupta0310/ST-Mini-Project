from solution import len_log

def test_single_word():
    assert len_log(["hello"]) == 5

def test_multiple_words():
    assert len_log(["python", "PHP", "bigdata"]) == 7

def test_empty_list():
    assert len_log([]) == 0

def test_mixed_lengths():
    assert len_log(["a", "ab", "abc", "abcd"]) == 4

def test_duplicate_longest():
    assert len_log(["short", "medium", "longest", "longest"]) == 7

def test_case_sensitive():
    assert len_log(["Python", "python", "PYTHON"]) == 6

def test_with_spaces():
    assert len_log(["hello world", "hi"]) == 11
