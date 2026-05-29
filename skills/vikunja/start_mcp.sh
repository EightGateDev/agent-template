#!/bin/bash
# Vikunja MCP server launcher — uses long-lived API token (tk_...) if available,
# falls back to login JWT. Long-lived token never expires; JWT lasts ~10 min.
# NOTE: @aimbitgmbh/vikunja-mcp reads VIKUNJA_URL (must include /api/v1).
#       It ignores VIKUNJA_API_URL — do NOT use that var.
AGENT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
set -a; source "$AGENT_DIR/.env"; set +a

# Ensure VIKUNJA_URL ends with /api/v1 (package requirement, README explicit)
case "$VIKUNJA_URL" in
  */api/v1|*/api/v1/) ;;
  *) VIKUNJA_URL="${VIKUNJA_URL%/}/api/v1" ;;
esac
export VIKUNJA_URL

if [ -n "$VIKUNJA_API_TOKEN" ]; then
    # Long-lived token already stored — use it directly (no login needed)
    export VIKUNJA_API_TOKEN
else
    # Fallback: get fresh login JWT (expires ~10 min, sufficient for setup)
    VIKUNJA_API_TOKEN=$(python3 -c "
import urllib.request, json, os, sys
url = os.environ.get('VIKUNJA_URL','').rstrip('/')
u = os.environ.get('VIKUNJA_USERNAME','')
p = os.environ.get('VIKUNJA_PASSWORD','')
if not u or not url:
    print(os.environ.get('VIKUNJA_TOKEN',''), end=''); sys.exit(0)
try:
    req = urllib.request.Request(url+'/api/v1/login',
        data=json.dumps({'username':u,'password':p}).encode(),
        headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=5) as r:
        print(json.loads(r.read())['token'], end='')
except:
    print(os.environ.get('VIKUNJA_TOKEN',''), end='')
" 2>/dev/null)
    export VIKUNJA_API_TOKEN
fi

exec npx -y @aimbitgmbh/vikunja-mcp "$@"
