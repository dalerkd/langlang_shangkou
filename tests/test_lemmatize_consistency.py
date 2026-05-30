"""Verify frontend lemmatizeWord logic matches backend lemmatize_word."""
from app.services.analyzer import lemmatize_word as backend_lemmatize


def _frontend_lemmatize(word: str) -> str:
    """Python port of app.js lemmatizeWord — must stay in sync."""
    value = word.lower().strip("'").strip('"')
    irregular = {
        "ran": "run", "running": "run", "was": "be", "were": "be", "is": "be",
        "are": "be", "been": "be", "being": "be", "has": "have", "had": "have",
        "did": "do", "done": "do", "doing": "do", "goes": "go", "went": "go",
        "gone": "go", "going": "go", "came": "come", "coming": "come",
        "saw": "see", "seen": "see", "seeing": "see", "made": "make",
        "making": "make", "took": "take", "taken": "take", "taking": "take",
        "got": "get", "gotten": "get", "getting": "get", "knew": "know",
        "known": "know", "knowing": "know", "thought": "think",
        "thinking": "think", "said": "say", "saying": "say", "told": "tell",
        "telling": "tell", "asked": "ask", "asking": "ask", "worked": "work",
        "working": "work", "called": "call", "calling": "call", "tried": "try",
        "trying": "try", "used": "use", "using": "use", "showed": "show",
        "showing": "show", "given": "give", "giving": "give", "found": "find",
        "finding": "find", "written": "write", "writing": "write",
        "spoken": "speak", "speaking": "speak", "read": "read",
        "reading": "read", "built": "build", "building": "build",
        "sent": "send", "sending": "send", "felt": "feel", "feeling": "feel",
        "left": "leave", "leaving": "leave", "put": "put", "putting": "put",
        "meant": "mean", "meaning": "mean", "kept": "keep", "keeping": "keep",
        "let": "let", "letting": "let", "began": "begin", "beginning": "begin",
        "begun": "begin", "became": "become", "becoming": "become",
        "brought": "bring", "bringing": "bring", "bought": "buy",
        "buying": "buy", "chose": "choose", "choosing": "choose",
        "chosen": "choose", "drew": "draw", "drawing": "draw", "drawn": "draw",
        "drove": "drive", "driving": "drive", "driven": "drive", "ate": "eat",
        "eating": "eat", "eaten": "eat", "fell": "fall", "falling": "fall",
        "fallen": "fall", "flew": "fly", "flying": "fly", "flown": "fly",
        "forgot": "forget", "forgetting": "forget", "forgotten": "forget",
        "forgave": "forgive", "forgiving": "forgive", "forgiven": "forgive",
        "froze": "freeze", "freezing": "freeze", "frozen": "freeze",
        "grew": "grow", "growing": "grow", "grown": "grow", "hid": "hide",
        "hiding": "hide", "hidden": "hide", "hit": "hit", "hitting": "hit",
        "held": "hold", "holding": "hold", "hurt": "hurt", "hurting": "hurt",
        "laid": "lay", "laying": "lay", "lain": "lie", "lying": "lie",
        "lit": "light", "lighting": "light", "lost": "lose", "losing": "lose",
        "paid": "pay", "paying": "pay", "rode": "ride", "riding": "ride",
        "ridden": "ride", "rang": "ring", "ringing": "ring", "rung": "ring",
        "rose": "rise", "rising": "rise", "risen": "rise", "ran": "run",
        "shook": "shake", "shaking": "shake", "shaken": "shake",
        "shot": "shoot", "shooting": "shoot", "shut": "shut",
        "shutting": "shut", "sang": "sing", "singing": "sing", "sung": "sing",
        "sank": "sink", "sinking": "sink", "sunk": "sink", "sat": "sit",
        "sitting": "sit", "slept": "sleep", "sleeping": "sleep", "slid": "slide",
        "sliding": "slide", "spent": "spend", "spending": "spend",
        "stood": "stand", "standing": "stand", "stole": "steal",
        "stealing": "steal", "stolen": "steal", "stuck": "stick",
        "sticking": "stick", "struck": "strike", "striking": "strike",
        "sworn": "swear", "swearing": "swear", "swept": "sweep",
        "sweeping": "sweep", "swam": "swim", "swimming": "swim", "swum": "swim",
        "swung": "swing", "swinging": "swing", "taught": "teach",
        "teaching": "teach", "tore": "tear", "tearing": "tear", "torn": "tear",
        "thought": "think", "thinking": "think", "threw": "throw",
        "throwing": "throw", "thrown": "throw", "understood": "understand",
        "understanding": "understand", "woke": "wake", "waking": "wake",
        "woken": "wake", "wore": "wear", "wearing": "wear", "worn": "wear",
        "won": "win", "winning": "win", "wound": "wind", "winding": "wind",
        "wrote": "write", "written": "write",
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


def test_authoring_maps_to_author():
    """The word that triggered the bug: authoring -> author."""
    assert backend_lemmatize("authoring") == "author"
    assert _frontend_lemmatize("authoring") == "author"


def test_running_maps_to_run():
    assert backend_lemmatize("running") == "run"
    assert _frontend_lemmatize("running") == "run"


def test_skills_maps_to_skill():
    assert backend_lemmatize("skills") == "skill"
    assert _frontend_lemmatize("skills") == "skill"


def test_studies_maps_to_study():
    assert backend_lemmatize("studies") == "study"
    assert _frontend_lemmatize("studies") == "study"


def test_played_maps_to_play():
    assert backend_lemmatize("played") == "play"
    assert _frontend_lemmatize("played") == "play"


def test_es_suffix_generic_only_removes_s():
    """Generic -es words (not ses/xes/zes/ches/shes) should only lose the s."""
    assert backend_lemmatize("templates") == "template"
    assert _frontend_lemmatize("templates") == "template"
    assert backend_lemmatize("resources") == "resource"
    assert _frontend_lemmatize("resources") == "resource"
    assert backend_lemmatize("changes") == "change"
    assert _frontend_lemmatize("changes") == "change"


def test_short_s_words_and_ss_words_unchanged():
    """Words <=3 chars ending in s, or ending in ss, should stay as-is."""
    assert backend_lemmatize("as") == "as"
    assert _frontend_lemmatize("as") == "as"
    assert backend_lemmatize("ins") == "ins"
    assert _frontend_lemmatize("ins") == "ins"
    assert backend_lemmatize("seamless") == "seamless"
    assert _frontend_lemmatize("seamless") == "seamless"


def test_authoring_double_consonant_dedup_matches_backend():
    """The specific suffix rule that was broken: ing/ed dedup only when doubled."""
    assert backend_lemmatize("authoring") == "author"
    assert _frontend_lemmatize("authoring") == "author"
    assert backend_lemmatize("running") == "run"
    assert _frontend_lemmatize("running") == "run"
