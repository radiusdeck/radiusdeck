# Getting help with RadiusDeck

Use [GitHub Issues](https://github.com/radiusdeck/radiusdeck/issues) for questions
about installing and using RadiusDeck Community, bug reports, and suggestions.
You need a GitHub account to post. Issues and their attachments are public.
Please use English when possible so other users can find and use the answers.

## Ask a question

1. Search [existing issues](https://github.com/radiusdeck/radiusdeck/issues?q=is%3Aissue),
   including closed issues, for the same question or error message.
2. Open [Ask a question](https://github.com/radiusdeck/radiusdeck/issues/new?template=question.yml).
   If you are unsure whether something is a bug or a configuration problem,
   start with a question.
3. Give it a descriptive title and explain what you want to do, where you got
   stuck, and what you have already tried. The question is the only required
   field in the form; include environment details when they are relevant.
4. Review your text and any attachments for sensitive information, then submit
   the issue.
5. Return to the issue for replies and follow-up questions. Use GitHub's
   **Subscribe** control if needed; email notifications depend on your GitHub
   notification settings. Reply in the same issue with any requested details.
6. When the problem is resolved, say what worked and close the issue. This helps
   the next person with the same question.

For example:

> **Client added, but FreeRADIUS still reports "unknown client"**
>
> I use RadiusDeck 0.1.0 in Docker and FreeRADIUS on the host. The client appears
> in the UI after saving. Do I need to restart FreeRADIUS, and how can I check
> that both applications use the same clients.conf?

## Report a bug

Search existing issues first, then open
[Report a bug](https://github.com/radiusdeck/radiusdeck/issues/new?template=bug_report.yml).
Include:

- steps to reproduce the problem;
- what you expected and what actually happened;
- the RadiusDeck version, image tag, or source commit (write "unknown" if needed);
- how you run RadiusDeck: Docker, Docker Compose, or a local Python process;
- relevant environment details, such as the host OS, browser for UI problems,
  or FreeRADIUS version and reload method for authentication problems.

Short error messages, relevant log excerpts, and screenshots can help. If you
cannot reproduce the problem reliably, describe what happened before it occurred.
Report separate problems in separate issues.

For the README's Docker quick start, these commands show recent application
logs and container health. Replace `radiusdeck` if your container has another name:

```bash
docker logs --tail 100 radiusdeck
docker inspect --format '{{.State.Health.Status}}' radiusdeck
```

For a local Python process, use the relevant output from the terminal where
RadiusDeck is running. Review all output before sharing it.

## Share only the details needed

Remove passwords, RADIUS shared secrets, tokens, session keys, private keys,
and identifying user or network information from text and screenshots.
Share a small sanitized example rather than a complete production configuration,
`.env` file, backup, or full `docker inspect` output. Do not assume log redaction
has removed every sensitive value.

For suspected security vulnerabilities, follow [SECURITY.md](SECURITY.md) and
use the private reporting channel described there. Do not report undisclosed
vulnerabilities in public issues.

## What to expect

Support is provided by project maintainers and community contributors as time
allows, with no guaranteed response time. Answers and requests for more details
are posted in the issue comments. You do not need to post an email address.

Suggestions can be opened as a regular issue: describe the task you want to
accomplish and why the current behavior makes it difficult. For code
contributions, see [CONTRIBUTING.md](CONTRIBUTING.md).
