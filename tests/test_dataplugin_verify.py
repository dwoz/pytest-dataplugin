import pytest
import platform
from contextlib import contextmanager
from _pytest.capture import MultiCapture, SysCapture
from helpers import PYTESTFILE, create_test_archive, print_result


def test_dataplugin_verify(testdir):
    testdir.makepyfile(PYTESTFILE)
    create_test_archive(testdir)
    testdir.makefile('ini', **{
            'pytest': [
                '[pytest]',
                'dataplugin-signature = 2479d9203e1f4a326fd2cb49c66ab0904ebbd54c\n'
            ]
        }
    )
    result = testdir.runpytest_subprocess('--dataplugin-verify')
    assert result.errlines == [
        'dataplugin verify invoked, skipping collection.',
        'Archive passed verification :)'
    ]

def test_dataplugin_fail_verify(testdir):
    testdir.makepyfile(PYTESTFILE)
    local_archive_files = {('txt', 'test-data-file'): 'test data content x'}
    create_test_archive(testdir, archive='.test-data.tar.gz', files=local_archive_files)
    testdir.makefile('ini', **{
            'pytest': [
                '[pytest]',
                'dataplugin-signature = 2479d9203e1f4a326fd2cb49c66ab0904ebbd54c\n'
            ]
        }
    )
    result = testdir.runpytest_subprocess('--dataplugin-verify')
    print_result(result)
    assert result.errlines == [
        'dataplugin verify invoked, skipping collection.',
        'Archive failed verification!'
    ]
    print_result(result)
