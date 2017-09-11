import pytest
import dataplugin


PYTESTFILE = """
def test_truth():
    assert True == True
def test_truth_a():
    assert True == True
def test_truth_b():
    assert True == True
"""


def create_test_archive(testdir):
    '''
    Create a dataplugin archive file in a testdir (see pytester plugin docs)
    '''
    p = testdir.tmpdir.join('data/test-data-file').new(ext='txt')
    p.dirpath().ensure_dir()
    p.write('test data content')
    datapath = str(testdir.tmpdir.join('data'))
    dataplugin.create_archive('.test-data.tar.gz', datapath)


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


