"""
Tests for pyq_engine.py V4.1 — the cases agreed in the design discussion.

Run:  python test_pyq_engine.py
      (finds the PYQ file and the rules file automatically), or
      python test_pyq_engine.py --pyq <PYQ.xlsx> --rules <PYQ_Scoring_Rules.md> [--original <V1.0.xlsx>]

Every test must pass before the script is used. Re-run after ANY change.

The expected star ratings below are the agreed V4.0 tables, written out by
hand — not computed by the script. If someone edits a number in the rules
file, the "RV" test fails first and the star cases that fail show exactly
which ratings the edit moves. Review them; if the change is intended, update
the expected values here to match.

Latest year in these tests: 2025, so "recent" = 2014–2025 (12-year window).
"""
import itertools
import os
import re
import sys
import shutil
import tempfile

import pandas as pd

import pyq_engine as E

CY = 2025
RESULTS = []
RULES = None          # loaded in main()

AGREED_SETTINGS = {
    "rules_version": "4.1", "recent_window_years": 12, "x2_recent_needed": 1,
    "x3_recent_needed": 2, "x4_5_recent_needed": 2, "x6_plus_recent_needed": 3,
    "x0_two_star_min_y": 3, "safety_net_max_y": 1, "term_hit_limit": 30,
    "pool_limit": 40, "y_warn": 25, "auto_word_hit_limit": 10,
}


def check(name, got, expected):
    ok = got == expected
    RESULTS.append((name, ok, got, expected))


# ------------------------------------------------------------ rules file
def test_rules_file(rules_path):
    check("RV  rules file has the agreed V4.1 settings", RULES, AGREED_SETTINGS)
    good = open(rules_path, encoding="utf-8").read()
    for name, text in [
        ("RP1 no settings block refused", good.replace("```settings", "```text")),
        ("RP2 missing setting refused", re.sub(r"\npool_limit:.*", "", good)),
        ("RP3 unknown setting refused", good.replace("pool_limit:", "extra: 1\npool_limit:")),
        ("RP4 non-number refused", re.sub(r"pool_limit: *\d+", "pool_limit: forty", good)),
    ]:
        try:
            E.parse_rules(text)
            check(name, False, True)
        except E.EngineError:
            check(name, True, True)
    check("RP5 comments after values ignored",
          E.parse_rules("```settings\n" + "\n".join(
              f"{k}: {v}   # note" for k, v in AGREED_SETTINGS.items()) + "\n```"),
          AGREED_SETTINGS)


