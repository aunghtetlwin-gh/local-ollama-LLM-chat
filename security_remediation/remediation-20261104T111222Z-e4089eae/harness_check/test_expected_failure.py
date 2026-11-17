"""Deliberate harness self-check, excluded from all application regression suites."""
def test_expected_failure_exit_code():
    assert False, 'EXPECTED: prove failed assertions produce a nonzero runner exit'
