
import json, time


# Bakes xfailflakes together with a timestamp and a repo, and spits out JSON.
def convert_to_default(xfailflakes, repo):
    output = {
        "timestamp": time.strftime("%Y.%m.%d %H:%M"),
        "xfailflakes": xfailflakes
    }

    return json.dumps(output)


# Redash requires particular format for JSON input,
# see https://redash.io/help/data-sources/querying-urls .
# We organise the output in three columns: "test", "ticket", "file".
def convert_to_redash(xfailflakes):
    columns = [
        {
            "name": "test",
            "type": "string",
            "friendly_name": "Test"
        },
        {
            "name": "ticket",
            "type": "string",
            "friendly_name": "JIRA ticket"
        },
        {
            "name": "file",
            "type": "string",
            "friendly_name": "File"
        },
        {
            "name": "repo",
            "type": "string",
            "friendly_name": "Repository"
        },
        {
            "name": "branch",
            "type": "string",
            "friendly_name": "Branch"
        }
    ]

    output = {
        "columns": columns,
        "rows": xfailflakes
    }

    return json.dumps(output)
