"""Unit tests for the pure Marcolphus discography parser (no database)."""

from apps.discography.parsers.marcolphus import (
    VARIOUS_ARTISTS,
    _parse_edition_line,
    _parse_track_line,
    parse_marcolphus,
)

# --------------------------------------------------------------------------- #
# Edition lines
# --------------------------------------------------------------------------- #


def test_edition_line_label_and_catalogue():
    ed = _parse_edition_line('   12": 1990 UK (Creation; CRE 090T)                    15:52')
    assert ed.media == '12"'
    assert ed.year == 1990
    assert ed.country == "UK"
    assert ed.record_label == "Creation"
    assert ed.catalogue_number == "CRE 090T"
    assert ed.notes == ""


def test_edition_line_unknown_label_becomes_blank():
    ed = _parse_edition_line('   12": 1988 UK (??; FP1) [clear blue vinyl]            8:23')
    assert ed.record_label == ""
    assert ed.catalogue_number == "FP1"
    assert ed.notes == "clear blue vinyl"


def test_edition_line_triple_question_catalogue_blank():
    ed = _parse_edition_line('   VHS: 1995 UK (Circa Records/Virgin; ???) [promo]')
    assert ed.record_label == "Circa Records/Virgin"
    assert ed.catalogue_number == ""
    assert ed.notes == "promo"


def test_edition_line_na_label_blank():
    ed = _parse_edition_line("   CDR: 1996 EU (n/a)")
    assert ed.media == "CDR"
    assert ed.country == "EU"
    assert ed.record_label == ""
    assert ed.catalogue_number == ""


def test_edition_line_multiword_media_and_spaced_catalogue():
    ed = _parse_edition_line('   12": 2002 UK (One Little Indian; 370TP 12P1) [28 Oct]   16:59')
    assert ed.catalogue_number == "370TP 12P1"
    assert ed.record_label == "One Little Indian"


def test_edition_line_unparsed_year_is_none():
    ed = _parse_edition_line("    LP: 199? UK (???; ???)")
    assert ed.year is None
    assert ed.country == "UK"


def test_edition_line_tolerates_bracket_typo_for_paren():
    # Real typo in the source: closing "]" instead of ")".
    ed = _parse_edition_line("     2xCD: 1994 UK (World's End; TEEX CD4]   5:51")
    assert ed.record_label == "World's End"
    assert ed.catalogue_number == "TEEX CD4"


def test_non_edition_line_returns_none():
    assert _parse_edition_line("         3:39   Island Life (mix 1)") is None
    assert _parse_edition_line("  [Mixers: Slid]") is None


# --------------------------------------------------------------------------- #
# Track lines
# --------------------------------------------------------------------------- #


def test_track_line_with_length_and_mix():
    tr = _parse_track_line("         3:39   Island Life (mix 1)")
    assert tr.length == "3:39"
    assert tr.name == "Island Life"
    assert tr.mix_info == "mix 1"


def test_track_line_without_mix():
    tr = _parse_track_line("        11:16   Switch/Twitch")
    assert tr.length == "11:16"
    assert tr.name == "Switch/Twitch"
    assert tr.mix_info == ""


def test_track_line_without_length():
    tr = _parse_track_line("                Hang Tough (wild oscar mix)")
    assert tr.length == ""
    assert tr.name == "Hang Tough"
    assert tr.mix_info == "wild oscar mix"


def test_track_line_strips_quoted_annotation():
    tr = _parse_track_line('         7:41   Slid (pdfmone) ["pdfmix"]')
    assert tr.name == "Slid"
    assert tr.mix_info == "pdfmone"


def test_track_line_strips_unquoted_annotation():
    tr = _parse_track_line("         5:45   Atom Bomb (atomix 1) [mix unlabeled]")
    assert tr.name == "Atom Bomb"
    assert tr.mix_info == "atomix 1"


def test_track_line_keeps_seven_inch_mix():
    tr = _parse_track_line('         4:18   Philly (7")')
    assert tr.name == "Philly"
    assert tr.mix_info == '7"'


