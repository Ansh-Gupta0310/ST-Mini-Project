def bell_number(n):
    # Bell numbers can be computed using the recurrence relation:
    # B(0) = 1
    # B(n+1) = sum_{k=0}^{n} C(n, k) * B(k)
    # We'll use dynamic programming to compute B(n) iteratively.
    bell = [0] * (n + 1)
    bell[0] = 1
    for i in range(1, n + 1):
        total = 0
        for k in range(i):
            # Compute binomial coefficient C(i-1, k) using multiplicative formula
            # to avoid large intermediate values and improve efficiency.
            comb = 1
            for j in range(1, k + 1):
                comb = comb * (i - j) // j
            total += comb * bell[k]
        bell[i] = total
    return bell[n]
