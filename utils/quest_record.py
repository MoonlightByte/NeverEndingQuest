# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Quests in the rules engine: the module plot's status record.

The engine (bin/nql-apply, NQL docs/QUESTS.md) keeps each quest's status and
a log of what happened to it, inside the same live_state document that holds
the occupants (core/nql/occupants.py). The host declares every plot point and
side quest of every installed module on every call, from the authored plot
(modules/<M>/module_plot_BU.json), and changes a quest only with typed
actions the DM emits as ``updatePlot``. module_plot.json is authored content
after the switch: play never writes it again.

Four parts:

- the declarations and the one-time conversion of a played plot, a port of
  NQL's reference tool (private/conversion/neq_quests.py, rules in
  QUEST_CONVERSION.md): same function names, same decisions, so the
  reference evidence compares line for line;
- the DM action: ``update_line`` maps updatePlot to one engine line, and
  ``apply_update`` sends it with the occupant ladder; a refusal goes back to
  the DM as a "Quest Error" correction;
- travel: ``prepare_travel_update`` / ``apply_travel_receipt`` stage an
  updatePlot behind a within-module travel (P4-g's pass-through);
- the reader adapter: ``module_plot(module)`` returns the module_plot.json
  shape with status and impact from the engine's quests view, so every
  reader of plot status keeps its code and reads the engine.
"""
import collections
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from utils.enhanced_logger import debug, info, warning
from utils.file_operations import safe_read_json, safe_write_json

MAX_OPS = 128
MAX_TEXT = 512
MAX_REQUIRES = 16

NOT_STARTED, IN_PROGRESS, COMPLETED = "not started", "in progress", "completed"

RULES = collections.OrderedDict([
    ("1", "not started: declared only"),
    ("2", "in progress: started"),
    ("3", "completed: completed"),
    ("3a", "completed with a requirement not completed: completed ahead"),
    ("4", "a status NEQ does not have: declared only"),
    ("5", "not in the played file: declared only"),
    ("6", "in the played file only: not converted"),
])

# The engine's status -> the plot file's status word.
ENGINE_STATUS = {"unstarted": NOT_STARTED, "started": IN_PROGRESS, "completed": COMPLETED, "failed": "failed"}
# Status words the DM may send, read case and space insensitive.
STATUSES = (IN_PROGRESS, COMPLETED, "failed", "reopened")

CONVERSION_REPORT = os.path.join("debug", "quest_conversion.json")


def q(text):
    """An NQL string: NQL strings are JSON strings."""
    return json.dumps(text)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def quest_id(module, ident):
    return "quest:%s/%s" % (module, ident)


def clean(text):
    """Agent text as the engine takes it: whitespace runs, line breaks
    included, become one space, and at most 512 bytes. Returns the text, or
    None when blank, and what was changed."""
    if not isinstance(text, str):
        return None, []
    out = " ".join(text.split())
    if not out:
        return None, []
    changes = []
    if out != text.strip():
        changes.append("whitespace collapsed")
    if len(out.encode("utf-8")) > MAX_TEXT:
        cut = out.encode("utf-8")[:MAX_TEXT - 3].decode("utf-8", "ignore").rstrip()
        changes.append("shortened from %d bytes" % len(out.encode("utf-8")))
        out = cut + "..."
    return out, changes


def entries(plot):
    """The plot points and their side quests, in file order, as
    (id, parent id or None, record)."""
    out = []
    points = plot.get("plotPoints") if isinstance(plot, dict) else None
    for p in points or []:
        if not isinstance(p, dict):
            continue
        out.append((p.get("id"), None, p))
        for s in p.get("sideQuests") or []:
            if isinstance(s, dict):
                out.append((s.get("id"), p.get("id"), s))
    return out


def status_of(record):
    s = record.get("status")
    return " ".join(s.lower().split()) if isinstance(s, str) else None


# Quests -------------------------------------------------------------------

class Quest:
    """One authored entry: its declaration and the decision for its played
    state."""

    def __init__(self, module, ident, parent, authored):
        self.module, self.ident, self.parent, self.authored = module, ident, parent, authored
        self.id = quest_id(module, ident)
        self.side_of = quest_id(module, parent) if parent else None
        name, changes = clean(authored.get("title"))
        self.name = name or ident
        self.notes = ["title: " + c for c in changes]
        if name is None:
            self.notes.append("no title: named by its ID")
        self.requires = []
        self.played = None
        self.rule = None
        self.action = None
        self.final = "unstarted"
        self.impact = None
        self.ahead = []

    def declaration(self):
        body = ["requires %s;" % q(r) for r in self.requires]
        if self.side_of:
            body.append("side of %s;" % q(self.side_of))
        if not body:
            return "quest %s named %s;" % (q(self.id), q(self.name))
        return "quest %s named %s { %s }" % (q(self.id), q(self.name), " ".join(body))

    def row(self):
        return {"id": self.id, "neq": self.ident, "name": self.name, "played": status_of(self.played) if self.played else None,
                "rule": self.rule, "action": self.action, "ahead": self.ahead, "notes": self.notes}


def declare(module, authored, notes):
    """Every entry of an authored plot, with requirements from nextPoints
    (a point requires the points that name it) and prerequisites. A
    requirement that would close a cycle, name an unknown entry or pass the
    engine's 16 is left out and noted."""
    quests = collections.OrderedDict()
    for ident, parent, record in entries(authored):
        if not isinstance(ident, str) or not ident.strip():
            notes.append(("declare", "%s: an entry without an ID is skipped" % module))
            continue
        if ident in quests:
            notes.append(("declare", "%s: %s is declared twice; the first is kept" % (module, ident)))
            continue
        quests[ident] = Quest(module, ident, parent, record)
        if parent is not None and parent not in quests:
            quests[ident].side_of = None
            quests[ident].notes.append("its plot point is not declared: no side of")
    wants = collections.defaultdict(list)
    for ident, quest in quests.items():
        record = quest.authored
        for nxt in record.get("nextPoints") or []:
            if nxt not in quests:
                quest.notes.append("next point %s is not declared" % nxt)
            elif nxt != ident:
                wants[nxt].append(ident)
        for pre in record.get("prerequisites") or []:
            if pre not in quests:
                quest.notes.append("prerequisite %s is not declared" % pre)
            elif pre != ident:
                wants[ident].append(pre)
    for ident, quest in quests.items():
        reqs = sorted(set(wants[ident]))
        if len(reqs) > MAX_REQUIRES:
            quest.notes.append("%d requirements; the first 16 by ID are kept" % len(reqs))
            reqs = reqs[:MAX_REQUIRES]
        quest.requires = [quest_id(module, r) for r in reqs]
    # Depth-first in ID order, as the engine checks: a requirement still on
    # the path would close a cycle, and is left out.
    by_id = {quest.id: quest for quest in quests.values()}
    state = {}

    def visit(quest):
        state[quest.id] = "path"
        for r in list(quest.requires):
            if state.get(r) == "path":
                quest.requires.remove(r)
                quest.notes.append("requirement %s closes a cycle; left out" % r.rsplit("/", 1)[1])
            elif r not in state:
                visit(by_id[r])
        state[quest.id] = "done"

    for qid in sorted(by_id):
        if qid not in state:
            visit(by_id[qid])
    return quests


def decide(module, quests, played):
    """The decision for each quest from its played entry. Returns the
    played entries that are not authored, and the actions."""
    seen = {}
    extra = []
    for ident, _, record in entries(played):
        if ident in seen:
            continue
        seen[ident] = record
        if ident not in quests:
            extra.append({"module": module, "neq": ident, "status": status_of(record), "rule": "6",
                          "title": record.get("title")})
    for ident, quest in quests.items():
        record = seen.get(ident)
        quest.played = record
        if record is None:
            quest.rule = "5"
            continue
        status = status_of(record)
        impact, changes = clean(record.get("plotImpact"))
        authored, _ = clean(quest.authored.get("plotImpact"))
        if impact is not None and impact == authored:
            # The authored impact is a design note: never play state.
            if status in (IN_PROGRESS, COMPLETED):
                quest.notes.append("impact is the authored note: not converted")
            impact, changes = None, []
        if status == NOT_STARTED:
            quest.rule = "1"
            if impact is not None:
                quest.notes.append("impact on a quest not started: not converted")
        elif status == IN_PROGRESS:
            quest.rule = "2"
            quest.action = "start quest %s%s;" % (q(quest.id), "" if impact is None else " impact %s" % q(impact))
            quest.final = "started"
            quest.notes += ["impact: " + c for c in changes]
        elif status == COMPLETED:
            quest.rule = "3"
            quest.impact = impact
            quest.final = "completed"
            quest.notes += ["impact: " + c for c in changes]
        else:
            quest.rule = "4"
            quest.notes.append("status %r" % record.get("status"))
    # Completions in requirement order: a requirement that ends completed is
    # completed first, and one that does not leaves the quest ahead of it.
    by_id = {quest.id: quest for quest in quests.values()}
    order, done = [], set()

    def place(quest):
        if quest.id in done:
            return
        done.add(quest.id)
        for r in quest.requires:
            place(by_id[r])
        order.append(quest)

    for quest in quests.values():
        place(quest)
    for quest in order:
        if quest.rule != "3":
            continue
        open_ = [by_id[r] for r in quest.requires if by_id[r].final != "completed"]
        text = "" if quest.impact is None else " impact %s" % q(quest.impact)
        if open_:
            quest.rule = "3a"
            quest.ahead = [o.id for o in open_]
            names = [o.ident for o in open_]
            listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
            reason = "converted: %s %s not completed in the played file" % (listed, "was" if len(names) == 1 else "were")
            quest.action = "complete quest %s ahead because %s%s;" % (q(quest.id), q(reason), text)
        else:
            quest.action = "complete quest %s%s;" % (q(quest.id), text)
    starts = [quest.action for quest in quests.values() if quest.rule == "2"]
    completes = [quest.action for quest in order if quest.rule in ("3", "3a")]
    return extra, starts + completes


# The game's files ---------------------------------------------------------

def _plot_paths(root, module):
    base = os.path.join(root, "modules", module)
    return os.path.join(base, "module_plot_BU.json"), os.path.join(base, "module_plot.json")


def authored_plot(root, module, notes=None):
    """The authored plot: the BU file, or the played file with its statuses
    ignored when a module has no BU file (noted)."""
    bu, played = _plot_paths(root, module)
    if os.path.exists(bu):
        try:
            data = load(bu)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError) as exc:
            if notes is not None:
                notes.append(("declare", "%s: module_plot_BU.json unreadable (%s); the played file declares" % (module, exc)))
    if os.path.exists(played):
        try:
            data = load(played)
            if isinstance(data, dict):
                if notes is not None:
                    notes.append(("declare", "%s: no authored plot (module_plot_BU.json); declared from the played file" % module))
                return data
        except (OSError, ValueError):
            pass
    return {}


