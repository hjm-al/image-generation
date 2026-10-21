# Security Policy

## Supported Versions

Security fixes target the current `main` branch. Until versioned releases are
published, older commits and copied local installations are not separately
supported.

## Report a Vulnerability

Do not publish API keys, private image contents, account details, or an
unpatched exploit in a public issue.

Use the repository's **Security** tab and choose **Report a vulnerability** when
private vulnerability reporting is available. If that option is unavailable,
open a minimal public issue asking the maintainer to establish a private channel;
include no sensitive details in that issue.

Useful reports include:

- the affected script and command;
- the Python and operating-system versions;
- whether the issue requires a live provider or reproduces offline;
- a minimal sanitized request, response shape, or test case;
- the security impact and any suggested mitigation.

## Scope

Examples of in-scope issues include:

- a path that exposes an API key in output, metadata, logs, or process arguments;
- unintended overwrite of an image or sidecar;
- an unsafe URL-download path or credential leak in the helper;
- a batch preflight bypass that can create an unintended request or output;
- a dependency or CI configuration that grants unnecessary repository access.

Provider outages, model quality, pricing disputes, and whether a third-party
service is trustworthy are outside this repository's security scope. Report those
to the provider.

## Safe Usage

- Set credentials only in environment variables.
- Review prompts and image paths before sending confidential material to a
  third-party API.
- Run `--dry-run` before unfamiliar or high-impact requests.
- Keep `.env`, generated outputs, private inputs, and local quality records out
  of Git.
- Prefer base64 responses when a provider would require credentialed image
  downloads.