# ------------------------------------------------------------ star rating
# (name, exact-match years, related-match years, expected (stars, rescued))
STAR_CASES = [
    # X = 0
    ("X0-1 no matches", [], [], (None, False)),
    ("X0-2 Y=1", [], [2001], (1, False)),
    ("X0-3 Y=2", [], [2001, 1999], (1, False)),
    ("X0-4 Y=3", [], [2001, 1999, 1997], (2, False)),
    # X = 1
    ("X1-1 recent, no Y", [2022], [], (2, False)),
    ("X1-2 recent (2014 counts), no Y", [2014], [], (2, False)),
    ("X1-3 recent, Y 1998 (any year)", [2022], [1998], (3, False)),
    ("X1-4 old, Y 1998 not recent", [2008], [1998], (2, False)),
    ("X1-5 old, Y 2021 rescues", [2008], [2021], (3, True)),
    ("X1-6 old, Y 2015 rescues (12y window)", [2008], [2015], (3, True)),
    # X = 2 — the agreed 9-row table
    ("X2-1 both recent, no Y", [2023, 2018], [], (3, False)),
    ("X2-2 both recent, Y old", [2023, 2018], [2008], (3, False)),
    ("X2-3 both recent, Y recent", [2023, 2018], [2021], (3, False)),
    ("X2-4 one recent one old, no Y", [2020, 2010], [], (3, False)),
    ("X2-5 one recent one old, Y old (Desert NP)", [2020, 2010], [2012], (3, False)),
    ("X2-6 one recent one old, Y recent", [2020, 2010], [2021], (3, False)),
    ("X2-7 both old, no Y", [2012, 2005], [], (2, False)),
    ("X2-8 both old, Y old", [2012, 2005], [2008], (2, False)),
    ("X2-9 both old, Y recent rescues", [2012, 2005], [2021], (3, True)),
    ("X2-10 2015 + 2008 (12y window)", [2015, 2008], [], (3, False)),
    # X = 3 — the agreed table
    ("X3-1 all 3 recent", [2024, 2019, 2017], [], (4, False)),
    ("X3-2 2 recent 1 old", [2022, 2018, 2005], [], (4, False)),
    ("X3-3 2020, 2015, 2005 — 2015 now recent", [2020, 2015, 2005], [], (4, False)),
    ("X3-4 same, Y 2020 — no rescue needed", [2020, 2015, 2005], [2020], (4, False)),
    ("X3-5 1 recent 2 old, no Y", [2021, 2010, 2003], [], (3, False)),
    ("X3-6 1 recent 2 old, Y old", [2021, 2010, 2003], [2009], (3, False)),
    ("X3-7 1 recent 2 old, Y 2015 rescues", [2021, 2010, 2003], [2015], (4, True)),
    ("X3-8 1 recent 2 old, Y 2020 rescues", [2021, 2010, 2003], [2020], (4, True)),
    ("X3-9 all old, no Y", [2012, 2008, 2001], [], (3, False)),
    ("X3-10 all old, Y 2015 rescues", [2012, 2008, 2001], [2015], (4, True)),
    # X = 4–5 — the agreed table
    ("X4-1 3 recent", [2024, 2020, 2017, 2005], [], (4, False)),
    ("X4-2 exactly 2 recent, no Y", [2022, 2018, 2008, 2001], [], (4, False)),
    ("X4-3 exactly 2 recent, Y 2015", [2022, 2018, 2008, 2001], [2015], (4, False)),
    ("X4-4 exactly 2 recent, Y 2020 — no rescue needed", [2022, 2018, 2008, 2001], [2020], (4, False)),
    ("X4-5 1 recent, no Y", [2021, 2010, 2005, 2001], [], (3, False)),
    ("X4-6 1 recent, Y old", [2021, 2010, 2005, 2001], [2009], (3, False)),
    ("X4-7 1 recent, Y 2015 rescues", [2021, 2010, 2005, 2001], [2015], (4, True)),
    ("X4-8 0 recent, Y 2020 rescues", [2012, 2008, 2003, 1999], [2020], (4, True)),
    ("X4-9 2015 + 2014 + 2 old", [2015, 2014, 2001, 1998], [], (4, False)),
    ("X5-1 exactly 2 recent", [2023, 2017, 2010, 2005, 1999], [], (4, False)),
    ("X5-2 1 recent, no Y", [2019, 2011, 2006, 2001, 1997], [], (3, False)),
    ("X5-3 0 recent, Y 2015 rescues", [2013, 2009, 2004, 2000, 1996], [2015], (4, True)),
    # X ≥ 6
    ("X6-1 exactly 3 of 6 recent", [2024, 2022, 2020, 2010, 2005, 2001], [], (5, False)),
    ("X6-2 2 of 6 recent, no Y", [2024, 2022, 2010, 2005, 2001, 1999], [], (4, False)),
    ("X6-3 2 of 6 recent, Y 2019 rescues", [2024, 2022, 2010, 2005, 2001, 1999], [2019], (5, True)),
    ("X7-1 4 of 7 recent", [2025, 2020, 2018, 2014, 2013, 2000, 1999], [], (5, False)),
    ("X8-1 3 of 8 recent", [2025, 2020, 2014, 2012, 2010, 2005, 2000, 1999], [], (5, False)),
]


def test_stars():
    for name, xy, yy, exp in STAR_CASES:
        check(name, E.star_rating(xy, yy, CY, RULES), exp)


