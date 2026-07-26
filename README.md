# tk-uia

Make Tkinter widgets visible to Windows accessibility clients.

Tk 8.6 gives every widget an empty accessible name and mostly the wrong control
type, so screen readers announce nothing and UI Automation sees a window full of
anonymous panes. `tk_uia.enable(root)` annotates each widget through MSAA, which
Windows bridges to UI Automation, and the tree starts telling the truth.

```python
import tkinter as tk
import tk_uia

root = tk.Tk()
tk.Button(root, text="New Task").pack()
tk_uia.enable(root)
```

Documentation is written up in M2, once the claims here are proven against a
live window from another process.
