"""What routing every widget's messages through the provider layer costs.

    python probes/subclass_overhead.py

Spawns itself twice, bare and provided, over the same redraw-heavy window: a
canvas animation plus a widget-heavy form, timed over a fixed number of
update() cycles. Prints both timings and the difference.
"""

from __future__ import annotations

import subprocess
import sys
import time
import tkinter as tk

_FRAMES = 600
_FORM_ROWS = 30


def a_busy_window() -> tuple[tk.Tk, tk.Canvas, list[tk.Label]]:
    root = tk.Tk()
    root.title("subclass overhead probe")
    canvas = tk.Canvas(root, width=300, height=120)
    canvas.grid(row=0, column=0, columnspan=2)
    form = []
    for row in range(_FORM_ROWS):
        label = tk.Label(root, text=f"Field {row}")
        label.grid(row=row + 1, column=0, sticky="w")
        tk.Entry(root, width=18).grid(row=row + 1, column=1)
        form.append(label)
    root.update()
    return root, canvas, form


def timed_frames(mode: str) -> float:
    root, canvas, form = a_busy_window()
    if mode == "provided":
        import tk_uia

        strategy = tk_uia.enable(root)
        print(f"enable -> {strategy}", file=sys.stderr)
    box = canvas.create_rectangle(0, 40, 30, 70, fill="black")
    started = time.perf_counter()
    for frame in range(_FRAMES):
        canvas.moveto(box, (frame * 3) % 270, 40)
        form[frame % _FORM_ROWS].configure(text=f"Field {frame}")
        root.update()
    elapsed = time.perf_counter() - started
    root.destroy()
    return elapsed


def main() -> None:
    if len(sys.argv) > 1:
        print(f"{timed_frames(sys.argv[1]):.4f}")
        return
    timings = {}
    for mode in ("bare", "provided"):
        answer = subprocess.run(
            [sys.executable, __file__, mode],
            capture_output=True,
            text=True,
            check=True,
        )
        timings[mode] = float(answer.stdout.strip())
    slowdown = (timings["provided"] - timings["bare"]) / timings["bare"] * 100
    print(f"bare:     {timings['bare']:.3f}s for {_FRAMES} frames")
    print(f"provided: {timings['provided']:.3f}s for {_FRAMES} frames")
    print(f"difference: {slowdown:+.1f}%")


if __name__ == "__main__":
    main()
