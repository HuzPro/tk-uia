# Roadmap

Direction: the one-stop shop for making a Tkinter GUI fully accessible through
UI Automation, until Tk itself makes this package unnecessary. Tk 9.1 begins
implementing accessibility natively (TIP 733, MSAA-first), and the gate here
stands down for any Tk that answers for itself; until an application really
runs on one, everything a client should get -- names, types, live state, and
patterns that genuinely act -- is this package's job. Every item below either
widens what a client can do, or raises confidence that what ships is really
being announced to a person rather than merely present in a data structure.

1.0 has a definition rather than a vibe: the release where the headline claims
have been verified against NVDA speech, not only against the UIA tree.

## Shipped in v0.1

Role and name annotation for every classic and themed Tk widget, driven by
`<Map>`, with a version gate that stands down for a Tk that answers for itself,
and a package that costs an application nothing to install.

- **`enable(root)`, and it reports what it did.** `ANNOTATED`, `NATIVE` or
  `UNSUPPORTED`, returned rather than logged, because "annotated" and "the gate
  mis-fired and this did nothing" are otherwise the same silence.
- **Roles inferred from `winfo_class()`, names from `-text`**, both overridable,
  and names never invented for a widget that has none.
- **Auto-registration** on `<Map>`/`<Destroy>` on the `all` bindtag with
  `add="+"`, plus a one-time sweep of everything already on screen, because
  `<Map>` fires once and will not fire again for a window that was already up.
- **Handles released on destroy**, through the HWND cached at map time, so a
  handle Windows recycles does not arrive wearing a dead widget's name.
- **A thread guard.** Tk and the COM apartment both belong to the thread that
  entered them, and an annotation made from another one is written where no
  client will look. `AnnotationRefused`, rather than silence.
- **Proven from another process.** Eight gui specs launch a real Tk window and
  read it back through UI Automation, including the one that pins the honest
  limitation: `InvokePattern.Invoke()` returns cleanly and presses nothing.
- **Zero runtime dependencies**, and a unit suite that runs with no Tk, no
  display and no Windows, enforced by the Ubuntu CI lane.

## Shipped in v0.3

- **`describe(root)`, so an application can ask what it has told Windows.** A
  row per widget with everything that was written about it, and for every widget
  it did not write, a named reason drawn from the caveats `docs/GUIDE.md`
  already documents. It walks the live widget tree and reads the annotation
  ledger; it touches neither UI Automation nor COM, so runtime dependencies stay
  at zero and the whole report renders on a Linux CPython with no `tkinter`. The
  strategy leads the report, because a page of blanks on a machine where
  `enable()` stood down would otherwise read as a clean bill of health. Nothing
  in it is verification, and it says so in its own last paragraph.

## Shipped in v0.6

- **Publishing to PyPI.** `pip install tk-uia`. A release is a tag push: the
  publish workflow builds the artifacts, refuses a tag that disagrees with
  `__version__`, and uploads through Trusted Publishing with no token stored
  anywhere. [RELEASING.md](RELEASING.md) has the flow. The first upload claimed
  the name.

## Shipped in 0.7

Widgets answer UI Automation for themselves: a native provider per widget
window, beside the MSAA annotation. Invoke presses, Value types, Toggle flips,
SelectionItem selects radios and switches notebook tabs, RangeValue moves a
scale and reads a progressbar; names, values, state, help and description are
pulled live; name and value changes raise property-changed events;
`annotate_only()` keeps the old behaviour and `leave_to_the_proxy()` opts one
widget out; `describe()` says who answers for what and why not.

## Next

- **ExpandCollapse for `Menubutton` and `TCombobox`.** Blocked on a measured
  wiring that really opens the dropdown, not on machinery: the candidates are
  `ttk::combobox::Post`/`Unpost` and `menu.post`, driven from an idle
  callback, with focus and grab recovery measured before anything advertises.
  Until then a combobox carries the ComboBox control type without its
  customary ExpandCollapse, which is a documented gap.
- **Selection containers.** A radio group and a notebook answer
  `SelectionItem` per item today with no `SelectionContainer` behind it;
  screen readers phrase "x of y" from the container or from
  PositionInSet/SizeOfSet, and which of those this package should carry is a
  measurement against NVDA and Narrator, not a guess.
- **More property-changed events.** Name and Value ship; ToggleState,
  IsSelected and RangeValue changes belong with `bind_state_variable`, and the
  Invoked event belongs after a posted press completes.
