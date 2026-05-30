from app.services.analyzer import analyze_text, lemmatize_word, split_paragraphs


def test_split_paragraphs_keeps_order_and_ignores_blank_blocks():
    text = "First paragraph.\n\n\nSecond paragraph.\n  \nThird paragraph."

    paragraphs = split_paragraphs(text)

    assert paragraphs == ["First paragraph.", "Second paragraph.", "Third paragraph."]


def test_lemmatize_word_collapses_common_english_forms():
    assert lemmatize_word("Running") == "run"
    assert lemmatize_word("runs") == "run"
    assert lemmatize_word("studies") == "study"
    assert lemmatize_word("played") == "play"
    assert lemmatize_word("phrases") == "phrase"


def test_analyze_text_returns_frequency_sorted_words_and_learning_phrases():
    result = analyze_text(
        "Running makes learners look up words. "
        "She looks up examples and runs again.\n\n"
        "Learners are looking up short phrases for learners in context. "
        "We look up context."
    )

    words = result.words
    phrases = result.phrases

    assert [word.canonical for word in words[:3]] == ["look", "up", "learner"]
    assert words[0].frequency == 4
    assert words[0].forms == {"look", "looks", "looking"}
    assert phrases[0].canonical == "look up"
    assert phrases[0].frequency == 4
    assert phrases[0].paragraph_numbers == {1, 2}
