"""
Tests for find_best_match and its component similarity functions.

Species choices are sourced from the species_speciesname table in the local
wildebackyard PostgreSQL database.
"""

import pytest

from similarity.similarity import (
    CONFIDENT_THRESHOLD,
    SUGGEST_THRESHOLD,
    find_best_match,
    get_cosine_similarity,
    get_jaccard_similarity,
    get_levenshtein_ratio,
    suggest_species,
)

# ---------------------------------------------------------------------------
# Species list sourced from species_speciesname table in the local
# wildebackyard PostgreSQL database (ordered by name).
# ---------------------------------------------------------------------------

SPECIES = [
    "Acorn Woodpecker",
    "American Badger",
    "American crow",
    "American Robin",
    "Barn owl",
    "Bat (any species)",
    "Black bear",
    "Black-tailed jackrabbit",
    "Bobcat",
    "Brush rabbit",
    "Burrowing Owl",
    "California Quail",
    "California Thrasher",
    "California Towhee",
    "Canada Goose",
    "Common raven",
    "Cottontail rabbit",
    "Cow, Cattle",
    "Coyote",
    "Cyclist",
    "Dark-eyed Junco",
    "Domestic cat",
    "Domestic dog",
    "Domestic horse",
    "Duck species",
    "Eastern grey squirrel",
    "Electric Bicycle",
    "Elk or deer- Consider flagging for staff 1st",
    "Goat (domestic)",
    "Golden Eagle",
    "Gray fox",
    "Great horned owl",
    "Heron/Egret Species",
    "Horse rider",
    "House finch",
    "Human",
    "invertebrate",
    "Long-tailed Weasel",
    "Merriam's Chipmunk",
    "Motorized vehicle",
    "Mourning dove",
    "Mule deer",
    "Non motorized vehicle (bike)",
    "Northern Band-tailed Pigeon",
    "Northern Flicker",
    "prey-bird",
    "prey-mammal",
    "prey-unknown",
    "Puma",
    "Raccoon",
    "Red fox",
    "Red-Shouldered Hawk",
    "Red-tailed hawk",
    "reptile (any species)",
    "River otter",
    "Sheep (domestic)",
    "Spotted Skunk",
    "Spotted Towhee",
    "Steller's Jay",
    "Striped Skunk",
    "Tule Elk",
    "Turkey",
    "Turkey Vulture",
    "Unknown",
    "Unknown bird species",
    "Unknown hawk",
    "Unknown mouse or rat spp",
    "Unknown Nightjar",
    "Unknown owl species",
    "Unknown Rabbit spp",
    "Unknown squirrel spp",
    "Virginia Opossum",
    "Western Blue Bird",
    "Western grey squirrel",
    "Western Screech owl",
    "Western scrub-jay",
    "Wild Boar",
]


# ---------------------------------------------------------------------------
# Helper: assert a candidate resolves to the expected species
# ---------------------------------------------------------------------------


def best_match_choice(candidate):
    return find_best_match(candidate, SPECIES)["choice"]


# ---------------------------------------------------------------------------
# Unit tests for component similarity functions
# ---------------------------------------------------------------------------


class TestGetLevenshteinRatio:
    def test_identical_strings(self):
        assert get_levenshtein_ratio("coyote", "coyote") == 1.0

    def test_case_insensitive(self):
        assert get_levenshtein_ratio("Coyote", "coyote") == 1.0

    def test_empty_strings(self):
        assert get_levenshtein_ratio("", "") == 1.0

    def test_completely_different(self):
        score = get_levenshtein_ratio("abc", "xyz")
        assert score < 0.5

    def test_single_char_off(self):
        score = get_levenshtein_ratio("racoon", "raccoon")
        assert score > 0.85

    def test_range(self):
        score = get_levenshtein_ratio("bobcat", "puma")
        assert 0.0 <= score <= 1.0