- **`ILegacyIAccessibleProvider`**, so `set_acc_action` and `set_acc_state`
  reach UIA clients on provided widgets the way they reach MSAA ones.
- **Role-driven pattern acquisition.** `set_acc_role(widget,
  Role.PUSH_BUTTON)` on a canvas button should be able to bring a working
  Invoke with it, once there is an honest way to say what pressing means for
  a widget with no `-command`.
- **COVERAGE.md regenerated with a patterns column**, so the per-class
  difference between the proxy's synthesised patterns and the provider's
  working ones is measured and published rather than described.
- **A subclass overhead probe**, pinning what routing every widget's messages
  through the provider layer costs a redraw-heavy window.

- **The cross-repo comparison, as a recipe rather than a tool.** `describe()`
  says what this library believes it wrote; a client-side dump says what a
  client sees; the difference is every `S_OK`-and-nothing failure this package
  has. The script spans tk-uia and pytest-uia, so it belongs in neither. The
  half of it that fits here is already a gui spec, checking every name the
  description claims against the real UI Automation tree. What is missing is the
  written recipe, and a decision about whether the `Gap` member names are stable
  enough to be a documented interface for the client half to match on.

- **Verify with a real screen reader.** Verification today stops at the
  accessibility tree. That is what a screen reader consumes, so it is the right
  boundary to have reached first. But "NVDA can read this tree" and "NVDA says
  the right thing at the right moment" are different claims, and only the first
  is evidenced. What is missing is a run against NVDA with its speech captured
  (the `nvda_speech` log, or the NVDA Remote add-on), asserting that moving
  focus to the button announces "New Task button" rather than merely that the
  tree says so. **`docs/GUIDE.md` carries this as a checklist**, under *Not yet
  verified: a real screen reader*, because the individual checks are the work,
  and several of them (a value announced on focus, nothing announced twice) test
  claims this library has no other way to falsify.
- **Wire the Tk 9.1 native path.** `enable()` detects the `tk accessible`
  ensemble and defers to it, deliberately binding nothing and calling nothing,
  because those commands have never been run here or anywhere else. Turning
  `NATIVE` into "call Tk's own commands, so one API covers both eras" is the
  main outstanding piece of work, and it is blocked on Tk 9.1 being installable
  rather than on any open design question.
- **`bind_state_variable`, so that state stops being a write-once claim.**
  `set_acc_state` exists and works: measured, a `tk.Button(state=DISABLED)`
  reads back `IsEnabled=True` until it is called, and `False` afterwards. But
  it is a write and not a subscription, so nothing keeps it true. That is the
  same shape of hole `bind_text_variable` and `bind_value_variable` already
  fill, and the same fix: a `write` trace on the variable behind the widget,
  mapping its value onto `STATE_SYSTEM_*` bits. Deferred out of v0.2.1 because
  that release is bug fixes only. Worth knowing before starting it: **checked
  state needs none of this.** An annotated `Checkbutton` is a `CheckBoxControl`
  whose `ToggleState` is correct and follows its variable with no call to this
  package at all: measured `1`, then `0` after the application wrote the
  variable. The MSAA proxy derives that one for free, so the gap is narrower
  than it looks and is really about disabled, selected and read-only. Note that
  `describe(root)` reports a written state as the raw `STATE=1` integer rather
  than as `STATE_SYSTEM_UNAVAILABLE`: a bit-name table is a second source of
  truth for a property almost nobody sets, and it can wait for the binding.
- **`IAccPropServer` for dynamic properties.** Largely superseded: for UIA
  clients the provider *is* the pull model, answering names, values and state
  from the widget at the moment of the question. What an `IAccPropServer`
  would still buy is the same liveness for MSAA-only clients reading the
  annotated proxy, and it remains the right shape for a listbox or a treeview,
  whose contents are far too large to push on every change.

  **0.6.0 narrowed this without changing the model.** A widget that declared its
  own `-textvariable` is followed from `<Map>` onwards with no call at all, so a
  status line and a variable-driven entry are no longer things an application
  can forget to keep true, because the push happens on the write that changed
  them.
  What is left for a pull is the widget whose contents live somewhere it never
  named, and the compound widgets below.
