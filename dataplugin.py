'''
pytest-dataplugin

The dataplugin allows you to manage a directory of test data that lives outside
your main code repository. The use case for this plugin is when test data is
larger than what you want to store with your code or test data that otherwise
doesn't make sense to store with the code (binary data might be one example).

The test data directory can be ignored by git. The plugin creates an archive
with a consistant hash. This hash is intended to be stored in file that gets
commited to the repository. The plugin uses this hash to know if the data
directory is out of date after.
'''
import sys
import io
import os
import gzip
import shutil
import hashlib
import tarfile
from functools import partial
import re
import py
import pytest

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
try:
    from urllib2 import build_opener
except ImportError:
    from urllib.request import build_opener
try:
    import smb.SMBHandler
except ImportError:
    HAS_PYSMB = False
else:
    HAS_PYSMB = True
try:
    import boto3
except ImportError:
    HAS_BOTO = False
else:
    HAS_BOTO = True


# pytest handler order:
#   - pytest_addoption
#   - pytest_cmdline_preparse
#   - pytest_configure
#   - pytest_sessionstart
#   - pytest_collectstart
#   - pytest_collectreport
#   - pytest_collection_modifyitems
#   - ipytest_runtestloop
#   - pytest_sessionfinish
#   - pytest_terminal_summary


SIGNATURE_RE = '^.*dataplugin-signature.*=.*$'
NOOP = '_dataplugin_NOOP'
STATE = {
    'action': NOOP,
    'location': 'test-data.tar.gz',
    'filename': None,
    'directory': 'tests/data',
    'signature': '',
    'user': None,
    'secret': None,
    'signature_re': None,
    'inifile': None,
    'return_code': 0,
    'tests_disabled': False,
}
ACTIONS = (
    'create',
    'extract',
    'upload',
    'download',
    'verify',
)


DEFAULT_INFO = tarfile.TarInfo()
_writer_mode = 'w'
_reader_mode = 'r:gz'
collect_ignore = []
tw = py.io.TerminalWriter(sys.stderr)


class DataPluginException(Exception):
    '''
    Base exception class for all dataplugin exceptions.
    '''


class SignatureNotFound(DataPluginException):
    '''
    Raised when there is no signature in the ini file
    '''


def shasum(filename):
    '''
    Return the sha1 checksum of the file at location 'filename'
    '''
    import hashlib
    hsh = hashlib.sha1()
    with io.open(filename, 'rb') as fp:
        while True:
            chunk = fp.read(1024 * 100)
            if not chunk:
                break
            hsh.update(chunk)
    return hsh.hexdigest()


def checkignore(path):
    'Check if a file is ignored by .gitignore'
    import subprocess
    return 0 == subprocess.call(['git', 'check-ignore', path])


def verify_data_archive(filename, signature):
    '''
    True when the sha1 of the file meats that of the signature arg.
    '''
    return shasum(filename) == signature


class ConsistantArchiveReader(object):
    '''
    Read the archive and extract it's contents to a directory without setting
    any times or permissions.
    '''

    def __init__(self, archivefile, _mode=_reader_mode):
        self.archivefile = archivefile
        self.tar = tarfile.open(self.archivefile, mode=_reader_mode)

    def extract_to_directory(self, root):
        # tar = tarfile.TarFile(self.archivefile, fileobj=self.gz)
        for fileinfo in self.tar:
            filedir = os.path.dirname(fileinfo.name)
            if filedir:
                filedir = os.path.join(root, filedir)
            else:
                filedir = root
            if not os.path.exists(filedir):
                os.makedirs(filedir)
            extractpath = os.path.join(filedir, os.path.basename(fileinfo.name.decode('utf-8')))
            self.tar.makefile(fileinfo, extractpath)

    def close(self):
        self.tar.close()

    def sha1(self, filename=None):
        filename = filename or self.archivefile
        hsh = hashlib.sha1()
        with io.open(filename, 'rb') as fp:
            while True:
                chunk = fp.read(1024 * 100)
                if not chunk:
                    break
                hsh.update(chunk)
        return hsh.hexdigest()


