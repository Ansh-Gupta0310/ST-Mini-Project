from solution import bell_number

def test_bell_number_zero():
    assert bell_number(0) == 1

def test_bell_number_one():
    assert bell_number(1) == 1

def test_bell_number_two():
    assert bell_number(2) == 2

def test_bell_number_three():
    assert bell_number(3) == 5

def test_bell_number_four():
    assert bell_number(4) == 15

def test_bell_number_five():
    assert bell_number(5) == 52

def test_bell_number_six():
    assert bell_number(6) == 203
