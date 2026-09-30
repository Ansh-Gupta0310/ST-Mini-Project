def is_sublist(l, s):
    n = len(l)
    m = len(s)
    if m == 0:
        return True
    for i in range(n - m + 1):
        if l[i:i+m] == s:
            return True
    return False
