from backend.models.pull_request import PullRequestEvent


def parse_payload(payload: dict) -> PullRequestEvent:
    """
    Convert a GitHub webhook payload
    into our internal PullRequestEvent object.
    """

    # Shortcuts
    pr = payload["pull_request"]
    repo = payload["repository"]
    sender = payload["sender"]

    return PullRequestEvent(

        # Event information
        action=payload["action"],

        # Repository
        repository_name=repo["name"],

        # Pull Request
        pr_number=pr["number"],
        title=pr["title"],
        body=pr["body"] or "",

        # Author
        author=sender["login"],

        # Branches
        head_branch=pr["head"]["ref"],
        base_branch=pr["base"]["ref"],

        # Timestamps
        created_at=pr["created_at"],
        updated_at=pr["updated_at"],

        # GitHub URL
        html_url=pr["html_url"],

        # Filled later by the GitHub API
        changed_files=[]
    )
