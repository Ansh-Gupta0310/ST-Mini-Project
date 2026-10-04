from solution import len_log

def test_empty_list():
    assert len_log([]) == 0

def test_single_word():
    assert len_log(["hello"]) == 5

def test_two_words():
    assert len_log(["hi", "world"]) == 5

def test_three_words():
    assert len_log(["python", "PHP", "bigdata"]) == 7

def test_longest_at_start():
    assert len_log(["supercalifragilisticexpialidocious", "a"]) == 34

def test_longest_at_end():
    assert len_log(["a", "supercalifragilisticexpialidocious"]) == 34

def test_all_same_length():
    assert len_log(["abc", "def", "ghi"]) == 3

def test_mixed_case():
    assert len_log(["Python", "python", "PYTHON"]) == 6

def test_with_empty_strings():
    assert len_log(["", "test", ""]) == 4
