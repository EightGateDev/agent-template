#!/bin/bash
# Vikunja MCP server launcher — refreshes JWT, then starts @aimbitgmbh/vikunja-mcp
AGENT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
set -a; source "$AGENT_DIR/.env"; set +a

JWT=$(python3 -c "
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

export VIKUNJA_API_URL="${VIKUNJA_URL}/api/v1"
export VIKUNJA_API_TOKEN="$JWT"
exec npx -y @aimbitgmbh/vikunja-mcp "$@"
