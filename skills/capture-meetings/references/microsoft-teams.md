# Microsoft Teams

Use Outlook Calendar as discovery and OneDrive or SharePoint as artifact storage. Prefer an accessible VTT transcript over the MP4 recording. Microsoft Graph transcript access may require administrator enablement and scoped permissions; report missing access rather than attempting a workaround.

Preserve the event ID, online meeting ID, and transcript or recording artifact ID for deduplication.

## Person filter

Attendees and participants include a display name and an email address when Graph returns them. When `person` is set, map the display name to `name` and the email address to `email`, then run `meeting_params.py filter`. If a record has only one of those, pass only that field. A name-only record matches a name. An email-only record matches an email. Do not scan the transcript.