def test_no_inversions():
    """Adding one more exact match (of any year) must never lower the stars."""
    years = [2024, 2019, 2015, 2014, 2013, 2008, 2001]
    y_sets = [[], [2021], [2015], [2005], [2005, 2001, 1999]]
    bad = []
    for n in range(0, 8):
        for x in itertools.combinations_with_replacement(years, n):
            for y in y_sets:
                a = E.star_rating(list(x), y, CY, RULES)[0] or 0
                for extra in years:
                    b = E.star_rating(list(x) + [extra], y, CY, RULES)[0] or 0
                    if b < a:
                        bad.append((x, extra, y, a, b))
    check("INV more exact matches never lower the stars", bad[:3], [])


def test_window():
    check("W1 2025 -> recent from 2014", E.recent_start(2025, RULES), 2014)
    check("W2 2026 -> recent from 2015", E.recent_start(2026, RULES), 2015)


def test_rule_change_shows_impact():
    """Changing a number changes exactly the expected cases (the review list)."""
    r10 = dict(RULES, recent_window_years=10)
    moved = [name for name, xy, yy, exp in STAR_CASES
             if E.star_rating(xy, yy, CY, r10) != exp]
    check("RC  a 10-year window would move these agreed cases",
          sorted(moved),
          sorted(["X1-6 old, Y 2015 rescues (12y window)",
                  "X2-10 2015 + 2008 (12y window)",
                  "X3-3 2020, 2015, 2005 — 2015 now recent",
                  "X3-4 same, Y 2020 — no rescue needed",
                  "X3-7 1 recent 2 old, Y 2015 rescues",
                  "X3-10 all old, Y 2015 rescues",
                  "X4-7 1 recent, Y 2015 rescues",
                  "X4-9 2015 + 2014 + 2 old",
                  "X5-3 0 recent, Y 2015 rescues",
                  "X8-1 3 of 8 recent"]))


# ------------------------------------------------------------ ticker / refs
def fake(n, start_year, kind):
    """n items with distinct years counting down; ids like 2024 (Q11)."""
    items, rows = [], {}
    for i in range(n):
        y = start_year - i
        q = 10 + i if kind == "x" else 50 + i
        qid = f"{y} (Q{q})"
        items.append({"id": qid, "year": y, "qno": q})
        rows[qid] = {"ID": qid, "Question": f"question {qid}", "Answer Key": "a",
                     "Solution": ""}
    return items, rows


def line_for(X, Y):
    xi, xr = fake(X, 2025, "x")
    yi, yr = fake(Y, 2025, "y")
    return E.compose(xi, yi, CY, {**xr, **yr}, RULES)


TICKER_CASES = [
    ("T1  X=1 Y=0", 1, 0, "Reflected in 1 PYQ", 1, ""),
    ("T2  X=2 Y=1", 2, 1, "Reflected in 3 PYQs", 3, ""),
    ("T3  X=4 Y=2", 4, 2, "Reflected in 6 PYQs", 6, " +3 more"),
    ("T4  X=3 Y=10", 3, 10, "Reflected in 7 PYQs", 7, " +4 more"),
    ("T5  X=7 Y=5", 7, 5, "Reflected in 7 PYQs", 7, " +4 more"),
    ("T6  X=8", 8, 3, "Reflected in 7+ PYQs", 7, " +4 more"),
    ("T7  X=0 Y=1", 0, 1, "Related themes seen in 1 PYQ", 1, ""),
    ("T8  X=0 Y=5", 0, 5, "Related themes seen in 5 PYQs", 5, " +2 more"),
    ("T9  X=0 Y=9", 0, 9, "Related themes seen in 5+ PYQs", 5, " +2 more"),
    ("T10 X=1 Y=10", 1, 10, "Reflected in 6 PYQs", 6, " +3 more"),
]


def test_ticker():
    for name, X, Y, ticker, shown, tail in TICKER_CASES:
        out = line_for(X, Y)
        ids = out["shown_ids"]
        expected_ref = f"{ticker} ›› " + ", ".join(ids[:3]) + tail
        check(name + " line", out["pyq_reference"], expected_ref)
        check(name + " shown", len(ids), shown)
    out = line_for(7, 5)
    check("T5  no related separator", E.SEP_RELATED in out["block"], False)
    out = line_for(3, 10)
    check("T4  exact ids come first",
          [i.split("Q")[1].rstrip(")") for i in out["shown_ids"]][:3],
          ["10", "11", "12"])


