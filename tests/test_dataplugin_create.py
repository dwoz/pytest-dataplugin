import pytest
import platform
from contextlib import contextmanager
from _pytest.capture import MultiCapture, SysCapture
from helpers import PYTESTFILE


def test_dataplugin_added_to_plugins(testdir):
    'Check that dataplugin is added to plugins via pytest_plugins'
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
    assert result.ret == 5


def test_create_with_dir(testdir):
    testdir.makepyfile(PYTESTFILE)
    testdir.mkdir('data')
    result = testdir.runpytest_subprocess('--dataplugin-create')
    ERRLINES = 'Archive createded, name is test-data.tar.gz and hash is 39e2bc4a67e0336eb6bdf17bdd7bf8a1671dd9a7'
    assert result.errlines[-1] == ERRLINES
