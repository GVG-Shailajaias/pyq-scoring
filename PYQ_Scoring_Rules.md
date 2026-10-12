# PYQ Scoring — Rules (version 4.1)

*The scoring rules: what is searched, what counts, and how stars are given. The process — commands, steps, files, output format — is in the Instructions file in the Project. This file lives on GitHub (`GVG-Shailajaias/pyq-scoring`) and is downloaded at every setup. October 2026.*

**How this file is used**
- Claude follows §1–§2 and §4 (search and judgement).
- The script reads **only the settings block below**; it holds no scoring numbers of its own. §3 explains in words what the script does with them.
- **To change a rule:** edit the number in the settings block and the matching text, raise `rules_version`, then run the tests. Failing test cases are exactly the ratings the change moves — review them before using the new rules. A new *kind* of rule (not just a new number) needs a script change.
- Every scored topic records the `rules_version` it was scored under. If the rules change mid-day, the final validation stops and lists the topics to redo.

```settings
rules_version: 4.1
recent_window_years: 12      # "recent" = latest year in the PYQ file back 11 years, inclusive
x2_recent_needed: 1          # X=2: recent exact matches needed for 3★
x3_recent_needed: 2          # X=3: recent exact matches needed for 4★
x4_5_recent_needed: 2        # X=4–5: recent exact matches needed for 4★
x6_plus_recent_needed: 3     # X≥6: recent exact matches needed for 5★
x0_two_star_min_y: 3         # X=0: Y of at least this gives 2★, below it 1★
safety_net_max_y: 1          # safety net when X=0 and Y is at most this
term_hit_limit: 30           # a search term matching more questions is too broad
pool_limit: 40               # most candidates allowed per topic
auto_word_hit_limit: 10      # automatic single-word search terms: used only if they match at most this many questions
y_warn: 25                   # flag (never cut) when Y is above this
```

---

## 1. Stage 1 — search terms (Claude)

- Read the topic in full first: Title, In News, Tags and Content, plus any dictionary suggestions the script gives.
- Terms: the topic's name, its synonyms and alternative names, and the specific names, places, schemes, species, institutions or laws in its content. Use dictionary suggestions unless clearly irrelevant to this topic; respect their notes (e.g. "noisy").
- Prefer specific terms and full phrases ("Ramsar Convention", "Brahmaputra") over generic words. Never search a broad word on its own.
- The script matches terms in **Keywords, Question text (statements and options included) and Solution**: whole words, case ignored, simple plurals (s/es) accepted.
- **Automatic terms (on the first search of every topic)** — so that two runs never depend only on which words were chosen:
  - the topic's **Title** (and any alternative name in brackets), every **Tag**, and every short **bold** label of up to 4 words in In News / Content;
  - any multi-word term (Claude's or automatic) that finds nothing is **broken into shorter parts** ("battery energy storage" → "energy storage", "battery").
  - A part or term is used only if it is narrow: a phrase at most `term_hit_limit` matches, a single word at most `auto_word_hit_limit`. Single words are taken only from the Title, Tags and Claude's own terms, never from long sentences. Automatic finds are capped at `pool_limit`, separately from Claude's own candidates.
  - Automatic finds are shown as **one-line previews**. Open the plausible ones in full and judge them like any candidate; previews left unopened are recorded as discards ("auto-found; unrelated on preview").
- Synonyms the automatic terms cannot know (e.g. "genetic disorder" vs "genetic disease") come from the synonym dictionary — record them in the insights file.
- A term matching more than `term_hit_limit` questions is rejected as too broad; a topic pool above `pool_limit` is rejected. Narrow the terms. Override only with a written reason (the topic is then flagged).
- A pool of 0–1 for an exam-relevant topic: one more search with more synonyms before accepting X=0, Y=0.

## 2. Stage 2 — classification (Claude)

Every candidate gets a verdict — **exact**, **related** or **discard** — with a one-line reason.

- A match counts as exact or related ONLY if the topic-linked term or fact is part of the question's correct answer — never when it appears only in a wrong option. Use the Answer Key column.
- "Statements — how many are correct" questions: counts if the topic's statement has to be judged true or false to reach the correct answer. Flag any ambiguous case.
- Match-the-following: EXACT if the topic is one of the tested pairs, even if it is not the question's sole subject.
- **Exact** = the question's core tested fact IS the topic.
- **Related** = topically connected but not the specific fact tested — including links through names, places or facts in the topic's own content (e.g. a sanctuary named in the topic's In News).
- **Dropped questions** (no correct answer): judge on the question itself — exact if its core tested fact is the topic, related if topically connected; the usual discard bar applies.
- When in doubt between related and discard: discard.
- If `precedent_log.md` exists, follow it on borderline calls. Record every new borderline decision for the insights file, so the next run decides the same way.

