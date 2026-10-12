"""Build the Sites capability into a deterministic static-asset-first fixture."""
from pathlib import Path


def test_sites_build_declares_public_readonly_before_entry_without_worker_rewriting(tmp_path, monkeypatch):
    tools = Path(__file__).resolve().parents[2] / 'casepath' / 'tools'
    monkeypatch.syspath_prepend(str(tools))
    import build_sites_site as sites

    public = tmp_path / 'public'
    (public / 'assets').mkdir(parents=True)
    # Keep inventory validation active against the explicit miniature fixture.
    inventory = frozenset({'index.html', 'corpus.html', 'assets/autonomous-entry-v1.js'})
    monkeypatch.setattr(sites.build_static_site, 'PUBLIC_INVENTORY', inventory)
    monkeypatch.setattr(sites.build_static_site, 'PUBLIC_DIRECTORIES', frozenset({'assets'}))
    (public / 'index.html').write_text('<!doctype html><html><head><script>window.fixtureBoot=true;</script></head>'
                                      '<body><script src="assets/autonomous-entry-v1.js"></script></body></html>')
    (public / 'corpus.html').write_text('<html>Original fixture collection</html>')
    (public / 'assets' / 'autonomous-entry-v1.js').write_text('/* Fixture entry */')
    monkeypatch.setattr(sites, 'REPOSITORY', tmp_path)
    monkeypatch.setattr(sites, 'PUBLIC_ROOT', public)
    monkeypatch.setattr(sites, 'OUTPUT_ROOT', tmp_path / 'dist')
    sites.build()
    built = (tmp_path / 'dist' / 'client' / 'index.html').read_text()
    assert built.count(sites.API_CONFIGURATION) == 1
    assert 'window.CASEPATH_PUBLIC_READ_ONLY = true' in sites.API_CONFIGURATION
    assert built.index(sites.API_CONFIGURATION) < built.index('<script>window.fixtureBoot')
    assert (tmp_path / 'dist' / 'server' / 'index.js').read_bytes() == sites.WORKER_SOURCE.read_bytes()
    # A repeated build emits exactly one capability declaration.
    sites.build()
    assert (tmp_path / 'dist' / 'client' / 'index.html').read_text() == built
