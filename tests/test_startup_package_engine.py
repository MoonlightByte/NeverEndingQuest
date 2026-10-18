"""Starting packages: the engine fault cases (plan startup-package-gold r5, G4).

Real binaries and forwarding scripts only: apply.call and the transient
classifier are never patched (LN-F10, #151). Each Linux busy case records the
kernel release and the errno it observed; a kernel that raises no ETXTBSY makes
the case NOT-REACHED (skipped), never FAILED (AC-N13).
"""
import copy
import errno
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from test_startup_review_provenance import ROOT, wizard  # noqa: F401 (fixture)
from test_startup_package_gold import _bram, _weapon_rows

REAL = ROOT / "bin" / ("nql-apply.exe" if os.name == "nt" else "nql-apply")
GRANT = "startup:starting-packages"
ROWS = {"Scimitar", "Shortsword", "Longbow", "Unarmed Strike"}

pytestmark = pytest.mark.skipif(os.name == "nt", reason="the forwarding scripts are POSIX shell")


def _script(path, body):
    """A forwarding executable: reads the request into $input, then runs ``body``."""
    path.write_text("#!/bin/sh\ninput=$(cat)\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _forward(binary):
    return f'exec "{binary}" <<EOF_REQUEST\n$input\nEOF_REQUEST'


def _waits(wizard, monkeypatch, on_wait=None):
    """The status lines shown by the (c) wait (and the (d) rebuild), in order."""
    shown = []

    def record(message):
        shown.append(message)
        if on_wait is not None:
            on_wait(message)

    monkeypatch.setattr(wizard, "display_status", record)
    return shown


def _wait_lines(wizard, shown):
    return [m for m in shown if m.startswith(wizard.STARTUP_ENGINE_WAIT_TEXT)]


def _assert_d_without_engine(wizard, candidate, provenance, cause):
    sheet = candidate["character"]
    assert sheet["currency"] == {"gold": 0, "silver": 0, "copper": 0}
    assert sheet["equipment"] == [] and sheet["ammunition"] == [] and sheet["equipment_effects"] == []
    assert _weapon_rows(sheet) == []
    assert sheet["armorClass"] == 15  # the authored value stands, unchecked [OQ-3]
    facts = wizard._starting_gear_facts(candidate, provenance)["starting_packages"]
    assert facts == {"status": "engine_unavailable", "armor_class": "unchecked", "policy": "D-PKG-1"}
    packages = provenance["starting_packages"]
    assert (packages["status"], packages["policy"], packages["cause"]) == ("engine_unavailable", "D-PKG-1", cause)
    assert packages["exit"] is None


def _notice(wizard, provenance, kind):
    from core.nql import apply
    moves = (f"To play with them, make sure {apply.binary_path()} runs on this computer, reset the campaign, and "
             "create the character again; otherwise you can play on without them.")
    text = {
        "unavailable": f"The rules engine could not run, so Bram Holloway starts with no gold, no starting gear and "
                       f"no weapons. {moves}",
        "timeout": f"The rules engine did not answer in time, so Bram Holloway starts with no gold, no starting gear "
                   f"and no weapons. {moves}",
        "refused": "The rules engine refused the starting gear, so Bram Holloway starts with no gold, no starting gear "
                   "and no weapons. You can play on without them, or reset the campaign and create the character again.",
    }[kind]
    assert wizard._starting_gear_notice({"name": "Bram Holloway"}, provenance) == text


# ---- (d): the engine cannot run ------------------------------------------------

def test_g4_non_executable_file(wizard, monkeypatch, tmp_path):
    blocked = tmp_path / "nql-apply"
    blocked.write_bytes(REAL.read_bytes()[:64])  # not executable (mode 0644)
    monkeypatch.setenv("NQL_APPLY_BINARY", str(blocked))
    shown = _waits(wizard, monkeypatch)
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    _assert_d_without_engine(wizard, candidate, provenance, "unavailable")
    assert provenance["starting_packages"]["phase"] == "grant"
    assert _wait_lines(wizard, shown) == []
    _notice(wizard, provenance, "unavailable")


def test_g4_exit_2_with_2kb_stderr(wizard, monkeypatch, tmp_path, caplog):
    from core.nql import apply
    noise = "e" * 2048
    engine = _script(tmp_path / "nql-apply", f"printf '%s' '{noise}' >&2\nexit 2")
    monkeypatch.setenv("NQL_APPLY_BINARY", str(engine))
    with pytest.raises(apply.EngineUnavailable) as error:
        apply.call({})
    assert str(error.value).endswith(noise)  # NL-N1: not cut
    caplog.set_level("WARNING")
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    _assert_d_without_engine(wizard, candidate, provenance, "unavailable")
    # NL-N1: the starting_packages record carries no engine text (the existing engine_projection and
    # engine_rows reason strings are display text, as before).
    assert "eeee" not in json.dumps(provenance["starting_packages"])
    assert noise in caplog.text  # the whole of it in telemetry


def test_g4_binary_removed_after_the_grant(wizard, monkeypatch, tmp_path):
    engine = _script(tmp_path / "nql-apply", f'case "$input" in\n*{GRANT}*)\n'
                     f'  out=$("{REAL}" <<EOF_REQUEST\n$input\nEOF_REQUEST\n)\n'
                     '  rm -f "$0"\n  printf "%s" "$out"\n  exit 0;;\nesac\n' + _forward(REAL))
    monkeypatch.setenv("NQL_APPLY_BINARY", str(engine))
    shown = _waits(wizard, monkeypatch)
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    assert not engine.exists()
    _assert_d_without_engine(wizard, candidate, provenance, "unavailable")
    assert provenance["starting_packages"]["phase"] == "attack_rows"
    assert "Finishing your character without starting gear." in shown
    _notice(wizard, provenance, "unavailable")


def test_g4_no_items_at_view(wizard, monkeypatch, tmp_path):
    strip = f'"{sys.executable}" -c "import json,sys; r=json.load(sys.stdin); r.pop(\'items_at\', None); print(json.dumps(r))"'
    engine = _script(tmp_path / "nql-apply", f'case "$input" in\n*{GRANT}*)\n'
                     f'  "{REAL}" <<EOF_REQUEST | {strip}\n$input\nEOF_REQUEST\n  exit 0;;\nesac\n' + _forward(REAL))
    monkeypatch.setenv("NQL_APPLY_BINARY", str(engine))
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    sheet = candidate["character"]
    assert provenance["starting_packages"]["status"] == "engine_unavailable"
    assert provenance["starting_packages"]["phase"] == "grant"
    assert sheet["currency"]["gold"] == 0 and sheet["equipment"] == [] and sheet["ammunition"] == []


# ---- (d) while the engine runs: a refusal ------------------------------------------

def test_g4_attack_rows_refused_after_the_grant(wizard, monkeypatch, tmp_path):
    engine = _script(tmp_path / "nql-apply", 'case "$input" in\n*\'"attack_options"\'*)\n'
                     "  printf '%s' '{\"ok\": false, \"phase\": \"apply\"}'\n  exit 0;;\nesac\n" + _forward(REAL))
    monkeypatch.setenv("NQL_APPLY_BINARY", str(engine))
    shown = _waits(wizard, monkeypatch)
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    sheet = candidate["character"]
    packages = provenance["starting_packages"]
    assert (packages["status"], packages["phase"], packages["cause"]) == ("engine_unavailable", "attack_rows", "refused")
    assert sheet["currency"]["gold"] == 0 and sheet["equipment"] == [] and sheet["ammunition"] == []
    assert _weapon_rows(sheet) == []
    assert "Finishing your character without starting gear." in shown
    _notice(wizard, provenance, "refused")


def test_g4_grant_refused_with_a_working_engine(wizard, monkeypatch, tmp_path):
    engine = _script(tmp_path / "nql-apply", f'case "$input" in\n*{GRANT}*)\n'
                     "  printf '%s' '{\"ok\": false, \"phase\": \"apply\"}'\n  exit 0;;\nesac\n" + _forward(REAL))
    monkeypatch.setenv("NQL_APPLY_BINARY", str(engine))
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    sheet = candidate["character"]
    assert provenance["starting_packages"]["cause"] == "refused"
    assert sheet["currency"]["gold"] == 0 and sheet["equipment"] == []
    # SP-N6: the engine's unarmored AC and its Unarmed Strike row reach the sheet.
    projection = provenance["engine_projection"]
    unarmored = 10 + (sheet["abilities"]["dexterity"] - 10) // 2
    assert projection["applied"] is True and sheet["armorClass"] == projection["armorClass"] == unarmored
    assert [a["name"] for a in _weapon_rows(sheet)] == ["Unarmed Strike"]
    assert _weapon_rows(sheet)[0]["engine"] is True
    assert wizard._starting_gear_facts(candidate, provenance)["starting_packages"]["armor_class"] == unarmored
    _notice(wizard, provenance, "refused")


# ---- (c): the engine is busy ----------------------------------------------------

def _kernel(record_property):
    release = os.uname().release
    record_property("uname_r", release)
    return release


def _hold(path, seconds):
    """A writer holding ``path`` open for writing; returns once the fd is held."""
    holder = subprocess.Popen([sys.executable, "-c", (
        "import sys, time\n"
        "handle = open(sys.argv[1], 'ab')\n"
        "print('held', flush=True)\n"
        "time.sleep(float(sys.argv[2]))\n"), str(path), str(seconds)], stdout=subprocess.PIPE)
    assert holder.stdout.readline().strip() == b"held"
    return holder


def _busy_errno(path):
    """The errno exec of ``path`` raises now, or None."""
    try:
        subprocess.run([str(path)], input=b"{}", capture_output=True, timeout=10)
    except OSError as error:
        return error.errno
    return None


def _held_copy(tmp_path, record_property, seconds):
    copy_path = tmp_path / "nql-apply-copy"
    shutil.copy2(REAL, copy_path)
    release = _kernel(record_property)
    holder = _hold(copy_path, seconds)
    observed = _busy_errno(copy_path)
    record_property("errno", observed)
    if observed != errno.ETXTBSY:
        holder.kill()
        holder.wait()
        pytest.skip(f"NOT-REACHED: exec of a file held open for writing raised errno {observed}, "
                    f"not ETXTBSY, on kernel {release}")
    return copy_path, holder


def _etxtbsy_gate(wizard, monkeypatch, tmp_path, record_property):
    copy_path, holder = _held_copy(tmp_path, record_property, 3.5)
    monkeypatch.setenv("NQL_APPLY_BINARY", str(copy_path))
    shown = _waits(wizard, monkeypatch)
    try:
        candidate, provenance = wizard._prepare_startup_proposal(_bram())
    finally:
        holder.kill()
        holder.wait()
    assert len(_wait_lines(wizard, shown)) >= 1  # (c): waited and reissued
    assert wizard._startup_engine_timeouts.get("grant", 0) == 0  # not counted as a timeout
    assert provenance["starting_packages"]["status"] == "applied"
    assert candidate["character"]["currency"]["gold"] == 61


def test_g4_etxtbsy_copy_held_then_released(wizard, monkeypatch, tmp_path, record_property):
    _etxtbsy_gate(wizard, monkeypatch, tmp_path, record_property)


def test_mutant_engine_fault_counted(wizard, monkeypatch, tmp_path, record_property):
    real = wizard._startup_engine_fault

    def counted(fault, scope, call):
        outcome = real(fault, scope, call)
        if outcome is None and isinstance(getattr(fault, "__cause__", None), OSError):
            wizard._startup_engine_timeouts[call] = wizard._startup_engine_timeouts.get(call, 0) + 1
            if wizard._startup_engine_timeouts[call] >= wizard.STARTUP_ENGINE_TIMEOUT_LIMIT:
                return {"status": "engine_unavailable", "policy": "D-PKG-1", "phase": call, "exit": None,
                        "cause": "timeout"}
        return outcome

    monkeypatch.setattr(wizard, "_startup_engine_fault", counted)
    with pytest.raises(AssertionError):
        _etxtbsy_gate(wizard, monkeypatch, tmp_path, record_property)


def test_g4_windows_sharing_violation_waits():
    pytest.skip("NOT-REACHED: winerror 32 (a no-share open of the engine) needs a native Windows host "
                "(codex-ps native acceptance, NEQ-OPS-07); never stubbed")


HOLDER = """import sys, time
handle = open(sys.argv[1], "ab")
with open(sys.argv[2], "wb") as signal:
    signal.write(b"1")
time.sleep(float(sys.argv[3]))
"""


def test_g4_hold_on_the_attack_rows_call(wizard, monkeypatch, tmp_path, record_property):
    # AC-N12, AC-N15: the hold starts on the armor_class.project request (its typed explain of "defense"),
    # from inside the forwarding script, and is live when attack_rows execs the same script.
    release = _kernel(record_property)
    (tmp_path / "holder.py").write_text(HOLDER, encoding="utf-8")
    fifo = tmp_path / "held.fifo"
    os.mkfifo(fifo)
    engine = _script(tmp_path / "nql-apply", (
        f'case "$input" in\n*\'"stat": "defense"\'*)\n'
        f'  if [ ! -e "{tmp_path}/hold-started" ]; then\n'
        f'    : > "{tmp_path}/hold-started"\n'
        f'    "{sys.executable}" "{tmp_path}/holder.py" "$0" "{fifo}" 2.5 </dev/null >/dev/null 2>&1 &\n'
        f'    head -c 1 "{fifo}" >/dev/null\n'
        '  fi;;\nesac\n' + _forward(REAL)))
    monkeypatch.setenv("NQL_APPLY_BINARY", str(engine))
    shown = _waits(wizard, monkeypatch)
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    assert (tmp_path / "hold-started").exists()
    waits = _wait_lines(wizard, shown)
    record_property("waits", len(waits))
    if not waits:
        pytest.skip(f"NOT-REACHED: exec of a script held open for writing raised no ETXTBSY on kernel {release}")
    record_property("errno", errno.ETXTBSY)
    assert provenance["engine_projection"]["applied"] is True  # AC was projected before the hold
    assert wizard._startup_engine_timeouts.get("attack_rows", 0) == 0
    rows = provenance["engine_rows"]
    assert "reason" not in rows
    assert {name.split(" (")[0] for name in rows["written"]} == ROWS
    assert provenance["starting_packages"]["status"] == "applied"
    assert candidate["character"]["currency"]["gold"] == 61


def test_g4_superseded_scope_during_the_wait(wizard, monkeypatch, tmp_path, record_property):
    from utils.capture.live_provider_call import (LiveProviderSuperseded, finish_live_turn_scope,
                                                  open_live_turn_scope)
    copy_path, holder = _held_copy(tmp_path, record_property, 20)
    monkeypatch.setenv("NQL_APPLY_BINARY", str(copy_path))
    scope = open_live_turn_scope()
    _waits(wizard, monkeypatch, on_wait=lambda message: scope.request_supersession("quit"))
    started = time.monotonic()
    try:
        with pytest.raises(LiveProviderSuperseded):
            wizard._prepare_startup_proposal(_bram(), live_scope=scope)
        assert time.monotonic() - started < 10  # out of the wait, not after the hold
    finally:
        finish_live_turn_scope(scope)
        holder.kill()
        holder.wait()


# ---- (c'): a timeout --------------------------------------------------------------

def _timeout_error(tmp_path):
    from core.nql import apply
    sleeper = _script(tmp_path / "sleeper", "exec sleep 5")
    with pytest.raises(apply.EngineUnavailable) as error:
        apply.call({}, binary=str(sleeper), timeout=0.5)
    assert isinstance(error.value.__cause__, subprocess.TimeoutExpired)
    return error.value


def _escalation_check(wizard, tmp_path):
    fault = _timeout_error(tmp_path)
    wizard._startup_engine_timeouts.clear()
    assert wizard._startup_engine_fault(fault, None, "grant") is None  # the first reissues after the wait
    second = wizard._startup_engine_fault(fault, None, "grant")
    assert second == {"status": "engine_unavailable", "policy": "D-PKG-1", "phase": "grant", "exit": None,
                      "cause": "timeout"}


def test_c_prime_second_timeout_is_d(wizard, tmp_path):
    _escalation_check(wizard, tmp_path)


def test_mutant_timeout_never_escalates(wizard, monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "STARTUP_ENGINE_TIMEOUT_LIMIT", 10 ** 6)
    with pytest.raises(AssertionError):
        _escalation_check(wizard, tmp_path)


def test_a_busy_wait_between_timeouts_resets_the_count(wizard, tmp_path, record_property):
    # FF R6: D-PKG-5 counts consecutive timeouts of one call.
    from core.nql import apply
    timeout = _timeout_error(tmp_path)
    copy_path, holder = _held_copy(tmp_path, record_property, 5)
    try:
        with pytest.raises(apply.EngineUnavailable) as busy:
            apply.call({}, binary=str(copy_path))
    finally:
        holder.kill()
        holder.wait()
    wizard._startup_engine_timeouts.clear()
    assert wizard._startup_engine_fault(timeout, None, "grant") is None
    assert wizard._startup_engine_fault(busy.value, None, "grant") is None
    assert wizard._startup_engine_fault(timeout, None, "grant") is None
    assert wizard._startup_engine_fault(timeout, None, "attack_rows") is None  # counted per call


def test_g4_sleeping_engine_times_out_twice_then_d(wizard, monkeypatch, tmp_path):
    # Real deadline (apply.DEFAULT_TIMEOUT_SECONDS, 30 s) on the grant request only: about a minute.
    engine = _script(tmp_path / "nql-apply", f'case "$input" in\n*{GRANT}*)\n  exec sleep 45;;\nesac\n' + _forward(REAL))
    monkeypatch.setenv("NQL_APPLY_BINARY", str(engine))
    shown = _waits(wizard, monkeypatch)
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    packages = provenance["starting_packages"]
    assert (packages["status"], packages["phase"], packages["cause"]) == ("engine_unavailable", "grant", "timeout")
    assert len(_wait_lines(wizard, shown)) == 1  # (c') once, then (d)
    sheet = candidate["character"]
    assert sheet["currency"]["gold"] == 0 and sheet["equipment"] == [] and sheet["ammunition"] == []
    _notice(wizard, provenance, "timeout")


# ---- Level-up keeps its rows path (W9, LC-17) ---------------------------------------

def test_g4_level_up_refresh_rows_after_the_faults_keyword(wizard):
    from core.nql import armor_class, startup_rows
    candidate, _ = wizard._prepare_startup_proposal(_bram())
    sheet = copy.deepcopy(candidate["character"])
    stale = next(a for a in sheet["attacksAndSpellcasting"] if a.get("engine") is True and a["name"].startswith("Scimitar"))
    stale["attackBonus"] = 99
    report = startup_rows.refresh_rows(sheet, armor_class.PROJECTION_LOCATION)
    assert report["refreshed"] is True
    assert sheet["attacksAndSpellcasting"] == candidate["character"]["attacksAndSpellcasting"]