# ------------------------------------------------------------ cells / blocks
def test_cells():
    out = line_for(0, 3)
    check("C1  X=0 starts with Related separator", out["block"][0], E.SEP_RELATED)
    check("C1  X=0 has no Topic separator", E.SEP_TOPIC in out["block"], False)
    out = line_for(7, 4)
    check("C2  X=7: Topic sep + 7 cells, no Related",
          (out["block"][0], len(out["block"]), E.SEP_RELATED in out["block"]),
          (E.SEP_TOPIC, 8, False))
    items = [{"id": "2020 (Q9)", "year": 2020, "qno": 9},
             {"id": "2022 (Q40)", "year": 2022, "qno": 40},
             {"id": "2020 (Q3)", "year": 2020, "qno": 3},
             {"id": "2022 (Q5)", "year": 2022, "qno": 5}]
    check("C3  order", [i["id"] for i in E.sort_items(items)],
          ["2022 (Q5)", "2022 (Q40)", "2020 (Q3)", "2020 (Q9)"])
    row = {"ID": "2022 (Q61)", "Question": "Q text\n(a) x", "Answer Key": "Dropped",
           "Solution": ""}
    check("C4  dropped", E.pyq_cell(row),
          "UPSC CSE 2022 (Q61)\nQ text\n(a) x\n\nAnswer Key: Dropped by UPSC\n"
          "-----------------------")
    row = {"ID": "2024 (Q16)", "Question": "Q text", "Answer Key": "b", "Solution": ""}
    check("C5  no solution -> no line", E.pyq_cell(row),
          "UPSC CSE 2024 (Q16)\nQ text\n\nAnswer Key: (b)\n-----------------------")
    row["Solution"] = "Because."
    check("C5  solution line", E.pyq_cell(row),
          "UPSC CSE 2024 (Q16)\nQ text\n\nAnswer Key: (b)\nSolution: Because.\n"
          "-----------------------")
    out = E.compose([], [], CY, {}, RULES)
    check("C6  render-gated",
          (out["pyq_score"], out["pyq_reference"], out["block"]),
          ("Not rendered (X=0, Y=0)", "", []))
    xi = [{"id": "2010 (Q21)", "year": 2010, "qno": 21},
          {"id": "2013 (Q4)", "year": 2013, "qno": 4},
          {"id": "1998 (Q111)", "year": 1998, "qno": 111}]
    yi = [{"id": "2024 (Q52)", "year": 2024, "qno": 52}]
    rows = {i["id"]: {"ID": i["id"], "Question": "q", "Answer Key": "a", "Solution": ""}
            for i in xi + yi}
    out = E.compose(xi, yi, CY, rows, RULES)
    check("C7  PYQ Score text", out["pyq_score"],
          "★★★★☆ (X=3, Y=1, Y-rescued, X: 2013 (Q4), 2010 (Q21), 1998 (Q111), "
          "Y: 2024 (Q52))")
    out = E.compose([], yi, CY, rows, RULES)
    check("C7  PYQ Score text, X=0", out["pyq_score"], "★☆☆☆☆ (X=0, Y=1, Y: 2024 (Q52))")


# ------------------------------------------------------------ search terms
def test_terms():
    p = E.term_pattern("BRO")
    check("K1  BRO not in Broach", bool(p.search("Broach | Drill")), False)
    check("K1  BRO matches BRO", bool(p.search("BRO | Roads")), True)
    p = E.term_pattern("malaria")
    check("K2  case ignored", bool(p.search("Malaria vaccine")), True)
    p = E.term_pattern("Nilgiri Tahr")
    check("K3  phrase", bool(p.search("the Nilgiri  Tahr is")), True)
    check("K3  phrase needs both words", bool(p.search("Nilgiri hills")), False)
    p = E.term_pattern("tiger")
    check("K4  plural s", bool(p.search("Tigers of India")), True)
    p = E.term_pattern("bus")
    check("K4  plural es", bool(p.search("electric buses")), True)
    p = E.term_pattern("tiger")
    check("K4  no other suffix", bool(p.search("Tigerish")), False)


