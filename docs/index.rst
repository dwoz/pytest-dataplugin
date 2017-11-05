.. pytest-dataplugin documentation master file, created by
   sphinx-quickstart on Sat Nov  4 21:54:29 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to pytest-dataplugin's documentation!
=============================================

Installation
------------

.. code-block:: bash

    pip install pytest-dataplugin


Configuration
-------------

.. code-block:: bash

   [pytest]
   dataplugin-directory: tests/data
   dataplugin-location: /mnt/gluster/testdata.tar.gz

Usage
-----

Create a data archive

.. code-block:: bash

   pytest --dataplugin-create

Upload the data archive

.. code-block:: bash

   pytest --dataplugin-upload

Download an upstream data archive

.. code-block:: bash

   pytest --dataplugin-download

Extract the downloaded archive to the data dir

.. code-block:: bash

   pytest --dataplugin-extract

Verify the archive contents

.. code-block:: bash

   pytest --dataplugin-verify


:doc:`Module documentation <module>`.


.. toctree::
   :maxdepth: 2
   :caption: Contents:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
