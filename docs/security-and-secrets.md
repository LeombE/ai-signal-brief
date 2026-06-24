# Security And Secrets

## Public Repository Rule

The public repository must not contain secrets, private migration material, or local operator paths.

## Secret Types

Never commit:

- OpenAI API keys
- Telegram bot tokens
- Telegram chat IDs
- service credentials
- private env files
- local machine identifiers
- raw logs that contain credentials

## Future GitHub Actions Rule

When automation is added later, production credentials must be configured as GitHub Secrets. Workflows should avoid printing secret-derived values and should keep delivery logs redacted.

## Telegram Rule

Telegram production output should default to an English top-three summary plus a GitHub Pages URL. DOCX attachment delivery is optional and disabled by default.

## Image Generation Rule

Image generation is not configured in Phase 1. A dedicated API key may be added later as a GitHub Secret only.