# ------------------------------------------------------------ real file
def new_engine(pyq, rules, work, date="2026-10-08"):
    return E.Engine(pyq, date, work, dictionary_path=None, rules_path=rules)


def test_real_file(pyq_path, rules_path, original_path):
    work = tempfile.mkdtemp()
    try:
        eng = new_engine(pyq_path, rules_path, work)
        check("R1  current year = latest in file", eng.current_year, 2025)
        bad = [q for q, r in eng.rows.items()
               if not E.check_cell(E.pyq_cell(r), eng.rows)]
        check("R2  all cells self-consistent", (len(eng.rows) >= 3893, bad), (True, []))
        if original_path:
            orig = pd.read_excel(original_path, sheet_name="PYQ", dtype=str,
                                 keep_default_na=False)
            mism = []
            for _, o in orig.iterrows():
                m = re.match(r"\AQ(\d+)\. (.*)\n\nAnswer Key: \(([a-dx])\)\n(-+)\Z",
                             o["Full Question"], re.S)
                qid = f"{int(float(o['Year']))} (Q{int(m.group(1))})"
                ak = ("Answer Key: Dropped by UPSC" if m.group(3) == "x"
                      else f"Answer Key: ({m.group(3)})")
                expected = (f"UPSC CSE {qid}\n{m.group(2)}\n\n{ak}\n"
                            "-----------------------")
                if E.pyq_cell(eng.rows[qid]) != expected:
                    mism.append(qid)
            check("R3  every cell matches the ORIGINAL file", mism, [])

        eng.load_topics([
            {"S.No": "1", "Title": "Malaria — WHO report  (exact spacing)",
             "In News": "x", "Tags": "Health", "Content": "**Malaria** content"},
            {"S.No": "2", "Title": "Imaginary topic", "In News": "", "Tags": "",
             "Content": ""}])
        # the three-call pattern
        text = eng.prepare("1")
        check("P1  prepare shows the topic", text.startswith("S.No 1 — Malaria"), True)
        shown = eng.search_and_show("1", ["malaria"])
        n_first = shown.count("=== ")
        check("P2  search_and_show lists the candidates", n_first > 0, True)
        shown2 = eng.search_and_show("1", ["malaria", "Plasmodium"], pass_name="stage1-widen")
        w = eng._load_work("1")
        own = [q for q, c in w["candidates"].items() if c["found_by"] != "auto"]
        check("P3  widening shows only the new candidates",
              shown2.count("=== "), len(own) - n_first)
        r2 = eng.search("1", ["India"])
        check("E2  broad term blocked", r2["status"], "narrow_terms")
        w = eng._load_work("1")
        cands = E.sort_ids(w["candidates"], eng.rows)
        check("E2  blocked search added nothing", len(cands), len(w["candidates"]))
        own = [q for q in cands if w["candidates"][q]["found_by"] != "auto"]
        verdicts = {q: ("related", "test") for q in own}
        verdicts[own[0]] = ("exact", "test")
        try:
            eng.score("1", {own[0]: ("exact", "x")})
            check("E3  missing verdicts rejected", False, True)
        except E.EngineError:
            check("E3  missing verdicts rejected", True, True)
        out = eng.score("1", verdicts)
        if out["status"] == "needs_safety_net":
            out = eng.score("1", verdicts, safety_net_done=True)
        check("E4  scored", out["status"], "saved")
        eng.prepare("2")
        eng.search("2", ["zzqqxx"])
        out = eng.score("2", {})
        check("E5  safety net demanded", out["status"], "needs_safety_net")
        out = eng.score("2", {}, safety_net_done=True)
        check("E6  saved as not rendered",
              (out["status"], "not rendered" in out["flags"],
               "safety net: confirmed discard" in out["flags"]),
              ("saved", True, True))
        check("E7  validation passes", eng.validate(), [])
        check("E7  records carry the rules version",
              {r["rules_version"] for r in eng.records().values()}, {"4.1"})
        path = eng.build_output(work)
        x = pd.read_excel(path, header=None, dtype=str, keep_default_na=False)
        check("E8  headers", list(x.iloc[0, :5]), E.OUTPUT_HEADERS)
        check("E8  title copied exactly", x.iloc[1, 1],
              "Malaria — WHO report  (exact spacing)")
        check("E8  render-gated row", list(x.iloc[2, 2:4]),
              ["Not rendered (X=0, Y=0)", ""])
        verdicts[own[0]] = ("related", "redo")
        out = eng.score("1", verdicts, safety_net_done=True)
        check("E9  redo reports change", "change" in out, True)
        check("E11 session stats",
              eng.session_stats().startswith("Topics scored: 2 · safety net triggered"),
              True)
        saved = os.path.join(work, "saved_progress.json")
        shutil.copyfile(eng.results_path, saved)
        work2 = tempfile.mkdtemp()
        try:
            eng2 = new_engine(pyq_path, rules_path, work2)
            r = eng2.resume(saved)
            check("E12 resume restores topics and records",
                  (r, [t["S.No"] for t in eng2.topics()], eng2.validate()),
                  ({"scored": ["1", "2"], "remaining": []}, ["1", "2"], []))
            try:
                new_engine(pyq_path, rules_path, work2, "2026-10-09").resume(saved)
                check("E13 resume refuses another date", False, True)
            except E.EngineError:
                check("E13 resume refuses another date", True, True)
            # rules changed mid-day -> validation stops and names the topics
            changed = os.path.join(work2, "PYQ Scoring Rules changed.md")
            with open(changed, "w", encoding="utf-8") as f:
                f.write(open(rules_path, encoding="utf-8").read().replace(
                    "rules_version: 4.1", "rules_version: 4.2"))
            eng3 = new_engine(pyq_path, changed, work2)
            probs = eng3.validate()
            check("E14 rules version change caught",
                  (len(probs), all("scored under rules 4.1" in p for p in probs)),
                  (2, True))
            try:
                eng3.build_output(work2)
                check("E14 no output under mixed rules", False, True)
            except E.EngineError:
                check("E14 no output under mixed rules", True, True)
        finally:
            shutil.rmtree(work2)
        res = eng._load_results()
        res["records"]["1"]["pyq_reference"] += " tampered"
        eng._save_results(res)
        check("E10 tampering caught", len(eng.validate()) > 0, True)
    finally:
        shutil.rmtree(work)