class ConsistantArchiveWriter(object):
    '''
    Create an gziped tar archive that will have a consistant hash as long as
    the contents do file contents do not change. This is accomplished doing the
    following.

      - Sort all file and directory names in a consistant manner before adding
        them to the archive
      - Store a consistant user id, user name, group id, group name, and
        modified time on each file.
      - Use the same timstamp as the modified time of the archived files for
        the gzip file header.
    '''

    def __init__(self, archivefile, default_info=DEFAULT_INFO, _mode=_writer_mode):
        self.archivefile = archivefile
        self.tar = tarfile.open('.' + archivefile, _writer_mode)
        self.default_info = default_info

    def add_directory(self, root, _thisdir=None):
        if not _thisdir:
            _thisdir = root
        for dirname, dirs, files in os.walk(_thisdir):
            for filename in sorted(files):
                with open(os.path.join(dirname, filename), 'rb') as fp:
                    info = self.sanitize_info(self.tar.gettarinfo(fileobj=fp))
                    # TODO: Why would we expect one or other not to have
                    # leading slash, fix this upstream.
                    newname = info.name.lstrip('/').split(root.lstrip('/'), 1)[-1].lstrip('/')
                    info.name = newname
                    self.tar.addfile(info, fp)
            for d in sorted(dirs):
                self.add_directory(root, os.path.join(dirname, d))
            break

    def sanitize_info(self, info):
        for attr in ('mtime', 'uid', 'gid', 'uname', 'gname', ):
            newval = getattr(self.default_info, attr)
            setattr(info, attr, newval)
        return info

    def close(self):
        self.tar.close()
        self._compress()
        hsh = hashlib.sha1()
        with open(self.archivefile, 'rb') as fp:
            while True:
                chunk = fp.read(1024 * 100)
                if not chunk:
                    break
                hsh.update(chunk)
        os.remove('.'+self.archivefile)
        return hsh.hexdigest()

    def _compress(self):
        with open('.' + self.archivefile, 'rb') as f_in, \
                gzip.GzipFile(self.archivefile, 'wb', mtime=self.default_info.mtime) as f_out:
            shutil.copyfileobj(f_in, f_out)


def create_archive(output_name, archive_directory):
    '''
    Create an archive and return it's signature
    '''
    archiver = ConsistantArchiveWriter(output_name)
    archiver.add_directory(archive_directory)
    sha1 = archiver.close()
    return sha1


def extract_archive(input_name, output_directory):
    '''
    Extract the archive
    '''
    archiver = ConsistantArchiveReader(input_name)
    sha1 = archiver.sha1()
    archiver.extract_to_directory(output_directory)
    archiver.close()
    return sha1


def find_signature(path, signature_re):
    with io.open(path, 'r') as fp:
        for line in fp:
            if signature_re.search(line):
                found = True
                break
        else:
            return False
    return True


def update_signature(newsig, origpath, signature_re):
    '''
    Update the archive signature in the doc string of this file.
    '''
    basename = os.path.basename(origpath)
    dirname = os.path.dirname(origpath)
    tmppath = os.path.join(dirname, '.' + basename)
    found = False
    with open(origpath) as fp:
        with open(tmppath, 'w') as nfp:
            for line in fp:
                if signature_re.search(line):
                    line = 'dataplugin-signature = {}\n'.format(newsig)
                    found = True
                nfp.write(line)
    if not found:
        raise SignatureNotFound("Signature not found in config")
    os.rename(tmppath, origpath)


def pytest_addoption(parser):
    parser.addoption(
        "--dataplugin-create",
        action='store_true',
        default=False,
        help='Create an archive based on the contents of the data direcory',
    )
    parser.addoption(
        "--dataplugin-extract",
        action='store_true',
        default=False,
        help='Extract the archive to the data directory',
    )
    parser.addoption(
        "--dataplugin-upload",
        action='store_true',
        default=False,
        help=(
            'Upload the archive to shared storage, this will also update the '
            'signature in the local config file'
        )
    )
    parser.addoption(
        "--dataplugin-download",
        action='store_true',
        default=False,
        help='Download the newest archive from shared storage',
    )
    parser.addoption(
        "--dataplugin-verify",
        action='store_true',
        default=False,
        help=(
            'Verify the signature of the archive against the contents of '
            'the data directory'
        ),
    )


