def remove_Occ(s, ch):
    # Find first occurrence
    first = s.find(ch)
    # Find last occurrence
    last = s.rfind(ch)
    # If character not found or only one occurrence, return original string
    if first == -1 or first == last:
        return s
    # Remove first and last occurrences
    return s[:first] + s[first+1:last] + s[last+1:]