def test_files_and_dictionary(pyq_path, rules_path):
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "uploads", "abc")
        os.makedirs(d)
        p1 = os.path.join(d, "9f2c1a7e-UPSC_CSE__Prelims_PYQ_1995-2025_UnlockIAS_V4.0.xlsx")
        shutil.copyfile(pyq_path, p1)
        r1 = os.path.join(d, "5d-PYQ_Scoring_Rules.md")
        shutil.copyfile(rules_path, r1)
        with open(os.path.join(d, "6e-PYQ_Scoring_Instructions_V4.1.md"), "w") as f:
            f.write("instructions — must not be taken for the rules file")
        dic = os.path.join(d, "77aa-synonym_dictionary.csv")
        with open(dic, "w", encoding="utf-8") as f:
            f.write("Term,Also search,Note\n"
                    "Nilgiri Tahr,Eravikulam | Varayaadu | Mountain Monarch,\n"
                    "Wheat,Rabi crop,Rabi crop is noisy: use only with a crop name\n")
        found = E.find_files((root,))
        check("F1  finds PYQ file under upload name", found["pyq"], os.path.realpath(p1))
        check("F1  finds the rules file (not the instructions)", found["rules"],
              os.path.realpath(r1))
        check("F1  finds dictionary", found["dictionary"], os.path.realpath(dic))
        check("F1  no precedent log", found["precedents"], None)
        shutil.copyfile(p1, os.path.join(d, "11-UPSC CSE Prelims PYQ UnlockIAS V9.9.xlsx"))
        check("F2  identical copy under another version name tolerated",
              bool(E.find_files((root,))["pyq"]), True)
        with open(os.path.join(d, "22-PYQ_UnlockIAS_other.xlsx"), "wb") as f:
            f.write(b"different")
        try:
            E.find_files((root,))
            check("F3  two different PYQ files refused", False, True)
        except E.EngineError:
            check("F3  two different PYQ files refused", True, True)

        work = os.path.join(root, "work")
        eng = E.Engine(pyq_path, "2026-10-08", work, dictionary_path=dic,
                       rules_path=rules_path)
        eng.load_topics([{"S.No": "1", "Title": "Nilgiri Tahr census",
                          "Content": "The **Nilgiri Tahr** survey..."},
                         {"S.No": "2", "Title": "Wheat procurement", "Content": ""}])
        s = eng.suggest_terms("1")
        check("D1  suggestion from topic text",
              [(e["term"], e["also"]) for e in s],
              [("Nilgiri Tahr", ["Eravikulam", "Varayaadu", "Mountain Monarch"])])
        check("D1  prepare shows suggestions", "Eravikulam" in eng.prepare("1"), True)
        ws = os.path.join(root, "CA_Prelims_2026-10-08_v1.0.xlsx")
        with pd.ExcelWriter(ws) as xw:
            pd.DataFrame({"S.No": [1, 2, None], "Title": ["A  title", "B", ""],
                          "Content": ["**x**", "y", ""]}).to_excel(
                xw, sheet_name="Content", index=False)
            pd.DataFrame({"x": [1]}).to_excel(xw, sheet_name="PYQ", index=False)
        check("L1  working sheet from xlsx", eng.load_topics_file(ws),
              [("1", "A  title"), ("2", "B")])
        eng.load_topics([{"S.No": "1", "Title": "Nilgiri Tahr census",
                          "Content": "The **Nilgiri Tahr** survey..."},
                         {"S.No": "2", "Title": "Wheat procurement", "Content": ""}])
        r = eng.search("2", ["wheat", "Rabi crop"])
        check("D2  noisy note shown on search",
              r.get("dictionary_notes", {}).get("Rabi crop", "")[:16],
              "Rabi crop is noi")
    finally:
        shutil.rmtree(root)


