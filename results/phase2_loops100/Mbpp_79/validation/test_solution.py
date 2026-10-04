from solution import word_len

def test_word_len_even_length():
    assert word_len("Hadoop") == False

def test_word_len_odd_length():
    assert word_len("Hello") == True

def test_word_len_empty_string():
    assert word_len("") == True

def test_word_len_single_char():
    assert word_len("a") == True

def test_word_len_two_chars():
    assert word_len("ab") == False

def test_word_len_long_even():
    assert word_len("abcdef") == False

def test_word_len_long_odd():
    assert word_len("abcdefg") == True
