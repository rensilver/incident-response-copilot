"""Check current Markdown file/fragment links and archived Git objects offline."""

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
names = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True
).splitlines()
checked = 0
archived = 0
failures = []
for name in sorted(set(names)):
    path = ROOT / name
    if path.suffix != ".md" or not path.is_file():
        continue
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        archive = re.search(r"github\.com/[^/]+/[^/]+/blob/([a-f0-9]{40})/([^#]+)", target)
        if archive:
            commit, resource = archive.groups()
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{commit}:{unquote(resource)}"],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                failures.append({"file": name, "target": target, "error": "missing Git object"})
            archived += 1
            continue
        if "://" in target or target.startswith("mailto:"):
            continue
        resource, _, fragment = unquote(target).partition("#")
        destination = path.parent / resource if resource else path
        if not destination.exists():
            failures.append({"file": name, "target": target, "error": "missing local file"})
        elif fragment and destination.suffix == ".md":
            headings = re.findall(r"^#{1,6}\s+(.+)$", destination.read_text(), re.MULTILINE)
            slugs = [
                re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-") for heading in headings
            ]
            if fragment not in slugs:
                failures.append({"file": name, "target": target, "error": "missing heading"})
        checked += 1
summary = {"local_links": checked, "archived_git_objects": archived, "failures": failures}
print(json.dumps(summary, indent=2))
assert not failures, "Broken documentation references"