# ------------------------------------------------------------ search fixes (4.1)
RAMAPPA = {"S.No": "3", "Title": "Ramappa Temple (aka Rudreshwara Temple)",
           "In News": "Heritage Activists oppose open mine near Ramappa Temple.",
           "Tags": "Telangana, Temple, UNESCO World Heritage Site",
           "Content": "- It was constructed in 1213 AD during the reign of the **Kakatiya "
                      "Empire by Recharla Rudra**.\n- **Sandbox technique** is used where "
                      "the foundation pit is filled with a mixture of sand-lime.\n- "
                      "**presence of a very long bold sentence that is not a label**"}
PMDHARA = {"S.No": "1", "Title": "PM-DHARA Scheme", "Tags": "Schemes, Renewables, Energy",
           "In News": "", "Content": "- deployment of 50 GWh of Battery Energy Storage Systems"}


def test_search_fixes(pyq_path, rules_path):
    terms = [t for t, _ in E.baseline_terms(RAMAPPA)]
    check("B1  baseline: title, alternative name, tags, short bold labels",
          [t for t in ["Ramappa Temple", "Rudreshwara Temple", "UNESCO World Heritage Site",
                       "Sandbox technique"] if t not in terms], [])
    check("B1  baseline: bold phrases over 4 words left out",
          [t for t in terms if "Recharla" in t or "very long bold sentence" in t], [])
    parts = E.phrase_parts("battery energy storage")
    check("B2  phrase parts", ("energy storage" in parts, "battery" in parts), (True, True))
    check("B2  no parts for one word", E.phrase_parts("Ramsar"), [])
    work = tempfile.mkdtemp()
    try:
        eng = new_engine(pyq_path, rules_path, work, "2026-10-03")
        eng.load_topics([PMDHARA, RAMAPPA])
        # Ramappa with the exact terms the 3 Oct V4 run used (which missed 3 PYQs)
        eng.prepare("3")
        out = eng.search_and_show("3", ["Ramappa", "Rudreshwara", "Kakatiya", "Ganapati Deva",
                                        "Ramalingeswara", "Warangal", "Palampet",
                                        "floating bricks", "World Heritage Site"])
        w = eng._load_work("3")
        check("B3  Ramappa: the 3 missed UNESCO questions are now found",
              [q for q in ["2024 (Q65)", "2009 (Q25)", "2005 (Q39)"] if q not in w["candidates"]], [])
        check("B3  auto finds are shown as one-line previews",
              ("Found automatically" in out, "- 2024 (Q65)" in out), (True, True))
        n_auto = sum(1 for c in w["candidates"].values() if c["found_by"] == "auto")
        check("B4  auto candidates stay within pool_limit", n_auto <= RULES["pool_limit"], True)
        full = eng.full("3", ["2024 (Q65)"])
        check("B4  full() opens the whole question", full.startswith("=== 2024 (Q65)"), True)
        own = [q for q, c in w["candidates"].items() if c["found_by"] != "auto"]
        verd = {q: ("discard", "t") for q in own}
        verd["2024 (Q65)"] = ("related", "UNESCO WHS inscriptions; Ramappa inscribed 2021")
        res = eng.score("3", verd)
        if res["status"] == "needs_safety_net":
            res = eng.score("3", verd, safety_net_done=True)
        rec = eng.records()["3"]
        check("B5  unopened previews recorded as discards",
              rec["verdicts"]["2009 (Q25)"]["verdict"] + " / " + rec["verdicts"]["2009 (Q25)"]["reason"],
              "discard / " + E.AUTO_DISCARD_REASON)
        check("B5  opened preview can be judged related", "2024 (Q65)" in rec["y_matches"], True)
        # PM-DHARA with the V4 terms (which missed 2024 Q27 'Battery storage')
        eng.prepare("1")
        eng.search_and_show("1", ["PM-DHARA", "Intra-State Transmission", "Green Energy Corridor",
                                  "transmission system", "battery energy storage", "grid storage",
                                  "smart grid", "renewable energy evacuation", "BOOM"])
        check("B6  PM-DHARA: 2024 (Q27) now found",
              "2024 (Q27)" in eng._load_work("1")["candidates"], True)
        # a broad term of Claude's own still blocks, and no auto terms run then
        eng.prepare("1")
        r = json_first(eng.search_and_show("1", ["India", "BOOM"]))
        check("B7  Claude's broad term still blocks; nothing added",
              (r["status"], len(eng._load_work("1")["candidates"])), ("narrow_terms", 0))
    finally:
        shutil.rmtree(work)


