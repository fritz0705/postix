postix
======

.. image:: https://travis-ci.org/c3cashdesk/postix.svg?branch=master
   :target: https://travis-ci.org/c3cashdesk/postix

.. image:: https://codecov.io/gh/c3cashdesk/postix/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/c3cashdesk/postix

postix (formerly c6sh) is the cashdesk system used at various events to redeem preorder tickets and sell tickets:

- MRMCD16
- 33C3
- 34C3
- 35C3

Features
--------

postix supports a full cash desk setup with both preorder redemptions (it comes
with a pretix import module) and cash transactions, with a layer of
accountability for each cashier.

postix has the user roles of **cashiers**, who do the main work of exchanging
preorder codes or cash for goodies (at least an entrance token), **backoffice**
users (who give and collect cash and goodies to the cashiers), and
**troubleshooters** who support cashiers by looking up presale data, talking to
troublesome attendees, resupply the cashiers with goodies, etc.

Every cashier will receive a custom amount of cash (and, optionally, goodies),
and will be assigned a cashdesk. After the cashier's session is over, a report
is printed, where the cash and goodies present can be checked against the
amounts that *should* be present.  These reports also come with a QR code to
make them easily readable into a tab delimited file or a spreadsheet.

postix supports adding a variety of constraints to products to be sold or redeemed:

- Some products may only be redeemed or bought if the buyer has a secret code,
  such as a member number, or a name.
- postix can show warnings when a specific product is redeemed, helping to
  inform and direct people directly on arrival to their destination.
- Products may be restricted to be sold at certain times only.

Setup
-----

postix requires Python 3.5+. Install in a virtalenv of any kind::

  pip install --upgrade setuptools pip
  pip install -r requirements.txt
  pip install -r requirements-dev.txt  # Only for development setup
  python manage.py migrate
  python manage.py createsuperuser

Optionally, import data::

  python manage.py import_presale pretix.json
  python manage.py import_member member_list.csv [--prefix BLN]

Run development server::

  POSTIX_STATIC_ROOT=_static python manage.py runserver

Open your browser at one of the following URLs:

* http://localhost:8000/admin/ for the Django admin
* http://localhost:8000/troubleshooter/ for the troubleshooter interface
* http://localhost:8000/backoffice/ for the backoffice interface
* http://localhost:8000/ for the cashdesk interface (requires an active cashdesk and session)

Configuration
-------------

You can configure some aspects of your installation by setting the following
environment variables:

* ``POSTIX_SECRET`` -- Secret key used for signing purposes

* ``POSTIX_DEBUG`` -- Turns on Django's debug mode if set to ``"True"``

* ``POSTIX_DB_TYPE`` -- Database backend, defaults to ``sqlite3``. Other options
  are ``mysql`` and ``postgresql``

* ``POSTIX_DB_NAME`` -- Database name (or filename in case of SQLite). Defaults
  to ``db.sqlite3``

* ``POSTIX_DB_USER`` -- Database user

* ``POSTIX_DB_PASS`` -- Database password

* ``POSTIX_DB_HOST`` -- Database host

* ``POSTIX_DB_PORT`` -- Database port

* ``POSTIX_STATIC_URL`` -- Base URL for static files

* ``POSTIX_STATIC_ROOT`` -- Filesystem directory to plstore static files

Development
-----------

Regenerate translation files::

  pip install django_extensions pytest
  python manage.py makemessages
  python manage.py makemessages --all -d djangojs

Run linters and tests::

  isort -rc .
  flake8
  pytest