class TestGetJaccardSimilarity:
    def test_identical_strings(self):
        # identical → all ngrams shared → 1.0
        assert get_jaccard_similarity("coyote", "coyote") == 1.0

    def test_case_insensitive(self):
        assert get_jaccard_similarity("Coyote", "coyote") == 1.0

    def test_short_string_no_ngrams(self):
        # strings shorter than 3 chars produce no trigrams
        score = get_jaccard_similarity("hi", "hi")
        assert score == 0

    def test_partial_overlap(self):
        score = get_jaccard_similarity("turkey vulture", "turkey")
        assert 0.0 < score < 1.0

    def test_no_overlap(self):
        score = get_jaccard_similarity("zzz", "aaa")
        assert score == 0.0

    def test_range(self):
        score = get_jaccard_similarity("golden eagle", "bald eagle")
        assert 0.0 <= score <= 1.0


class TestGetCosineSimilarity:
    def test_identical_strings(self):
        assert get_cosine_similarity("golden eagle", "golden eagle") == pytest.approx(1.0)

    def test_case_insensitive(self):
        assert get_cosine_similarity("Golden Eagle", "golden eagle") == pytest.approx(1.0)

    def test_no_common_words(self):
        score = get_cosine_similarity("wild boar", "domestic cat")
        assert score == 0.0

    def test_partial_word_overlap(self):
        score = get_cosine_similarity("red fox", "red tailed hawk")
        assert 0.0 < score < 1.0

    def test_single_word_match(self):
        assert get_cosine_similarity("puma", "puma") == 1.0

    def test_range(self):
        score = get_cosine_similarity("river otter", "sea otter")
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# find_best_match — return structure
# ---------------------------------------------------------------------------


class TestFindBestMatchReturnStructure:
    def test_returns_dict(self):
        result = find_best_match("coyote", SPECIES)
        assert isinstance(result, dict)

    def test_has_choice_key(self):
        result = find_best_match("coyote", SPECIES)
        assert "choice" in result

    def test_has_scores_key(self):
        result = find_best_match("coyote", SPECIES)
        assert "scores" in result

    def test_has_total_key(self):
        result = find_best_match("coyote", SPECIES)
        assert "total" in result

    def test_scores_is_three_tuple(self):
        result = find_best_match("coyote", SPECIES)
        assert len(result["scores"]) == 3

    def test_choice_is_in_species_list(self):
        result = find_best_match("coyote", SPECIES)
        assert result["choice"] in SPECIES

    def test_total_is_average_of_scores(self):
        result = find_best_match("coyote", SPECIES)
        lev, jac, cos = result["scores"]
        assert abs(result["total"] - (lev + jac + cos) / 3) < 1e-9

    def test_single_choice(self):
        result = find_best_match("anything", ["Coyote"])
        assert result["choice"] == "Coyote"


# ---------------------------------------------------------------------------
# find_best_match — exact and canonical matches
# ---------------------------------------------------------------------------


class TestExactMatches:
    """Exact species names (possibly different case) should resolve to themselves."""

    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("Coyote", "Coyote"),
            ("coyote", "Coyote"),
            ("Bobcat", "Bobcat"),
            ("Puma", "Puma"),
            ("Raccoon", "Raccoon"),
            ("Human", "Human"),
            ("Turkey", "Turkey"),
            ("Golden Eagle", "Golden Eagle"),
            ("Gray fox", "Gray fox"),
            ("Wild Boar", "Wild Boar"),
            ("Mule deer", "Mule deer"),
            ("Red fox", "Red fox"),
            ("Canada Goose", "Canada Goose"),
            ("River otter", "River otter"),
            ("American Robin", "American Robin"),
            ("Mourning dove", "Mourning dove"),
        ],
    )
    def test_exact_match(self, candidate, expected):
        assert best_match_choice(candidate) == expected


# ---------------------------------------------------------------------------
# find_best_match — case variations
# ---------------------------------------------------------------------------


