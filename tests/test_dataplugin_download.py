import pytest
import platform
from contextlib import contextmanager
from _pytest.capture import MultiCapture, SysCapture
from helpers import PYTESTFILE, create_test_archive, print_result


def test_dataplugin_download(testdir):
    testdir.makepyfile(PYTESTFILE)
    local_archive_files = {('txt', 'test-data-file'): 'test data content x'}
    remote_archive_files = {('txt', 'test-data-file'): 'test data content remote'}
    create_test_archive(testdir, archive='test-data.tar.gz', files=remote_archive_files)
    create_test_archive(testdir, archive='.test-data.tar.gz', files=local_archive_files)
    #create_test_archive(testdir)
    testdir.makefile('ini', **{
            'pytest': [
                '[pytest]',
                'dataplugin-signature = 2479d9203e1f4a326fd2cb49c66ab0904ebbd54c\n'
            ]
        }
    )
    result = testdir.runpytest_subprocess('--dataplugin-download')
    assert result.errlines == [
        'dataplugin download invoked, skipping collection.',
        'Storing local archive: test-data.tar.gz',
        'file downloaded',
    ]
