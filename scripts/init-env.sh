#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then echo '.env already exists; kept existing credentials.'; exit 0; fi
umask 077
python3 -c 'import secrets; print("API_KEY=" + secrets.token_hex(32))' > .env
echo 'Created .env with a random local API key.'
