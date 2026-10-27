.PHONY: scan-secrets

scan-secrets:
	uv run python scripts/scan_secrets.py