- **Compound widgets, not just the HWND they live in.** A `Listbox` is annotated
  as a `LIST` and its *rows* are invisible; the same goes for `Treeview` rows and
  a `Menu`'s items. This is the last widget-level gap: as of 0.5.0 every widget
  class both toolkits ship has a role, and `COVERAGE.md` measures the result at
  17 of 18 classic widgets and 20 of 20 themed ones typed, named and queryable.
  What is left is what is *inside* them.
  Exposing them means child ids under one HWND: MSAA's `IAccessible` child
  model, which is a different piece of machinery from annotating a window
  handle. This is documented as a caveat in the README, because a user reads the
  shop window rather than the roadmap, and "your listbox is findable and its
  contents are not" is something to know before adopting rather than after.
  `describe(root)` names the affected widgets per path
  (`ITEMS_NOT_IN_THE_TREE`), which is the same information at the point where an
  author can act on it.

  **`Notebook` tabs came off this list in 0.4.0, and how is worth recording.**
  The assumption above, that reaching *any* compound widget's items needs the
  server, was not measured, and for tabs it was wrong. A tab is not a window,
  but nothing stops one being given a window: a `WS_EX_TRANSPARENT`,
  owner-drawn child positioned over the tab is a real HWND, so the annotation
  machinery already here applies unchanged, it paints nothing, and a click goes
  through it to Tk. That does not rescue rows and items: they scroll and there
  can be thousands of them, where a notebook has four, so the entry above
  stands. The lesson is narrower and worth keeping: "this needs a different
  mechanism" was a conclusion nobody had tried to falsify.

- **`infer_names_from_layout` should prefer the nearest caption by position.**
  It picks a row's subject by child order today, which misfires on a paginator
  built right-to-left: ttkbootstrap's `Page [entry] of [1]` row named the entry
  `of`.
  The rectangles are available (`winfo_x`/`winfo_y`); nearest-to-the-left, then
  nearest-above, is a strictly better rule. Until then the return value is the
  audit: the function reports every name it chose.
- **`python -m tk_uia app.py`.** The external verification ran three foreign
  applications through a thirty-line wrapper that patches `mainloop`, calls
  `enable()`, and `runpy`s the target. It worked unchanged on a stdlib module,
  a package `__main__`, and an IDE that re-enters its event loop, because
  `enable()` is idempotent. Shipping that wrapper would let a developer answer
  "what would this cost me" without editing a line, and it is the natural home
  for an `--infer-names` flag.

## Non-goals

These are deliberate, not oversights. Each is a decision that was made, and the
reason it was made.

- **Non-goal: activation through the MSAA proxy.** `InvokePattern` on the
  *proxy's* view of an owner-drawn Tk button returns cleanly and fires
  nothing: the proxy synthesises it from a posted `BM_CLICK`, and Tk does not
  listen for one. No amount of annotation changes that, which is why widgets
  answer UIA themselves instead, and why a widget the application leaves to
  the proxy is reported as carrying patterns that advertise and do nothing.
  A spec fails the day the proxy's behaviour changes.
- **Non-goal: annotating other processes.** `IAccPropServices` annotates the
  calling process's own windows. Reaching across does not raise. It silently
  does nothing, and can corrupt an annotation the other process made properly.
  `docs/GUIDE.md` documents the `SetWindowTextW` names-only rescue for
  applications you cannot modify, with that warning attached; it will not be
  wrapped in an API here, because an API is an invitation.
- **Non-goal: non-Windows platforms.** MSAA is a Windows API. `enable()` returns
  `UNSUPPORTED` off Windows so that cross-platform applications can call it
  unconditionally, and the whole unit suite runs there. But that exists to keep
  the design honest, not because an ATK port is planned. Linux accessibility for
  Tk is a different project with a differently shaped hole in the middle of it.
- **Non-goal: runtime dependencies.** Permanently empty, and that is a feature:
  this is installed inside somebody else's application, which must not inherit a
  test tool's dependency tree in order to make its buttons announceable. It also
  rules out `comtypes`, which has no bundled `IAccPropServices` anyway, and
  whose `GetModule("oleacc.dll")` writes generated code into `site-packages` on
  first run.
- **Non-goal: automatic AutomationIds.** `enable()` never assigns one. `GWLP_ID`
  is the control id Win32 puts in `WM_COMMAND.wParam` and `WM_DRAWITEM.idCtl`,
  and every Tk button is owner-drawn, so an id written over an existing one can
  stop a widget being painted. An id derived from a widget path would also make
  every repack a breaking change for whoever locates by it.
- **Non-goal: touching toplevels.** `wm title` already gives a window a correct
  accessible name, and overriding it breaks resolving a window by its title,
  which is where every other query starts.
