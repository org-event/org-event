#!/usr/bin/env python3
"""Draws the profile's stats and language cards as SVG, in the tokyonight colours.

Reads public data from the GitHub GraphQL API with GITHUB_TOKEN and writes
cards/stats.svg, cards/languages.svg and cards/streak.svg. Standard library only.
"""

import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

LOGIN = os.environ.get("CARDS_LOGIN", "org-event")
OUT = Path(__file__).resolve().parent.parent / "cards"

BG, TITLE, TEXT, ICON = "#1a1b27", "#70a5fd", "#38bdae", "#bf91f3"
WIDTH, HEIGHT = 420, 170

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if body.get("errors"):
        sys.exit(f"GraphQL errors: {body['errors']}")
    return body["data"]["user"]


def frame(title: str, inner: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{escape(title)}">
<style>text{{font:600 14px 'Segoe UI',Ubuntu,'Helvetica Neue',sans-serif}}.t{{fill:{TITLE};font-size:18px}}.l{{fill:{TEXT}}}.v{{fill:{TEXT};font-weight:700}}.n{{fill:{TEXT};font-size:12px;font-weight:400}}</style>
<rect width="{WIDTH}" height="{HEIGHT}" rx="6" fill="{BG}"/>
<text x="25" y="35" class="t">{escape(title)}</text>
{inner}
</svg>
"""


def stats_card(user: dict) -> str:
    c = user["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    rows = [
        ("Total stars", stars),
        ("Commits (last year)", c["totalCommitContributions"]),
        ("Pull requests", c["totalPullRequestContributions"]),
        ("Issues", c["totalIssueContributions"]),
        ("Contributed to", c["totalRepositoriesWithContributedCommits"]),
    ]
    inner = "".join(
        f'<circle cx="31" cy="{60 + i * 22}" r="4" fill="{ICON}"/>'
        f'<text x="45" y="{65 + i * 22}" class="l">{escape(label)}:</text>'
        f'<text x="260" y="{65 + i * 22}" class="v">{value}</text>'
        for i, (label, value) in enumerate(rows)
    )
    return frame(f"{LOGIN}'s GitHub stats", inner)


def languages_card(user: dict) -> str:
    sizes: dict[str, tuple[int, str]] = {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name, color = edge["node"]["name"], edge["node"]["color"] or ICON
            total, _ = sizes.get(name, (0, color))
            sizes[name] = (total + edge["size"], color)
    top = sorted(sizes.items(), key=lambda item: item[1][0], reverse=True)[:8]
    whole = sum(size for _, (size, _) in top) or 1
    bar, x = [], 25.0
    for _, (size, color) in top:
        width = (WIDTH - 50) * size / whole
        bar.append(f'<rect x="{x:.1f}" y="50" width="{width:.1f}" height="8" fill="{color}"/>')
        x += width
    legend = "".join(
        f'<circle cx="{31 + (i % 2) * 190}" cy="{80 + (i // 2) * 22}" r="5" fill="{color}"/>'
        f'<text x="{42 + (i % 2) * 190}" y="{85 + (i // 2) * 22}" class="n">{escape(name)} {100 * size / whole:.1f}%</text>'
        for i, (name, (size, color)) in enumerate(top)
    )
    return frame("Most used languages", '<g clip-path="inset(0 round 4px)">' + "".join(bar) + "</g>" + legend)


def streak_card(user: dict) -> str:
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [d for week in calendar["weeks"] for d in week["contributionDays"]]
    longest = run = 0
    for day in days:
        run = run + 1 if day["contributionCount"] else 0
        longest = max(longest, run)
    # Today may have nothing yet; the streak still counts up to yesterday.
    current = 0
    for i, day in enumerate(reversed(days)):
        if day["contributionCount"]:
            current += 1
        elif i > 0:
            break
    columns = [
        (calendar["totalContributions"], "Contributions", "last year"),
        (current, "Current streak", "days"),
        (longest, "Longest streak", "days, last year"),
    ]
    inner = "".join(
        f'<text x="{75 + i * 135}" y="95" text-anchor="middle" class="v" style="font-size:28px;fill:{TITLE if i == 1 else TEXT}">{value}</text>'
        f'<text x="{75 + i * 135}" y="122" text-anchor="middle" class="l">{escape(label)}</text>'
        f'<text x="{75 + i * 135}" y="142" text-anchor="middle" class="n">{escape(note)}</text>'
        for i, (value, label, note) in enumerate(columns)
    ) + "".join(f'<line x1="{142 + i * 135}" y1="60" x2="{142 + i * 135}" y2="150" stroke="{ICON}" stroke-opacity=".35"/>' for i in range(2))
    return frame("Contribution streak", inner)


def main() -> None:
    user = fetch()
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(stats_card(user))
    (OUT / "languages.svg").write_text(languages_card(user))
    (OUT / "streak.svg").write_text(streak_card(user))
    print(f"wrote the cards to {OUT}")


if __name__ == "__main__":
    main()
