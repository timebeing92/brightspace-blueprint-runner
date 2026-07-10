#!/usr/bin/env python3
"""Splash screen: a pixel-art wizard drafting a blueprint.

The scene is a character grid (one char = one pixel) rendered two pixel rows
per terminal line using the half-block trick: ``▀`` drawn with the upper
pixel's color as foreground and the lower pixel's color as background. Pure
stdlib; anything that can't animate (no TTY, --plain) gets a static or text
banner instead.
"""
from __future__ import annotations

import select
import sys
import time

# One char per pixel. Legend maps chars to 256-color indexes; '.' is transparent.
SCENE = [
    "..............................................",
    ".........*...........................*.......",
    "....................*.........................",
    ".......H..................................*..",
    "......HHH.....................................",
    ".....HHHHH............*.......................",
    "....HHHHHHH...................................",
    "...HHHHHHHHH..................*...............",
    "..hhhhhhhhhhh.................................",
    ".....SSSSS....................................",
    "....SSSSSSS...................................",
    "....BSSSSSB...................................",
    ".....BBBBB....................................",
    "....RRBBBRR...................................",
    "...RRRRRRRRRRRSS..............................",
    "..RRRRRRRRRRRRRQ..............................",
    "..rRRRRRRRRRr..PPPPPPPPPPPPPPPPPPPPPPPPPPPP..",
    "..rRRRRRRRRRr..PGGPGGPGGPGGPGGPGGPGGPGGPGGP..",
    "..rRRRRRRRRRr..PGWWWWWGGWWWWWGGGWWWWWWWGGGP..",
    "..rRRRRRRRRRr..PGWGGGWGGWGGGWGGGWGGGGGWGGGP..",
    "..rrRRRRRRRrr..PGWWWWWGGWWWWWGGGWWWWWWWGGGP..",
    "..rrrRRRRRrrr..PGGGGGGGWGGGGGGWGGGGGGGGGGGP..",
    "...............PPPPPPPPPPPPPPPPPPPPPPPPPPPP..",
    "..............TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT.",
    "..................tt....................tt....",
    "..................tt....................tt....",
]

PALETTE = {
    "H": 54,   # hat / deep robe
    "h": 97,   # hat brim highlight
    "*": 222,  # stars
    "S": 223,  # skin
    "B": 253,  # beard
    "R": 61,   # robe
    "r": 54,   # robe shadow
    "Q": 253,  # quill
    "P": 24,   # blueprint paper
    "G": 31,   # blueprint grid
    "W": 195,  # drafted plan lines
    "T": 137,  # table top
    "t": 94,   # table legs
    "!": 230,  # sparkle (animation only)
}

TITLE = "B L U E P R I N T   W I Z A R D"
SUBTITLE = "Brightspace export  →  course blueprint"


def _grid() -> list[list[str]]:
    width = max(len(row) for row in SCENE)
    return [list(row.ljust(width, ".")) for row in SCENE]


def _render(grid: list[list[str]], term) -> str:
    """Half-block render: two pixel rows per text line."""
    lines = []
    for upper_row in range(0, len(grid) - 1, 2):
        chars = []
        for col in range(len(grid[0])):
            upper = PALETTE.get(grid[upper_row][col])
            lower = PALETTE.get(grid[upper_row + 1][col])
            if upper is None and lower is None:
                chars.append(" ")
            elif upper is not None and lower is None:
                chars.append(f"\x1b[38;5;{upper}m▀\x1b[0m")
            elif upper is None and lower is not None:
                chars.append(f"\x1b[38;5;{lower}m▄\x1b[0m")
            else:
                chars.append(f"\x1b[38;5;{upper};48;5;{lower}m▀\x1b[0m")
        lines.append("  " + "".join(chars))
    return "\n".join(lines)


def _key_pressed(timeout: float) -> bool:
    """Best-effort non-blocking key check (POSIX); falls back to plain sleep."""
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            sys.stdin.readline()
            return True
        return False
    except (OSError, ValueError):
        time.sleep(timeout)
        return False


def _plan_cells(grid: list[list[str]]) -> list[tuple[int, int]]:
    cells = [
        (row, col)
        for row, line in enumerate(grid)
        for col, char in enumerate(line)
        if char == "W"
    ]
    cells.sort(key=lambda rc: (rc[1], rc[0]))  # left-to-right, like drafting
    return cells


def splash(term, *, animate: bool = True, version: str = "") -> None:
    """Draw the wizard. Animated on a TTY: the plan lines draft themselves."""
    title_line = f"  {term.accent(term.bold(TITLE))}"
    subtitle_line = "  " + term.dim(SUBTITLE + (f"  ·  {version}" if version else ""))

    if term.plain:
        print()
        print(f"  === {TITLE} ===")
        print(subtitle_line)
        print()
        return

    grid = _grid()
    plan = _plan_cells(grid)
    frame_height = (len(grid) // 2) + 3  # art lines + blank + title + subtitle

    def draw(current: list[list[str]], first: bool) -> None:
        if not first:
            sys.stdout.write(f"\x1b[{frame_height}F")
        sys.stdout.write(_render(current, term) + "\n\n")
        sys.stdout.write(title_line + "\n" + subtitle_line + "\n")
        sys.stdout.flush()

    term.hide_cursor()
    try:
        if animate and plan:
            working = [row[:] for row in grid]
            for row, col in plan:
                working[row][col] = "G"  # start with plan lines undrafted
            batch = max(1, len(plan) // 10)
            drawn_any = False
            for start in range(0, len(plan), batch):
                for row, col in plan[start : start + batch]:
                    working[row][col] = "W"
                tip_row, tip_col = plan[min(start + batch, len(plan)) - 1]
                keep = working[tip_row][tip_col]
                working[tip_row][tip_col] = "!"  # sparkle at the drafting tip
                draw(working, first=not drawn_any)
                drawn_any = True
                working[tip_row][tip_col] = keep
                if _key_pressed(0.08):
                    break
            draw(grid, first=not drawn_any)
        else:
            draw(grid, first=True)
    finally:
        term.show_cursor()
    print()
