# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in HarnessDiff, please report it by:

1. **Do NOT** open a public GitHub issue
2. Email the maintainer directly (contact information in GitHub profile)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to expect

- **Response time**: We aim to respond within 48 hours
- **Updates**: You'll receive updates on the progress of your report
- **Credit**: Security researchers who report valid vulnerabilities will be credited (unless they prefer to remain anonymous)

## Security Considerations

HarnessDiff is designed for research and testing purposes. When using it:

- **Mock Model**: The default mock model is deterministic and safe for offline use
When using OpenAI, Anthropic, or Gemini APIs, your API keys are only read from environment variables (never written to code, logs, results JSON, or traces). Trace save and `publish-results` scrub fields and substrings that look like secrets (`api_key`, `Authorization`, Bearer tokens, `AIza…` / `sk-…` keys).
- **Sandbox Layer**: Demonstrates isolation concepts but is NOT a security boundary for production use
- **Permissions Layer**: Educational demonstration of approval patterns, not a production access control system

### Not a Production Security Tool

HarnessDiff demonstrates harness engineering concepts for educational purposes. The sandbox and permissions layers show *how* these patterns work, but are not hardened for production security use cases.

For production agent systems, use proper:
- Container isolation (Docker, Firecracker, gVisor)
- OS-level permissions and SELinux/AppArmor policies
- Network segmentation
- Secrets management systems
- Audit logging and monitoring
