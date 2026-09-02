import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYOUT_FILE = ROOT / "src" / "img" / "layout.json"
PRACTICE_DIR = ROOT / "src" / "practice"
DEFAULT_FREQ = (
    ROOT.parent / "Froj" / "Froj_theories" / "Mussel_Power" / "complete_output.json"
)

parser = argparse.ArgumentParser(description="Generate steno practice files")
parser.add_argument("dictionary", help="Path to the steno dictionary JSON file")
args = parser.parse_args()

DICT_FILE = (ROOT / args.dictionary).resolve()

TOKEN_RE = re.compile(r"\d(?:[lrLR])?|.")
VOWELS = set("AOEU")
LETTER_RE = re.compile(r"[A-Za-z]")

INNER_LEFT = {str(n) for n in range(1, 9)}
INNER_RIGHT = {"-" + str(n) for n in range(1, 9)}
MIDDLE = {f"{n}{m}" for n in range(1, 9) for m in "lr"}
OUTER = {f"{n}{m}" for n in range(1, 9) for m in "LR"}
RIGHT_MIDDLE = {"-" + name for name in MIDDLE}
RIGHT_OUTER = {"-" + name for name in OUTER}
SIMPLE_VOWELS = {"A", "O", "E", "U"}
VOWEL_CLUSTERS = {
    "AE",
    "AO",
    "AU",
    "EU",
    "OU",
    "AEU",
    "AOE",
    "AOEU",
    "AOU",
    "OE",
    "OEU",
}

NEW_CHORDS_BY_LESSON = [
    {
        "name": "03-inner-rings-simple-vowels",
        "new": INNER_LEFT | INNER_RIGHT | SIMPLE_VOWELS,
        "max_strokes": 9,
        "size": 2500,
    },
    {
        "name": "04-middle-ring-initials",
        "new": MIDDLE,
        "max_strokes": 9,
        "size": 2500,
    },
    {
        "name": "05-outer-ring-initials",
        "new": OUTER,
        "max_strokes": 9,
        "size": 2500,
    },
    {
        "name": "06-middle-ring-finals",
        "new": RIGHT_MIDDLE,
        "max_strokes": 9,
        "size": 2500,
    },
    {
        "name": "07-outer-ring-finals",
        "new": RIGHT_OUTER,
        "max_strokes": 9,
        "size": 2500,
    },
    {
        "name": "08-vowel-clusters",
        "new": VOWEL_CLUSTERS,
        "max_strokes": 9,
        "size": 2500,
    },
]


def load_layout(layout_file):
    with open(layout_file, encoding="utf-8") as f:
        layout = json.load(f)
    left = {key: value.split("\n")[0] for key, value in layout["left"].items()}
    right = {key: value.split("\n")[0] for key, value in layout["right"].items()}
    return left, right


def load_frequency(freq_file):
    with open(freq_file, encoding="utf-8") as f:
        data = json.load(f)
    frequency = {}
    for entry in data:
        word = entry.get("word_boundaries") or entry.get("word")
        if not word:
            continue
        try:
            value = int(entry.get("frequency") or 0)
        except (TypeError, ValueError):
            value = 0
        if value > frequency.get(word, 0):
            frequency[word] = value
    return frequency


def convert_key(key, left, right):
    out = []
    prev = None
    for token in TOKEN_RE.findall(key):
        if token[0].isdigit():
            if prev == "-" or prev in VOWELS:
                out.append(right[token])
            else:
                out.append(left[token])
        else:
            out.append(token)
        prev = token
    return "".join(out)


def iter_chords(stroke):
    prev = None
    for token in TOKEN_RE.findall(stroke):
        if token == "-" or token in VOWELS:
            prev = token
            continue
        if not token[0].isdigit():
            continue
        side = "R" if (prev == "-" or prev in VOWELS) else "L"
        yield side, ("-" + token) if side == "R" else token
        prev = token


def vowel_runs(stroke):
    runs = []
    i = 0
    while i < len(stroke):
        if stroke[i] in VOWELS:
            j = i
            while j < len(stroke) and stroke[j] in VOWELS:
                j += 1
            runs.append(stroke[i:j])
            i = j
        else:
            i += 1
    return runs


def unexpected_tokens(stroke):
    for token in TOKEN_RE.findall(stroke):
        if token in VOWELS or token == "-":
            continue
        if not token[0].isdigit():
            return True
    return False


def chords_in_stroke(stroke):
    for run in vowel_runs(stroke):
        yield run
    for _, name in iter_chords(stroke):
        yield name


class Lesson:
    def __init__(self, config, new_before):
        self.slug = config["name"]
        self.new = config["new"]
        self.allowed = new_before | self.new
        self.max_strokes = config["max_strokes"]
        self.size = config["size"]

    def entry_ok(self, raw, word):
        if raw.startswith("S/") or raw == "1-1":
            return False
        if not LETTER_RE.search(str(word)):
            return False
        strokes = raw.split("/")
        if len(strokes) > self.max_strokes:
            return False

        has_new = False
        for stroke in strokes:
            if unexpected_tokens(stroke):
                return False
            for chord in chords_in_stroke(stroke):
                if chord not in self.allowed:
                    return False
                if chord in self.new:
                    has_new = True

        if self.new and not has_new:
            return False
        return True

    def __repr__(self):
        return f"<Lesson {self.slug}>"


def generate(lesson, dictionary, frequency, left, right, seen_raw, limit):
    candidates = []
    for raw, word in dictionary.items():
        if raw in seen_raw:
            continue
        if not lesson.entry_ok(raw, word):
            continue
        readable = convert_key(raw, left, right)
        candidates.append((word, readable, raw))

    candidates.sort(key=lambda item: (-frequency.get(str(item[0]), 0), item[2]))
    if limit:
        candidates = candidates[:limit]
    else:
        candidates = candidates[: lesson.size]

    for _, _, raw in candidates:
        seen_raw.add(raw)
    return candidates


def write_practice(lesson, candidates):
    txt_path = PRACTICE_DIR / f"{lesson.slug}.txt"
    json_path = PRACTICE_DIR / f"{lesson.slug}.json"

    txt_lines = [f"{word}\t{readable} | {raw}" for word, readable, raw in candidates]
    json_obj = {f"{readable} | {raw}": word for word, readable, raw in candidates}

    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(json_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return txt_path, json_path


left, right = load_layout(LAYOUT_FILE)
frequency = load_frequency(DEFAULT_FREQ)

with open(DICT_FILE, encoding="utf-8") as f:
    dictionary = json.load(f)

lessons = []
new_before = set()
for config in NEW_CHORDS_BY_LESSON:
    lessons.append(Lesson(config, new_before))
    new_before |= config["new"]

seen_raw = set()
for lesson in lessons:
    candidates = generate(lesson, dictionary, frequency, left, right, seen_raw, 0)
    print(f"{lesson.slug}: {len(candidates)} entries")
    txt_path, json_path = write_practice(lesson, candidates)
    print(f"  wrote {txt_path.name}, {json_path.name}")
    if candidates:
        first = candidates[0]
        last = candidates[-1]
        print(f"  first: {first[0]!r} {first[1]} | {first[2]}")
        print(f"  last : {last[0]!r} {last[1]} | {last[2]}")
