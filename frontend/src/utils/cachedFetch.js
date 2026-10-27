// Dashboard components each ask for the same endpoints. Share one request per
// URL (and reuse it for a short time) instead of fetching it once per component.
const CACHE_MS = 60 * 1000;
const cache = new Map();

export const cachedFetch = (url) => {
  const hit = cache.get(url);
  let request;
  if (hit && Date.now() - hit.at < CACHE_MS) {
    request = hit.request;
  } else {
    request = fetch(url);
    cache.set(url, { at: Date.now(), request });
    // Never keep a failed request around.
    request.then((res) => { if (!res.ok) cache.delete(url); }, () => cache.delete(url));
  }
  // Each caller reads its own copy of the body.
  return request.then((res) => res.clone());
};
