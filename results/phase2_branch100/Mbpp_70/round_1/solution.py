def get_equal(Input):
    if not Input:
        return True
    first_len = len(Input[0])
    for tup in Input:
        if len(tup) != first_len:
            return False
    return True
