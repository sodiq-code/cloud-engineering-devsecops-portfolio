# Dev Container LocalStack Setup

## Quick Start

1. Copy the example environment file:
   - `cp .env.example .env`
2. Open `.env` and set `LOCALSTACK_AUTH_TOKEN` to your rotated LocalStack Pro token.
3. Start the dev container stack:
   - `docker compose up -d`

## Security Note

If any token was previously committed, rotate it immediately in your LocalStack account and replace local copies before running the stack.