class TestCaseVariations:
    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("golden eagle", "Golden Eagle"),
            ("COYOTE", "Coyote"),
            ("turkey vulture", "Turkey Vulture"),
            ("california quail", "California Quail"),
            ("striped skunk", "Striped Skunk"),
            ("spotted skunk", "Spotted Skunk"),
            ("black bear", "Black bear"),
            ("red fox", "Red fox"),
            ("wild boar", "Wild Boar"),
            ("virginia opossum", "Virginia Opossum"),
        ],
    )
    def test_case_variation(self, candidate, expected):
        assert best_match_choice(candidate) == expected


# ---------------------------------------------------------------------------
# find_best_match — minor typos and misspellings
# ---------------------------------------------------------------------------


class TestTyposAndMisspellings:
    @pytest.mark.parametrize(
        "candidate,expected",
        [
            # Single missing letter
            ("racoon", "Raccoon"),
            # Transposition
            ("coyoet", "Coyote"),
            # Missing hyphen / space normalisation
            ("mule dear", "Mule deer"),
            ("black bera", "Black bear"),
            ("goldon eagle", "Golden Eagle"),
            ("red taild hawk", "Red-tailed hawk"),
            ("calfornia quail", "California Quail"),
            ("turkey vuture", "Turkey Vulture"),
            ("virginia opissum", "Virginia Opossum"),
            ("easter grey squirrel", "Eastern grey squirrel"),
            ("canada goos", "Canada Goose"),
            ("mourning dovee", "Mourning dove"),
            ("rver otter", "River otter"),
            ("striped skung", "Striped Skunk"),
        ],
    )
    def test_typo(self, candidate, expected):
        assert best_match_choice(candidate) == expected


# ---------------------------------------------------------------------------
# find_best_match — partial / abbreviated input
# ---------------------------------------------------------------------------


class TestPartialInput:
    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("acorn woodpeck", "Acorn Woodpecker"),
            ("burrowing owl", "Burrowing Owl"),
            ("dark eyed junco", "Dark-eyed Junco"),
            ("stellers jay", "Steller's Jay"),
            ("red shouldered hawk", "Red-Shouldered Hawk"),
        ],
    )
    def test_partial(self, candidate, expected):
        assert best_match_choice(candidate) == expected


# ---------------------------------------------------------------------------
# find_best_match — discriminating closely related species
# ---------------------------------------------------------------------------


class TestDiscrimination:
    """Candidates that share words with multiple species must resolve correctly."""

    def test_red_fox_vs_red_tailed_hawk(self):
        assert best_match_choice("red fox") == "Red fox"

    def test_turkey_vs_turkey_vulture(self):
        assert best_match_choice("turkey vulture") == "Turkey Vulture"

    def test_spotted_skunk_vs_striped_skunk(self):
        assert best_match_choice("spotted skunk") == "Spotted Skunk"
        assert best_match_choice("striped skunk") == "Striped Skunk"

    def test_domestic_cat_vs_domestic_dog(self):
        assert best_match_choice("domestic cat") == "Domestic cat"
        assert best_match_choice("domestic dog") == "Domestic dog"

    def test_california_quail_vs_california_thrasher(self):
        assert best_match_choice("california quail") == "California Quail"
        assert best_match_choice("california thrasher") == "California Thrasher"

    def test_black_bear_vs_black_tailed_jackrabbit(self):
        assert best_match_choice("black bear") == "Black bear"

    def test_american_crow_vs_common_raven(self):
        assert best_match_choice("american crow") == "American crow"
        assert best_match_choice("common raven") == "Common raven"


# ---------------------------------------------------------------------------
# find_best_match — new species: exact matches
# ---------------------------------------------------------------------------


class TestNewSpeciesExactMatches:
    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("Barn owl", "Barn owl"),
            ("barn owl", "Barn owl"),
            ("Cottontail rabbit", "Cottontail rabbit"),
            ("Cow, Cattle", "Cow, Cattle"),
            ("Northern Flicker", "Northern Flicker"),
            ("northern flicker", "Northern Flicker"),
            ("Spotted Towhee", "Spotted Towhee"),
            ("spotted towhee", "Spotted Towhee"),
            ("Tule Elk", "Tule Elk"),
            ("tule elk", "Tule Elk"),
            ("Western Blue Bird", "Western Blue Bird"),
            ("western blue bird", "Western Blue Bird"),
            ("Western grey squirrel", "Western grey squirrel"),
            ("western grey squirrel", "Western grey squirrel"),
            ("Northern Band-tailed Pigeon", "Northern Band-tailed Pigeon"),
        ],
    )
    def test_exact_match_new(self, candidate, expected):
        assert best_match_choice(candidate) == expected