def json_first(text):
    import json
    return json.loads(text.split("\n\n")[0])


def main():
    args = sys.argv[1:]
    opts = {}
    while args:
        k = args.pop(0)
        if k in ("--pyq", "--rules", "--original") and args:
            opts[k[2:]] = args.pop(0)
        else:
            sys.exit(f"Unknown argument {k!r}. Use --pyq, --rules, --original.")
    if "pyq" not in opts or "rules" not in opts:
        found = E.find_files()
        opts.setdefault("pyq", found["pyq"])
        opts.setdefault("rules", found["rules"])
    if not opts.get("rules"):
        sys.exit("Rules file not found.")
    global RULES
    RULES = E.load_rules(opts["rules"])
    test_rules_file(opts["rules"])
    test_stars(); test_no_inversions(); test_window(); test_rule_change_shows_impact()
    test_ticker(); test_cells(); test_terms()
    test_real_file(opts["pyq"], opts["rules"], opts.get("original"))
    test_files_and_dictionary(opts["pyq"], opts["rules"])
    test_search_fixes(opts["pyq"], opts["rules"])
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, got, exp in RESULTS:
        print(("PASS " if ok else "FAIL ") + name +
              ("" if ok else f"\n     got:      {got!r}\n     expected: {exp!r}"))
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
