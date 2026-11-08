"""Offline tests for GLITCHLAB_ smart patch preview (no Gemini key needed)."""
import pytest
import smart_patch
from intelligence import AIUnavailable

RULES = [
    {'code': 'BR-101', 'pattern': r'72\s*[- ]?hour(?:s)?', 'title': 'Battery life',
     'category': 'fact', 'explanation': 'Up to 48 hours', 'source': 'Approved fact sheet', 'replacement': '48 hours'},
    {'code': 'BR-105', 'pattern': r'\brevolutionary\b', 'title': 'Brand voice',
     'category': 'tone', 'explanation': 'Avoid exaggerated language', 'source': 'Voice guide', 'replacement': 'new'},
]


def test_good_patch_reduces_failures(monkeypatch):
    monkeypatch.setattr(smart_patch, '_call_model', lambda system, payload: {
        'original_span': 'Guaranteed 72-hour performance.',
        'replacement_span': 'Designed for up to 48 hours of performance.',
        'rationale': 'Use approved battery specification.'
    })
    r = smart_patch.preview_smart_patch('Guaranteed 72-hour performance.', 'social', RULES)
    assert (r['before_count'], r['after_count']) == (1, 0)
    assert r['safe_to_offer'] and r['resolved_codes'] == ['BR-101']


def test_unanchored_patch_rejected(monkeypatch):
    monkeypatch.setattr(smart_patch, '_call_model', lambda system, payload: {
        'original_span': 'not in draft', 'replacement_span': 'x', 'rationale': 'n/a'
    })
    with pytest.raises(AIUnavailable, match='missing or ambiguous'):
        smart_patch.preview_smart_patch('A revolutionary product.', 'social', RULES)


def test_regression_not_offered(monkeypatch):
    monkeypatch.setattr(smart_patch, '_call_model', lambda system, payload: {
        'original_span': 'A revolutionary product.',
        'replacement_span': 'A revolutionary 72-hour product.', 'rationale': 'n/a'
    })
    r = smart_patch.preview_smart_patch('A revolutionary product.', 'social', RULES)
    assert r['safe_to_offer'] is False
    assert r['introduced_codes'] == ['BR-101']


def test_clean_draft_skips_model(monkeypatch):
    def fail(*args):
        raise AssertionError('should not call AI on clean draft')
    monkeypatch.setattr(smart_patch, '_call_model', fail)
    assert smart_patch.preview_smart_patch('A new product.', 'social', RULES)['status'] == 'no_failures'
