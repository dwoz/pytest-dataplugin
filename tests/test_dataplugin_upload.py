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

def print_result(result):
    header = '*' * 40
    print(header + ' stderr ' + header)
    for line in result.errlines:
        print(line)
    print(header + ' end stderr ' + header)
    print(header + ' stdout ' + header)
    for line in result.outlines:
        print(line)
    print(header + ' end stdout ' + header)


def create_test_archive(testdir):
    import dataplugin
    p = testdir.tmpdir.join('data/test-data-file').new(ext='txt')
    p.dirpath().ensure_dir()
    p.write('test data content')
    datapath = str(testdir.tmpdir.join('data'))
    dataplugin.create_archive('.test-data.tar.gz', datapath)


def test_dataplugin_update_when_no_inifile(testdir):
    #testdir.makeconftest("""
    #    import pytest
    #""")
    testdir.makepyfile(PYTESTFILE)
    testdir.mkdir('data')
    testdir.makefile('txt', **{'data/testdata': 'some test data'})
    #testdir.makefile('tar.gz', {'test-data': ''})
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
    assert result.outlines[-3].startswith('plugins: dataplugin-')



#def test_create_without_dir(testdir):
#    #testdir.makeconftest("""
#    #    import pytest
#    #""")
#    testdir.makepyfile("""
#        def test_truth():
#            assert True == True
#        def test_truth_a():
#            assert True == True
#        def test_truth_b():
#            assert True == True
#    """)
#    result = testdir.runpytest_subprocess('--dataplugin-create')
#    errlines = [
#        'dataplugin create invoked, skipping collection.',
#        'Directory does not exist',
#    ]
#    for line, exp in zip(result.errlines, errlines):
#        assert line.startswith(exp)
#    assert result.outlines[-1].startswith('plugins: dataplugin-')
#    assert result.ret == 1
