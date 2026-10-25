import pytest

from score_to_song.continuation import check_score_prefix

HEAD = "X:1\nT:\nM:4/4\nL:1/16\nQ:1/4=60\nK:Am\n"


def score(bars):
    return HEAD + "% verse\nV: Vocal\n" + "".join(f'"Am"{b}|' for b in bars) + "\nV: Ins\n" + "A,,16|" * len(bars) + "\n"


def test_prefix_must_match_up_to_the_bar_holding_keep_s():
    src = score(["A8B8", "c16", "d16"])
    assert check_score_prefix(src, score(["A8B8", "c16", "e16", "f16"]), 7.9)["bars_kept"] == 2   # 4 s bars
    with pytest.raises(ValueError, match="bar 2 of Vocal"):
        check_score_prefix(src, score(["A8B8", "c8z8", "d16"]), 4.5)
