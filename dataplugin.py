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
except:
    from urlparse import urlparse
try:
    import pysmb
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


class SignatureNotFound(Exception):
    'Raised when there is no signature in the ini file'


def shasum(filename):
    """
    Return the sha1 checksum of the file at location 'filename'
    """
    import hashlib
    hsh = hashlib.sha1()
    with io.open(filename, 'rb') as fp:
        while True:
            chunk = fp.read(1024 * 100)
            if not chunk:
                break
            hsh.update(chunk)
    return hsh.hexdigest()


def verify_data_archive(filename, signature):
    """
    True when the sha1 of the file meats that of the signature arg.
    """
    return shasum(filename) == signature


class ConsistantArchiveReader(object):
    """
    Read the archive and extract it's contents to a directory without setting
    any times or permissions.
    """

    def __init__(self, archivefile, _mode=_reader_mode):
        self.archivefile = archivefile
        self.tar = tarfile.open(self.archivefile, mode=_reader_mode)

    def extract_to_directory(self, root):
        #tar = tarfile.TarFile(self.archivefile, fileobj=self.gz)
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
    """
    Create an gziped tar archive that will have a consistant hash as long as
    the contents do file contents do not change. This is accomplished doing the
    following.

      - Sort all file and directory names in a consistant manner before adding
        them to the archive
      - Store a consistant user id, user name, group id, group name, and
        modified time on each file.
      - Use the same timstamp as the modified time of the archived files for
        the gzip file header.
    """

    def __init__(self, archivefile, default_info=DEFAULT_INFO, _mode=_writer_mode):
        self.archivefile = archivefile
        self.tar = tarfile.open('.' + archivefile, _writer_mode)
        self.default_info = default_info

    def add_directory(self, root, _thisdir=None):
        if not _thisdir:
            _thisdir = root
        for dirname, dirs, files in os.walk(_thisdir):
            print('archive', dirname, dirs, files)
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
    """
    Create an archive and return it's signature
    """
    archiver = ConsistantArchiveWriter(output_name)
    archiver.add_directory(archive_directory)
    sha1 = archiver.close()
    return sha1


def extract_archive(input_name, output_directory):
    """
    Extract the archive
    """
    archiver = ConsistantArchiveReader(input_name)
    sha1 = archiver.sha1()
    archiver.extract_to_directory(output_directory)
    archiver.close()
    return sha1


def transfer(src, dst):
    """
    Copy the src to the dst
    """
    if dst.exists():
        dst.remove()
    while True:
        chunk = src.read(1024 * 1024)
        if not chunk:
            break
        dst.write(chunk)


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
    """
    Update the archive signature in the doc string of this file.
    """
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


def download_archive():
    """
    Download the test data archive
    """
    # TODO: Fix this
    from urlio import path
    path.SMB_USER = STATE['smbuser']
    path.SMB_PASS = STATE['smbpass']
    src = Path(CONIFG['data_location'], mode='wb')
    transfer(src, dst)
    dst.close()
    src.close()


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
    """ before session.main() is called. """
    if STATE['action'] == NOOP:
        return
    # print(repr(session.config.inifile))
    # print(dir(session.config))
    # sys.exit()
    # collect_ignore.extend('*')
    # return True

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
        urlprs = urlparse(STATE['location'])
        if not urlprs.scheme:
            tw.line("Storing local archive: {}".format(STATE['location']), bold=True)
            with io.open('.' + STATE['filename'], 'rb') as src:
                with io.open(STATE['location'], 'wb') as dst:
                    for chunk in iterchunks(src, 1024 * 100):
                        dst.write(chunk)
        # else:
        #     pass
        STATE['signature'] = shasum(STATE['filename'])
        tw.line(
            "Uploaded archive {} with hash {}".format(
                STATE['filename'], STATE['signature']
            ),
            green=True,
        )
        STATE['return_code'] = 0
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
        urlprs = urlparse(STATE['location'])
        if not urlprs.scheme:
            tw.line("Storing local archive: {}".format(STATE['location']), bold=True)
            with io.open(STATE['location'], 'rb') as src:
                with io.open('.' + STATE['filename'], 'wb') as dst:
                    for chunk in iterchunks(src, 1024 * 100):
                        dst.write(chunk)
        # else:
        #     download_archive()
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


# class FileBackend(object):
# 
#     def __init__(self):
#         pass
#     def fetch(self):
#         pass
#     def put(self):
#         pass
# 
# 
# def smb_connection():
#     global USE_NTLM, MACHINE_NAME
# 
#     host = req.get_host()
#     if not host:
#         raise urllib2.URLError('SMB error: no host given')
#     host, port = splitport(host)
#     if port is None:
#         port = 139
#     else:
#         port = int(port)
# 
#     # username/password handling
#     user, host = splituser(host)
#     if user:
#         user, passwd = splitpasswd(user)
#     else:
#         passwd = None
#     host = unquote(host)
#     user = user or ''
# 
#     domain = ''
#     if ';' in user:
#         domain, user = user.split(';', 1)
# 
#     passwd = passwd or ''
#     myname = MACHINE_NAME or self.generateClientMachineName()
# 
#     n = NetBIOS()
#     names = n.queryIPForName(host)
#     if names:
#         server_name = names[0]
#     else:
#         raise urllib2.URLError('SMB error: Hostname does not reply back with its machine name')
# 
#     path, attrs = splitattr(req.get_selector())
#     if path.startswith('/'):
#         path = path[1:]
#     dirs = path.split('/')
#     dirs = map(unquote, dirs)
#     service, path = dirs[0], '/'.join(dirs[1:])
# 
#     try:
#         conn = SMBConnection(user, passwd, myname, server_name, domain=domain, use_ntlm_v2 = USE_NTLM)
#         conn.connect(host, port)
#     except:
#         pass
