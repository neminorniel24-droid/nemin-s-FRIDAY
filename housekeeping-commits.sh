#!/bin/bash
set -e

echo "--- 1/9: rename package.json ---"
python3 - << 'PYEOF'
import json
with open('package.json') as f:
    data = json.load(f)
data['name'] = 'nemiii'
data['description'] = 'Voice-controlled PC assistant with a holographic orb UI'
with open('package.json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
PYEOF
git add -A
git commit -m "fix: rename package.json from leftover fork name to nemiii"
git push origin main

echo "--- 2/9: pin node engine ---"
python3 - << 'PYEOF'
import json
with open('package.json') as f:
    data = json.load(f)
data['engines'] = {"node": ">=20"}
with open('package.json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
PYEOF
git add -A
git commit -m "chore: specify minimum Node version in package.json"
git push origin main

echo "--- 3/9: .gitattributes ---"
cat > .gitattributes << 'EOF'
* text=auto eol=lf
*.bat text eol=crlf
*.ps1 text eol=crlf
EOF
git add -A
git commit -m "chore: add .gitattributes for consistent line endings across WSL/Windows"
git push origin main

echo "--- 4/9: gitignore additions ---"
cat >> .gitignore << 'EOF'
.DS_Store
Thumbs.db
*.log
EOF
git add -A
git commit -m "chore: add OS-generated file patterns to .gitignore"
git push origin main

echo "--- 5/9: CHANGELOG.md ---"
cat > CHANGELOG.md << 'EOF'
# Changelog

## Unreleased
- Gmail read-only integration (check_email)
- Expanded /health to report per-integration config status
- Boss greeting

## Earlier
- Memory across conversation turns
- Gesture-based PC control (swipe to switch tabs / minimize)
- Spoken-only info actions: news, Wikipedia, currency, GitHub, project status
- WhatsApp news, YouTube playback
- Fixed: open_folder PowerShell variable-expansion bug
- Fixed: voice replies now reflect real action success/failure
- Fixed: media keys via WScript.Shell instead of unreliable .NET SendKeys
- Weather + local news dashboard
- Auto-launch on Windows login, desktop shortcut with custom icon
EOF
git add -A
git commit -m "docs: add CHANGELOG.md"
git push origin main

echo "--- 6/9: README badge ---"
python3 - << 'PYEOF'
with open('README.md') as f:
    content = f.read()
badge = '![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)\n\n'
marker = '# NEMIII\n'
if marker in content and badge not in content:
    content = content.replace(marker, marker + '\n' + badge, 1)
with open('README.md', 'w') as f:
    f.write(content)
PYEOF
git add -A
git commit -m "docs: add license badge to README"
git push origin main

echo "--- 7/9: bug report template ---"
mkdir -p .github/ISSUE_TEMPLATE
cat > .github/ISSUE_TEMPLATE/bug_report.md << 'EOF'
---
name: Bug report
about: Something isn't working
---

**What happened**

**What you expected**

**Steps to reproduce**

**Backend /health output** (helps rule out config issues fast)
EOF
git add -A
git commit -m "chore: add bug report issue template"
git push origin main

echo "--- 8/9: feature request template ---"
cat > .github/ISSUE_TEMPLATE/feature_request.md << 'EOF'
---
name: Feature request
about: Suggest a new action or capability
---

**What should Nemiii be able to do**

**Why**
EOF
git add -A
git commit -m "chore: add feature request issue template"
git push origin main

echo "--- 9/9: known limitations update ---"
python3 - << 'PYEOF'
with open('NEMIII_SETUP.md') as f:
    content = f.read()
marker = "## Known v1 limitations / natural next steps"
addition = "\n- Gmail requires a manual one-time OAuth setup (see the Gmail section above) — it's not automatic like the other integrations.\n- Conversation memory is in-process only; it resets whenever the backend restarts.\n"
if marker in content and "Gmail requires a manual one-time OAuth setup" not in content:
    content = content.replace(marker, marker + addition, 1)
with open('NEMIII_SETUP.md', 'w') as f:
    f.write(content)
PYEOF
git add -A
git commit -m "docs: update known limitations for current feature set"
git push origin main

echo "Done — 9 commits pushed."
git log --oneline -9
