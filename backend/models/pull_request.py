from dataclasses import dataclass, field


# Represents a Pull Request inside our application
@dataclass
class PullRequestEvent:

    # What happened? opened, closed, synchronize, etc.
    action: str

    # Repository information
    repository_name: str

    # Pull Request information
    pr_number: int
    title: str
    body: str

    # Who opened the PR?
    author: str

    # Branches
    head_branch: str
    base_branch: str

    # Timestamps
    created_at: str
    updated_at: str

    # Link to the PR on GitHub
    html_url: str

    # Files changed by the PR
    changed_files: list[str] = field(default_factory=list)