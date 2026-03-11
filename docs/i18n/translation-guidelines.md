# Translation Guidelines

## Source of truth
- Keep `panel/src/i18n/locales/en/common.json` as the source file.
- Add new keys only in the English file first.
- Use stable dot notation keys (`topnav.logout`, `auth.login.title`).
- Each `common.json` must contain:
  - `_meta.code`
  - `_meta.native_label`
  - `_meta.flag`
  - `_meta.default_timezone`
  - `_meta.timezones` (list of allowed IANA timezones for this language; must include `_meta.default_timezone`)
  - `strings` object with all translation keys.

## Adding a new language
- Create `panel/src/i18n/locales/<code>/common.json`.
- Copy the structure from `en/common.json`.
- Fill `_meta` (including flag code for `flag-icons` like `de`, `gb`, `us`, default timezone, and timezone options).
- Translate `strings`.
- No code change is required; language is auto-discovered.

## Placeholders
- Use `{token}` placeholders for dynamic values.
- Keep placeholders identical in every language.

## Time and locale
- UI language comes from `user.preferences.language`.
- UI time formatting uses `user.preferences.timezone`.
- Use `panel/src/utils/datetime/formatDateTime.ts` for date/time formatting.

## Review rules
- Do not change keys during translation.
- Keep casing and punctuation aligned with the source.
- Prefer short labels for buttons and chips.
- Do not translate or rename `_meta` field names.
