**NOTE**: This study was completed at the end of July 2025. Thus, this bot was inactivated and this repository was set to archival mode.

# Type Changes Bot

## Requirements

 - Python 3.11+
 - Pip
 - A running Redis-compatible server
 - A running database server (MySQL is known to work)
 - A working JDK installation (JDK 17.0.13 is known to work)

See [pyproject.toml](pyproject.toml) for more specific requirements.

## Setup

### Basic Installation

This section is applicable to the first node.

 1. Clone repository from GitHub, and cd into it.
 2. Create a Python virtual environment, `python -mvenv venv`
 3. Activate the virtual environment, `source venv/bin/activate`
 4. Install minimum necessary packages, with `pip install -e .`
 5. Generate a secret key and copy to the clipboard: `python manage.py shell -c "from django.core.management import utils; print(utils.get_random_secret_key())"`.
 6. Copy `env.template` to `.env` and edit according to your local configuration (see also [Configuration](#Configuration)).
 7. Create migration files for the database: `python manage.py makemigrations`
 8. Create database tables: `python manage.py migrate`
 9. Collect static files: `python manage.py collectstatic`
 10. Create an administrative user, `python manage.py createsuperuser`

On all remaining nodes, complete steps 1--4, copying the `.env` file and make any necessary changes.

### GumTree Installation

On all nodes which will run the worker, complete the following additional steps to install gumtree.

 1. Activate the virtual environment, `source venv/bin/activate`
 2. Install the gumtree support packages, `pip install -e .[gumtree_support]`.
 3. Initialize GumTree submodules, `git submodule update --init --recursive`.
 4. Navigate to the gumtree directory, `cd gumtree`
 5. Build gumtree, `./gradlew build`
 6. Navigate to the gumtree parser directory (`cd ../gumtree-parser`), and pre-build the tree-sitter parsers by running the following commands:
    - `./tree-sitter-parser.py ../test-data/py/arg-type/with.py python`
    - `./tree-sitter-parser.py ../test-data/php/arg-definition/with.php php`
    - `./tree-sitter-parser.py ../test-data/r/args-default/with.r r`
    - `./tree-sitter-parser.py ../test-data/rb/local/with.rb ruby`
    - `./tree-sitter-parser.py ../test-data/ts/arg-type/with.ts typescript`

### Worker Service Installation

This section is applicable to all nodes running the worker service.

 1. Copy the file `template-typechangebot-worker.service` to `typechangebot-worker.service`.
 2. Edit the file, taking special care to set the `WorkingDirectory` setting to the installation directory, and the `User` setting to the user which will the worker will be run as.
 3. Copy `typechangebot-worker.service` to the `/etc/systemd/system/` directory.
 4. Reload the systemd daemon with `systemctl daemon-reload`.
 5. Enable and start the service with `systemctl enable --now typechangebot-worker`.

### Web Server Installation

Configure your webserver/WSGI installation following vendor directions.  If using Ubuntu and Apache, [Digital Ocean's guide](https://www.digitalocean.com/community/tutorials/how-to-serve-django-applications-with-apache-and-mod_wsgi-on-ubuntu-16-04) may be helpful.

## Configuration

The following environment variable must be configured in a `.env`
file.  This file must be available on all nodes, and all nodes must be
uniformly configured.

### Basic

 - `SECRET_KEY` Necessary configuration parameter to ensure application security.  See above.
 - `ALLOWED_HOSTS` Comma-separated list of allowed host names, see also [Django documentation](https://docs.djangoproject.com/en/5.1/ref/settings/#allowed-hosts)
 - `URL_ROOT` Path from domain root to app, normally `/`, but may be `/tcbot` or similar based on your configuration.
 - `DATA_DIR` Absolute path to directory containing stored repositories.

### GitHub Application

The following must be collected from GitHub's application management UI.

 - `GITHUB_APP_KEY` Separate newlines with literal `\n`
 - `GITHUB_APP_ID`
 - `GITHUB_APP_CLIENT_SECRET`

### Gum Tree

 - `GUMTREE_DIR` Location of GumTree binaries.  Note, the example configuration will only need `TODO` replaced with the path to the installation directory.
 - `GUMTREE_TREE_SITTER_DIR` Location of the GumTree treesitter parser.  Note, the example configuration will only need `TODO` replaced with the path to the installation directory.

### Database

 - `DATABASE_URL` a [`dj-database-url`](https://pypi.org/project/dj-database-url/) compatible database URL.  Make sure to install the relevant database drivers (necessary packages for MySQL are available with the `mysql` optional dependency set).

### Task Queue

 - `CELERY_BROKER_URL` URL for Redis access.  See also [Celery documentation](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html#broker-redis).  It is recommended that you use a database number specific to this project.