def pytest_cmdline_preparse(config, args):
    # TODO: Update opts to show config and environment defaults
    # print(config.inifile)
    pass


def pytest_configure(config):
    STATE['directory'] = config.inicfg.get(
        'dataplugin-directory', os.path.join(str(config.rootdir), 'data')
    )
    STATE['signature'] = config.inicfg.get('dataplugin-signature')
    STATE['location'] = config.inicfg.get('dataplugin-location', STATE['location'])
    STATE['filename'] = os.path.basename(STATE['location'])
    STATE['inifile'] = config.inifile
    STATE['signature_re'] = re.compile(SIGNATURE_RE)
    for action in ACTIONS:
        if getattr(config.option, 'dataplugin_{}'.format(action), False):
            break
    else:
        action = NOOP
    STATE['action'] = action
    if STATE['action'] == NOOP:
        return
    urlprs = urlparse(STATE['location'])


def pytest_sessionstart(session):
    if STATE['action'] == NOOP:
        return


def pytest_collectstart(collector):
    if STATE['action'] == NOOP:
        return
    tw.line("dataplugin {} invoked, skipping collection.".format(STATE['action']), bold=True)


@pytest.hookimpl(tryfirst=True)
def pytest_collectreport(report):
    if STATE['action'] == NOOP:
        return
    return True


def pytest_ignore_collect(path, config):
    if STATE['action'] == NOOP:
        return
    config.option.verbose = -1
    return True


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    if STATE['action'] == NOOP:
        return
    return True


def iterchunks(fp, size):
    for chunk in iter(partial(fp.read, size), b''):
        yield chunk


def pytest_runtestloop(session):
    if STATE['action'] == NOOP:
        return
    STATE['return_code'] = 1
    if STATE['action'] == 'create':
        abspath = os.path.abspath(STATE['directory'])
        if os.path.exists(abspath):
            tw.line(
                "Creating archive {} from directory {}".format(
                    STATE['filename'], abspath
                ), bold=True
            )
            sha1 = create_archive('.' + STATE['filename'], abspath)
            tw.line(
                "Archive createded, name is {} and hash is {}".format(
                    STATE['filename'], sha1
                ),
                green=True
            )
            STATE['return_code'] = 0
            return True
        else:
            tw.line("Directory does not exist {}".format(abspath), red=True)
            return True
    elif STATE['action'] == 'extract':
        sha1 = extract_archive('.' + STATE['filename'], STATE['directory'])
        tw.line(
            "Extracted archive {} with hash {}".format(
                STATE['filename'], sha1
            ),
            green=True
        )
        STATE['return_code'] = 0
    elif STATE['action'] == 'upload':
        if STATE['inifile'] is None:
            tw.line("No ini file configured.", red=True)
            return True
        elif not find_signature(str(STATE['inifile']), STATE['signature_re']):
            tw.line("Signature not found in ini file {}".format(STATE['inifile']), red=True)
            return True
        cache_filename = '.' + STATE['filename']
        transfer_file(
            STATE['location'], cache_filename, UPLOADER_SCHEMAS
        )
        STATE['signature'] = shasum(cache_filename)
        STATE['return_code'] = 0
        tw.line(
            "Uploaded archive {} with hash {}".format(
                STATE['filename'], STATE['signature']
            ),
            green=True,
        )
        update_signature(
            STATE['signature'],
            str(STATE['inifile']),
            STATE['signature_re'],
        )
        tw.line(
            "Signature updated, you may want to commit the changes too: {}".format(
                os.path.basename(str(STATE['inifile']))
            ),
            green=True
        )
    elif STATE['action'] == 'download':
        if STATE['inifile'] is None:
            tw.line("No ini file configured.", red=True)
            return True
        elif not find_signature(str(STATE['inifile']), STATE['signature_re']):
            tw.line("Signature not found in ini file {}".format(STATE['inifile']), red=True)
            return True
        transfer_file(
            STATE['location'], '.' + STATE['filename'], DOWNLOADER_SCHEMAS
        )
        tw.line("file downloaded", green=True)
        STATE['return_code'] = 0
    else:
        if verify_data_archive('.' + STATE['filename'], STATE['signature']):
            tw.line("Archive passed verification :)", green=True)
            STATE['return_code'] =0
        else:
            tw.line("Archive failed verification!", red=True)
            STATE['return_code'] = 1


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """ whole test run finishes. """
    if STATE['action'] == NOOP:
        return
    return True


