# Import our parser
from backend.parsers.github_parser import parse_payload


# Fake GitHub payload for testing
payload = {
    "action": "opened",

    "repository": {
        "name": "spectre-impact"
    },

    "sender": {
        "login": "abubakr"
    },

    "pull_request": {
        "number": 5,
        "title": "Database Migration",
        "body": "Update customer database",

        "head": {
            "ref": "feature/database"
        },

        "base": {
            "ref": "main"
        },

        "created_at": "2026-08-02T18:00:00Z",
        "updated_at": "2026-08-02T18:05:00Z",

        "html_url": "https://github.com/example/repo/pull/5"
    }
}


# Convert GitHub payload into our model
event = parse_payload(payload)

# Print the result
print(event)
