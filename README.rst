`pytest-dataplugin <https://github.com/dwoz/pytest-dataplugin>`_
================================================================

`documentation <http://pytest-dataplugin.readthedocs.io/>`_

`pytest-dataplugin <https://github.com/dwoz/pytest-dataplugin>`_ is a pytest
plugin for managing an archive of test data that lives outide your code's
repository.


The dataplugin allows you to manage a directory of test data that lives outside
your main code repository. The use case for this plugin is when test data is
larger than what you want to store with your code or test data that otherwise
doesn't make sense to store with the code (binary data might be one example).

The test data directory can be ignored by git. The plugin creates an archive
with a consistant hash. This hash is intended to be stored in file that gets
commited to the repository. The plugin uses this hash to know if the data
directory is out of date after.
