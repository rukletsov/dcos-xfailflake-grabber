# dcos-xfailflake-grabber

A python script for collecting muted tests from DC/OS repositories.

At the moment of writing, two DC/OS repositories, OSS and EE, use the `xfailflake` attribute to mark specific tests as expected to fail. This script collects such tests from a given repo and presents the resulted output in various ways, for example pushes to a database. Internal CI monitoring dashboards in Mesosphere rely on this script.

Usage: `python xfailflake-grabber.py <action> <repository> <branch> [args]`

Example: `python3 xfailflake_grabber.py redshift https://github.com/dcos/dcos.git master`

## Dependencies

The only non-standard dependency is postgres database driver: `psycopg2-binary` or equivalent. Both python2 and python3 are supported.

## Components

The task of visualising CI state with respect to `xfailflake`d tests can be divided into several logical stages: extract data, serve or store, visualize. This script focuses on the first two (the third is implemented via [redash.io dashboards](https://app.redash.io/)).

The script has three components:
  * CLI, see "xfailflake_grabber.py";
  * Data extraction from a given repo, see "repo_utils.py";
  * Data representation, see "postgres_redshift.py", "json_formats.py", "Dockerfile".

### CLI

Built-in help should be sufficient: `python3 xfailflake_grabber.py help`.

### Data extraction

At the moment the script relies on a specific regex pattern to extract the test name and the associated meta data from the source code. Note that the provided repository must be cloneable; an access token can be provided via the `GITHUB_TOKEN` env var.

The regex approach has a number of limitations, see below. A more robust alternative is to use `pytest` to collect data for us, e.g., during nightly CI runs.

### Data representation

Data extracted from the previous steps can be presented in several ways, which a user determines via the `<action>` command line parameter:
  * `dump` - JSON blob is printed to stdout;
  * `serve` -  JSON blob in [redash format](https://redash.io/help/data-sources/querying-urls) is served via a built-in python webserver;
  * `redshift` - data is pushed to a redshift database, which configuration is partially hard-coded and partially passed via `POSTGRES_USER` and `POSTGRES_PASSWORD` env vars.

## Deployment

Currently at Mesosphere we use the `redshift` pipeline. The script is launched daily against both OSS and EE DC/OS repos and for all active branches and will be deployed to the internal cluster soon.

Once we migrate away from regex model to the `pytest`-based one, the script will be adjusted and deployed onto the internal CI.

## Limitations

  * Possible collisions if the test with the same name exists in the same file and repo.
  * Only works if `xfailflake` is on a test, not a fixture.
  * The order of attributes in `xfailflake` macro is important.

## Future work

  * Extract DB constants into parameters
  * Set up a DB cleaning procedure
