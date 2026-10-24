#!/usr/bin/env python3
"""Keeps feed.json topped up with a rolling window of daily exercises written by Gemini.
Needs env var GEMINI_API_KEY (stays on the server / in GitHub Secrets, never in the web page). Run daily (see .github/workflows/daily-feed.yml). Existing 'extra' content is preserved."""
import json, os, sys, time, datetime, urllib.request

KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
FEED, AHEAD = "feed.json", 7          # days generated in advance
LEVELS = {"A1": "very basic words, simple present tense", "A2": "everyday topics, simple past, future with going to",
          "B1": "everyday topics, phrasal verbs, first and second conditional", "B2": "abstract topics, passive, reported speech, linking words",
          "C1": "idioms, nuance, inversion, complex grammar", "C2": "sophisticated, near-native register, subtle collocations",
          "IELTS": "academic vocabulary, exam-style paraphrase, Task 1/2 language"}
PROMPT = """Write 6 English-learning exercises for CEFR level {lv} ({desc}). Topic seed: {date}. Reply with ONLY a JSON array, no prose, using exactly these item formats:
["mc", question, [3 options], correctIndex, short explanation]            (make 2)
["order", a sentence of 6-12 words]                                      (make 1)
["type", prompt, expected answer, explanation, optionalTextToBeReadAloud] (make 1; an error-correction or dictation task)
["tf", statement, 0 true | 1 false | 2 not given, explanation, a 2-3 sentence passage]  (make 1)
["speak", a natural sentence to say aloud]                               (make 1)"""

def ask(prompt):
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent", method="POST",
        data=json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                         "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.8, "responseMimeType": "application/json"}}).encode(),
        headers={"x-goog-api-key": KEY, "content-type": "application/json"})
    out = json.load(urllib.request.urlopen(req, timeout=90))["candidates"][0]["content"]["parts"][0]["text"]
    time.sleep(5)                                         # stay under the free-tier requests-per-minute limit
    return out

def valid(it):
    try:
        t = it[0]
        return ((t == "mc" and isinstance(it[2], list) and len(it[2]) >= 2 and isinstance(it[3], int) and 0 <= it[3] < len(it[2]))
             or (t == "order" and len(it[1].split()) >= 3) or (t == "type" and bool(it[1]) and bool(it[2]))
             or (t == "tf" and it[2] in (0, 1, 2) and bool(it[4])) or (t == "speak" and bool(it[1])))
    except Exception:
        return False

def make(lv, date):
    for _ in range(2):                                    # one retry on bad output
        try:
            txt = ask(PROMPT.format(lv=lv, desc=LEVELS[lv], date=date)).strip().strip("`")
            items = json.loads(txt[txt.index("["):txt.rindex("]") + 1])
            good = [i for i in items if valid(i)]
            if len(good) >= 4: return good
        except Exception as e:
            print(f"  {lv} {date}: {e}", file=sys.stderr)
    return []

def main():
    if not KEY: sys.exit("Set GEMINI_API_KEY first.")
    try: feed = json.load(open(FEED, encoding="utf8"))
    except Exception: feed = {"version": 1, "extra": {}, "daily": {}}
    today = datetime.date.today()
    days = feed.setdefault("daily", {})
    for d in list(days):                                  # drop days older than 2 days ago
        if datetime.date.fromisoformat(d) < today - datetime.timedelta(days=2): del days[d]
    for n in range(AHEAD + 1):                            # fill any missing day/level
        d = str(today + datetime.timedelta(days=n))
        for lv in LEVELS:
            if lv not in days.setdefault(d, {}):
                items = make(lv, d)
                if items: days[d][lv] = items; print("added", d, lv, len(items))
    json.dump(feed, open(FEED, "w", encoding="utf8"), ensure_ascii=False, indent=1)

if __name__ == "__main__": main()
