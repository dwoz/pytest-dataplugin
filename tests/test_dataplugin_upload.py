import pytest
import platform
from contextlib import contextmanager
from _pytest.capture import MultiCapture, SysCapture


def test_dataplugin_added_to_plugins(testdir):
    'Check that dataplugin is added to plugins via pytest_plugins'
    #testdir.makeconftest("""
    #    import pytest
    #""")
    testdir.makepyfile("""
        def test_truth():
            assert True == True
        def test_truth_a():
            assert True == True
        def test_truth_b():
            assert True == True
    """)
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
    #testdir.makeconftest("""
    #    import pytest
    #""")
    testdir.makepyfile("""
        def test_truth():
            assert True == True
        def test_truth_a():
            assert True == True
        def test_truth_b():
            assert True == True
    """)
    result = testdir.runpytest_subprocess('--dataplugin-create')
    errlines = [
        'dataplugin create invoked, skipping collection.',
        'Directory does not exist',
    ]
    for line, exp in zip(result.errlines, errlines):
        assert line.startswith(exp)
    assert result.outlines[-1].startswith('plugins: dataplugin-')
    assert result.ret == 1
