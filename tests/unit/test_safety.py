"""Test delle regole di sicurezza dei comandi a voce."""

from types import ModuleType, SimpleNamespace


def _state(entity_id: str, device_class: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=entity_id,
        domain=entity_id.split(".")[0],
        name=entity_id.split(".")[1],
        attributes={"device_class": device_class} if device_class else {},
    )


def test_locks_alarms_and_gates_are_never_controlled(safety: ModuleType) -> None:
    for state in (
        _state("lock.porta"),
        _state("alarm_control_panel.casa"),
        _state("cover.cancello", "gate"),
        _state("cover.box", "garage"),
    ):
        # Nemmeno dopo un sì.
        pending = {"c": {state.entity_id}}
        guard = safety.Guard(pending, "c", "sì")
        assert guard.check([state])["error"] == "not_allowed_by_voice"


def test_lights_pass(safety: ModuleType) -> None:
    guard = safety.Guard({}, "c", "accendi la luce")
    assert guard.check([_state("light.salotto")]) is None


def test_covers_and_valves_move_only_after_yes(safety: ModuleType) -> None:
    pending: dict[str, set[str]] = {}
    targets = [_state("cover.tapparella", "shutter"), _state("valve.giardino")]

    first = safety.Guard(pending, "c", "apri tapparella e acqua")
    assert first.check(targets)["error"] == "confirmation_required"
    # Il modello riprova nello stesso giro senza aver chiesto: niente.
    assert first.check(targets)["error"] == "confirmation_required"

    assert safety.Guard(pending, "c", "sì, vai").check(targets) is None
    # La conferma vale una volta sola.
    assert safety.Guard(pending, "c", "sì").check(targets) is not None


def test_no_or_other_conversation_does_not_confirm(safety: ModuleType) -> None:
    targets = [_state("valve.giardino")]
    for conversation_id, answer in (("c", "no, lascia stare"), ("altra", "sì")):
        pending: dict[str, set[str]] = {}
        safety.Guard(pending, "c", "apri l'acqua").check(targets)
        guard = safety.Guard(pending, conversation_id, answer)
        assert guard.check(targets) is not None


def test_answers(safety: ModuleType) -> None:
    assert safety.is_yes("Sì grazie")
    assert safety.is_yes("ok")
    assert not safety.is_yes("non si muove")
    assert not safety.is_yes("chiudi tutto")
    assert safety.is_read_only("HassGetState")
    assert safety.is_read_only("homeassistant__GetLiveContext")
    assert not safety.is_read_only("HassTurnOn")
