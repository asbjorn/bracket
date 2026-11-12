#!/usr/bin/env bash
# Deploys the pushed branch to production through Dokploy, with a database backup first.
#
#   ./deploy/dokploy/deploy.sh
#
# Steps: check that the local branch is pushed → back up the database on the server →
# trigger the Dokploy deploy (Dokploy clones the branch and builds the image) → wait until it
# finishes and the app is healthy → show the deployed commit and the database migration.
# The Dokploy API is called on the server itself (the UI is behind Cloudflare Access); the API key
# is read there from ~/.bashrc and never printed. No secrets are printed by this script.
set -euo pipefail

SERVER="${BRACKET_DEPLOY_SERVER:-asbjorn@s-tistelvegen.fellinghaug.com}"
COMPOSE_ID="${BRACKET_DOKPLOY_COMPOSE_ID:-C7chPPxGVIGMQ8ubYSG3-}"
APP="${BRACKET_DOKPLOY_APP:-compose-generate-back-end-feed-zbl9eq}"
BRANCH="${BRACKET_DEPLOY_BRANCH:-phase-0-norwegian}"
SITE="${BRACKET_SITE:-https://bracket.fellinghaug.com}"

cd "$(git rev-parse --show-toplevel)"
git fetch -q origin "$BRANCH"
if [ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/$BRANCH")" ]; then
  echo "The local branch differs from origin/$BRANCH: push first (Dokploy deploys what is pushed)." >&2
  exit 1
fi
echo "Deploying $(git log --oneline -1)"

# Runs a Dokploy API call on the server: dokploy <GET|POST> <endpoint> [json]
dokploy() {
  # ssh joins the arguments into one string for the remote shell: quote them
  ssh -o BatchMode=yes "$SERVER" "bash -s $(printf '%q ' "$@")" <<'REMOTE'
eval "$(grep -E '^export DOKPLOY_(API_KEY|URL)=' ~/.bashrc)"
base="http://localhost:3000"
curl -s -m 5 -o /dev/null "$base/api/settings.health" || base="$DOKPLOY_URL"
if [ "$1" = GET ]; then
  curl -sS -m 60 -H "x-api-key: $DOKPLOY_API_KEY" "$base/api/$2"
else
  curl -sS -m 600 -X POST -H "x-api-key: $DOKPLOY_API_KEY" -H 'content-type: application/json' \
    -d "$3" "$base/api/$2"
fi
REMOTE
}

# Only the deploy status: the full compose response contains the environment (secrets)
deploy_status() {
  dokploy GET "compose.one?composeId=$COMPOSE_ID" | python3 -c '
import json, sys
d = json.load(sys.stdin)
deps = sorted(d.get("deployments", []), key=lambda x: x.get("createdAt", ""))
print(d.get("composeStatus"), deps[-1].get("status") if deps else None, len(deps))'
}

echo "1/4 Backing up the database"
ssh -o BatchMode=yes "$SERVER" "set -e; mkdir -p ~/backups/bracket
  f=~/backups/bracket/bracket-\$(date +%Y%m%d-%H%M%S)-before-deploy.dump
  docker exec $APP-postgres-1 pg_dump -U bracket -d bracket -Fc > \"\$f\"
  test -s \"\$f\" && echo \"\$f\" > ~/backups/bracket/LATEST && echo \"    \$f\""

echo "2/4 Starting the Dokploy deploy"
before=$(deploy_status | awk '{print $3}')
dokploy POST compose.deploy "{\"composeId\":\"$COMPOSE_ID\"}" \
  | python3 -c 'import json, sys; print("    " + json.load(sys.stdin).get("message", "?"))'

echo "3/4 Waiting for the build and restart"
for _ in $(seq 1 90); do
  read -r compose_status last_status count < <(deploy_status)
  if [ "$count" -gt "$before" ] && [ "$compose_status" != running ] && [ "$last_status" != running ]; then
    break
  fi
  sleep 10
done
echo "    Dokploy: $compose_status / last deployment: $last_status"
[ "$last_status" = done ] || { echo "Deploy failed: check the Dokploy deployment log." >&2; exit 1; }

health=starting
for _ in $(seq 1 40); do
  health=$(ssh -o BatchMode=yes "$SERVER" "docker inspect -f '{{.State.Health.Status}}' $APP-bracket-1")
  [ "$health" = healthy ] && break
  sleep 3
done
echo "    App container: $health"
[ "$health" = healthy ] || { echo "The app is not healthy." >&2; exit 1; }

echo "4/4 Checking"
ssh -o BatchMode=yes "$SERVER" "
  echo \"    Deployed commit: \$(git -c safe.directory='*' -C /etc/dokploy/compose/$APP/code log --oneline -1)\"
  echo \"    Database migration: \$(docker exec $APP-postgres-1 psql -U bracket -d bracket -tAc 'select version_num from alembic_version')\""
echo "    $SITE/api/ping → $(curl -sS -m 10 "$SITE/api/ping")"
echo "Done."
