export function canonicalQueueValue(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalQueueValue).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(
      key => `${JSON.stringify(key)}:${canonicalQueueValue(value[key])}`,
    ).join(',')}}`;
  }
  return JSON.stringify(value);
}

export function queueSnapshotIsConsistent(
  pages,
  { pageLimit = 100, stateRosterSha256 } = {},
) {
  if (
    !Array.isArray(pages)
    || pages.length === 0
    || !Number.isInteger(pageLimit)
    || pageLimit <= 0
    || typeof stateRosterSha256 !== 'function'
    || pages.some(page => !page || typeof page !== 'object' || !Array.isArray(page.items))
  ) {
    return false;
  }
  const first = pages[0];
  if (!Number.isInteger(first.total_count) || first.total_count <= 0) return false;

  const claims = pages.flatMap(page => page.items);
  const stateRoster = [...claims]
    .sort((left, right) => left.claim_id.localeCompare(right.claim_id))
    .map(row => ({
      claim_id: row.claim_id,
      revision: row.revision,
      state_sha256: row.state_sha256,
      operational_projection_sha256: row.operational_projection.projection_sha256,
    }));
  return pages.length === Math.ceil(first.total_count / pageLimit)
    && claims.length === first.total_count
    && new Set(claims.map(row => row.claim_id)).size === claims.length
    && stateRosterSha256(stateRoster) === first.state_roster_sha256
    && pages.every(page => page.generated_at === first.generated_at
      && canonicalQueueValue(page.corpus_identity)
        === canonicalQueueValue(first.corpus_identity)
      && page.request_sha256 === first.request_sha256
      && page.state_roster_sha256 === first.state_roster_sha256
      && page.total_count === first.total_count
      && canonicalQueueValue(page.facets) === canonicalQueueValue(first.facets));
}
