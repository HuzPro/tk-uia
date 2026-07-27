# Your first accessible form

One small form, and the calls that make it announce itself. Ten minutes.

The [README](README.md) is the reference — what is measured, what is not, and
why. This page is the short way in: a form written the way you already write
one, then the two or three lines that put it in the accessibility tree, then how
to check that they worked.

## The form, as you already write it

Two captioned rows with a `Browse...` button each, a checkbox, a Create button,
and a status line driven by a `StringVar`. Nothing here is unusual, and the two
`Browse...` captions are identical on purpose — most real dialogs have a pair.

```python
import tkinter as tk

root = tk.Tk()
root.title("New Task")

status = tk.StringVar(value="Ready.")
overwrite = tk.IntVar(value=0)


def create_the_task():
    status.set("Created 1 task.")


file_row = tk.Frame(root)
file_caption = tk.Label(file_row, text="Task file:")
file_caption.pack(side="left")
task_file = tk.Entry(file_row, width=24)
task_file.pack(side="left", padx=4)
tk.Button(file_row, text="Browse...").pack(side="left")
file_row.pack(fill="x", padx=8, pady=4)

folder_row = tk.Frame(root)
folder_caption = tk.Label(folder_row, text="Output folder:")
folder_caption.pack(side="left")
output_folder = tk.Entry(folder_row, width=24)
output_folder.pack(side="left", padx=4)
tk.Button(folder_row, text="Browse...").pack(side="left")
folder_row.pack(fill="x", padx=8, pady=4)

tk.Checkbutton(root, text="Overwrite existing files", variable=overwrite).pack(
    anchor="w", padx=8
)
tk.Button(root, text="Create", command=create_the_task).pack(anchor="w", padx=8, pady=4)
tk.Label(root, textvariable=status).pack(anchor="w", padx=8, pady=(0, 8))

root.mainloop()
```

