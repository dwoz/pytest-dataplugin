import pytest
import platform
from contextlib import contextmanager
from _pytest.capture import MultiCapture, SysCapture
from helpers import PYTESTFILE, create_test_archive


def test_dataplugin_update_when_no_inifile(testdir):
    testdir.makepyfile(PYTESTFILE)
    testdir.mkdir('data')
    testdir.makefile('txt', **{'data/testdata': 'some test data'})
    create_test_archive(testdir)
    result = testdir.runpytest_subprocess('--dataplugin-upload')
    assert result.errlines[-1].startswith('No ini file configured.')


def test_dataplugin_update_with_pytest_ini(testdir):
    testdir.makepyfile(PYTESTFILE)
    create_test_archive(testdir)
    testdir.makefile('ini', **{'pytest': ['[pytest]', 'dataplugin-signature =\n']})
    result = testdir.runpytest_subprocess('--dataplugin-upload')
    assert result.errlines == [
        'dataplugin upload invoked, skipping collection.',
        'Storing local archive: test-data.tar.gz',
        'Uploaded archive test-data.tar.gz with hash 2479d9203e1f4a326fd2cb49c66ab0904ebbd54c',
        'Signature updated, you may want to commit the changes too: pytest.ini',
    ]
