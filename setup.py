from setuptools import setup

test_requires = [
    'tox',
    'pytest',
    'py',
    'pysmb',
    'boto3',
]

setup(
    name = 'pytest-dataplugin',
    py_modules = ['dataplugin'],
    version = '0.0.2',
    description = (
        'A pytest plugin for managing an archive of test data.'
    ),
    author = 'Daniel Wozniak',
    description_file = 'README.md',
    author_email = 'dan@woz.io',
    url = 'https://github.com/dwoz/pytest-dataplugin',
    download_url = 'https://github.com/dwoz/pytest-dataplugin/archive/0.0.0rc1.tar.gz',
    bugtrack_url = 'https://github.com/dwoz/pytest-dataplugin/issues',
    keywords = [
        'testing', 'pytest', 'plugin', 'fixture',
    ],
    entry_points = {
        'pytest11': [
            'dataplugin = dataplugin',
        ]
    },
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Testing',
        'Topic :: Utilities',
        'Framework :: Pytest',
    ],
    extras_require = {
        'smb':  ["pysmb"],
        's3': ["boto3"],
    }
)
