"""Behavioral spec for what a provided widget answers a client, at the moment it asks."""

from __future__ import annotations

from tests.doubles import FakeWidget, HeldPoster, RecordingPlatform
from tk_uia.annotate import Ledger, PropId, Wrote
from tk_uia.provide import (
    Pattern,
    Providers,
    WidgetWiring,
)
from tk_uia.roles import Role

_A_BUTTON_HANDLE = 0x000707C2
_AN_ENTRY_HANDLE = 0x000707C3
_A_CHECK_HANDLE = 0x000707C4
_A_RADIO_HANDLE = 0x000707C5
_A_BAR_HANDLE = 0x000707C6

_BUTTON_CONTROL = 50000
_EDIT_CONTROL = 50004


class AToggle:
    def __init__(self) -> None:
        self.on = False

    def flip(self) -> None:
        self.on = not self.on

    def is_on(self) -> bool:
        return self.on


class AValue:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def read(self) -> str:
        return self.text

    def write(self, text: str) -> None:
        self.text = text

    def is_read_only(self) -> bool:
        return False


class ASelection:
    def __init__(self) -> None:
        self.selected = False

    def select(self) -> None:
        self.selected = True

    def is_selected(self) -> bool:
        return self.selected


class AReadOnlyRange:
    """A progressbar's numbers: readable, never writable."""

    write = None

    def now(self) -> float:
        return 40.0

    def low(self) -> float:
        return 0.0

    def high(self) -> float:
        return 100.0

    def step(self) -> float | None:
        return None

    def is_read_only(self) -> bool:
        return True


def _attached(
    widget: FakeWidget, platform: RecordingPlatform, said: Ledger, **wiring_fields
):
    fields = {
        "words": lambda: None,
        "is_enabled": lambda: True,
        "post": HeldPoster(),
        "still_there": widget.winfo_exists,
    }
    fields.update(wiring_fields)
    providers = Providers(platform, lambda _: WidgetWiring(**fields), said=said)
    providers.attach(widget)
    return platform.hosted[widget.winfo_id()]


def test_a_name_the_application_chose_outranks_the_words_the_widget_shows() -> None:
    # Given a button the application named by hand
    said = Ledger()
    said.record(_A_BUTTON_HANDLE, PropId.NAME, "Create a task", Wrote.SAID_ONCE)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    blueprint = _attached(button, RecordingPlatform(), said, words=lambda: "New Task")

    # When a client asks for its name
    # Then the application's word wins
    assert blueprint.name() == "Create a task", (
        "the words on the widget outranked the name the application chose"
    )


def test_a_name_the_package_only_inferred_never_outranks_what_the_widget_shows_now() -> (
    None
):
    # Given a button whose name was inferred at map time, and whose words have
    # since changed under a plain config(text=...)
    said = Ledger()
    said.record(_A_BUTTON_HANDLE, PropId.NAME, "New Task", Wrote.INFERRED)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="Save Task")
    blueprint = _attached(button, RecordingPlatform(), said, words=lambda: "Save Task")

    # When a client asks
    # Then it hears what the widget shows now, not the stale echo of map time
    assert blueprint.name() == "Save Task", (
        "the inferred echo from map time outranked the live words, which is "
        "the staleness the pull model exists to cure"
    )


def test_a_name_nobody_chose_is_read_off_the_widget_at_the_moment_a_client_asks() -> (
    None
):
    # Given a button nobody named, whose words keep changing
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="Step 1")
    blueprint = _attached(
        button, RecordingPlatform(), Ledger(), words=lambda: str(button.cget("text"))
    )

    # When the words change and a client asks again
    button.says_something_else("Step 2")

    # Then the answer is the moment's truth
    assert blueprint.name() == "Step 2", (
        "a client heard an old name; the pull happens at ask time or never"
    )


def test_a_role_the_application_chose_decides_the_control_type_a_client_is_told() -> (
    None
):
    # Given an entry the application re-roled into a button
    said = Ledger()
    said.record(_AN_ENTRY_HANDLE, PropId.ROLE, Role.PUSH_BUTTON.value, Wrote.SAID_ONCE)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    blueprint = _attached(entry, RecordingPlatform(), said)

    # When a client asks what kind of control it is
    # Then the chosen role decides, through the same table as the class role
    assert blueprint.control_type() == _BUTTON_CONTROL, (
        f"the class won over the application's chosen role: {blueprint.control_type()}"
    )


def test_a_widget_with_no_name_anywhere_answers_no_name_rather_than_an_invented_one() -> (
    None
):
    # Given an entry with no name from anyone
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    blueprint = _attached(entry, RecordingPlatform(), Ledger())

    # When a client asks
    # Then the honest answer is nothing
    assert blueprint.name() is None, f"a nameless widget invented {blueprint.name()!r}"
    assert blueprint.control_type() == _EDIT_CONTROL


def test_is_enabled_is_read_from_the_widget_at_the_moment_a_client_asks() -> None:
    # Given a button that gets disabled after it was attached
    truth = {"enabled": True}
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    blueprint = _attached(
        button, RecordingPlatform(), Ledger(), is_enabled=lambda: truth["enabled"]
    )

    # When the application disables it and a client asks
    truth["enabled"] = False

    # Then the answer is live, never a write-once claim
    assert blueprint.is_enabled() is False, (
        "IsEnabled answered from map time; state must be read when asked"
    )


