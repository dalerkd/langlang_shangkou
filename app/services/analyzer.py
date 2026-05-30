from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re


WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


@dataclass(frozen=True)
class Occurrence:
    paragraph_number: int
    original_text: str
    char_start: int
    char_end: int


@dataclass
class TermAnalysis:
    type: str
    canonical: str
    frequency: int = 0
    forms: set[str] = field(default_factory=set)
    paragraph_numbers: set[int] = field(default_factory=set)
    occurrences: list[Occurrence] = field(default_factory=list)
    first_paragraph_number: int = 0
    first_position: int = 0


@dataclass
class AnalysisResult:
    paragraphs: list[str]
    words: list[TermAnalysis]
    phrases: list[TermAnalysis]


def split_paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n")
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def lemmatize_word(word: str) -> str:
    value = word.lower().strip("'")
    irregular = {
        "are": "be",
        "asked": "ask",
        "asking": "ask",
        "ate": "eat",
        "became": "become",
        "becoming": "become",
        "been": "be",
        "began": "begin",
        "beginning": "begin",
        "begun": "begin",
        "being": "be",
        "bought": "buy",
        "bringing": "bring",
        "brought": "bring",
        "building": "build",
        "built": "build",
        "buying": "buy",
        "called": "call",
        "calling": "call",
        "came": "come",
        "choosing": "choose",
        "chose": "choose",
        "chosen": "choose",
        "coming": "come",
        "did": "do",
        "doing": "do",
        "done": "do",
        "drawing": "draw",
        "drawn": "draw",
        "drew": "draw",
        "driven": "drive",
        "driving": "drive",
        "drove": "drive",
        "eaten": "eat",
        "eating": "eat",
        "fallen": "fall",
        "falling": "fall",
        "feeling": "feel",
        "fell": "fall",
        "felt": "feel",
        "finding": "find",
        "flew": "fly",
        "flown": "fly",
        "flying": "fly",
        "forgave": "forgive",
        "forgetting": "forget",
        "forgiven": "forgive",
        "forgiving": "forgive",
        "forgot": "forget",
        "forgotten": "forget",
        "found": "find",
        "freezing": "freeze",
        "froze": "freeze",
        "frozen": "freeze",
        "getting": "get",
        "given": "give",
        "giving": "give",
        "goes": "go",
        "going": "go",
        "gone": "go",
        "got": "get",
        "gotten": "get",
        "grew": "grow",
        "growing": "grow",
        "grown": "grow",
        "had": "have",
        "has": "have",
        "held": "hold",
        "hid": "hide",
        "hidden": "hide",
        "hiding": "hide",
        "hit": "hit",
        "hitting": "hit",
        "holding": "hold",
        "hurt": "hurt",
        "hurting": "hurt",
        "is": "be",
        "keeping": "keep",
        "kept": "keep",
        "knew": "know",
        "knowing": "know",
        "known": "know",
        "laid": "lay",
        "lain": "lie",
        "laying": "lay",
        "leaving": "leave",
        "left": "leave",
        "let": "let",
        "letting": "let",
        "lighting": "light",
        "lit": "light",
        "losing": "lose",
        "lost": "lose",
        "lying": "lie",
        "made": "make",
        "making": "make",
        "meaning": "mean",
        "meant": "mean",
        "paid": "pay",
        "paying": "pay",
        "put": "put",
        "putting": "put",
        "ran": "run",
        "rang": "ring",
        "read": "read",
        "reading": "read",
        "ridden": "ride",
        "riding": "ride",
        "ringing": "ring",
        "risen": "rise",
        "rising": "rise",
        "rode": "ride",
        "rose": "rise",
        "rung": "ring",
        "running": "run",
        "said": "say",
        "sang": "sing",
        "sank": "sink",
        "sat": "sit",
        "saw": "see",
        "saying": "say",
        "seeing": "see",
        "seen": "see",
        "sending": "send",
        "sent": "send",
        "shaken": "shake",
        "shaking": "shake",
        "shook": "shake",
        "shooting": "shoot",
        "shot": "shoot",
        "showed": "show",
        "showing": "show",
        "shut": "shut",
        "shutting": "shut",
        "singing": "sing",
        "sinking": "sink",
        "sitting": "sit",
        "sleeping": "sleep",
        "slept": "sleep",
        "slid": "slide",
        "sliding": "slide",
        "speaking": "speak",
        "spending": "spend",
        "spent": "spend",
        "spoken": "speak",
        "standing": "stand",
        "stealing": "steal",
        "sticking": "stick",
        "stole": "steal",
        "stolen": "steal",
        "stood": "stand",
        "striking": "strike",
        "struck": "strike",
        "stuck": "stick",
        "sung": "sing",
        "sunk": "sink",
        "swam": "swim",
        "swearing": "swear",
        "sweeping": "sweep",
        "swept": "sweep",
        "swimming": "swim",
        "swinging": "swing",
        "sworn": "swear",
        "swum": "swim",
        "swung": "swing",
        "taken": "take",
        "taking": "take",
        "taught": "teach",
        "teaching": "teach",
        "tearing": "tear",
        "telling": "tell",
        "thinking": "think",
        "thought": "think",
        "threw": "throw",
        "throwing": "throw",
        "thrown": "throw",
        "told": "tell",
        "took": "take",
        "tore": "tear",
        "torn": "tear",
        "tried": "try",
        "trying": "try",
        "understanding": "understand",
        "understood": "understand",
        "used": "use",
        "using": "use",
        "waking": "wake",
        "was": "be",
        "wearing": "wear",
        "went": "go",
        "were": "be",
        "winding": "wind",
        "winning": "win",
        "woke": "wake",
        "woken": "wake",
        "won": "win",
        "wore": "wear",
        "worked": "work",
        "working": "work",
        "worn": "wear",
        "wound": "wind",
        "writing": "write",
        "written": "write",
        "wrote": "write",
    }
    if value in irregular:
        return irregular[value]
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if value.endswith("ing") and len(value) > 5:
        stem = value[:-3]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if value.endswith("ed") and len(value) > 4:
        stem = value[:-2]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if value.endswith("es") and len(value) > 4:
        if value.endswith("ses") and value[:-1].endswith("se"):
            return value[:-1]
        if value.endswith(("ses", "xes", "zes", "ches", "shes")):
            return value[:-2]
        return value[:-1]
    if value.endswith("s") and len(value) > 3 and not value.endswith("ss"):
        return value[:-1]
    return value


