import os
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

default_files = {('txt', 'test-data-file'): 'test data content'}

def create_test_archive(testdir, archive='.test-data.tar.gz', path='data', files=None):
    '''
    Create a dataplugin archive file in a testdir (see pytester plugin docs)
    '''
    if files is None:
        files = default_files
    for (ext, name), content in files.items():
        testdir.makefile(ext, **{os.path.join(path, name): content})
    datapath = str(testdir.tmpdir.join(path))
    dataplugin.create_archive(archive, datapath)

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