def played_plot(root, module):
    _, played = _plot_paths(root, module)
    if not os.path.exists(played):
        return {}
    try:
        data = load(played)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def declarations(root, modules):
    """(quests, notes): every quest of these modules, in module order, as
    the world source declares them."""
    notes: List[Tuple[str, str]] = []
    quests: List[Quest] = []
    for m in modules:
        quests += list(declare(m, authored_plot(root, m, notes), notes).values())
    return quests, notes


def declaration_lines(root, modules):
    return [x.declaration() for x in declarations(root, modules)[0]]


def conversion(root, modules):
    """(quests, extra, actions, notes): the typed actions that bring the
    quests to the game as played, from module_plot.json."""
    notes: List[Tuple[str, str]] = []
    quests: List[Quest] = []
    extra: List[Dict[str, Any]] = []
    actions: List[str] = []
    for m in modules:
        declared = declare(m, authored_plot(root, m, notes), notes)
        more, acts = decide(m, declared, played_plot(root, m))
        quests += list(declared.values())
        extra += more
        actions += acts
    return quests, extra, actions, notes


def conversion_requests(actions):
    """The actions in requests of at most 128 operations: [(id, text)]."""
    return [("quest-conversion:%d" % (i // MAX_OPS + 1), "\n".join(actions[i:i + MAX_OPS]))
            for i in range(0, len(actions), MAX_OPS)]


def write_conversion_report(root, quests, extra, notes, requests, outcome):
    """debug/quest_conversion.json: every decision with its rule and notes."""
    path = os.path.join(root, CONVERSION_REPORT)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    report = {
        "outcome": outcome,
        "requests": [{"id": rid, "actions": text} for rid, text in requests],
        "quests": [x.row() for x in quests],
        "not_converted": extra,
        "notes": ["%s: %s" % n for n in notes],
    }
    if not safe_write_json(path, report):
        warning("QUESTS: the conversion report could not be written to %s" % path, category="plot_updates")


def carry_actions(document):
    """The actions that replay a document's quest logs on a new document
    (D3: a set-aside document carries its quests). Quests in requirement
    order (a requirement before the quest that needs it), each log in its
    order; a completion is sent ahead only of requirements the replay has
    not completed by then."""
    quests = [x for x in (document or {}).get("quests") or [] if isinstance(x, dict) and x.get("log")]
    by_id = {x.get("id"): x for x in quests}
    requires = {}
    for x in quests:
        last = [e for e in x.get("log") or [] if isinstance(e, dict) and e.get("ahead")]
        requires[x["id"]] = list(last[-1].get("ahead") or []) if last else []
    order, done = [], set()

    def place(qid):
        if qid in done:
            return
        done.add(qid)
        for r in requires.get(qid) or []:
            if r in by_id:
                place(r)
        order.append(qid)

    for qid in sorted(by_id):
        place(qid)
    state: Dict[str, str] = {}
    actions = []
    for qid in order:
        for e in by_id[qid].get("log") or []:
            kind = e.get("kind")
            text = e.get("text") if isinstance(e.get("text"), str) and e.get("text") else None
            reason = e.get("reason") if isinstance(e.get("reason"), str) and e.get("reason") else None
            impact = "" if text is None else " impact %s" % q(text)
            if kind == "started":
                actions.append("start quest %s%s;" % (q(qid), impact))
                state[qid] = "started"
            elif kind == "note":
                if text is not None:
                    actions.append("note quest %s impact %s;" % (q(qid), q(text)))
            elif kind == "completed":
                open_ = [r for r in (e.get("ahead") or []) if state.get(r) != "completed"]
                if open_ and reason:
                    actions.append("complete quest %s ahead because %s%s;" % (q(qid), q(reason), impact))
                else:
                    actions.append("complete quest %s%s;" % (q(qid), impact))
                state[qid] = "completed"
            elif kind == "failed":
                actions.append("fail quest %s%s;" % (q(qid), impact))
                state[qid] = "failed"
            elif kind == "reopened":
                actions.append("reopen quest %s because %s;" % (q(qid), q(reason or "carried from the previous record")))
                state[qid] = "started"
    return actions


# The engine's view --------------------------------------------------------

_VIEW_CACHE: Dict[Tuple[str, str], Tuple[Any, Dict[str, Dict[str, Any]]]] = {}
_FALLBACK_LOGGED: set = set()


def _ids(root, module):
    try:
        return [x.id for x in declarations(root, [module])[0]]
    except Exception as exc:  # fail forward
        warning("QUESTS: could not declare %s (%s)" % (module, exc), category="plot_updates")
        return []


def quest_view(module, *, root=".", create=False) -> Optional[Dict[str, Dict[str, Any]]]:
    """{ident: engine record} for every quest of the module, from one engine
    call, cached until the document changes. None when the engine is
    unavailable or no document exists (a reader never creates it)."""
    from core.nql import occupants
    module = (module or "").replace(" ", "_")
    if not module:
        return None
    key = (os.path.abspath(root), module)
    if not create and not os.path.exists(occupants.document_path(root)):
        return None  # before the first DM turn: nothing to read, nothing to make
    stamp = occupants._stamp(root)
    hit = _VIEW_CACHE.get(key)
    if hit and stamp is not None and hit[0] == stamp:
        return hit[1]
    ids = _ids(root, module)
    if not ids:
        return None
    try:
        response = occupants.request(quests=tuple(ids), root=root, create=create)
    except Exception as exc:  # fail forward
        warning("QUESTS: view of %s unavailable (%s)" % (module, exc), category="plot_updates")
        return None
    if not response or not response.get("ok"):
        return None
    out: Dict[str, Dict[str, Any]] = {}
    prefix = "quest:%s/" % module
    for record in response.get("quests") or []:
        qid = str(record.get("id") or "")
        if qid.startswith(prefix):
            out[qid[len(prefix):]] = record
    _VIEW_CACHE[key] = (occupants._stamp(root), out)
    return out


def _short(qid):
    return str(qid).rsplit("/", 1)[-1]


def _overlay(record, view_record, authored_impact):
    """The plot entry with the engine's status and the newest impact."""
    log = [e for e in view_record.get("log") or [] if isinstance(e, dict)]
    record["status"] = ENGINE_STATUS.get(str(view_record.get("status")), str(view_record.get("status")))
    texts = [e.get("text") for e in log if isinstance(e.get("text"), str) and e.get("text")]
    if texts:
        record["plotImpact"] = texts[-1]
    elif log:
        record["plotImpact"] = ""
    else:
        record["plotImpact"] = authored_impact if isinstance(authored_impact, str) else ""
    record["requires"] = [_short(r) for r in view_record.get("requires") or []]
    record["open"] = [_short(r) for r in view_record.get("open") or []]
    record["ready"] = bool(view_record.get("ready"))
    # The engine's log, as it happened (#544: the journal summarizes this,
    # not the authored description).
    record["log"] = [
        {"kind": str(e.get("kind") or ""), "text": e.get("text") or "",
         "ahead": [_short(r) for r in e.get("ahead") or []], "reason": e.get("reason") or ""}
        for e in log
    ]
    record["bypassed"] = False
    record["bypassedBy"] = []
    ahead = [e for e in log if e.get("kind") == "completed" and e.get("ahead")]
    if ahead:
        record["aheadOf"] = [_short(r) for r in ahead[-1].get("ahead") or []]
        record["aheadReason"] = ahead[-1].get("reason") or ""
    else:
        record.pop("aheadOf", None)
        record.pop("aheadReason", None)
    return record


def _mark_bypassed(plot):
    """#544: a quest is bypassed while it is not started and a completed
    quest's ahead list names it (the party finished later work by another
    route). Started later, it is an active quest again. Readers leave a
    bypassed quest out of the objectives and the completion checks count it
    as closed."""
    entries_ = []
    for point in plot.get("plotPoints") or []:
        if isinstance(point, dict):
            entries_.append(point)
            entries_ += [sq for sq in point.get("sideQuests") or [] if isinstance(sq, dict)]
    by_id = {e.get("id"): e for e in entries_}
    for e in entries_:
        if e.get("status") != "completed":
            continue
        for entry in e.get("log") or []:
            if entry.get("kind") != "completed":
                continue
            for skipped in entry.get("ahead") or []:
                target = by_id.get(skipped)
                if target is not None and target.get("status") == NOT_STARTED and "bypassed" in target:
                    target["bypassed"] = True
                    if e.get("id") not in target["bypassedBy"]:
                        target["bypassedBy"].append(e.get("id"))


def is_closed(record) -> bool:
    """Completed, failed, or bypassed: nothing left for the party to do."""
    return isinstance(record, dict) and (
        record.get("status") in (COMPLETED, "failed") or bool(record.get("bypassed")))


def module_plot(module, *, root=".") -> Optional[Dict[str, Any]]:
    """The module_plot.json shape for readers: authored text from the file,
    status and impact from the engine's quests view (plus requires, open,
    ready, aheadOf, aheadReason). Without a document or engine: the file as
    it is, logged once per process."""
    module = (module or "").replace(" ", "_")
    data = played_plot(root, module)
    if not data:
        return None
    view = quest_view(module, root=root)
    if view is None:
        # No document yet (before the first DM turn) is silent: the headless
        # `state` command prints its snapshot on stdout. An engine that
        # cannot answer while a document exists is logged once per process.
        key = (os.path.abspath(root), module)
        if key not in _FALLBACK_LOGGED and os.path.exists(os.path.join(root, "live_state.json")):
            _FALLBACK_LOGGED.add(key)
            warning("QUESTS: the engine's quest record for %s could not be read; plot status "
                    "read from module_plot.json" % module, category="plot_updates")
        return data
    for point in data.get("plotPoints") or []:
        if not isinstance(point, dict):
            continue
        record = view.get(point.get("id"))
        if record is not None:
            _overlay(point, record, point.get("plotImpact"))
        for sq in point.get("sideQuests") or []:
            if isinstance(sq, dict) and view.get(sq.get("id")) is not None:
                _overlay(sq, view[sq.get("id")], sq.get("plotImpact"))
    _mark_bypassed(data)
    return data


def plot_digest(plot_data) -> str:
    """The digest of what the readers see: the adapter's JSON, sorted keys."""
    import hashlib
    return hashlib.sha256(json.dumps(plot_data, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


# The DM action ------------------------------------------------------------

def _status_word(value):
    return " ".join(str(value or "").lower().split())


def _titles(module, root):
    out = {}
    for ident, _, record in entries(authored_plot(root, module)):
        if isinstance(ident, str):
            out[ident] = record.get("title") or ident
    return out


def _quest_list(module, view, root):
    titles = _titles(module, root)
    parts = []
    for ident, title in titles.items():
        status = ENGINE_STATUS.get(str((view or {}).get(ident, {}).get("status")), NOT_STARTED)
        parts.append("%s (%s) [%s]" % (ident, title, status))
    return ", ".join(parts) or "none"


def update_line(module, parameters, view, *, root=".") -> Dict[str, Any]:
    """Map one updatePlot to an engine line. Returns {"line", "reason",
    "guidance", "ident", "status", "notes"}: a line when the action is
    allowed locally, else the refusal's reason and guidance."""
    p = parameters if isinstance(parameters, dict) else {}
    ident = str(p.get("plotPointId") or "").strip()
    status = _status_word(p.get("newStatus"))
    impact, impact_notes = clean(p.get("plotImpact"))
    ahead_reason, reason_notes = clean(p.get("aheadReason"))
    notes = ["plotImpact: " + c for c in impact_notes] + ["aheadReason: " + c for c in reason_notes]
    out: Dict[str, Any] = {"line": None, "reason": None, "guidance": None, "ident": ident,
                           "status": status, "notes": notes}
    known = view if view is not None else {}
    titles = _titles(module, root)
    if not ident or ident not in titles:
        out["reason"] = "%s is not a quest of %s" % (ident or "(no plotPointId)", module)
        out["guidance"] = "Quest ids here: %s." % _quest_list(module, view, root)
        return out
    qid = quest_id(module, ident)
    now = str(known.get(ident, {}).get("status") or "unstarted")
    text = "" if impact is None else " impact %s" % q(impact)
    if status == IN_PROGRESS:
        if now == "started":
            if impact is None:
                out["line"] = ""  # nothing to record: applied
            else:
                out["line"] = "note quest %s impact %s;" % (q(qid), q(impact))
        elif now == "unstarted":
            out["line"] = "start quest %s%s;" % (q(qid), text)
        else:
            out["line"] = "start quest %s%s;" % (q(qid), text)  # the engine answers E_QUEST status
    elif status == COMPLETED:
        if ahead_reason is not None:
            out["line"] = "complete quest %s ahead because %s%s;" % (q(qid), q(ahead_reason), text)
        else:
            out["line"] = "complete quest %s%s;" % (q(qid), text)
    elif status == "failed":
        out["line"] = "fail quest %s%s;" % (q(qid), text)
    elif status == "reopened":
        if impact is None:
            out["reason"] = '"reopened" needs plotImpact saying why'
            out["guidance"] = ""
            return out
        out["line"] = "reopen quest %s because %s;" % (q(qid), q(impact))
    elif status == NOT_STARTED:
        out["reason"] = "a quest never goes back to not started"
        out["guidance"] = 'Use "failed" or "reopened" if that is what happened.'
    else:
        out["reason"] = "newStatus %r is not one of %s" % (str(p.get("newStatus")), ", ".join('"%s"' % s for s in STATUSES))
        out["guidance"] = 'Use "in progress", "completed", "failed" or "reopened".'
    return out


def correction(ident, reason, guidance) -> str:
    """The message that sends a refused updatePlot back to the DM."""
    return (
        "Quest Error: updatePlot for %s was refused: %s. Nothing changed in the quest record. "
        "%sLater actions from this response have not executed. Do not repeat earlier completed "
        "actions; issue the action again with an id and status the record allows, or narrate "
        "without it." % (ident or "(no plotPointId)", reason, (guidance + " ") if guidance else "")
    )


def _engine_refusal(module, fault, view, root):
    """(reason, guidance) for an E_QUEST / E_REFERENCE refusal."""
    field = str(fault.get("field") or "")
    actual = str(fault.get("actual") or "")
    code = str(fault.get("code") or "")
    titles = _titles(module, root)
    if code == "E_REFERENCE":
        return ("%s is not a quest of %s" % (_short(fault.get("subject") or ""), module),
                "Quest ids here: %s." % _quest_list(module, view, root))
    if field == "requires":
        open_ = [a.strip() for a in actual.split(",") if a.strip()]
        listed = ", ".join("%s (%s)" % (_short(r), titles.get(_short(r), _short(r))) for r in open_)
        return ("its requirements are not completed: %s" % listed,
                'Complete them first in the same response only if the story has actually done them. '
                'If the party finished this one without them (out of order, or by another route that '
                'bypassed them), send "completed" again with "aheadReason" saying how. Never complete '
                'a quest the party did not do.')
    if field == "ahead":
        return ("aheadReason was given but no requirement is open", 'Send "completed" without aheadReason.')
    if field == "status":
        return ("it is %s" % ENGINE_STATUS.get(actual, actual),
                'A completed or failed quest comes back only with "reopened" and a plotImpact saying why.')
    if field == "log":
        return ("its log is full of status changes", "Narrate without changing it.")
    message = str(fault.get("message") or "the engine refused it")
    return (message, "")


def apply_update(parameters, request_id, module, *, root=".") -> Dict[str, Any]:
    """Send one updatePlot to the engine. Returns {"ok": bool, "outcome":
    applied | historical | no_change | refused | unavailable, "correction":
    text or None, "ident": id}. A refusal is a correction for the DM; an
    unavailable engine is logged and the turn goes on (nothing is written to
    module_plot.json)."""
    from core.nql import occupants
    module = (module or "").replace(" ", "_")
    p = parameters if isinstance(parameters, dict) else {}
    ident = str(p.get("plotPointId") or "").strip()
    try:
        view = quest_view(module, root=root, create=True)
        mapped = update_line(module, p, view, root=root)
        for note in mapped["notes"]:
            info("QUESTS: updatePlot %s: %s" % (ident, note), category="plot_updates")
        if mapped["line"] is None:
            warning("QUESTS: updatePlot %s refused locally: %s" % (ident, mapped["reason"]), category="plot_updates")
            return {"ok": False, "outcome": "refused", "ident": ident,
                    "correction": correction(ident, mapped["reason"], mapped["guidance"])}
        if mapped["line"] == "":
            info("QUESTS: updatePlot %s: in progress with no impact on a started quest; nothing to record"
                 % ident, category="plot_updates")
            return {"ok": True, "outcome": "no_change", "ident": ident, "correction": None}
        response = occupants.request(mapped["line"], request_id, root=root)
        if response is None:
            warning("QUESTS: quest_unavailable: updatePlot %s %s not recorded (engine unavailable): %s"
                    % (ident, mapped["status"], mapped["line"]), category="plot_updates")
            return {"ok": False, "outcome": "unavailable", "ident": ident, "correction": None}
        if response.get("ok"):
            if response.get("historical"):
                debug("QUESTS: %s already applied" % request_id, category="plot_updates")
                return {"ok": True, "outcome": "historical", "ident": ident, "correction": None}
            info("QUESTS: %s applied: %s" % (request_id, mapped["line"]), category="plot_updates")
            return {"ok": True, "outcome": "applied", "ident": ident, "correction": None}
        fault = response.get("fault") or {}
        if fault.get("code") == "E_NO_CHANGE":
            info("QUESTS: %s changes nothing (%s); taken as applied" % (request_id, mapped["line"]),
                 category="plot_updates")
            return {"ok": True, "outcome": "no_change", "ident": ident, "correction": None}
        reason, guidance = _engine_refusal(module, fault, view, root)
        warning("QUESTS: %s refused: %s (%s)" % (request_id, reason, mapped["line"]), category="plot_updates")
        return {"ok": False, "outcome": "refused", "ident": ident, "correction": correction(ident, reason, guidance)}
    except Exception as exc:  # fail forward
        warning("QUESTS: updatePlot %s skipped (%s)" % (ident, exc), category="plot_updates")
        return {"ok": False, "outcome": "unavailable", "ident": ident, "correction": None}


# Travel -------------------------------------------------------------------

def prepare_travel_update(parameters, request_id, module, *, root=".") -> Dict[str, Any]:
    """The receipt for an updatePlot staged behind a within-module travel:
    the local checks run before movement; a local refusal is recorded and
    never stops travel. The outcome lives under "quest_status" (prepared |
    refused | committed | attempted_unavailable): the checkpoint owns the
    receipt's "status" field."""
    module = (module or "").replace(" ", "_")
    p = parameters if isinstance(parameters, dict) else {}
    receipt: Dict[str, Any] = {
        "kind": "updatePlot", "module": module, "quest_id": None, "ident": str(p.get("plotPointId") or "").strip(),
        "line": None, "request_id": request_id, "quest_status": "refused", "reason": None,
    }
    try:
        view = quest_view(module, root=root)
        mapped = update_line(module, p, view, root=root)
        if mapped["line"] is None:
            receipt["reason"] = mapped["reason"]
            return receipt
        receipt["quest_id"] = quest_id(module, mapped["ident"])
        receipt["line"] = mapped["line"]
        receipt["quest_status"] = "prepared"
        return receipt
    except Exception as exc:  # fail forward
        warning("QUESTS: travel updatePlot skipped (%s)" % exc, category="plot_updates")
        receipt["reason"] = "could not be prepared (%s)" % exc
        return receipt


def receipt_from_legacy(receipt, request_id, *, root=".") -> Dict[str, Any]:
    """A checkpoint written before the switch holds a T077 receipt ({kind,
    module, target_id, before, after}); it resolves by mapping after.status
    and after.plotImpact to the engine line."""
    after = receipt.get("after") if isinstance(receipt.get("after"), dict) else {}
    return prepare_travel_update(
        {"plotPointId": receipt.get("target_id"), "newStatus": after.get("status"),
         "plotImpact": after.get("plotImpact")},
        request_id, str(receipt.get("module") or ""), root=root)


def apply_travel_receipt(receipt, *, root=".") -> str:
    """Apply a prepared travel receipt after arrival: "committed" (applied,
    already on record under the same request id, or nothing to record),
    "refused" (the engine's reason kept) or "attempted_unavailable". None
    of them blocks arrival; the caller writes the checkpoint."""
    from core.nql import occupants
    if receipt.get("quest_status") in ("committed", "refused", "attempted_unavailable"):
        return str(receipt["quest_status"])
    line = receipt.get("line")
    request_id = str(receipt.get("request_id") or "")
    if line == "":
        receipt["quest_status"] = "committed"
        return "committed"
    if not line or not request_id:
        receipt["quest_status"] = "refused"
        receipt["reason"] = receipt.get("reason") or "no engine line was prepared"
        return "refused"
    try:
        response = occupants.request(line, request_id, root=root)
    except Exception as exc:  # fail forward
        warning("QUESTS: travel updatePlot skipped (%s)" % exc, category="plot_updates")
        response = None
    if response is None:
        receipt["quest_status"] = "attempted_unavailable"
        warning("QUESTS: quest_unavailable: travel updatePlot %s not recorded (engine unavailable): %s"
                % (request_id, line), category="plot_updates")
        return "attempted_unavailable"
    fault = response.get("fault") or {}
    if response.get("ok") or fault.get("code") == "E_NO_CHANGE":
        receipt["quest_status"] = "committed"
        info("QUESTS: travel updatePlot %s: %s" % (request_id, line), category="plot_updates")
        return "committed"
    reason, _ = _engine_refusal(str(receipt.get("module") or ""), fault, None, root)
    receipt["quest_status"] = "refused"
    receipt["reason"] = reason
    warning("QUESTS: travel updatePlot %s refused: %s (%s)" % (request_id, reason, line), category="plot_updates")
    return "refused"


def journal_after_change(module):
    """T090 keeps the player's journal (D4): run after each committed change."""
    try:
        from utils.quest_player_formatter import format_quests_for_player
        format_quests_for_player((module or "").replace(" ", "_"))
    except Exception as exc:  # fail forward
        warning("QUESTS: player journal not refreshed (%s)" % exc, category="plot_updates")
