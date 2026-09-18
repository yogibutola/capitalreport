/**
 * Pure URL predicates used by the app shell to decide which chrome/nav state to
 * show. Kept free of Angular imports so they can be unit-tested with plain vitest.
 */

function urlPath(url: string): string {
  return url.split('?')[0].split('#')[0];
}

/** Public marketing pages rendered without the signed-in app chrome. */
export function isMarketingUrl(url: string): boolean {
  const path = urlPath(url);
  return path === '/' || path === '/book-demo';
}

/**
 * The club "Manage" tab is the overview hub at /admin only. Its league and
 * tournament sub-pages have their own tabs (see isLeaguesUrl / isTournamentsUrl)
 * and /admin/season has the "Active Season" tab, so none of those light up Manage.
 */
export function isManageUrl(url: string): boolean {
  return urlPath(url) === '/admin';
}

/** "Leagues" tab: the league list, the create form, and every league detail page. */
export function isLeaguesUrl(url: string): boolean {
  const path = urlPath(url);
  return (
    path === '/admin/leagues' ||
    path === '/admin/create-league' ||
    path.startsWith('/admin/league/')
  );
}

/** "Tournaments" tab: the tournament list, the create form, and every tournament detail page. */
export function isTournamentsUrl(url: string): boolean {
  const path = urlPath(url);
  return (
    path === '/admin/tournaments' ||
    path === '/admin/create-tournament' ||
    path.startsWith('/admin/tournament/')
  );
}