def test_help_and_description_the_application_set_are_answered_to_a_client() -> None:
    # Given a button carrying chosen help and description
    said = Ledger()
    said.record(_A_BUTTON_HANDLE, PropId.HELP, "the help", Wrote.SAID_ONCE)
    said.record(
        _A_BUTTON_HANDLE, PropId.DESCRIPTION, "the description", Wrote.SAID_ONCE
    )
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    blueprint = _attached(button, RecordingPlatform(), said)

    # When a client asks
    # Then both writes still reach it in provider mode
    assert blueprint.help_text() == "the help", (
        "set_acc_help lost its effect the moment a provider answered"
    )
    assert blueprint.description() == "the description", (
        "set_acc_description lost its effect the moment a provider answered"
    )


def test_toggle_state_is_read_from_the_variable_behind_the_widget() -> None:
    # Given a checkbutton whose application flips its own variable
    toggle = AToggle()
    check = FakeWidget("Checkbutton", _A_CHECK_HANDLE, text="Notify")
    blueprint = _attached(check, RecordingPlatform(), Ledger(), toggle=toggle)

    # When the application flips it and a client asks
    toggle.flip()

    # Then the pattern answers the variable's truth
    assert blueprint.patterns[Pattern.TOGGLE].is_on() is True, (
        "ToggleState ignored the application writing its own variable"
    )


def test_a_radiobutton_answers_selection_item_and_never_toggle() -> None:
    # Given a radio, which can be selected but never cycled off
    radio = FakeWidget("Radiobutton", _A_RADIO_HANDLE, text="High")
    blueprint = _attached(radio, RecordingPlatform(), Ledger(), selection=ASelection())

    # When a client asks what it can do
    # Then it hears SelectionItem alone; Toggle on a radio promises an
    # interaction the widget cannot honour
    assert tuple(blueprint.patterns) == (Pattern.SELECTION_ITEM,), (
        f"a radio offered {tuple(blueprint.patterns)}"
    )


def test_a_progressbar_refuses_a_range_write_and_says_it_is_read_only() -> None:
    # Given a progressbar, whose numbers a client may read and never set
    bar = FakeWidget("TProgressbar", _A_BAR_HANDLE)
    blueprint = _attached(
        bar, RecordingPlatform(), Ledger(), range_value=AReadOnlyRange()
    )

    # When a client asks
    answers = blueprint.patterns[Pattern.RANGE_VALUE]

    # Then the numbers are there, the write is not, and it says so
    assert answers.now() == 40.0 and answers.is_read_only() is True, (
        "a progressbar's range must read back and declare itself read-only"
    )
    assert answers.write is None, (
        "a progressbar advertised a write it would have had to ignore"
    )


def test_the_invoke_on_offer_follows_the_command_the_widget_has_right_now() -> None:
    # Given a button whose command the application later takes away
    class AnInvoke:
        def __init__(self) -> None:
            self.command = "something to run"
            self.pressed = 0

        def press(self) -> None:
            self.pressed += 1

        def offered(self) -> bool:
            return bool(self.command)

    invoke = AnInvoke()
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    blueprint = _attached(button, RecordingPlatform(), Ledger(), invoke=invoke)

    # When the command is emptied and a client asks
    invoke.command = ""

    # Then Invoke stops being on offer rather than pressing nothing
    assert blueprint.patterns[Pattern.INVOKE].offered() is False, (
        "a button with no command still advertised an Invoke, which would "
        "return cleanly and do nothing"
    )


def test_the_ledger_tells_a_chosen_property_apart_from_an_inferred_echo() -> None:
    # Given one property said by the application and one merely inferred
    ledger = Ledger()
    ledger.record(_A_BUTTON_HANDLE, PropId.NAME, "inferred words", Wrote.INFERRED)
    ledger.record(_A_BUTTON_HANDLE, PropId.HELP, "chosen help", Wrote.SAID_ONCE)

    # When each is asked for as a choice
    # Then only the application's own word comes back
    assert ledger.chosen(_A_BUTTON_HANDLE, PropId.NAME) is None, (
        "an inferred write was handed back as if the application chose it"
    )
    assert ledger.chosen(_A_BUTTON_HANDLE, PropId.HELP) == "chosen help"


def test_a_value_the_application_said_is_carried_for_a_class_with_no_live_value() -> (
    None
):
    # Given a listbox, whose class has no value wiring of its own
    said = Ledger()
    listbox = FakeWidget("Listbox", _A_BAR_HANDLE)
    blueprint = _attached(listbox, RecordingPlatform(), said)

    # Then before the application says anything, there is no value to serve
    assert blueprint.value_the_application_said() is None, (
        "a value was invented for a widget nobody wrote one on"
    )

    # When the application says one, as set_acc_value does
    said.record(_A_BAR_HANDLE, PropId.VALUE, "Rust in production", Wrote.SAID_ONCE)

    # Then a client asking from now on is served it
    assert blueprint.value_the_application_said() == "Rust in production", (
        "set_acc_value never reached the answers a UIA client is given"
    )
