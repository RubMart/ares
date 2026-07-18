/** Max search query length (chars). Keep in sync with API `MAX_QUERY_LENGTH` (default 500). */
const parsed = Number.parseInt(
  process.env.NEXT_PUBLIC_MAX_QUERY_LENGTH ?? '500',
  10,
)

export const MAX_QUERY_LENGTH =
  Number.isFinite(parsed) && parsed > 0 ? parsed : 500
