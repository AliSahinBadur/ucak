=======================
Big_Agent Documentation
=======================

Big_Agent is a local-first report assistant for vehicle test and analysis
documents. It ingests PDF, DOCX and PPTX reports, stores searchable chunks,
links catalog records to report files, and answers questions with the source
passages the answer came from.

Everything runs on the machine it is installed on: the database is a local
SQLite file, the embedding model is loaded from disk, and the optional chat
model is served by a local Ollama instance. No document leaves the network.

.. rubric:: Where to start

* New to the project? Read :doc:`overview` and then :doc:`installation`.
* Deploying it for a team? :doc:`configuration` and :doc:`operations`.
* Calling it from another program? :doc:`api`.
* Changing retrieval or the review rules? :doc:`retrieval`, :doc:`review`
  and :doc:`testing`.

.. toctree::
   :maxdepth: 2
   :caption: Contents
   :numbered:

   overview
   installation
   configuration
   architecture
   ingestion
   retrieval
   review
   catalog
   catia_skill
   api
   data_model
   operations
   testing
   glossary

Indices
=======

* :ref:`genindex`
* :ref:`search`