# ---------------------------------------------------------------------------
# find_best_match — new species: typos and misspellings
# ---------------------------------------------------------------------------


class TestNewSpeciesTypos:
    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("barn owll", "Barn owl"),
            ("cotontail rabbit", "Cottontail rabbit"),
            ("cottontail rabit", "Cottontail rabbit"),
            ("tule elck", "Tule Elk"),
            ("nothern flicker", "Northern Flicker"),
            ("spotted towhee", "Spotted Towhee"),
            ("western bluebird", "Western Blue Bird"),
            ("western grey squirrl", "Western grey squirrel"),
            ("band tailed pigeon", "Northern Band-tailed Pigeon"),
        ],
    )
    def test_typo_new(self, candidate, expected):
        assert best_match_choice(candidate) == expected


# ---------------------------------------------------------------------------
# find_best_match — new species: partial / abbreviated
# ---------------------------------------------------------------------------


class TestNewSpeciesPartialInput:
    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("band-tailed pigeon", "Northern Band-tailed Pigeon"),
            ("tule elk", "Tule Elk"),
            ("barn owl", "Barn owl"),
            ("cottontail", "Cottontail rabbit"),
            ("northern flick", "Northern Flicker"),
        ],
    )
    def test_partial_new(self, candidate, expected):
        assert best_match_choice(candidate) == expected


# ---------------------------------------------------------------------------
# find_best_match — new species: discrimination
# ---------------------------------------------------------------------------


class TestNewSpeciesDiscrimination:
    """New species that share words with existing entries must resolve correctly."""

    def test_barn_owl_vs_great_horned_owl(self):
        assert best_match_choice("barn owl") == "Barn owl"
        assert best_match_choice("great horned owl") == "Great horned owl"

    def test_cottontail_vs_brush_rabbit(self):
        assert best_match_choice("cottontail rabbit") == "Cottontail rabbit"
        assert best_match_choice("brush rabbit") == "Brush rabbit"

    def test_spotted_towhee_vs_california_towhee(self):
        assert best_match_choice("spotted towhee") == "Spotted Towhee"
        assert best_match_choice("california towhee") == "California Towhee"

    def test_western_grey_vs_eastern_grey_squirrel(self):
        assert best_match_choice("western grey squirrel") == "Western grey squirrel"
        assert best_match_choice("eastern grey squirrel") == "Eastern grey squirrel"

    def test_tule_elk_vs_mule_deer(self):
        assert best_match_choice("tule elk") == "Tule Elk"
        assert best_match_choice("mule deer") == "Mule deer"

    def test_western_screech_owl_vs_barn_owl(self):
        assert best_match_choice("western screech owl") == "Western Screech owl"
        assert best_match_choice("barn owl") == "Barn owl"

    def test_northern_flicker_vs_northern_band_tailed_pigeon(self):
        assert best_match_choice("northern flicker") == "Northern Flicker"
        assert best_match_choice("northern band-tailed pigeon") == "Northern Band-tailed Pigeon"


# ---------------------------------------------------------------------------
# suggest_species — threshold behaviour
#
# Threshold summary (empirically derived from score analysis):
#
#   Input type          Score range     Outcome
#   ─────────────────── ─────────────── ────────────────────────────────
#   Exact / case only   1.000           suggest, confident
#   Multi-word typo     0.65 – 0.70     suggest, confident
#   Single-word typo    0.39 – 0.48     suggest, not confident
#   Heavy 2-char typo   0.32 – 0.49     suggest, not confident
#   Partial single word 0.38 – 0.66     suggest (may or may not be confident)
#   Garbage / symbols   0.00 – 0.12     no suggestion (below SUGGEST_THRESHOLD)
#
#   SUGGEST_THRESHOLD   = 0.30  (gap above max garbage score of 0.12)
#   CONFIDENT_THRESHOLD = 0.60  (catches multi-word typos; avoids single-char mangling)
# ---------------------------------------------------------------------------