def analyze_text(text: str) -> AnalysisResult:
    paragraphs = split_paragraphs(text)
    word_map: dict[str, TermAnalysis] = {}
    phrase_map: dict[str, TermAnalysis] = {}
    normalized_by_paragraph: dict[int, list[tuple[str, Occurrence]]] = defaultdict(list)
    global_position = 0

    for paragraph_number, paragraph in enumerate(paragraphs, start=1):
        paragraph_text = paragraph.replace("\r\n", "\n")
        for match in WORD_RE.finditer(paragraph_text):
            original = match.group(0)
            canonical = lemmatize_word(original)
            occurrence = Occurrence(
                paragraph_number=paragraph_number,
                original_text=original,
                char_start=match.start(),
                char_end=match.end(),
            )
            term = word_map.setdefault(
                canonical,
                TermAnalysis(
                    type="word",
                    canonical=canonical,
                    first_paragraph_number=paragraph_number,
                    first_position=global_position,
                ),
            )
            term.frequency += 1
            term.forms.add(original.lower())
            term.paragraph_numbers.add(paragraph_number)
            term.occurrences.append(occurrence)
            normalized_by_paragraph[paragraph_number].append((canonical, occurrence))
            global_position += 1

    for paragraph_number, tokens in normalized_by_paragraph.items():
        phrase_counter: Counter[str] = Counter()
        phrase_occurrences: dict[str, list[Occurrence]] = defaultdict(list)
        for i in range(len(tokens) - 1):
            first, first_occ = tokens[i]
            second, second_occ = tokens[i + 1]
            phrase = _learning_phrase(first, second)
            if phrase:
                phrase_counter[phrase] += 1
                phrase_occurrences[phrase].append(
                    Occurrence(
                        paragraph_number=paragraph_number,
                        original_text=f"{first_occ.original_text} {second_occ.original_text}",
                        char_start=first_occ.char_start,
                        char_end=second_occ.char_end,
                    )
                )
        for phrase, count in phrase_counter.items():
            term = phrase_map.setdefault(
                phrase,
                TermAnalysis(
                    type="phrase",
                    canonical=phrase,
                    first_paragraph_number=paragraph_number,
                    first_position=global_position,
                ),
            )
            term.frequency += count
            term.forms.add(phrase)
            term.paragraph_numbers.add(paragraph_number)
            term.occurrences.extend(phrase_occurrences[phrase])
            global_position += 1

    return AnalysisResult(
        paragraphs=paragraphs,
        words=_sort_terms(word_map.values()),
        phrases=_sort_terms(phrase_map.values()),
    )


def _sort_terms(terms: list[TermAnalysis] | object) -> list[TermAnalysis]:
    return sorted(
        terms,
        key=lambda term: (-term.frequency, term.first_position, term.canonical),
    )


def _learning_phrase(first: str, second: str) -> str | None:
    particles = {
        "about",
        "across",
        "after",
        "around",
        "away",
        "back",
        "down",
        "for",
        "from",
        "in",
        "into",
        "off",
        "on",
        "out",
        "over",
        "through",
        "to",
        "up",
        "with",
    }
    if second in particles and first not in {"a", "an", "the", "and", "or", "but"}:
        return f"{first} {second}"
    return None
