import pytest
import platform
from contextlib import contextmanager
from _pytest.capture import MultiCapture, SysCapture


PYTESTFILE = """
def test_truth():
    assert True == True
def test_truth_a():
    assert True == True
def test_truth_b():
    assert True == True
"""


def test_dataplugin_added_to_plugins(testdir):
    'Check that dataplugin is added to plugins via pytest_plugins'
    #testdir.makeconftest("""
    #    import pytest
    #""")
    testdir.makepyfile(PYTESTFILE)
    config = testdir.parseconfig()
    plugin_names = []
    class Found(Exception): pass
    with pytest.raises(Found):
        for i in config.pluginmanager.get_plugins():
            if getattr(i, '__name__', i) == 'dataplugin':
                raise Found
    result = testdir.runpytest()
    result.assert_outcomes(passed=3)


def test_create_without_dir(testdir):
    testdir.makepyfile(PYTESTFILE)
    result = testdir.runpytest_subprocess('--dataplugin-create')
    errlines = [
        'dataplugin create invoked, skipping collection.',
        'Directory does not exist',
    ]
    for line, exp in zip(result.errlines, errlines):
        assert line.startswith(exp)
    last_outline = 'plugins: dataplugin-'
    assert result.outlines[-1].startswith(last_outline)
    assert result.ret == 1


def test_create_with_dir(testdir):
    testdir.makepyfile(PYTESTFILE)
    testdir.mkdir('data')
    result = testdir.runpytest_subprocess('--dataplugin-create')
    ERRLINES = 'Archive createded, name is test-data.tar.gz and hash is 39e2bc4a67e0336eb6bdf17bdd7bf8a1671dd9a7'
    assert result.errlines[-1] == ERRLINES
    assert result.outlines[-1].startswith('plugins: dataplugin-')