class TestSuggestSpecies:
    # ---- return structure -----------------------------------------------

    def test_returns_dict_for_valid_input(self):
        result = suggest_species("Coyote", SPECIES)
        assert isinstance(result, dict)

    def test_dict_has_required_keys(self):
        result = suggest_species("Coyote", SPECIES)
        assert {"choice", "total", "confident"} <= result.keys()

    def test_total_in_range(self):
        result = suggest_species("coyote", SPECIES)
        assert 0.0 <= result["total"] <= 1.0

    def test_choice_is_in_species_list(self):
        result = suggest_species("coyote", SPECIES)
        assert result["choice"] in SPECIES

    # ---- None / edge-case guards ----------------------------------------

    def test_empty_candidate_returns_none(self):
        assert suggest_species("", SPECIES) is None

    def test_empty_choices_returns_none(self):
        assert suggest_species("coyote", []) is None

    def test_none_candidate_returns_none(self):
        assert suggest_species(None, SPECIES) is None

    # ---- garbage inputs must return None (below SUGGEST_THRESHOLD) ------

    @pytest.mark.parametrize("garbage", ["zzz", "xkcd", "asdfgh", "12345", "!!!"])
    def test_garbage_returns_none(self, garbage):
        assert suggest_species(garbage, SPECIES) is None

    def test_garbage_scores_below_suggest_threshold(self):
        """Document that the highest garbage score we observed is well below the threshold."""
        for garbage in ["zzz", "xkcd", "asdfgh", "12345"]:
            best = find_best_match(garbage, SPECIES)
            assert best["total"] < SUGGEST_THRESHOLD

    # ---- confident flag: exact / case-only matches ----------------------

    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("Coyote", "Coyote"),
            ("golden eagle", "Golden Eagle"),
            ("RACCOON", "Raccoon"),
            ("turkey vulture", "Turkey Vulture"),
            ("mule deer", "Mule deer"),
        ],
    )
    def test_exact_match_is_confident(self, candidate, expected):
        result = suggest_species(candidate, SPECIES)
        assert result is not None
        assert result["choice"] == expected
        assert result["confident"] is True

    # ---- confident flag: multi-word typos (score >= CONFIDENT_THRESHOLD) ----

    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("goldon eagle", "Golden Eagle"),  # 0.652
            ("turkey vuture", "Turkey Vulture"),  # 0.693
            ("mule dear", "Mule deer"),  # 0.648
        ],
    )
    def test_multiword_typo_is_confident(self, candidate, expected):
        result = suggest_species(candidate, SPECIES)
        assert result is not None
        assert result["choice"] == expected
        assert result["confident"] is True

    # ---- not confident: single-word or heavy typos ----------------------

    @pytest.mark.parametrize(
        "candidate,expected",
        [
            ("racoon", "Raccoon"),  # 0.474
            ("coyoet", "Coyote"),  # 0.389
            ("cyoote", "Coyote"),  # 0.325
            ("screech", "Western Screech owl"),  # 0.470
        ],
    )
    def test_single_word_typo_not_confident(self, candidate, expected):
        result = suggest_species(candidate, SPECIES)
        assert result is not None
        assert result["choice"] == expected
        assert result["confident"] is False

    # ---- threshold constants are within expected bounds -----------------

    def test_suggest_threshold_value(self):
        assert 0.20 <= SUGGEST_THRESHOLD <= 0.40

    def test_confident_threshold_above_suggest_threshold(self):
        assert CONFIDENT_THRESHOLD > SUGGEST_THRESHOLD

    def test_confident_threshold_value(self):
        assert 0.55 <= CONFIDENT_THRESHOLD <= 0.75