# def pytest_report_collectionfinish(config, startdir, items):
#     print(config.option.verbose)
#
# def pytest_report_teststatus(report):
#     print(dir(report))


@pytest.hookimpl(tryfirst=True)
def pytest_terminal_summary(terminalreporter, exitstatus):
    '''
    Setting terminalreporter.verbosity = -2 prevents summary_stats_line from
    being shown.  Without this there is an extra 'no tests ran in 0.00 seconds'
    line added dataplugin invocation output.
    '''
    if STATE['action'] == NOOP:
        return
    terminalreporter.verbosity = -2
    #sys.exit(STATE['return_code'])


def local_downloader(location, filename):
    '''
    retrieve the file to a location on the localhost
    '''
    tw.line("Storing local archive: {}".format(location), bold=True)
    with io.open(filename, 'rb') as src:
        with io.open(filename, 'wb') as dst:
            for chunk in iterchunks(src, 1024 * 100):
                dst.write(chunk)


def smb_downloader(location, filename):
    '''
    retrieve the file from and smb location, the username and password should
    be a part of the location url if authentication is required.
    '''
    tw.line("Storing local archive: {}".format(location), bold=True)
    director = build_opener(smb.SMBHandler.SMBHandler)
    src = director.open(location)
    try:
        with io.open(filename, 'wb') as dst:
            while True:
                chunk = src.read(1024 * 100)
                if not chunk:
                    break
                dst.write(chunk)
    finally:
        src.close()


def boto3_downloader(location, filename):
    import boto3
    's3://bucket/path'
    prs = urlparse(location)
    key = prs.path
    creds = parse_netloc_creds(prs.netloc)
    if creds:
        bucket = prs.netloc.split('@', 1)[-1]
        session = boto3.Session(
            aws_access_key_id=creds[0],
            aws_secret_access_key=creds[1],
        )
    else:
        bucket = prs.netloc
        session = boto3.Session()
    s3 = session.client('s3')
    with open(filename, "wb") as f:
        s3.download_fileobj(f, bucket, key)


DOWNLOADER_SCHEMAS = {
    '': local_downloader,
    'smb': smb_downloader,
    's3': boto3_downloader,
}


def local_uploader(location, filename):
    '''
    persist the file to a location on the localhost
    '''
    tw.line("Storing local archive: {}".format(location), bold=True)
    with io.open(filename, 'rb') as src:
        with io.open(location, 'wb') as dst:
            for chunk in iterchunks(src, 1024 * 100):
                dst.write(chunk)


def smb_uploader(location, filename):
    tw.line("Storing local archive: {}".format(location), bold=True)
    director = urllib2.build_opener(smb.SMBHandler.SMBHandler)
    with io.open(filename, 'rb') as src:
        try:
            dst = director.open(location, src)
        finally:
            dst.close()

def boto3_uploader(location, filename):
    import boto3
    's3://bucket/path'
    prs = urlparse(location)
    key = prs.path
    creds = parse_netloc_creds(prs.netloc)
    if creds:
        bucket = prs.netloc.split('@', 1)[-1]
        session = boto3.Session(
            aws_access_key_id=creds[0],
            aws_secret_access_key=creds[1],
        )
    else:
        bucket = prs.netloc
        session = boto3.Session()
    s3 = session.client('s3')
    with open(filename, "rb") as f:
        s3.upload_fileobj(f, bucket, key)


def parse_netloc_creds(netloc):
    if netloc.find('@') == -1:
        raise Exception("No Creds")
    credpart, locpart = netloc.split('@', 1)
    if credpart.find(':') == -1:
        return credpart, None
    else:
        return credpart.split(':', 1)


UPLOADER_SCHEMAS = {
    '': local_uploader,
    'smb': smb_uploader,
    's3': boto3_uploader,
}


def transfer_file(location, filename, schemas):
    method = schemas.get(urlparse(STATE['location']).scheme)
    method(location, filename)
