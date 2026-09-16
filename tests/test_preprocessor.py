"""Tests for the text preprocessor."""

import pytest
from ai.preprocessor import (
    normalize_text,
    remove_boilerplate,
    extract_action_verbs,
    extract_key_concepts,
    preprocess_co,
    get_enhanced_text,
)


class TestNormalizeText:
    def test_basic_normalization(self):
        assert normalize_text("  Hello   World  ") == "hello world"

    def test_trailing_punctuation(self):
        assert normalize_text("Do something.") == "do something"

    def test_empty_input(self):
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""

    def test_unicode_normalization(self):
        text = "students\u2019 will learn \u201cengineering\u201d"
        result = normalize_text(text)
        assert "'" in result
        assert '"' in result


class TestRemoveBoilerplate:
    def test_removes_student_will(self):
        text = "The student will be able to apply sorting algorithms."
        result = remove_boilerplate(text)
        assert not result.startswith("the student")
        assert "sorting" in result

    def test_removes_upon_completion(self):
        text = "Upon completion of the course, design solutions."
        result = remove_boilerplate(text)
        assert "design" in result

    def test_preserves_content_without_boilerplate(self):
        text = "Apply and implement sorting algorithms."
        result = remove_boilerplate(text)
        assert "apply" in result
        assert "implement" in result


class TestExtractActionVerbs:
    def test_finds_apply_and_implement(self):
        text = "Apply and implement sorting algorithms using C language."
        verbs = extract_action_verbs(text)
        assert "apply" in verbs
        assert "implement" in verbs

    def test_finds_analyze(self):
        text = "Analyze the efficiency of algorithms."
        verbs = extract_action_verbs(text)
        assert "analyze" in verbs

    def test_finds_design_and_develop(self):
        text = "Design and develop solutions for real-world problems."
        verbs = extract_action_verbs(text)
        assert "design" in verbs
        assert "develop" in verbs

    def test_no_verbs_in_simple_text(self):
        text = "Engineering knowledge and mathematics."
        verbs = extract_action_verbs(text)
        # "knowledge" and "mathematics" are not action verbs
        assert "knowledge" not in verbs


class TestExtractKeyConcepts:
    def test_extracts_concepts(self):
        text = "Apply and implement sorting algorithms using C language."
        concepts = extract_key_concepts(text)
        assert "algorithm" in concepts or "algorithms" in concepts or "sorting" in concepts

    def test_extracts_engineering_terms(self):
        text = "Engineering knowledge in database and network systems."
        concepts = extract_key_concepts(text)
        assert "database" in concepts
        assert "network" in concepts


class TestPreprocessCO:
    def test_full_pipeline(self):
        co_text = "Apply and implement the principle sorting and searching algorithms on the given data using the C language."
        result = preprocess_co(co_text)

        assert result["original"] == co_text
        assert "apply" in result["action_verbs"]
        assert "implement" in result["action_verbs"]
        assert len(result["normalized"]) > 0
        assert len(result["cleaned"]) > 0

    def test_enhanced_text(self):
        result = preprocess_co("Develop applications of stack and queue using arrays.")
        enhanced = get_enhanced_text(result)
        assert "develop" in enhanced.lower()
        assert "key actions" in enhanced.lower()
