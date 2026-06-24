# Security Policy

## Supported Status

This project is in early skeleton phase. No production automation is shipped yet.

## Secrets Policy

Do not commit secrets or private operator data. This includes:

- API keys
- Telegram bot tokens
- Telegram chat IDs
- local env files
- private migration files
- generated private reports
- screenshots containing credentials
- local machine paths

Future production secrets must be stored in GitHub Secrets or local ignored environment files.

## Reporting Security Issues

Do not open public issues containing secrets, tokens, chat IDs, private paths, or sensitive logs. Report security concerns through a private channel controlled by the repository owner.

## Safe Logs And Artifacts

Run metadata must never contain secret values. Delivery records may include status, timestamps, and artifact names, but not credentials or raw API responses containing sensitive data.