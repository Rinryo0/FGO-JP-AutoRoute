from fgoauto_v060.vision import classify_texts


def test_detects_result_screen_before_battle_hud():
    result = classify_texts(["RESULT", "BATTLE 2/2", "獲得EXP", "獲得した戦利品"])
    assert result.state == "result"
    assert result.confidence >= 0.9


def test_detects_battle_card_selection():
    result = classify_texts(["Buster", "Arts", "Quick", "Attack"])
    assert result.state == "battle_cards"


def test_detects_battle_command_screen():
    result = classify_texts(["BATTLE 1/3", "ENEMY", "TURN 1", "Attack"])
    assert result.state == "battle_command"


def test_detects_story_screen():
    result = classify_texts(["SKIP", "LOG", "AUTO"])
    assert result.state == "story"


def test_generic_next_does_not_trigger_chapter_map():
    result = classify_texts(["NEXT", "MENU"])
    assert result.state == "unknown"


def test_unknown_screen_fails_closed():
    result = classify_texts(["random text"])
    assert result.state == "unknown"
    assert result.confidence == 0.0
