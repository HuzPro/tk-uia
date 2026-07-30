"""Behavioral spec for which widgets answer UIA for themselves, and when."""

from __future__ import annotations

from tests.doubles import (
    AnInvoke,
    FakeWidget,
    HeldPoster,
    RecordingPlatform,
    a_wiring_with,
)
from tests.threads import the_failure_raised_on_another_thread
from tk_uia.annotate import AnnotationRefused
from tk_uia.patterns import Pattern
from tk_uia.provide import Providers, WidgetWiring

_A_BUTTON_HANDLE = 0x000607B2
_A_LABEL_HANDLE = 0x000607B3
_A_MENU_HANDLE = 0x000607B4
_A_ROOT_HANDLE = 0x000607B0
_A_REBUILT_HANDLE = 0x000708C1


def a_wiring_for(poster: HeldPoster, invokes: dict[str, AnInvoke] | None = None):
    """A stand-in for the tkinter wiring layer, building from the fake widget."""

    def wiring(widget: FakeWidget) -> WidgetWiring:
        return a_wiring_with(
            widget, post=poster, invoke=(invokes or {}).get(str(widget))
        )

    return wiring


def test_a_widget_class_with_no_role_is_never_given_a_provider() -> None:
    # Given a widget class the role table has never heard of
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    stranger = FakeWidget("SomeMegaWidget", _A_LABEL_HANDLE)

    # When it is offered
    providers.attach(stranger)

    # Then nothing answers for it: a provider with no role would be a typed
    # claim about a widget this package knows nothing about
    assert platform.hosted == {}, (
        f"a roleless widget was given a provider: {platform.hosted}"
    )


def test_a_window_is_never_given_a_provider() -> None:
    # Given a toplevel, whose handle hosts Windows' own chain
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    root = FakeWidget("Tk", _A_ROOT_HANDLE)

    # When it is offered
    providers.attach(root)

    # Then it is left alone
    assert platform.hosted == {}, "a window was subclassed; wm title already names it"


def test_a_menu_is_never_given_a_provider() -> None:
    # Given a menu, which Tk posts as a window of its own and never maps
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    menu = FakeWidget("Menu", _A_MENU_HANDLE)

    # When it is offered
    providers.attach(menu)

    # Then it is left alone: menus are already accessible without this package
    assert platform.hosted == {}, f"a menu was given a provider: {platform.hosted}"


def test_attaching_a_button_hosts_a_blueprint_offering_exactly_the_invoke_pattern() -> (
    None
):
    # Given a button whose wiring can press it
    platform = RecordingPlatform()
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task", path=".!button")
    wiring_for = a_wiring_for(HeldPoster(), {".!button": AnInvoke()})
    providers = Providers(platform, wiring_for)

    # When it is attached
    providers.attach(button)

    # Then its handle answers with a blueprint carrying Invoke and nothing else
    blueprint = platform.hosted[_A_BUTTON_HANDLE]
    assert tuple(blueprint.patterns) == (Pattern.INVOKE,), (
        f"a button must offer exactly Invoke, not {tuple(blueprint.patterns)}"
    )


def test_attaching_the_same_widget_twice_hosts_it_once() -> None:
    # Given a button already answering for itself
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    providers.attach(button)
    hosted_the_first_time = dict(platform.hosted)

    # When `<Map>` fires again, as it does on every geometry shuffle
    providers.attach(button)

    # Then nothing is wired twice
    assert platform.hosted == hosted_the_first_time and platform.unhosted == [], (
        "a second <Map> re-wired a provider that was already answering"
    )


def test_a_widget_rebuilt_on_a_new_handle_is_hosted_again_on_its_next_map() -> None:
    # Given a button that was destroyed and rebuilt at the same Tk path
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    providers.attach(button)
    button.take_a_new_handle(_A_REBUILT_HANDLE)

    # When its next `<Map>` arrives
    providers.attach(button)

    # Then the abandoned handle is let go and the new one answers, so a
    # recycled handle never arrives wearing a dead widget's blueprint
    assert _A_BUTTON_HANDLE in platform.unhosted, (
        "the abandoned handle was never released, and Windows recycles handles"
    )
    assert _A_REBUILT_HANDLE in platform.hosted, (
        "the rebuilt widget never answered again after Tk rebuilt it"
    )


def test_attaching_from_a_foreign_thread_is_refused_before_anything_is_touched() -> (
    None
):
    # Given a provider layer owned by this thread
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When another thread reaches in
    failure = the_failure_raised_on_another_thread(lambda: providers.attach(button))

    # Then it is refused before Tk or the ledger hears anything
    assert isinstance(failure, AnnotationRefused), (
        f"a foreign thread got {type(failure).__name__} instead of a refusal"
    )
    assert platform.hosted == {}, "a foreign thread's attach still went through"


def test_leaving_a_widget_to_the_proxy_unhosts_it_and_map_does_not_bring_it_back() -> (
    None
):
    # Given a button answering for itself
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    providers.attach(button)

    # When the application asks for the proxy behaviour back
    providers.leave_to_the_proxy(button)

    # Then the provider comes off, and the next `<Map>` respects the choice
    assert _A_BUTTON_HANDLE in platform.unhosted, (
        "leave_to_the_proxy left the provider answering"
    )
    providers.attach(button)
    assert _A_BUTTON_HANDLE not in platform.hosted, (
        "the very next <Map> re-attached a provider the application refused"
    )


def test_forgetting_a_widget_clears_its_provider_bookkeeping() -> None:
    # Given a button answering for itself, then destroyed
    platform = RecordingPlatform()
    providers = Providers(platform, a_wiring_for(HeldPoster()))
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    providers.attach(button)

    # When the `<Destroy>` route lets go of the path
    providers.forget(str(button))

    # Then the ledger no longer claims patterns for it, and a rebuild at the
    # same path is free to answer again
    assert providers.ledger.patterns_on(str(button)) == (), (
        "a destroyed widget's path still claims the patterns it used to offer"
    )
    providers.attach(button)
    assert _A_BUTTON_HANDLE in platform.hosted, (
        "a rebuilt widget could not answer again after forget()"
    )
