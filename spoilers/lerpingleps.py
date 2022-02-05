"""
[SPOILER]
"""


def prompt_for_nums(count: int, prompt: str):
    while True:
        raw = input('\n'+prompt)
        if raw.count(',') + 1 != count:
            print(f"Expecting {count} numbers")

        items = raw.split(',')

        try:
            nums = [float(i.strip()) for i in items]
        except ValueError:
            print(f"Expecting {count} numbers")

        assert len(nums) == count

        return nums


grid_size, = prompt_for_nums(1, "Grid Size? ")
target_cell = prompt_for_nums(2, "Target cell [x,y]? ")

top_left = prompt_for_nums(3, "Top left [x,y,z]? ")
top_right = prompt_for_nums(3, "Top right [x,y,z]? ")
bottom_left = prompt_for_nums(3, "Bottom left [x,y,z]? ")


col, row = target_cell
row -= .5
col -= .5

print([
    (bl - tl) / grid_size * row + (tr - tl) / grid_size * col + tl
    for tl, tr, bl in zip(top_left, top_right, bottom_left)
])
