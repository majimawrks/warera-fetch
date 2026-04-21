# articles / art

**Endpoint:** `article.getArticlesPaginated` (default); `article.getArticleById` or `article.getArticleLiteById` when `--id`/`--url` given
**Auth:** optional
**Status:** existing, enrich
**Aliases:** `articles`, `art`

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--id ID` | string | no | — | Fetch single article by ID (`article.getArticleById`) |
| `--url URL` | string | no | — | Fetch single article by URL (extracts articleId) |
| `--lite` | flag | no | false | Use `article.getArticleLiteById` instead of full (only when `--id`/`--url` given) |
| `--article-type TYPE` | string | no | `last` | Feed type: `daily`, `weekly`, `top`, `my`, `subscriptions`, `last`. Maps to `type` API param. |
| `--limit N` | int | no | 10 | Max articles |
| `--cursor CURSOR` | string | no | — | Pagination cursor |
| `--language LANG+` | string[] | no | — | ISO codes e.g. `--language id en` |

## Resolution logic

**Single article** (when `--id` or `--url` given):
1. Extract articleId from URL if `--url` used.
2. Call `article.getArticleLiteById` if `--lite`, else `article.getArticleById`.

**Feed** (no `--id`/`--url`):
1. Build params: `type` from `--article-type` (default `"last"`), `limit`, `cursor`, `languages` from `--language`.
2. If `--uname`: resolve to userId via `search.searchAnything`, use to filter results client-side (API has no author param).
3. If `--country`: resolve to countryId client-side author filter (API has no countryId param).
4. Call `article.getArticlesPaginated`.
5. **Always include `type`** in the call — spec audit confirmed omitting it causes 400.

## Output shape

Feed: JSON `{items: [...], nextCursor: ...}`.
Single: JSON article object.

`--humanize`: ✅ Existing `humanize_articles` function (date / author / title / stripped body, `---` separator between articles). Works for both feed and single article.

## Examples

```sh
python fetch.py articles
python fetch.py art --article-type top --limit 5
python fetch.py articles --language id en
python fetch.py articles --id 67eb5cba...
python fetch.py articles --url https://app.warera.io/article/67eb5cba... --lite
```

## Backward-compat notes

All existing invocations must keep working. The `--type` default of `"last"` preserves current behavior.