## 3. Stars

**X** = exact matches, **Y** = related matches: raw, uncapped, de-duplicated by QID.

**Recent** = within the last `recent_window_years` (12) years of the PYQ file, inclusive — **2014–2025** while 2025 is the latest year. One window for everything. It moves forward when a newer paper is added.

| X | Earns the higher rating when… | Otherwise | Stars |
|---|---|---|---|
| 0 | — | Y below `x0_two_star_min_y` (1–2) → 1★; Y of 3 or more → 2★; Y=0 → not rendered | 1★ / 2★ / — |
| 1 | The one exact match is recent: 3★ if Y≥1, 2★ if Y=0 | Not recent: a recent related match → 3★ (rescued); else 2★ | 3★ / 2★ |
| 2 | At least **1** of the 2 is recent → 3★ | A recent related match → 3★ (rescued); else 2★ | 3★ / 2★ |
| 3 | At least **2** are recent → 4★ | A recent related match → 4★ (rescued); else 3★ | 4★ / 3★ |
| 4–5 | At least **2** are recent → 4★ | A recent related match → 4★ (rescued); else 3★ | 4★ / 3★ |
| 6+ | At least **3** are recent → 5★ | A recent related match → 5★ (rescued); else 4★ | 5★ / 4★ |

**Why it is built this way**
- **Directness, frequency, recency.** More exact matches raise the ceiling; recent interest decides whether a topic reaches it.
- **"At least N recent", not "a majority recent".** Finding one more old exact question must never lower a topic's stars. A majority test did exactly that (e.g. 3 exact with 2 recent = 4★, but one more old question made it 4 exact with 2 recent = 3★). With counts, extra evidence can only help. Checked over every combination of up to 8 matches: no inversions.
- **X=2 needs only one recent** — UPSC asking about a topic directly, then returning to it later, shows lasting interest (e.g. Desert National Park, 2020 + 2010 → 3★).
- **Related questions matter.** UPSC rarely repeats a question but keeps returning to themes, so Y lifts topics with no exact match to 1–2★ and rescues a rating when the exact matches are old.
- **12-year window** — the 2014–15 papers belong to the current (post-2011, 100-question) pattern, and a single window is simple to explain: "recent = the last 12 papers".

**What changed from V3.x** (no topic goes down):

| Situation | V3.x | V4.0 |
|---|---|---|
| X=2, one recent + one old, no recent related | 2★ | 3★ |
| X=3, the second recent match is from 2014–15 | 3★ | 4★ |
| X=4–5, exactly 2 recent | 3★ | 4★ |
| X≥6, exactly half recent (e.g. 3 of 6) | 4★ | 5★ |
| A related match from 2014–15 rescuing old exact matches | no rescue | rescues |

## 4. Safety net

The same bar applied more thoroughly — not a lower bar.

- **Trigger (script):** X=0 and Y at most `safety_net_max_y` (1), or the topic holds its stars only through a related-match rescue. Nothing is saved until the re-check is done.
- **Re-check (Claude):** re-examine each discarded candidate one at a time with an explicit reason — including the automatic previews, opening any that could plausibly link; read the answer key and any solution, not just the stem; run one more search with proper nouns from the topic's own Content; add implied-answer finds by hand with a note.
- `safety_net_max_y` = 1 is provisional — review at the first monthly compile, using the stats lines in the insights files. If the safety net rarely finds anything over 2–3 compiles, scale it back.

## 5. Change log

| Version | Date | Change |
|---|---|---|
| 4.0 | Oct 2026 | Rules separated from the instructions; settings read by the script. Single 12-year window. "At least N recent" replaces "majority recent". X=2 needs one recent. |
| 4.1 | Oct 2026 | Automatic search terms from the topic's Title, Tags and short bold labels; zero-hit phrases broken into parts; automatic finds shown as previews. New setting `auto_word_hit_limit`. Star rules unchanged. |