def test_bracket_only_line_is_not_a_track():
    assert _parse_track_line("        [disc one:]                          76:18") is None
    assert _parse_track_line("    [subtitled \"The Peal Sessions\"]") is None


# --------------------------------------------------------------------------- #
# Full parse: Fluke section
# --------------------------------------------------------------------------- #

FLUKE_DOC = """\
------------------------------------------------------------------------------
::: Fluke ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
------------------------------------------------------------------------------
Fluke: Island Life                                               single [1988]

   12": 1988 UK (??; FP1) [clear blue vinyl; white label]               8:23
         3:39   Island Life (mix 1)
         4:34   Island Life (mix 2)

------------------------------------------------------------------------------
Fluke: The Techno Rose of Blighty                                 album [1991]

    LP: 1991 UK (Creation; CRELP 072)                                   32:47
    CD: 1991 UK (Creation; CRECD 072)
         7:06   Philly
         5:53   Glorious

------------------------------------------------------------------------------
::: Bootlegs :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
------------------------------------------------------------------------------
Fluke: Best                                                     bootleg [199?]

    CD: 199? ?? (??; ??)                                                63:32
         3:49   Absurd (whitewash edit)
"""


def test_parse_fluke_releases_and_skips_bootlegs():
    releases = parse_marcolphus(FLUKE_DOC)
    names = [r.name for r in releases]
    assert names == ["Island Life", "The Techno Rose of Blighty"]
    assert all(r.section == "Fluke" for r in releases)
    assert all(r.artist == "Fluke" for r in releases)
    # The Bootlegs section must be ignored entirely.
    assert "Best" not in names


def test_parse_fluke_release_header_year_and_kind():
    releases = parse_marcolphus(FLUKE_DOC)
    island = releases[0]
    assert island.year == 1988
    assert island.kind == "single"
    rose = releases[1]
    assert rose.kind == "album"
    assert rose.year == 1991


def test_parse_shared_tracklist_applies_to_each_edition_in_run():
    releases = parse_marcolphus(FLUKE_DOC)
    rose = releases[1]
    assert len(rose.editions) == 2  # LP and CD
    for ed in rose.editions:
        assert [t.name for t in ed.tracks] == ["Philly", "Glorious"]


def test_parse_single_edition_tracks():
    releases = parse_marcolphus(FLUKE_DOC)
    island = releases[0]
    assert len(island.editions) == 1
    assert [t.mix_info for t in island.editions[0].tracks] == ["mix 1", "mix 2"]


# --------------------------------------------------------------------------- #
# Full parse: [Mixers:] blocks credit named remixers
# --------------------------------------------------------------------------- #

MIXERS_DOC = """\
::: Fluke :::
------------------------------------------------------------------------------
Fluke: Slid                                                      single [1993]

   12": 1993 UK (Circa Records; YRT103)                                 36:03
         6:58   Slid (glid)
         6:43   Slid (scat and sax frenzy)

  [Mixers: Slid]
     [remixed by Lionrock (Justin Robertson)]
         6:43   Slid (scat and sax frenzy)
     [remixed by Tom Middleton from Global Communication]
        10:11   Slid (modwheel remix)
"""


def test_mixers_block_credits_named_remixer_to_matching_track():
    releases = parse_marcolphus(MIXERS_DOC)
    tracks = releases[0].editions[0].tracks
    frenzy = next(t for t in tracks if t.mix_info == "scat and sax frenzy")
    assert frenzy.remixer == "Lionrock (Justin Robertson)"
    glid = next(t for t in tracks if t.mix_info == "glid")
    assert glid.remixer == ""  # an original Fluke mix, not remixed by anyone


# --------------------------------------------------------------------------- #
# Full parse: Remixes section (Fluke remixes others)
# --------------------------------------------------------------------------- #

