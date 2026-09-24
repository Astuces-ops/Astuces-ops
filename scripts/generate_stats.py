#!/usr/bin/env python3
"""Génère les cartes SVG du profil GitHub (stats, langages, activité).

Aucune dépendance externe : bibliothèque standard uniquement.
Variables d'environnement :
  GH_USER   login GitHub (défaut : Astuces-ops)
  GH_TOKEN  jeton GitHub (GITHUB_TOKEN de l'Action ou PAT METRICS_TOKEN)
  OUT_DIR   dossier de sortie (défaut : profile)
  DEMO=1    rendu avec des données fictives, pour tester sans réseau
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "Astuces-ops")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT_DIR = os.environ.get("OUT_DIR", "profile")

BG = "#1a1b27"
BORDER = "#2b2d42"
TITLE = "#58A6FF"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
ACCENT = "#8A2BE2"
FONT = "'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    name
    login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        forkCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    if payload.get("errors"):
        raise SystemExit(f"Erreur GraphQL : {payload['errors']}")
    return payload["data"]["user"]


def fetch():
    if not TOKEN:
        raise SystemExit("GH_TOKEN manquant.")
    cursor, repos, user = None, [], None
    while True:
        data = graphql({"login": USER, "cursor": cursor})
        user = user or data
        repos.extend(data["repositories"]["nodes"])
        page = data["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]

    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            color = edge["node"]["color"] or MUTED
            size, _ = langs.get(name, (0, color))
            langs[name] = (size + edge["size"], color)

    cc = user["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    return {
        "name": user["name"] or user["login"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "forks": sum(r["forkCount"] for r in repos),
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "langs": langs,
        "days": [(d["date"], d["contributionCount"]) for d in days],
    }


def demo():
    today = date.today()
    return {
        "name": "Issa Ibrahim Moubarak",
        "stars": 42, "forks": 9, "repos": 37, "followers": 58,
        "prs": 64, "issues": 21, "commits": 812, "contributions": 1034,
        "langs": {
            "Python": (520000, "#3572A5"), "Java": (310000, "#b07219"),
            "JavaScript": (220000, "#f1e05a"), "PHP": (120000, "#4F5D95"),
            "Shell": (60000, "#89e051"), "HTML": (40000, "#e34c26"),
        },
        "days": [((today - timedelta(days=i)).isoformat(), (i * 7) % 11)
                 for i in range(364, -1, -1)],
    }


def card(width, height, title, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{BG}" stroke="{BORDER}"/>'
        f'<text x="24" y="36" font-family="{FONT}" font-size="18" font-weight="600" '
        f'fill="{TITLE}">{escape(title)}</text>{body}</svg>'
    )


def fmt(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def stats_svg(s):
    rows = [
        ("Étoiles reçues", s["stars"]),
        ("Commits (12 mois)", s["commits"]),
        ("Pull requests", s["prs"]),
        ("Issues", s["issues"]),
        ("Dépôts publics et privés", s["repos"]),
        ("Abonnés", s["followers"]),
    ]
    body = ""
    for i, (label, value) in enumerate(rows):
        y = 72 + i * 22
        body += (
            f'<circle cx="30" cy="{y - 5}" r="3" fill="{ACCENT}"/>'
            f'<text x="44" y="{y}" font-family="{FONT}" font-size="14" fill="{TEXT}">{escape(label)}</text>'
            f'<text x="300" y="{y}" font-family="{FONT}" font-size="14" font-weight="700" '
            f'fill="{TEXT}" text-anchor="end">{fmt(value)}</text>'
        )
    total = fmt(s["contributions"])
    body += (
        f'<circle cx="400" cy="112" r="52" fill="none" stroke="{BORDER}" stroke-width="8"/>'
        f'<circle cx="400" cy="112" r="52" fill="none" stroke="{TITLE}" stroke-width="8" '
        f'stroke-dasharray="245 82" stroke-linecap="round" transform="rotate(-90 400 112)"/>'
        f'<text x="400" y="116" font-family="{FONT}" font-size="24" font-weight="700" '
        f'fill="{TEXT}" text-anchor="middle">{total}</text>'
        f'<text x="400" y="186" font-family="{FONT}" font-size="12" fill="{MUTED}" '
        f'text-anchor="middle">contributions sur 12 mois</text>'
    )
    return card(495, 205, "Statistiques GitHub", body)


def langs_svg(s):
    top = sorted(s["langs"].items(), key=lambda kv: kv[1][0], reverse=True)[:6]
    total = sum(v[0] for _, v in top) or 1
    body, x = "", 24.0
    bar_w = 302
    body += f'<clipPath id="b"><rect x="24" y="54" width="{bar_w}" height="10" rx="5"/></clipPath><g clip-path="url(#b)">'
    for _, (size, color) in top:
        w = bar_w * size / total
        body += f'<rect x="{x:.2f}" y="54" width="{w + 0.5:.2f}" height="10" fill="{color}"/>'
        x += w
    body += "</g>"
    for i, (name, (size, color)) in enumerate(top):
        col, row = i % 2, i // 2
        cx, cy = 30 + col * 150, 96 + row * 32
        body += (
            f'<circle cx="{cx}" cy="{cy - 4}" r="5" fill="{color}"/>'
            f'<text x="{cx + 12}" y="{cy}" font-family="{FONT}" font-size="13" fill="{TEXT}">'
            f'{escape(name)} <tspan fill="{MUTED}">{100 * size / total:.1f}%</tspan></text>'
        )
    return card(350, 205, "Langages les plus utilisés", body)


def activity_svg(s, n_days=31):
    days = s["days"][-n_days:]
    w, h = 1000, 300
    left, right, top, bottom = 56, 24, 60, 48
    pw, ph = w - left - right, h - top - bottom
    peak = max((c for _, c in days), default=0)
    peak = max(4, -(-peak // 4) * 4)  # échelle ronde, multiple de 4
    step = pw / max(len(days) - 1, 1)
    pts = [(left + i * step, top + ph - ph * c / peak) for i, (_, c) in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{left},{top + ph} {line} {left + pw},{top + ph}"

    body = (
        f'<defs><linearGradient id="a" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{TITLE}" stop-opacity="0.45"/>'
        f'<stop offset="1" stop-color="{TITLE}" stop-opacity="0"/></linearGradient></defs>'
    )
    for k in range(5):
        y = top + ph * k / 4
        val = peak * (4 - k) // 4
        body += (
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}" stroke="{BORDER}"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" font-family="{FONT}" font-size="11" '
            f'fill="{MUTED}" text-anchor="end">{val}</text>'
        )
    body += f'<polygon points="{area}" fill="url(#a)"/>'
    body += f'<polyline points="{line}" fill="none" stroke="{TITLE}" stroke-width="2.5" stroke-linejoin="round"/>'
    for i, ((d, c), (x, y)) in enumerate(zip(days, pts)):
        body += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#FFFFFF"><title>{d} : {c}</title></circle>'
        if (i % 5 == 0 and len(days) - 1 - i > 2) or i == len(days) - 1:
            body += (
                f'<text x="{x:.1f}" y="{h - 20}" font-family="{FONT}" font-size="11" '
                f'fill="{MUTED}" text-anchor="middle">{d[8:10]}/{d[5:7]}</text>'
            )
    return card(w, h, f"Contributions des {n_days} derniers jours", body)


def main():
    s = demo() if os.environ.get("DEMO") == "1" else fetch()
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, svg in (
        ("stats.svg", stats_svg(s)),
        ("top-langs.svg", langs_svg(s)),
        ("activity.svg", activity_svg(s)),
    ):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"écrit : {OUT_DIR}/{name}")


if __name__ == "__main__":
    sys.exit(main())
