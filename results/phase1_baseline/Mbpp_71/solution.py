def comb_sort(nums):
    n = len(nums)
    gap = n
    shrink = 1.3
    sorted_flag = False

    while not sorted_flag:
        sorted_flag = True
        gap = max(1, int(gap / shrink))
        for i in range(n - gap):
            if nums[i] > nums[i + gap]:
                nums[i], nums[i + gap] = nums[i + gap], nums[i]
                sorted_flag = False
    return nums
