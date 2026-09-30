from solution import len_log

def test_single_word():
    assert len_log(["hello"]) == 5

def test_multiple_words():
    assert len_log(["python", "PHP", "bigdata"]) == 7

def test_empty_string():
    assert len_log(["", "a", "ab"]) == 2

def test_all_same_length():
    assert len_log(["abc", "def", "ghi"]) == 3

def test_longest_at_start():
    assert len_log(["supercalifragilisticexpialidocious", "hi"]) == 34

def test_longest_at_end():
    assert len_log(["hi", "supercalifragilisticexpialidocious"]) == 34

def test_mixed_case():
    assert len_log(["Python", "pYTHON", "PYTHON"]) == 7

def test_unicode():
    assert len_log(["café", "coffee", "☕️"]) == 4