It looks right and it works. To a screen reader it is almost nothing: both
captions and the status line are announced as *pictures*, both entries arrive as
anonymous panes with no name and no readable contents, and the three buttons and
the checkbox are all unnamed buttons. The words are on the screen and none of
them are in the tree — [the claim, stated
precisely](README.md#the-claim-stated-precisely).

## Making it accessible

Three lines, and two of them are the same call:

```python
import tk_uia

# ... build the window exactly as above ...

tk_uia.enable(root)
tk_uia.label_for(file_caption, task_file)
tk_uia.label_for(folder_caption, output_folder)

root.mainloop()
```

What each line buys:

- **`enable(root)`** names every widget that carries its own words and gives
  every widget the right control type — so the captions become `TextControl`s
  that read themselves, the buttons become named `ButtonControl`s, and the
  checkbox becomes a `CheckBoxControl` whose `ToggleState` is correct and
  follows `overwrite` with nothing else said. The **status line** is named from
  `status` and *stays* in step with it: the label told Tk which variable it
  shows, so `enable()` reads that off the widget and follows it. Since 0.6.0
  that costs no call at all — set the variable, and what a client reads changes
  with what is on screen.
- **`label_for(caption, entry)`** says the one thing nothing can read back. An
  entry has no words of its own, and in Tk the label that names it is a
  *sibling*: no part of the toolkit records which widget a caption speaks for,
  so no amount of reading the entry will find it. Said once, the entry answers
  to `'Task file'` — the colon comes off, because every caption in a form has
  one and none of them is part of a control's name.

That is the whole of it for this window. There is no third call to remember:
anything else you might want to say is in the [API table](README.md#quickstart),
and most forms need none of it.

### The retrofit, for a window that already has fifty rows

One `label_for` per entry is fine for a form you are writing now. For a dialog
that already exists, `infer_names_from_layout(root)` applies the same convention
to every row at once and tells you what it did:

```python
tk_uia.enable(root)
for named in tk_uia.infer_names_from_layout(root):
    print(named.path, "->", named.name)
```

Which on this window prints:

```
.!frame.!entry -> Task file
.!frame.!button -> Browse... for Task file
.!frame2.!entry -> Output folder
.!frame2.!button -> Browse... for Output folder
```

It named the two entries exactly as the two `label_for` calls did — and it did
one thing more, which is the reason to prefer it here: it qualified both
`Browse...` buttons with the row they act on. Two controls announced
`Browse...` in one window are two controls nobody can choose between, and that
is a fault the per-row route leaves behind.

### Which route fits

| | |
|---|---|
| A form you are writing now, ten rows or fewer | **`label_for` per row.** It is explicit, it is in your source next to the widgets it talks about, and a reader of your code can see what the entry will be called. |
| A dialog that already exists, or one with dozens of rows | **`infer_names_from_layout(root)`.** One call, and it returns every name it chose so you can read the whole of the guess before shipping it. |
| A row the convention gets wrong | **`set_acc_name(widget, ...)`.** A name you chose is never replaced, whether you said it before the call or after it. |

The two mix freely, and neither is part of `enable()` on purpose: a layout is
not a statement — two widgets are beside each other because somebody packed them
that way — so applying it is a guess, and this library never guesses on its own.
Asked for by name it is something else: a convention you have recognised in your
own window. [The longer version](README.md#the-caption-an-entry-has-and-tk-does-not-record).

## Check your work

`describe(root)` reports what your application has told Windows, and names every
widget it did not. It reads no COM and no UI Automation, so you can leave the
call in.

```python
root.update()                 # let Tk map the window: <Map> is what annotates
print(tk_uia.describe(root))
```

With `enable()` and the two `label_for` calls, that prints:

```
tk-uia 0.6.0 -- what this application has told Windows it is showing
enable() reported ANNOTATED. 12 widgets under .: 11 written to, 1 not.

WIDGET            CLASS        ROLE               NAME                        VALUE  ID
----------------  -----------  -----------------  --------------------------  -----  --
.                 Tk           -                  -                           -      -
.!frame           Frame        GROUPING (20)      -                           -      -
.!frame.!label    Label        STATIC_TEXT (41)   'Task file:'                -      -
.!frame.!entry    Entry        TEXT (42)          'Task file'                 -      -
.!frame.!button   Button       PUSH_BUTTON (43)   'Browse...'                 -      -
.!frame2          Frame        GROUPING (20)      -                           -      -
.!frame2.!label   Label        STATIC_TEXT (41)   'Output folder:'            -      -
.!frame2.!entry   Entry        TEXT (42)          'Output folder'             -      -
.!frame2.!button  Button       PUSH_BUTTON (43)   'Browse...'                 -      -
.!checkbutton-1   Checkbutton  CHECK_BUTTON (44)  'Overwrite existing files'  -      -
.!button          Button       PUSH_BUTTON (43)   'Create'                    -      -
.!label           Label        STATIC_TEXT (41)   'Ready.'                    -      -
    kept in step with a variable: name

WHAT A CLIENT WILL NOT GET, AND WHY

  NAME_NOT_UNIQUE  (2)
    shares its role and its accessible name with another widget in the
    same window, so a client asking for it reaches one of them at random
    and a screen reader announces both of them the same way. Qualify the
    caption -- 'Browse... for GUI Executable' -- with set_acc_name, or let
    infer_names_from_layout(root) qualify the generic ones for a whole
    window at once.
      .!frame.!button  (Button)
      .!frame2.!button  (Button)

  NO_VALUE  (2)
    no accessible value. The role gives this widget a ValuePattern it did
    not have before, and it reads '' until something writes one -- a
    confident wrong answer where bare Tk gave none. bind_value_variable().
      .!frame.!entry  (Entry)
      .!frame2.!entry  (Entry)

  CANNOT_BE_PRESSED  (3)
    advertises an InvokePattern and a DefaultAction that press nothing. Tk
    buttons are owner-drawn, so the proxy's synthesised BM_CLICK goes into
    the void. Clients must click.
      .!frame.!button  (Button)
      .!frame2.!button  (Button)
      .!button  (Button)

LEFT ALONE ON PURPOSE

  NAMED_BY_ITS_TITLE  (1)
    a window, and `wm title` already gives it a correct accessible name.
    Overriding it would break resolving the window by its title, which is
    where every other query starts.
      .  (Tk)

Everything above is what tk-uia believes it wrote. It is not evidence that
a client can read it: IAccPropServices accepts a write to a window handle
nobody owns, answers S_OK, and changes nothing. Reading the same window
back from another process is the only thing that proves the bridge carried
it.
```

### How to read that

**The headline first.** `enable() reported ANNOTATED` is the line that says the
window was annotated at all. On a Tk 9.1, or off Windows, it reads `NATIVE` or
`UNSUPPORTED` and every row below is blank — which is why the strategy comes
before the table rather than after it.

**Then the table**, which is what a client will read: a role, a name and a value
per widget. `.!label` carries `kept in step with a variable: name`, which is the
status line following `status` — nothing goes stale there, ever.

**Then the gaps.** Three of them here, and a fourth heading that is not a fault
at all — `NAMED_BY_ITS_TITLE` is the report saying it left the window alone
because `root.title("New Task")` already named it correctly.

- **`NAME_NOT_UNIQUE` — the one to fix.** Both `Browse...` buttons are correctly
  typed and correctly named, and they are named *the same thing*: a screen
  reader user hears the same announcement for two controls that do different
  things, and a locator asking for "the Browse... button" gets whichever one the
  tree hands back first. Nothing about either button on its own is wrong, which
  is why it takes a whole-window check to see it. Two fixes, and both remove the
  gap from this report: qualify the captions by hand with
  `set_acc_name(button, "Browse... for Task file")`, or run
  `infer_names_from_layout(root)`, which does exactly that for every row at
  once. Take the retrofit route above and this heading is gone; the rest of the
  report is unchanged.
- **`NO_VALUE` — decide whether you care.** Annotating an entry gives it a
  ValuePattern it did not have in bare Tk, and until something says what is in
  the box it answers `''`. That is a confident wrong answer where bare Tk gave
  no answer at all, so it is worth a decision rather than a shrug. It costs one
  word at construction — `tk.Entry(file_row, textvariable=chosen_file)`, and
  `enable()` follows the variable from there — or one line afterwards,
  `bind_value_variable(task_file, chosen_file)`.
- **`CANNOT_BE_PRESSED` — nothing to fix, and worth knowing.** Every annotated
  Tk button says it can be invoked and cannot be. See below.

`describe()` reports what tk-uia believes it wrote, and says so in its own last
paragraph. It is not a client, and it is not proof. Reading the same window back
from another process is — [the recipe is in the
README](README.md#closing-the-gap-compare-it-with-what-a-client-sees).

### Call it once the window is on screen

`<Map>` is the event that annotates a widget, and Tk fires it when the widget
goes on screen. Call `describe(root)` between building the window and running
`mainloop()` and you get a report of a window that has not happened yet —
measured on this same form, nine of its twelve widgets come back `NEVER_MAPPED`
and the two entries `label_for` reached come back `UNMAPPED_SINCE_ANNOTATED`.
The `root.update()` above is what makes the report describe the window you are
looking at; in a running application, `root.after(0, ...)` or a debug key
binding does the same job.

## What a screen reader user gets

Tabbing through the annotated form, a screen reader has something to work with
at every stop: an edit control named `Task file`, a button named `Browse... for
Task file`, a check box named `Overwrite existing files` whose checked state is
correct and stays correct, and a status line whose name changes when `status`
does. Before `enable()`, every one of those stops is an anonymous pane or an
unnamed button: not a wrong name, but no name at all.

Three things it does **not** give you, none of them small:

- **Findable and readable is not activatable.** An annotated `tk.Button`
  advertises an `InvokePattern` and a default action of "Press", and both lie:
  the call returns cleanly and the Tk command never runs. Assistive technology
  and test tools have to click. [The measurement, and
  why](README.md#the-limitation-findable-and-readable-is-not-activatable).
- **What is *inside* a list is not in the tree.** A `Listbox` is a findable
  `ListControl` and its rows are not there at all; the same goes for `Treeview`
  items. A `ttk.Notebook`'s tabs are the exception and are reachable.
  [Caveats worth knowing](README.md#caveats-worth-knowing).
- **No screen reader has been in the room.** Everything this project claims is
  read back through UI Automation, which is the API a screen reader consumes —
  so "NVDA can read this tree" is evidenced and "NVDA says the right thing at
  the right moment" is not. The paragraph above is what the tree supports, not a
  transcript. [The checklist that would close
  it](README.md#not-yet-verified-a-real-screen-reader).

The honest claim is the narrow one: **the accessibility tree tells the truth.**
That is worth a great deal more than an untrue one.

## Where to go next

- [Is this for you?](README.md#is-this-for-you) — including the two cases where
  the answer is "use something else".
- [Caveats worth knowing](README.md#caveats-worth-knowing) — a name goes stale
  after `config(text=...)`, disabled state is not conveyed, and the rest.
- [COVERAGE.md](COVERAGE.md) — every widget class in both toolkits, measured
  bare, after `enable()`, and after the naming a well-behaved application adds.
- [The whole API](README.md#quickstart) — seventeen calls, and most forms need
  three.