REMIX_DOC = """\
::: Remixes :::
------------------------------------------------------------------------------

   [Horse: Celebrate]
        [on same]
           12": 1992 UK (MCA/Oxygen; GASPT 11)
           CD5: 1992 UK (MCA/Oxygen; GASXD 11)
                 6:10   Celebrate (magimix)
                 6:29   Celebrate (moulimix)

   [Bjork: Big Time Sensuality]
        [on same]
           12": 1993 UK (One Little Indian; 132 TP 12)
                 5:51   Big Time Sensuality (fluke's magimix)
    [on Various: Weekenders]
        CD: 199? ?? (??; ??)
                 5:51   Big Time Sensuality (fluke's magimix)
"""


def test_remix_release_owned_by_original_artist():
    releases = parse_marcolphus(REMIX_DOC)
    horse = next(r for r in releases if r.name == "Celebrate")
    assert horse.artist == "Horse"
    assert horse.section == "Remixes"
    assert len(horse.editions) == 2  # 12" and CD5 share the tracklist


def test_remix_tracks_are_credited_to_fluke():
    releases = parse_marcolphus(REMIX_DOC)
    horse = next(r for r in releases if r.name == "Celebrate")
    assert horse.fluke_is_remixer is True
    for ed in horse.editions:
        assert all(t.remixer == "Fluke" for t in ed.tracks)
    # The magimix/moulimix are not obviously Fluke in the text, but must be.
    mixes = {t.mix_info for ed in horse.editions for t in ed.tracks}
    assert mixes == {"magimix", "moulimix"}


def test_remix_on_various_becomes_various_artists_release():
    releases = parse_marcolphus(REMIX_DOC)
    weekenders = next(r for r in releases if r.name == "Weekenders")
    assert weekenders.artist == VARIOUS_ARTISTS


# --------------------------------------------------------------------------- #
# Full parse: Compilation Appearances
# --------------------------------------------------------------------------- #

COMP_DOC = """\
::: Compilation Appearances :::
------------------------------------------------------------------------------
Fluke on compilations, soundtracks, in games etc.

   [Absurd]
        [on Various: Tomb Raider Soundtrack]
            CD: 2001 US (Elektra; ???) [5 Jun]
                 3:40   Absurd (whitewash edit)
        [on Various: Hackers 3]
            CD: 1999 ?? (Edeltone; 4379)
                 5:58   Absurd (whitewash)
"""


def test_compilation_appearance_is_various_artists_release():
    releases = parse_marcolphus(COMP_DOC)
    tomb = next(r for r in releases if r.name == "Tomb Raider Soundtrack")
    assert tomb.artist == VARIOUS_ARTISTS
    assert tomb.section == "Compilation Appearances"
    assert tomb.fluke_is_remixer is False
    track = tomb.editions[0].tracks[0]
    assert track.name == "Absurd"
    assert track.mix_info == "whitewash edit"


def test_compilation_appearances_kept_separate_per_comp():
    releases = parse_marcolphus(COMP_DOC)
    names = {r.name for r in releases}
    assert {"Tomb Raider Soundtrack", "Hackers 3"} <= names


# --------------------------------------------------------------------------- #
# Full parse: Collaborations
# --------------------------------------------------------------------------- #

COLLAB_DOC = """\
::: Collaborations :::
------------------------------------------------------------------------------

   [Trisco: Ultra]
        [on same]
         2x12": 2001 UK (Positiva; 12TIVD-177)
                 6:00   Ultra (vocal mix)
    [Jon Fugler: vocals]
"""


def test_collaboration_release_owned_by_named_artist():
    releases = parse_marcolphus(COLLAB_DOC)
    ultra = next(r for r in releases if r.name == "Ultra")
    assert ultra.artist == "Trisco"
    assert ultra.section == "Collaborations"


def test_collaboration_person_credit_recorded():
    releases = parse_marcolphus(COLLAB_DOC)
    ultra = next(r for r in releases if r.name == "Ultra")
    assert "Jon Fugler" in ultra.featured_credits
