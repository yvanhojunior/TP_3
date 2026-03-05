import pandas as pd
 

def assign(df):
    """
    Assign contributor roles (developer, reviewer, merger, reporter, commenter, reactor)
    based on individual activity rows.
    Returns: df_roles with one row per (project, contributor) and counts per role.

    Full paper : https://link.springer.com/content/pdf/10.1007/s10664-021-10061-x.pdf
    """

    df_activities = normalize_activities(df)

    role_funcs = {
        "developer": is_developer,
        "reviewer": is_reviewer,
        "merger": is_merger,
        "reporter": is_reporter,
        "commenter": is_commenter,
        "reactor": is_reactor,
    }

    # Initialize an empty dataframe with project + contributor
    df_roles = (
        df_activities[["actor.login", "repository.name"]]
        .drop_duplicates()
        .copy()
    )

    # For each role, compute counts
    for role, func in role_funcs.items():
        # Boolean mask per row
        mask = df_activities.apply(func, axis=1)

        # Count occurrences per contributor + project
        counts = (
            df_activities.loc[mask]
            .groupby(["actor.login", "repository.name"])
            .size()
            .reset_index(name=role)
        )

        # Merge counts into df_roles
        df_roles = df_roles.merge(counts, on=["actor.login", "repository.name"], how="left")

    # Fill missing counts with 0
    df_roles = df_roles.fillna(0).astype({r: int for r in role_funcs})

    df_roles = df_roles.rename(columns={
        'actor.login': 'contributor',
        'repository.name': 'project'
    })

    return df_roles.sort_values(['project', 'contributor']).reset_index(drop=True)

def is_developer(row):
    actor_id = row["actor.id"]

    # User − [authors] → Commit
    # A user pushed a commit
    if row["activity"] == "PushCommits":
        return True

    # User − [authors] → Pull
    # A user opened a pull request
    if row["activity"] == "OpenPullRequest":
        return True

    # u1:User − [authors] → Comment − [hasParent] → Pull ← [authors] − u1:User
    # A user commented on their own pull request
    if row["activity"] == "CommentPullRequest":
        for action in row.get("actions", []):
            details = action.get("details", {})
            pull_request = details.get("pull_request")
            if pull_request:
                author_id = pull_request["author"].get("id")
                if actor_id == author_id:
                    return True

    return False

def is_reviewer(row):
    actor_id = row["actor.id"]

    # User − [authors] → Review
    # A user reviewed a pull request
    if row["activity"] == "ReviewPullRequest":
        for action in row.get("actions", []):
            if action.get("action") == "CreatePullRequestReview":
                return True

    # u1:User − [authors] → Comment − [hasParent] → Review ← [authors] − u1:User
    # A user commented on their own review
    # ! We can't check review authorship, so we assume it's their own review if they comment on a pull request they didn't author
    # check the activity hitosry for each review/author
    if row["activity"] == "ReviewPullRequest":
        for action in row.get("actions", []):
            if action.get("action") == "CreatePullRequestReviewComment":
                details = action.get("details", {})
                pull_request = details.get("pull_request", {})
                pr_author_id = pull_request.get("author", {}).get("id")

                if pr_author_id and pr_author_id != actor_id:
                    return True

    return False

def is_merger(row):
    # User − [authors] → Commit ← [mergedAs] − Pull
    # A user pushed a commit that results from merging a pull request
    if row["activity"] == "MergePullRequest":
        return True
        
    return False

def is_reporter(row):
    actor_id = row["actor.id"]

    # User − [authors] → Issue
    # A user opened an issue
    if row["activity"] == "OpenIssue":
        return True

    # u1:User − [authors] → Comment − [hasParent] → Issue ← [authors] − u1:User
    # A user commented on their own issue
    if row["activity"] == "CommentIssue":
        for action in row.get("actions", []):
            details = action.get("details", {})
            issue = details.get("issue", {})
            issue_author_id = issue.get("author", {}).get("id")

            if issue_author_id and issue_author_id == actor_id:
                return True

    return False

def is_commenter(row):
    actor_id = row["actor.id"]

    # u1:User − [authors] → Comment − [hasParent] → Issue ← [authors] − u2:User
    # A user commented on an issue opened by someone else
    if row["activity"] == "CommentIssue":
        for action in row.get("actions", []):
            details = action.get("details", {})
            issue = details.get("issue", {})
            issue_author_id = issue.get("author", {}).get("id")

            if issue_author_id and issue_author_id != actor_id:
                return True

    return False

def is_reactor(row):
    # u1:User − [reacts] → Issue/Pull/Review/Comment ← [authors] − u2:User
    # A user reacted to content (issue, PR, review, or comment) created by someone else.
    # This role cannot be inferred from the current dataset.
    # We need to fetch additional data from the GitHub API.
    
    return False

def normalize_activities(df):
    """
    Flatten nested dict columns so roles.assign() can work directly.
    Minimal transformation only.
    """
    df = df.copy()

    df["actor.login"] = df["actor"].apply(lambda x: x.get("login") if isinstance(x, dict) else None)
    df["actor.id"] = df["actor"].apply(lambda x: x.get("id") if isinstance(x, dict) else None)

    df["repository.name"] = df["repository"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)
    df["repository.id"] = df["repository"].apply(lambda x: x.get("id") if isinstance(x, dict) else None)

    return df
