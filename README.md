# Type Changes Bot

## Requirements

### Database

A database accessible from the head node and all worker nodes is required.

### GumTree

Support for AST diff is provided by
[GumTree](https://github.com/GumTreeDiff/gumtree), particularly the
[Tree Sitter
parsers](https://github.com/GumTreeDiff/tree-sitter-parser).  These
must be installed, and available on each worker node.  The optional
dependency group `gumtree_support` will ensure that Tree
Sitter-related Python dependencies are available in the worker's
environment.

### Redis

A running Redis-compatible server accessible from head node and all
worker nodes is required.

## Server Installation

### WSGI Configuration

Configure your head node's web server as normal.

### Running Workers

Modify the file `typechange-worker.service` so that it fits with your
installation of the application.  Install it into
`/etc/systemd/system`, execute `systemctl daemon-reload` to notify
systemd of the changes, and start and enable with `systemctl enable --now typechange-worker`.

## Configuration

The following environment variable must be configured in a `.env`
file.  This file must be available on all nodes, and all nodes must be
uniformly configured.

### Basic

 - `SECRET_KEY` Generate with `python manage.py shell -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
 - `ALLOWED_HOSTS`
 - `DATA_DIR` Data directory, should be a fully-qualified path

### GitHub Application

The following must be collected from GitHub's application management UI.

 - `GITHUB_APP_KEY`
 - `GITHUB_APP_ID`
 - `GITHUB_APP_CLIENT_SECRET`

### Gum Tree

 - `GUMTREE_DIR` Location of the Gumtree Diff installation binary
   directory.  This directory should contain an executable `gumtree`
   file.
 - `GUMTREE_TREE_SITTER_DIR` Location of the cloned
   [`gumtree/tree-sitter-parser`](https://github.com/GumTreeDiff/tree-sitter-parser)

### Database

 - `DATABASE_URL` a
   [`dj-database-url`](https://pypi.org/project/dj-database-url/)
   compatible database URL.  Make sure to install the relevant
   database drivers.

### Task Queue

 - `CELERY_BROKER_URL`
 - `CELERY_TASK_TRACK_STARTED` (default True)
 - `CELERY_TASK_TIME_LIMIT` (default 30 minutes)
