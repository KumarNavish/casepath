import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { constants as fsConstants } from 'node:fs';
import { fileURLToPath } from 'node:url';


const REPOSITORY_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const EXPECTED_BUILT_STATIC_PATHS = Object.freeze([
  '_headers',
  'assets/artifact-canvas.css',
  'assets/artifact-canvas.js',
  'assets/claims-workspace-v1.css',
  'assets/claims-workspace-v1.js',
  'assets/foundation-live.css',
  'assets/foundation-live.js',
  'assets/insurance-protocol-v1.css',
  'assets/insurance-protocol-v1.js',
  'assets/live-v16-stability.js',
  'assets/live-v16-viewer-fix.css',
  'assets/live-v16.css',
  'assets/live-v16.js',
  'assets/live-v17-continuity.css',
  'assets/live-v17.css',
  'assets/live-v17.js',
  'assets/live-v18-handoff.js',
  'assets/live-v18-insertion-guard.js',
  'assets/live-v18-law-normalize.js',
  'assets/live-v18.css',
  'assets/live-v18.js',
  'assets/live-v19-active-stage.js',
  'assets/live-v19.css',
  'assets/live-v20-focus.css',
  'assets/live-v20-focus.js',
  'assets/process-story.css',
  'assets/process-story.js',
  'deployment.json',
  'index.html',
  'release.json',
]);

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

export function canonicalizeInstalledDistributions(values) {
  if (!Array.isArray(values)) throw new Error('installed distribution roster must be an array');
  return [...new Set(values)].sort((left, right) => {
    const leftCasefold = left.toLowerCase();
    const rightCasefold = right.toLowerCase();
    if (leftCasefold < rightCasefold) return -1;
    if (leftCasefold > rightCasefold) return 1;
    return left < right ? -1 : left > right ? 1 : 0;
  });
}

export function validateDataRootProvenanceContract(value) {
  const accepted = new Set([
    'casepath.local-durable-data-provenance/1.2.0',
    'casepath.local-durable-data-provenance/1.3.0',
  ]);
  if (!accepted.has(value)) {
    throw new Error('candidate durable data-root provenance contract is unsupported');
  }
  return value;
}

function exactKeys(value, expected, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} must be an object`);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (JSON.stringify(actual) !== JSON.stringify(wanted)) throw new Error(`${label} keys are not closed: ${JSON.stringify(actual)}`);
}

export function validateRegistryCutoverAuthority(provenanceOrigin, dataRoot) {
  const registryCutover = provenanceOrigin?.legacy_registry_cutover;
  exactKeys(registryCutover, ['applied', 'mode_lease_receipt', 'mode_lease_receipt_sha256', 'mode_roster_sha256', 'open_handle_count_after_freeze', 'policy'], 'candidate registry cutover authority');
  const modeLease = registryCutover.mode_lease_receipt;
  if (registryCutover.applied === true) {
    exactKeys(modeLease, ['contract', 'destination', 'legacy_registry', 'legacy_registry_identity', 'mode_roster', 'mode_roster_sha256', 'registry_inventory_sha256', 'receipt_sha256'], 'candidate registry mode lease');
    exactKeys(modeLease.legacy_registry_identity, ['device', 'inode'], 'candidate registry mode lease identity');
    const leaseSemantic = { ...modeLease };
    delete leaseSemantic.receipt_sha256;
    if (!Array.isArray(modeLease.mode_roster) || modeLease.mode_roster.length === 0) {
      throw new Error('candidate registry mode lease roster is empty');
    }
    for (const row of modeLease.mode_roster) {
      exactKeys(row, ['kind', 'mode', 'path'], 'candidate registry mode lease row');
    }
    const modePaths = modeLease.mode_roster.map((row) => row.path);
    if (modeLease.contract !== 'casepath.legacy-registry-mode-lease/1.0.0'
      || modeLease.destination !== dataRoot
      || modeLease.legacy_registry !== path.join(path.dirname(provenanceOrigin.legacy_database_path), 'artifact-registry')
      || !Number.isInteger(modeLease.legacy_registry_identity.device)
      || modeLease.legacy_registry_identity.device < 0
      || !Number.isInteger(modeLease.legacy_registry_identity.inode)
      || modeLease.legacy_registry_identity.inode < 0
      || modePaths[0] !== '.'
      || new Set(modePaths).size !== modePaths.length
      || canonicalJson(modePaths.slice(1)) !== canonicalJson([...modePaths.slice(1)].sort())
      || modeLease.mode_roster.some((row) => !['directory', 'file'].includes(row.kind)
        || !Number.isInteger(row.mode) || row.mode < 0 || row.mode > 0o7777
        || typeof row.path !== 'string' || row.path.length === 0)
      || modeLease.mode_roster_sha256 !== sha256(Buffer.from(canonicalJson(modeLease.mode_roster), 'utf8'))
      || modeLease.registry_inventory_sha256 !== provenanceOrigin.legacy_registry_inventory_sha256
      || modeLease.receipt_sha256 !== sha256(Buffer.from(canonicalJson(leaseSemantic), 'utf8'))
      || registryCutover.mode_lease_receipt_sha256 !== modeLease.receipt_sha256
      || registryCutover.mode_roster_sha256 !== modeLease.mode_roster_sha256) {
      throw new Error('candidate registry mode lease is invalid');
    }
  } else if (modeLease !== null || registryCutover.mode_lease_receipt_sha256 !== null) {
    throw new Error('candidate empty registry cutover carries a mode lease');
  }
  if (typeof registryCutover.applied !== 'boolean'
    || !/^[0-9a-f]{64}$/.test(registryCutover.mode_roster_sha256 || '')
    || registryCutover.open_handle_count_after_freeze !== 0
    || registryCutover.policy !== 'write_bits_removed_and_zero_open_handles_through_atomic_publication') {
    throw new Error('candidate registry cutover authority is invalid');
  }
}

async function requireRegularFile(candidate, root) {
  const resolved = path.resolve(candidate);
  const relative = path.relative(root, resolved);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error(`candidate path escapes repository: ${candidate}`);
  const stat = await fs.lstat(resolved);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error(`candidate path is not a regular file: ${candidate}`);
  if (await fs.realpath(resolved) !== resolved) throw new Error(`candidate path has a symlinked ancestor: ${candidate}`);
  return { resolved, relative: relative.split(path.sep).join('/') };
}

async function requireCanonicalDirectory(candidate, label, expectedMode = null) {
  const resolved = path.resolve(candidate);
  const metadata = await fs.lstat(resolved);
  if (!metadata.isDirectory() || metadata.isSymbolicLink() || await fs.realpath(resolved) !== resolved) {
    throw new Error(`${label} is not a canonical non-symlink directory`);
  }
  if (expectedMode !== null && (metadata.mode & 0o7777) !== expectedMode) {
    throw new Error(`${label} mode is not canonical`);
  }
  return resolved;
}

async function executableOnPath(name) {
  for (const directory of (process.env.PATH || '').split(path.delimiter).filter(Boolean)) {
    const candidate = path.join(directory, name);
    try {
      await fs.access(candidate, 1);
      const stat = await fs.stat(candidate);
      if (stat.isFile()) return candidate;
    } catch (_) {
      // Continue through the declared executable search path.
    }
  }
  throw new Error(`${name} is required but absent from PATH`);
}

async function dirtySourceRows() {
  const raw = execFileSync('/usr/bin/git', ['status', '--porcelain=v1', '-z', '--untracked-files=all'], {
    cwd: REPOSITORY_ROOT,
    encoding: 'utf8',
  });
  const entries = raw.split('\0');
  const relativePaths = new Set();
  for (let index = 0; index < entries.length;) {
    const entry = entries[index];
    index += 1;
    if (!entry) continue;
    const status = entry.slice(0, 2);
    let candidate = entry.slice(3);
    if (status.includes('R') || status.includes('C')) {
      candidate = entries[index];
      index += 1;
    }
    relativePaths.add(candidate);
  }
  if (!relativePaths.size) throw new Error('candidate source identity requires a nonempty working-tree set');
  const rows = [];
  for (const candidate of [...relativePaths].sort()) {
    const file = await requireRegularFile(path.join(REPOSITORY_ROOT, candidate), REPOSITORY_ROOT);
    rows.push(`${sha256(await fs.readFile(file.resolved))}  ${file.relative}`);
  }
  return rows.sort();
}

async function archiveSourceIdentity() {
  const manifestPath = path.join(REPOSITORY_ROOT, 'casepath', 'source-manifest.json');
  const manifestFile = await requireRegularFile(manifestPath, REPOSITORY_ROOT);
  const manifest = JSON.parse((await fs.readFile(manifestFile.resolved)).toString('utf8'));
  exactKeys(manifest, [
    'artifact_manifest',
    'contract',
    'file_count',
    'files',
    'gate_count',
    'gates',
    'inventory_policy',
    'release_id',
  ], 'candidate archive source manifest');
  if (manifest.contract !== 'casepath.source-manifest/2.1.0'
    || !Array.isArray(manifest.files)
    || !Number.isInteger(manifest.file_count)
    || manifest.file_count !== manifest.files.length) {
    throw new Error('candidate archive source manifest schema is invalid');
  }
  const rows = [];
  const observedPaths = [];
  for (const row of manifest.files) {
    exactKeys(row, ['executable', 'path', 'sha256', 'size_bytes'], 'candidate archive source row');
    if (typeof row.path !== 'string'
      || !/^[0-9a-f]{64}$/.test(row.sha256 || '')
      || !Number.isInteger(row.size_bytes)
      || row.size_bytes < 0
      || typeof row.executable !== 'boolean') {
      throw new Error(`candidate archive source row is malformed: ${JSON.stringify(row)}`);
    }
    const file = await requireRegularFile(path.join(REPOSITORY_ROOT, row.path), REPOSITORY_ROOT);
    const bytes = await fs.readFile(file.resolved);
    const mode = (await fs.stat(file.resolved)).mode;
    if (file.relative !== row.path
      || bytes.length !== row.size_bytes
      || sha256(bytes) !== row.sha256
      || Boolean(mode & 0o100) !== row.executable) {
      throw new Error(`candidate archive source row drifted: ${row.path}`);
    }
    observedPaths.push(row.path);
    rows.push(`${row.sha256}  ${row.path}`);
  }
  const sortedPaths = [...observedPaths].sort();
  if (new Set(observedPaths).size !== observedPaths.length
    || JSON.stringify(observedPaths) !== JSON.stringify(sortedPaths)) {
    throw new Error('candidate archive source rows are duplicated or out of order');
  }
  const runtimeCommit = (process.env.RENDER_GIT_COMMIT || process.env.CASEPATH_SOURCE_COMMIT || '')
    .trim().toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(runtimeCommit)) {
    throw new Error('candidate source archive requires an exact runtime source commit');
  }
  return {
    git: { branch: 'source-archive', head: runtimeCommit },
    rows,
  };
}

async function sourceIdentity() {
  let gitMetadata;
  try {
    gitMetadata = await fs.lstat(path.join(REPOSITORY_ROOT, '.git'));
  } catch (error) {
    if (error?.code === 'ENOENT') return archiveSourceIdentity();
    throw error;
  }
  if (gitMetadata.isSymbolicLink() || (!gitMetadata.isDirectory() && !gitMetadata.isFile())) {
    throw new Error('candidate Git metadata is not a regular worktree identity');
  }
  const branch = execFileSync('/usr/bin/git', ['branch', '--show-current'], {
    cwd: REPOSITORY_ROOT,
    encoding: 'utf8',
  }).trim() || 'detached-head';
  const head = execFileSync('/usr/bin/git', ['rev-parse', '--verify', 'HEAD'], {
    cwd: REPOSITORY_ROOT,
    encoding: 'utf8',
  }).trim();
  if (!/^[0-9a-f]{40}$/.test(head)) throw new Error('candidate Git HEAD is invalid');
  return { git: { branch, head }, rows: await dirtySourceRows() };
}

async function regularTreeRows(root) {
  const rows = [];
  async function visit(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const candidate = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`symlink forbidden in built product: ${candidate}`);
      if (entry.isDirectory()) await visit(candidate);
      else if (entry.isFile()) {
        const relative = path.relative(root, candidate).split(path.sep).join('/');
        rows.push(`${sha256(await fs.readFile(candidate))}  ${relative}`);
      } else throw new Error(`special file forbidden in built product: ${candidate}`);
    }
  }
  await visit(root);
  return rows.sort();
}

function parentDirectoryRoster(filePaths) {
  const directories = new Set();
  for (const filePath of filePaths) {
    const parts = filePath.split('/');
    for (let index = 1; index < parts.length; index += 1) {
      directories.add(parts.slice(0, index).join('/'));
    }
  }
  return [...directories].sort();
}

async function validateClosedReadOnlyTree(root, expectedFiles, label) {
  if (await fs.realpath(root) !== root) throw new Error(`${label} root has a symlinked ancestor`);
  const rootStat = await fs.lstat(root);
  if (!rootStat.isDirectory() || rootStat.isSymbolicLink() || (rootStat.mode & 0o7777) !== 0o500) {
    throw new Error(`${label} root is not a read-only directory`);
  }
  if (process.platform === 'darwin') {
    const aclListing = [
      execFileSync('/bin/ls', ['-lde', '--', root], { encoding: 'utf8' }),
      execFileSync('/bin/ls', ['-lAeR', '--', root], { encoding: 'utf8' }),
    ].join('\n');
    if (/^[bcdlps-][rwxStTs-]{9}\+/m.test(aclListing) || /^\s*\d+:\s/m.test(aclListing)) {
      throw new Error(`${label} contains an ACL-bearing entry`);
    }
  }
  const actualFiles = [];
  const actualDirectories = [];
  async function visit(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const candidate = path.join(directory, entry.name);
      const candidateStat = await fs.lstat(candidate);
      const relative = path.relative(root, candidate).split(path.sep).join('/');
      if (entry.isSymbolicLink() || candidateStat.isSymbolicLink()) {
        throw new Error(`${label} contains a symlink: ${relative}`);
      }
      if (entry.isDirectory() && candidateStat.isDirectory()) {
        if ((candidateStat.mode & 0o7777) !== 0o500) throw new Error(`${label} contains a noncanonical directory mode: ${relative}`);
        actualDirectories.push(relative);
        await visit(candidate);
      } else if (entry.isFile() && candidateStat.isFile()) {
        if (candidateStat.mode & 0o222) throw new Error(`${label} contains a writable file: ${relative}`);
        if (candidateStat.nlink !== 1) throw new Error(`${label} contains an externally linked file: ${relative}`);
        actualFiles.push(relative);
      } else {
        throw new Error(`${label} contains a special entry: ${relative}`);
      }
    }
  }
  await visit(root);
  const wantedFiles = [...expectedFiles.keys()].sort();
  const wantedDirectories = parentDirectoryRoster(wantedFiles);
  if (canonicalJson(actualFiles.sort()) !== canonicalJson(wantedFiles)
    || canonicalJson(actualDirectories.sort()) !== canonicalJson(wantedDirectories)) {
    throw new Error(`${label} file or directory roster is not exact`);
  }
  for (const [relative, expected] of expectedFiles) {
    const candidate = await requireRegularFile(path.join(root, relative), root);
    const candidateBytes = await fs.readFile(candidate.resolved);
    const candidateMode = (await fs.stat(candidate.resolved)).mode;
    const expectedMode = expected.executable ? 0o555 : 0o444;
    if (candidate.relative !== relative
      || sha256(candidateBytes) !== expected.sha256
      || candidateBytes.length !== expected.size_bytes
      || Boolean(candidateMode & 0o100) !== expected.executable
      || (candidateMode & 0o7777) !== expectedMode) {
      throw new Error(`${label} file identity differs from its authority: ${relative}`);
    }
  }
}

async function validateClosedInstalledTree(root, expectedFiles, label) {
  const rootStat = await fs.lstat(root);
  if (!rootStat.isDirectory() || rootStat.isSymbolicLink() || await fs.realpath(root) !== root
    || (rootStat.mode & 0o7777) !== 0o500) {
    throw new Error(`${label} root is not an immutable runtime-bearing directory`);
  }
  const runtimePath = path.join(root, '.runtime');
  const runtimeStat = await fs.lstat(runtimePath);
  if (!runtimeStat.isDirectory() || runtimeStat.isSymbolicLink()
    || await fs.realpath(runtimePath) !== runtimePath || (runtimeStat.mode & 0o7777) !== 0o700) {
    throw new Error(`${label} mutable runtime boundary is not canonical`);
  }
  const actualFiles = [];
  const actualDirectories = [];
  async function visit(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      if (directory === root && entry.name === '.runtime') continue;
      const candidate = path.join(directory, entry.name);
      const candidateStat = await fs.lstat(candidate);
      const relative = path.relative(root, candidate).split(path.sep).join('/');
      if (entry.isSymbolicLink() || candidateStat.isSymbolicLink()) {
        throw new Error(`${label} contains a symlink: ${relative}`);
      }
      if (entry.isDirectory() && candidateStat.isDirectory()) {
        if ((candidateStat.mode & 0o7777) !== 0o500) {
          throw new Error(`${label} contains a noncanonical directory mode: ${relative}`);
        }
        actualDirectories.push(relative);
        await visit(candidate);
      } else if (entry.isFile() && candidateStat.isFile()) {
        if (candidateStat.mode & 0o222) throw new Error(`${label} contains a writable file: ${relative}`);
        if (candidateStat.nlink !== 1) throw new Error(`${label} contains an externally linked file: ${relative}`);
        actualFiles.push(relative);
      } else {
        throw new Error(`${label} contains a special entry: ${relative}`);
      }
    }
  }
  await visit(root);
  const wantedFiles = [...expectedFiles.keys()].sort();
  const wantedDirectories = parentDirectoryRoster(wantedFiles);
  if (canonicalJson(actualFiles.sort()) !== canonicalJson(wantedFiles)
    || canonicalJson(actualDirectories.sort()) !== canonicalJson(wantedDirectories)) {
    throw new Error(`${label} non-runtime file or directory roster is not exact`);
  }
  const roster = [];
  for (const [relative, expected] of [...expectedFiles.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const candidate = await requireRegularFile(path.join(root, relative), root);
    const candidateBytes = await fs.readFile(candidate.resolved);
    const candidateMode = (await fs.stat(candidate.resolved)).mode & 0o7777;
    const expectedMode = expected.executable ? 0o555 : 0o444;
    const row = {
      executable: expected.executable,
      path: relative,
      sha256: sha256(candidateBytes),
      size_bytes: candidateBytes.length,
      mode: candidateMode,
    };
    if (candidate.relative !== relative
      || row.sha256 !== expected.sha256
      || row.size_bytes !== expected.size_bytes
      || row.mode !== expectedMode) {
      throw new Error(`${label} file identity differs from its capsule: ${relative}`);
    }
    roster.push(row);
  }
  return {
    directory_count: actualDirectories.length,
    file_count: roster.length,
    roster_sha256: sha256(Buffer.from(canonicalJson(roster), 'utf8')),
  };
}

function manifestIdentity(rows) {
  return {
    entry_count: rows.length,
    manifest_file_sha256: sha256(Buffer.from(`${rows.join('\n')}\n`, 'utf8')),
  };
}

async function readExactRegular(candidate, label) {
  const handle = await fs.open(
    candidate,
    fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW || 0),
  );
  try {
    const before = await handle.stat();
    if (!before.isFile() || before.nlink !== 1) {
      throw new Error(`${label} is not a single-link regular file: ${candidate}`);
    }
    const bytes = await handle.readFile();
    const after = await handle.stat();
    for (const field of ['dev', 'ino', 'mode', 'uid', 'gid', 'size', 'mtimeMs']) {
      if (before[field] !== after[field]) throw new Error(`${label} changed while read: ${candidate}`);
    }
    if (bytes.length !== before.size) throw new Error(`${label} size changed while read: ${candidate}`);
    return { bytes, stat: before };
  } finally {
    await handle.close();
  }
}

async function closureEntry(candidate, displayPath, label) {
  const before = await fs.lstat(candidate);
  const common = {
    gid: before.gid,
    mode: before.mode & 0o7777,
    path: displayPath,
    uid: before.uid,
  };
  if (before.isDirectory()) return { kind: 'directory', ...common };
  if (before.isFile()) {
    const observed = await readExactRegular(candidate, label);
    return {
      kind: 'file',
      ...common,
      sha256: sha256(observed.bytes),
      size_bytes: observed.bytes.length,
    };
  }
  if (before.isSymbolicLink()) {
    const target = await fs.readlink(candidate);
    const after = await fs.lstat(candidate);
    for (const field of ['dev', 'ino', 'mode', 'uid', 'gid']) {
      if (before[field] !== after[field]) throw new Error(`${label} symlink changed while read: ${candidate}`);
    }
    const targetBytes = Buffer.from(target, 'utf8');
    return {
      kind: 'symlink',
      ...common,
      target,
      target_sha256: sha256(targetBytes),
      target_size_bytes: targetBytes.length,
    };
  }
  throw new Error(`${label} contains a special entry: ${candidate}`);
}

function closeClosureSection(material) {
  return {
    ...material,
    closure_sha256: sha256(Buffer.from(canonicalJson(material), 'utf8')),
  };
}

async function closureTreeSection(root, label) {
  if (await fs.realpath(root) !== root) throw new Error(`${label} root has a symlinked path`);
  const rootStat = await fs.lstat(root);
  if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) throw new Error(`${label} root is invalid`);
  const candidates = [];
  async function visit(directory) {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    for (const item of entries) {
      const candidate = path.join(directory, item.name);
      candidates.push(candidate);
      if (item.isDirectory() && !item.isSymbolicLink()) await visit(candidate);
    }
  }
  await visit(root);
  candidates.sort((left, right) => {
    const leftRelative = path.relative(root, left).split(path.sep).join('/');
    const rightRelative = path.relative(root, right).split(path.sep).join('/');
    return leftRelative < rightRelative ? -1 : leftRelative > rightRelative ? 1 : 0;
  });
  const roster = [await closureEntry(root, '.', label)];
  for (const candidate of candidates) {
    const relative = path.relative(root, candidate).split(path.sep).join('/');
    roster.push(await closureEntry(candidate, relative, label));
  }
  return closeClosureSection({
    root,
    entry_count: roster.length,
    roster,
    roster_sha256: sha256(Buffer.from(canonicalJson(roster), 'utf8')),
  });
}

const ISOLATED_PROBE_PROGRAM = [
  'import importlib.util,json,os,platform,site,sys',
  'names=("fastapi","pydantic","uvicorn")',
  'origins={}',
  'for name in names:',
  '    spec=importlib.util.find_spec(name)',
  '    origins[name]=None if spec is None else spec.origin',
  'value={',
  '    "argv":sys.argv,',
  '    "base_exec_prefix":sys.base_exec_prefix,',
  '    "base_prefix":sys.base_prefix,',
  '    "enable_user_site":site.ENABLE_USER_SITE,',
  '    "environment":dict(os.environ),',
  '    "exec_prefix":sys.exec_prefix,',
  '    "executable":sys.executable,',
  '    "flags":{',
  '        "dont_write_bytecode":bool(sys.flags.dont_write_bytecode),',
  '        "ignore_environment":bool(sys.flags.ignore_environment),',
  '        "isolated":bool(sys.flags.isolated),',
  '        "no_site":bool(sys.flags.no_site),',
  '        "no_user_site":bool(sys.flags.no_user_site),',
  '        "safe_path":bool(sys.flags.safe_path),',
  '    },',
  '    "implementation":sys.implementation.name,',
  '    "cache_tag":sys.implementation.cache_tag,',
  '    "module_origins":origins,',
  '    "path":sys.path,',
  '    "prefix":sys.prefix,',
  '    "python_build":list(platform.python_build()),',
  '    "python_compiler":platform.python_compiler(),',
  '    "python_version":platform.python_version(),',
  '    "version_info":[',
  '        sys.version_info.major,sys.version_info.minor,sys.version_info.micro,',
  '        sys.version_info.releaselevel,sys.version_info.serial,',
  '    ],',
  '}',
  'print(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(",",":")))',
].join('\n');

function parseRecordCsv(text, label) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else quoted = false;
      } else field += character;
    } else if (character === '"' && field.length === 0) quoted = true;
    else if (character === ',') {
      row.push(field);
      field = '';
    } else if (character === '\n') {
      if (field.endsWith('\r')) field = field.slice(0, -1);
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else field += character;
  }
  if (quoted) throw new Error(`${label} has an unterminated quoted field`);
  if (field.length || row.length) {
    if (field.endsWith('\r')) field = field.slice(0, -1);
    row.push(field);
    rows.push(row);
  }
  if (rows.some(value => value.length !== 3)) throw new Error(`${label} row is malformed`);
  return rows;
}

function metadataHeader(metadataBytes, name, label) {
  const lines = metadataBytes.toString('utf8').split(/\r?\n/);
  const headerEnd = lines.findIndex(line => line === '');
  const headerLines = headerEnd < 0 ? lines : lines.slice(0, headerEnd);
  const matches = headerLines
    .filter(line => line.toLowerCase().startsWith(`${name.toLowerCase()}:`))
    .map(line => line.slice(line.indexOf(':') + 1).trim());
  if (matches.length !== 1 || !matches[0]) throw new Error(`${label} lacks one ${name} header`);
  return matches[0];
}

function normalizeDistribution(value) {
  return value.toLowerCase().replace(/[-_.]+/g, '-');
}

function compareClosureText(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

export async function captureExecutableRuntimeClosure({
  serviceRoot,
  runtimeRoot,
  executionRoot,
  pythonPath,
  sourceCommit,
}) {
  const service = path.resolve(serviceRoot);
  const runtime = path.resolve(runtimeRoot);
  const execution = path.resolve(executionRoot);
  const pythonStated = path.resolve(pythonPath);
  const venv = path.join(runtime, 'venv');
  const dataRoot = path.join(service, '.runtime', 'casepath-data-v1');
  const probeEnvironment = {
    HOME: path.join(runtime, 'home'),
    LANG: 'C.UTF-8',
    LC_ALL: 'C.UTF-8',
    PATH: [path.join(venv, 'bin'), '/usr/bin', '/bin', '/usr/sbin', '/sbin'].join(':'),
    PYTHONHASHSEED: '0',
    PYTHONNOUSERSITE: '1',
    PYTHONSAFEPATH: '1',
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONPYCACHEPREFIX: path.join(runtime, 'pycache'),
    TZ: 'UTC',
  };
  const probeCommand = [pythonStated, '-I', '-B', '-P', '-c', ISOLATED_PROBE_PROGRAM];
  const completed = spawnSync(probeCommand[0], probeCommand.slice(1), {
    cwd: execution,
    env: probeEnvironment,
    encoding: null,
    timeout: 60_000,
    maxBuffer: 4 * 1024 * 1024,
  });
  if (completed.error || completed.status !== 0 || !Buffer.isBuffer(completed.stdout)
    || !Buffer.isBuffer(completed.stderr) || completed.stderr.length !== 0) {
    throw new Error('candidate isolated runtime probe failed');
  }
  const probe = JSON.parse(completed.stdout.toString('utf8'));
  const basePrefix = path.resolve(probe.base_prefix || '');
  const sitePackages = path.join(venv, 'lib', 'python3.13', 'site-packages');
  const expectedProbePaths = [
    path.join(basePrefix, 'lib', 'python313.zip'),
    path.join(basePrefix, 'lib', 'python3.13'),
    path.join(basePrefix, 'lib', 'python3.13', 'lib-dynload'),
    sitePackages,
  ];
  const expectedEnvironmentKeys = [
    ...Object.keys(probeEnvironment),
    ...(process.platform === 'darwin' ? ['__CF_USER_TEXT_ENCODING'] : []),
  ].sort();
  exactKeys(probe, ['argv', 'base_exec_prefix', 'base_prefix', 'cache_tag', 'enable_user_site', 'environment', 'exec_prefix', 'executable', 'flags', 'implementation', 'module_origins', 'path', 'prefix', 'python_build', 'python_compiler', 'python_version', 'version_info'], 'candidate isolated probe observation');
  exactKeys(probe.flags, ['dont_write_bytecode', 'ignore_environment', 'isolated', 'no_site', 'no_user_site', 'safe_path'], 'candidate isolated probe flags');
  exactKeys(probe.module_origins, ['fastapi', 'pydantic', 'uvicorn'], 'candidate isolated probe modules');
  if (canonicalJson(probe.argv) !== canonicalJson(['-c'])
    || probe.executable !== pythonStated
    || probe.prefix !== venv || probe.exec_prefix !== venv
    || probe.base_prefix !== basePrefix || probe.base_exec_prefix !== basePrefix
    || probe.enable_user_site !== false
    || canonicalJson(probe.path) !== canonicalJson(expectedProbePaths)
    || canonicalJson(Object.keys(probe.environment || {}).sort()) !== canonicalJson(expectedEnvironmentKeys)
    || Object.entries(probeEnvironment).some(([key, value]) => probe.environment?.[key] !== value)
    || canonicalJson(probe.flags) !== canonicalJson({
      dont_write_bytecode: true,
      ignore_environment: true,
      isolated: true,
      no_site: false,
      no_user_site: true,
      safe_path: true,
    })
    || probe.implementation !== 'cpython'
    || probe.cache_tag !== 'cpython-313'
    || probe.python_version !== '3.13.9'
    || canonicalJson(probe.version_info) !== canonicalJson([3, 13, 9, 'final', 0])
    || !Array.isArray(probe.python_build) || probe.python_build.length !== 2
    || probe.python_build.some(value => typeof value !== 'string' || !value)
    || typeof probe.python_compiler !== 'string' || !probe.python_compiler) {
    throw new Error('candidate isolated runtime path or environment is not closed');
  }
  for (const origin of Object.values(probe.module_origins)) {
    if (typeof origin !== 'string') throw new Error('candidate isolated runtime module is unavailable');
    const relative = path.relative(venv, await fs.realpath(origin));
    if (relative.startsWith('..') || path.isAbsolute(relative)) {
      throw new Error('candidate isolated runtime module escaped the venv');
    }
  }
  const isolatedProbe = closeClosureSection({
    contract: 'casepath.isolated-python-path-environment-probe/1.0.0',
    command: probeCommand,
    cwd: execution,
    expected_environment: probeEnvironment,
    observation: probe,
    stdout_sha256: sha256(completed.stdout),
  });

  const capsule = await closureTreeSection(execution, 'candidate active capsule closure');
  const capsuleFiles = capsule.roster.filter(row => row.kind === 'file').map(row => row.path);
  if (capsuleFiles.filter(value => value === 'CAPSULE_RECEIPT.json').length !== 1) {
    throw new Error('candidate active capsule receipt roster is invalid');
  }
  const sitePackagesSection = await closureTreeSection(sitePackages, 'candidate complete site-packages closure');
  if (sitePackagesSection.roster.some(row => row.kind === 'symlink')) {
    throw new Error('candidate site-packages contains a symlink');
  }
  const pythonRealPath = await fs.realpath(pythonStated);
  const pythonBaseRelative = path.relative(basePrefix, pythonRealPath);
  if (pythonBaseRelative.startsWith('..') || path.isAbsolute(pythonBaseRelative)) {
    throw new Error('candidate resolved Python escaped its reported CPython base');
  }
  if (await fs.realpath(path.dirname(pythonStated)) !== path.dirname(pythonStated)) {
    throw new Error('candidate Python entry has a symlinked venv path');
  }
  const symlinkChain = [];
  const visitedLinks = new Set();
  let chainPath = pythonStated;
  for (;;) {
    const chainStat = await fs.lstat(chainPath);
    if (!chainStat.isSymbolicLink()) break;
    if (visitedLinks.has(chainPath)) throw new Error('candidate Python entry symlink chain contains a cycle');
    visitedLinks.add(chainPath);
    symlinkChain.push(await closureEntry(chainPath, chainPath, 'candidate Python entry'));
    const target = await fs.readlink(chainPath);
    chainPath = path.normalize(path.isAbsolute(target) ? target : path.join(path.dirname(chainPath), target));
  }
  if (!symlinkChain.length || await fs.realpath(chainPath) !== pythonRealPath) {
    throw new Error('candidate Python entry symlink chain is not exact');
  }
  const pythonRuntime = closeClosureSection({
    contract: 'casepath.python-runtime-identity/1.0.0',
    stated_path: pythonStated,
    symlink_chain: symlinkChain,
    symlink_chain_sha256: sha256(Buffer.from(canonicalJson(symlinkChain), 'utf8')),
    real_path: pythonRealPath,
    real_file: await closureEntry(pythonRealPath, pythonRealPath, 'candidate Python real executable'),
    base_prefix: basePrefix,
    pyvenv_config: await closureEntry(path.join(venv, 'pyvenv.cfg'), path.join(venv, 'pyvenv.cfg'), 'candidate pyvenv config'),
    interpreter_argv_flags: ['-I', '-B', '-P'],
    implementation: probe.implementation,
    cache_tag: probe.cache_tag,
    python_version: probe.python_version,
    version_info: probe.version_info,
    python_build: probe.python_build,
    python_compiler: probe.python_compiler,
  });

  const requirements = await readExactRegular(path.join(execution, 'casepath-api', 'requirements.lock'), 'candidate requirements lock');
  const lockedPins = new Map();
  for (const line of requirements.bytes.toString('utf8').split(/\r?\n/).map(value => value.trim()).filter(value => value && !value.startsWith('#'))) {
    if (line.split('==').length !== 2) throw new Error('candidate requirements lock contains an unpinned row');
    const [name, version] = line.split('==');
    const normalized = normalizeDistribution(name);
    if (!normalized || !version || lockedPins.has(normalized)) throw new Error('candidate requirements lock package row is invalid');
    lockedPins.set(normalized, version);
  }
  const distInfoEntries = sitePackagesSection.roster.filter(row => row.path.endsWith('.dist-info'));
  const directDistInfoPrefix = 'lib/python3.13/site-packages';
  if (distInfoEntries.some(row => row.kind !== 'directory' || row.path.includes('/'))) {
    throw new Error('candidate venv contains a noncanonical dist-info instance');
  }
  const instances = [];
  const ownership = new Map();
  const normalizedInstances = new Set();
  const siteFileRows = new Map(sitePackagesSection.roster
    .filter(row => row.kind === 'file')
    .map(row => [`${directDistInfoPrefix}/${row.path}`, row]));
  for (const distInfoRow of [...distInfoEntries].sort((left, right) => compareClosureText(left.path, right.path))) {
    const distInfo = path.join(sitePackages, ...distInfoRow.path.split('/'));
    const metadata = await readExactRegular(path.join(distInfo, 'METADATA'), 'candidate dist-info METADATA');
    const record = await readExactRegular(path.join(distInfo, 'RECORD'), 'candidate dist-info RECORD');
    const name = metadataHeader(metadata.bytes, 'Name', 'candidate dist-info METADATA');
    const version = metadataHeader(metadata.bytes, 'Version', 'candidate dist-info METADATA');
    const normalizedName = normalizeDistribution(name);
    if (normalizedInstances.has(normalizedName)) {
      throw new Error('candidate venv contains duplicate normalized distributions');
    }
    normalizedInstances.add(normalizedName);
    if (lockedPins.get(normalizedName) !== version) throw new Error('candidate dist-info instance differs from requirements.lock');
    const recordRelative = `${directDistInfoPrefix}/${distInfoRow.path}/RECORD`;
    const recordPaths = new Set();
    const recordRows = [];
    for (const [relative, hashField, sizeField] of parseRecordCsv(record.bytes.toString('utf8'), 'candidate dist-info RECORD')) {
      if (!relative || relative.includes('\\') || path.posix.isAbsolute(relative)) throw new Error('candidate dist-info RECORD path is invalid');
      const normalizedPath = path.posix.normalize(path.posix.join(directDistInfoPrefix, relative));
      if (normalizedPath === '..' || normalizedPath.startsWith('../')) throw new Error('candidate dist-info RECORD path escapes the venv');
      if (recordPaths.has(normalizedPath) || ownership.has(normalizedPath)) throw new Error('candidate dist-info RECORD ownership is duplicated');
      recordPaths.add(normalizedPath);
      const target = path.join(venv, ...normalizedPath.split('/'));
      const capturedTarget = siteFileRows.get(normalizedPath);
      let targetSha256;
      let targetSize;
      if (capturedTarget) {
        targetSha256 = capturedTarget.sha256;
        targetSize = capturedTarget.size_bytes;
      } else {
        const targetStat = await fs.lstat(target);
        if (!targetStat.isFile() || targetStat.isSymbolicLink()) throw new Error('candidate dist-info RECORD target is not regular');
        const targetObserved = await readExactRegular(target, 'candidate dist-info RECORD target');
        targetSha256 = sha256(targetObserved.bytes);
        targetSize = targetObserved.bytes.length;
      }
      if (normalizedPath === recordRelative) {
        if (hashField || sizeField) throw new Error('candidate dist-info RECORD self-row is not canonical');
      } else {
        const expectedHash = Buffer.from(targetSha256, 'hex').toString('base64url');
        if (hashField !== `sha256=${expectedHash}` || !/^\d+$/.test(sizeField)
          || Number(sizeField) !== targetSize) {
          throw new Error('candidate dist-info RECORD target differs from authority');
        }
      }
      ownership.set(normalizedPath, path.basename(distInfo));
      recordRows.push({ hash: hashField, path: normalizedPath, size: sizeField });
    }
    recordRows.sort((left, right) => compareClosureText(left.path, right.path));
    instances.push({
      dist_info: distInfoRow.path,
      metadata_sha256: sha256(metadata.bytes),
      name,
      normalized_name: normalizedName,
      record_entry_count: recordRows.length,
      record_roster_sha256: sha256(Buffer.from(canonicalJson(recordRows), 'utf8')),
      record_sha256: sha256(record.bytes),
      version,
    });
  }
  instances.sort((left, right) => {
    for (const key of ['normalized_name', 'version', 'dist_info']) {
      if (left[key] < right[key]) return -1;
      if (left[key] > right[key]) return 1;
    }
    return 0;
  });
  if (instances.length !== lockedPins.size
    || canonicalJson(instances.map(row => row.normalized_name)) !== canonicalJson([...lockedPins.keys()].sort())) {
    throw new Error('candidate dist-info instances are not exact');
  }
  const bootstrapUnowned = [
    'lib/python3.13/site-packages/_virtualenv.pth',
    'lib/python3.13/site-packages/_virtualenv.py',
  ].sort();
  const siteRegularPaths = new Set(sitePackagesSection.roster.filter(row => row.kind === 'file')
    .map(row => `${directDistInfoPrefix}/${row.path}`));
  const unowned = [...siteRegularPaths].filter(relative => !ownership.has(relative)).sort();
  const unownedBytecode = unowned.filter(relative => relative.includes('/__pycache__/') && relative.endsWith('.pyc'));
  for (const relative of unownedBytecode) {
    const parts = relative.split('/');
    const cacheIndex = parts.indexOf('__pycache__');
    const match = parts.at(-1).match(/^(.+)\.cpython-313(?:(?:\.opt-[12])|(?:-pytest-[0-9]+\.[0-9]+\.[0-9]+))?\.pyc$/);
    if (cacheIndex < 0 || !match) throw new Error('candidate venv contains noncanonical unowned bytecode');
    const source = [...parts.slice(0, cacheIndex), `${match[1]}.py`].join('/');
    if (!ownership.has(source) && source !== `${directDistInfoPrefix}/_virtualenv.py`) {
      throw new Error('candidate venv contains unowned bytecode without source authority');
    }
  }
  const allowedUnowned = new Set([...bootstrapUnowned, ...unownedBytecode]);
  if (unowned.length !== allowedUnowned.size || unowned.some(relative => !allowedUnowned.has(relative))) {
    throw new Error('candidate venv contains an unowned non-bootstrap file');
  }
  const pthRelative = 'lib/python3.13/site-packages/_virtualenv.pth';
  const pth = await readExactRegular(path.join(venv, ...pthRelative.split('/')), 'candidate _virtualenv.pth');
  if (!pth.bytes.equals(Buffer.from('import _virtualenv', 'utf8'))) throw new Error('candidate _virtualenv.pth is not exact');
  const injectionPaths = sitePackagesSection.roster.map(row => row.path).filter(relative => {
    const lowered = relative.toLowerCase();
    const basename = path.posix.basename(lowered);
    const parts = lowered.split('/');
    return lowered.endsWith('.egg-link') || parts.some(part => part.endsWith('.egg'))
      || lowered.includes('.egg-info/') || lowered.endsWith('.egg-info')
      || basename.startsWith('__editable__') || basename === 'direct_url.json'
      || basename === 'easy-install.pth' || (lowered.endsWith('.pth') && relative !== '_virtualenv.pth')
      || parts.some(part => ['.git', '.hg', '.svn'].includes(part))
      || parts.some(part => ['sitecustomize', 'usercustomize'].includes(part)
        || part.startsWith('sitecustomize.') || part.startsWith('usercustomize.'))
      || lowered.includes('casepath-eval') || lowered.includes('casepath_eval');
  });
  if (injectionPaths.length) throw new Error('candidate venv contains an injection or editable-install artifact');
  const ownershipRows = [...ownership.entries()].sort(([left], [right]) => compareClosureText(left, right))
    .map(([relative, distInfo]) => ({ dist_info: distInfo, path: relative }));
  const distributions = instances.map(row => `${row.name}==${row.version}`).sort((left, right) => {
    const folded = compareClosureText(left.toLowerCase(), right.toLowerCase());
    return folded || compareClosureText(left, right);
  });
  const pthStat = pth.stat;
  const distributionIntegrity = closeClosureSection({
    contract: 'casepath.python-distribution-record-closure/1.0.0',
    site_packages: sitePackages,
    locked_pins: [...lockedPins.entries()].sort(([left], [right]) => compareClosureText(left, right))
      .map(([name, version]) => ({ name, version })),
    dist_info_instance_count: instances.length,
    dist_info_instances: instances,
    dist_info_instances_sha256: sha256(Buffer.from(canonicalJson(instances), 'utf8')),
    record_owned_path_count: ownershipRows.length,
    record_ownership: ownershipRows,
    record_ownership_sha256: sha256(Buffer.from(canonicalJson(ownershipRows), 'utf8')),
    allowed_unowned_bytecode_count: unownedBytecode.length,
    allowed_unowned_bytecode_sha256: sha256(Buffer.from(canonicalJson(unownedBytecode), 'utf8')),
    bootstrap_unowned_paths: bootstrapUnowned,
    bootstrap_unowned_paths_sha256: sha256(Buffer.from(canonicalJson(bootstrapUnowned), 'utf8')),
    virtualenv_pth: {
      path: pthRelative,
      mode: pthStat.mode & 0o7777,
      uid: pthStat.uid,
      gid: pthStat.gid,
      sha256: sha256(pth.bytes),
      size_bytes: pth.bytes.length,
      exact_utf8: 'import _virtualenv',
    },
    installed_distributions: distributions,
    installed_distributions_sha256: sha256(Buffer.from(canonicalJson(distributions), 'utf8')),
    provenance_boundary: 'installed_bytes_and_dist_info_RECORD_sha256_only;original_wheel_archive_hashes_not_captured',
  });

  if (!/^[0-9a-f]{40}$/.test(sourceCommit || '')) throw new Error('candidate runtime source commit is invalid');
  const childEnvironment = {
    HOME: path.join(runtime, 'home'),
    LANG: 'C.UTF-8',
    LC_ALL: 'C.UTF-8',
    PATH: [path.join(venv, 'bin'), '/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin'].join(':'),
    PYTHONHASHSEED: '0',
    PYTHONNOUSERSITE: '1',
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONPYCACHEPREFIX: path.join(runtime, 'pycache'),
    PYTHONSAFEPATH: '1',
    SOURCE_DATE_EPOCH: '1786406400',
    TMPDIR: path.join(runtime, 'tmp'),
    TZ: 'UTC',
    CASEPATH_MODEL_MODE: 'deterministic_reference',
    CASEPATH_SOURCE_COMMIT: sourceCommit,
    CASEPATH_DB_PATH: path.join(dataRoot, 'casepath.db'),
    CASEPATH_ARTIFACT_REGISTRY_PATH: path.join(dataRoot, 'artifact-registry'),
    CASEPATH_LOCAL_STATIC_ROOT: path.join(execution, 'casepath-public'),
    CASEPATH_LOCAL_RUNTIME_RECEIPT: path.join(runtime, 'runtime-boot-receipt.json'),
    LANGSMITH_TRACING: 'false',
    LANGCHAIN_TRACING: 'false',
    LANGCHAIN_TRACING_V2: 'false',
  };
  const serviceArgv = [
    pythonStated, '-I', '-B', '-P', '-m', 'uvicorn', 'casepath_api.app:app',
    '--app-dir', path.join(execution, 'casepath-api'),
    '--host', '127.0.0.1', '--port', '4173', '--no-access-log',
  ];
  const permutationBootstrap = 'import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_path(sys.argv.pop(1),run_name="__main__")';
  const permutationEnvironment = {
    HOME: path.join(runtime, 'home'),
    LANG: 'C.UTF-8',
    LC_ALL: 'C.UTF-8',
    PATH: [path.join(venv, 'bin'), '/usr/bin', '/bin', '/usr/sbin', '/sbin'].join(':'),
    PYTHONHASHSEED: '0',
    PYTHONNOUSERSITE: '1',
    PYTHONSAFEPATH: '1',
    PYTHONDONTWRITEBYTECODE: '1',
    TZ: 'UTC',
  };
  const permutationHelper = path.join(execution, 'casepath-qa', 'production-projection-permutation-v1.py');
  const launchContext = closeClosureSection({
    contract: 'casepath.closed-launch-context/1.0.0',
    service: {
      argv: serviceArgv,
      cwd: service,
      app_dir: path.join(execution, 'casepath-api'),
      environment: childEnvironment,
      environment_sha256: sha256(Buffer.from(canonicalJson(childEnvironment), 'utf8')),
    },
    permutation_subprocess: {
      argv: [
        pythonStated, '-B', '-I', '-P', '-c', permutationBootstrap,
        path.join(execution, 'casepath-api'), permutationHelper,
      ],
      cwd: service,
      environment: permutationEnvironment,
      environment_sha256: sha256(Buffer.from(canonicalJson(permutationEnvironment), 'utf8')),
      helper: await closureEntry(permutationHelper, permutationHelper, 'candidate permutation helper'),
    },
  });
  const sections = {
    capsule,
    distribution_integrity: distributionIntegrity,
    isolated_probe: isolatedProbe,
    launch_context: launchContext,
    python_runtime: pythonRuntime,
    site_packages: sitePackagesSection,
  };
  const subordinate = Object.fromEntries(Object.entries(sections).sort(([left], [right]) => compareClosureText(left, right))
    .map(([name, section]) => [name, section.closure_sha256]));
  const material = {
    contract: 'casepath.executable-runtime-closure/1.1.0',
    claim_boundary: 'exact_active_capsule_python_entry_real_executable_isolated_path_environment_and_complete_site_packages;cpython_stdlib_tree_and_original_wheel_archives_not_captured',
    sections,
    subordinate_closure_sha256: subordinate,
  };
  return { ...material, closure_sha256: sha256(Buffer.from(canonicalJson(material), 'utf8')) };
}

function validateTreeClosure(section, label) {
  const baseKeys = ['root', 'entry_count', 'roster', 'roster_sha256', 'closure_sha256'];
  exactKeys(section, baseKeys, label);
  if (!Array.isArray(section.roster) || section.entry_count !== section.roster.length
    || section.roster_sha256 !== sha256(Buffer.from(canonicalJson(section.roster), 'utf8'))
    || typeof section.root !== 'string' || !path.isAbsolute(section.root)) {
    throw new Error(`${label} roster is invalid`);
  }
  const paths = [];
  for (const row of section.roster) {
    const common = ['gid', 'kind', 'mode', 'path', 'uid'];
    if (row.kind === 'directory') exactKeys(row, common, `${label} directory row`);
    else if (row.kind === 'file') exactKeys(row, [...common, 'sha256', 'size_bytes'], `${label} file row`);
    else if (row.kind === 'symlink') exactKeys(row, [...common, 'target', 'target_sha256', 'target_size_bytes'], `${label} symlink row`);
    else throw new Error(`${label} row kind is invalid`);
    if (typeof row.path !== 'string' || !row.path
      || !Number.isInteger(row.mode) || row.mode < 0 || row.mode > 0o7777
      || !Number.isInteger(row.uid) || row.uid < 0 || !Number.isInteger(row.gid) || row.gid < 0) {
      throw new Error(`${label} row metadata is invalid`);
    }
    if (row.kind === 'file' && (!/^[0-9a-f]{64}$/.test(row.sha256 || '')
      || !Number.isInteger(row.size_bytes) || row.size_bytes < 0)) throw new Error(`${label} file row is invalid`);
    if (row.kind === 'symlink' && (typeof row.target !== 'string'
      || row.target_sha256 !== sha256(Buffer.from(row.target, 'utf8'))
      || row.target_size_bytes !== Buffer.byteLength(row.target, 'utf8'))) throw new Error(`${label} symlink row is invalid`);
    paths.push(row.path);
  }
  const expectedPaths = [...paths].sort((left, right) => {
    if (left === '.') return right === '.' ? 0 : -1;
    if (right === '.') return 1;
    return left < right ? -1 : left > right ? 1 : 0;
  });
  if (paths[0] !== '.' || new Set(paths).size !== paths.length
    || canonicalJson(paths) !== canonicalJson(expectedPaths)) throw new Error(`${label} paths are not canonical`);
  const semantic = { ...section };
  delete semantic.closure_sha256;
  if (section.closure_sha256 !== sha256(Buffer.from(canonicalJson(semantic), 'utf8'))) throw new Error(`${label} self-hash is invalid`);
}

function validateExecutableRuntimeClosure(value, label) {
  exactKeys(value, ['contract', 'claim_boundary', 'sections', 'subordinate_closure_sha256', 'closure_sha256'], label);
  if (value.contract !== 'casepath.executable-runtime-closure/1.1.0'
    || value.claim_boundary !== 'exact_active_capsule_python_entry_real_executable_isolated_path_environment_and_complete_site_packages;cpython_stdlib_tree_and_original_wheel_archives_not_captured') {
    throw new Error(`${label} contract or claim boundary is invalid`);
  }
  const sectionNames = ['capsule', 'distribution_integrity', 'isolated_probe', 'launch_context', 'python_runtime', 'site_packages'];
  exactKeys(value.sections, sectionNames, `${label} sections`);
  exactKeys(value.subordinate_closure_sha256, sectionNames, `${label} subordinate hashes`);
  validateTreeClosure(value.sections.capsule, `${label} capsule`);
  validateTreeClosure(value.sections.site_packages, `${label} site-packages`);
  exactKeys(value.sections.python_runtime, ['contract', 'stated_path', 'symlink_chain', 'symlink_chain_sha256', 'real_path', 'real_file', 'base_prefix', 'pyvenv_config', 'interpreter_argv_flags', 'implementation', 'cache_tag', 'python_version', 'version_info', 'python_build', 'python_compiler', 'closure_sha256'], `${label} Python runtime`);
  exactKeys(value.sections.launch_context, ['contract', 'service', 'permutation_subprocess', 'closure_sha256'], `${label} launch context`);
  exactKeys(value.sections.launch_context.service, ['argv', 'cwd', 'app_dir', 'environment', 'environment_sha256'], `${label} service launch`);
  exactKeys(value.sections.launch_context.permutation_subprocess, ['argv', 'cwd', 'environment', 'environment_sha256', 'helper'], `${label} permutation launch`);
  exactKeys(value.sections.isolated_probe, ['contract', 'command', 'cwd', 'expected_environment', 'observation', 'stdout_sha256', 'closure_sha256'], `${label} isolated probe`);
  exactKeys(value.sections.distribution_integrity, ['contract', 'site_packages', 'locked_pins', 'dist_info_instance_count', 'dist_info_instances', 'dist_info_instances_sha256', 'record_owned_path_count', 'record_ownership', 'record_ownership_sha256', 'allowed_unowned_bytecode_count', 'allowed_unowned_bytecode_sha256', 'bootstrap_unowned_paths', 'bootstrap_unowned_paths_sha256', 'virtualenv_pth', 'installed_distributions', 'installed_distributions_sha256', 'provenance_boundary', 'closure_sha256'], `${label} distribution integrity`);
  if (value.sections.python_runtime.contract !== 'casepath.python-runtime-identity/1.0.0'
    || value.sections.launch_context.contract !== 'casepath.closed-launch-context/1.0.0'
    || value.sections.isolated_probe.contract !== 'casepath.isolated-python-path-environment-probe/1.0.0'
    || value.sections.distribution_integrity.contract !== 'casepath.python-distribution-record-closure/1.0.0') {
    throw new Error(`${label} subordinate contract is invalid`);
  }
  for (const name of sectionNames) {
    const section = value.sections[name];
    const semantic = { ...section };
    const sectionSha = semantic.closure_sha256;
    delete semantic.closure_sha256;
    if (!/^[0-9a-f]{64}$/.test(sectionSha || '')
      || sectionSha !== sha256(Buffer.from(canonicalJson(semantic), 'utf8'))
      || value.subordinate_closure_sha256[name] !== sectionSha) {
      throw new Error(`${label} subordinate closure is invalid: ${name}`);
    }
  }
  const semantic = { ...value };
  delete semantic.closure_sha256;
  if (value.closure_sha256 !== sha256(Buffer.from(canonicalJson(semantic), 'utf8'))) throw new Error(`${label} self-hash is invalid`);
  return value;
}

function validateBootRuntimeClosure(value, label) {
  exactKeys(value, ['contract', 'baseline', 'baseline_closure_sha256', 'phases', 'phase_closure_equality'], label);
  if (value.contract !== 'casepath.boot-runtime-closure/1.0.0'
    || value.phase_closure_equality !== true || !Array.isArray(value.phases)
    || value.phases.length !== 3) throw new Error(`${label} schema is invalid`);
  const baseline = validateExecutableRuntimeClosure(value.baseline, `${label} baseline`);
  if (value.baseline_closure_sha256 !== baseline.closure_sha256) throw new Error(`${label} baseline hash is invalid`);
  const expectedPhases = ['after_sync', 'before_child', 'after_ready'];
  value.phases.forEach((phase, index) => {
    exactKeys(phase, ['phase', 'closure_sha256', 'subordinate_closure_sha256'], `${label} phase`);
    exactKeys(phase.subordinate_closure_sha256, Object.keys(baseline.subordinate_closure_sha256), `${label} phase subordinate hashes`);
    if (phase.phase !== expectedPhases[index]
      || phase.closure_sha256 !== baseline.closure_sha256
      || canonicalJson(phase.subordinate_closure_sha256) !== canonicalJson(baseline.subordinate_closure_sha256)) {
      throw new Error(`${label} phase closure drifted`);
    }
  });
  return baseline;
}

export function requireWorkspaceRosterPolicy({
  attestedStateRosterSha256,
  liveStateRosterSha256,
  allowValidatedWorkspaceJournalAdvance = false,
}) {
  if (typeof allowValidatedWorkspaceJournalAdvance !== 'boolean') {
    throw new Error('allowValidatedWorkspaceJournalAdvance must be boolean');
  }
  if (!/^[0-9a-f]{64}$/.test(attestedStateRosterSha256 || '')
    || !/^[0-9a-f]{64}$/.test(liveStateRosterSha256 || '')) {
    throw new Error('candidate workspace roster identity is invalid');
  }
  const changed = attestedStateRosterSha256 !== liveStateRosterSha256;
  if (changed && !allowValidatedWorkspaceJournalAdvance) {
    throw new Error('candidate live workspace roster differs from its boot attestation');
  }
  return { changed };
}

async function captureApiBootReceipt(
  builtRows,
  sourceIdentity,
  { required, allowValidatedWorkspaceJournalAdvance },
) {
  const configured = process.env.CASEPATH_QA_API_BOOT_RECEIPT;
  if (!configured) {
    if (required) throw new Error('CASEPATH_QA_API_BOOT_RECEIPT is required');
    return null;
  }
  const resolved = path.resolve(configured);
  const authorityManifestPath = path.join(REPOSITORY_ROOT, 'casepath', 'source-manifest.json');
  const authorityManifestBytes = await fs.readFile(authorityManifestPath);
  const configuredServiceRoot = process.env.CASEPATH_QA_SERVICE_ROOT;
  if (required && !configuredServiceRoot) {
    throw new Error('CASEPATH_QA_SERVICE_ROOT is required with an installed boot receipt');
  }
  const serviceRoot = configuredServiceRoot
    ? path.resolve(configuredServiceRoot)
    : REPOSITORY_ROOT;
  if (configuredServiceRoot) {
    if (!path.isAbsolute(configuredServiceRoot)
      || await fs.realpath(serviceRoot) !== serviceRoot) {
      throw new Error('candidate service root must be an absolute non-symlink path');
    }
    const serviceRootStat = await fs.lstat(serviceRoot);
    if (!serviceRootStat.isDirectory() || serviceRootStat.isSymbolicLink()
      || (serviceRootStat.mode & 0o7777) !== 0o500
      || path.basename(serviceRoot) !== sha256(authorityManifestBytes)) {
      throw new Error('candidate service root is not content-addressed by the source manifest');
    }
    const installedManifest = await requireRegularFile(
      path.join(serviceRoot, 'casepath', 'source-manifest.json'),
      serviceRoot,
    );
    if (!(await fs.readFile(installedManifest.resolved)).equals(authorityManifestBytes)) {
      throw new Error('candidate service root manifest differs from source authority');
    }
  }
  const runtimeRoot = path.join(serviceRoot, '.runtime', 'casepath-dev-v2');
  await requireCanonicalDirectory(runtimeRoot, 'candidate runtime root', 0o700);
  const expectedReceiptPath = path.join(serviceRoot, '.runtime', 'casepath-dev-v2', 'runtime-boot-receipt.json');
  if (resolved !== expectedReceiptPath) throw new Error('candidate API boot receipt path is not canonical');
  const bootReceiptFile = await requireRegularFile(resolved, serviceRoot);
  const bytes = await fs.readFile(bootReceiptFile.resolved);
  const receipt = JSON.parse(bytes.toString('utf8'));
  const legacyReceiptKeys = ['contract', 'boot_id', 'ready_at_utc', 'prior_boot_receipt_file_sha256', 'url', 'topology', 'launcher', 'process', 'environment', 'source', 'runtime', 'static', 'attestation', 'receipt_sha256'];
  const receiptKeysFor = contract => contract === 'casepath.local-runtime-boot/2.2.0'
    ? [...legacyReceiptKeys, 'runtime_closure']
    : legacyReceiptKeys;
  exactKeys(receipt, receiptKeysFor(receipt.contract), 'candidate API boot receipt');
  exactKeys(receipt.launcher, ['path', 'sha256', 'bytes'], 'candidate API boot launcher');
  exactKeys(receipt.process, ['pid', 'listener_owner_pid', 'cwd', 'argv', 'workers'], 'candidate API boot process');
  exactKeys(receipt.environment, ['values', 'provider_credential_names_present'], 'candidate API boot environment');
  exactKeys(receipt.source, ['repository', 'git_branch', 'git_head', 'execution_root', 'source_capsule_receipt_file_sha256', 'source_manifest_path', 'source_manifest_before_child_sha256', 'source_manifest_file_sha256', 'source_manifest_after_ready_sha256', 'artifact_manifest_file_sha256'], 'candidate API boot source');
  exactKeys(receipt.runtime, ['python_path', 'python_real_path', 'python_file_sha256', 'python_version', 'requirements_lock_sha256', 'installed_distributions', 'installed_distributions_sha256', 'data_root', 'data_root_provenance_file_sha256', 'database_path', 'artifact_registry_path'], 'candidate API boot runtime');
  exactKeys(receipt.static, ['inventory', 'inventory_sha256', 'inventory_before_child_sha256', 'inventory_after_ready_sha256', 'deployment_file_sha256'], 'candidate API boot static identity');
  const legacyAttestationKeys = ['health_response_sha256', 'ready_response_sha256', 'model_ledger_response_sha256', 'root_html_sha256', 'workspace_seed_receipt_file_sha256', 'workspace_seed_receipt_base64', 'workspace_seed_receipt_sha256', 'workspace_seed_event_roster_sha256', 'workspace_response_sha256', 'workspace_response_base64', 'workspace_projection_sha256', 'workspace_state_roster_sha256', 'workspace_total_count', 'workspace_authority', 'workspace_corpus_identity_sha256', 'credential_configured', 'model_ledger_records', 'model_ledger_network_calls', 'source_reverified_after_ready'];
  const durableAttestationKeys = [...legacyAttestationKeys, 'durable_event_count', 'durable_event_roster', 'durable_event_roster_sha256', 'durable_registry_file_count', 'durable_registry_inventory', 'durable_registry_inventory_sha256'];
  const validateDurableAttestation = (attestation, label) => {
    exactKeys(attestation, durableAttestationKeys, label);
    if (!Array.isArray(attestation.durable_event_roster)
      || attestation.durable_event_count !== attestation.durable_event_roster.length
      || attestation.durable_event_roster_sha256 !== sha256(Buffer.from(canonicalJson(attestation.durable_event_roster), 'utf8'))
      || !Array.isArray(attestation.durable_registry_inventory)
      || attestation.durable_registry_file_count !== attestation.durable_registry_inventory.length
      || attestation.durable_registry_inventory_sha256 !== sha256(Buffer.from(canonicalJson(attestation.durable_registry_inventory), 'utf8'))) {
      throw new Error(`${label} durable roster is invalid`);
    }
    const eventKeys = [];
    for (const row of attestation.durable_event_roster) {
      exactKeys(row, ['session_id', 'loop_id', 'sequence', 'event_sha256', 'event_json_sha256'], `${label} durable event row`);
      if (typeof row.session_id !== 'string' || typeof row.loop_id !== 'string'
        || !Number.isInteger(row.sequence) || row.sequence < 1
        || !/^[0-9a-f]{64}$/.test(row.event_sha256 || '')
        || !/^[0-9a-f]{64}$/.test(row.event_json_sha256 || '')) {
        throw new Error(`${label} durable event row is invalid`);
      }
      eventKeys.push(`${row.session_id}\u0000${row.loop_id}\u0000${String(row.sequence).padStart(20, '0')}`);
    }
    if (new Set(eventKeys).size !== eventKeys.length
      || canonicalJson(eventKeys) !== canonicalJson([...eventKeys].sort())) {
      throw new Error(`${label} durable event roster is not canonical`);
    }
    const registryPaths = [];
    for (const row of attestation.durable_registry_inventory) {
      exactKeys(row, ['path', 'sha256', 'size_bytes'], `${label} durable registry row`);
      if (typeof row.path !== 'string' || !row.path || row.path.startsWith('/')
        || row.path.split('/').some(part => !part || part === '.' || part === '..')
        || !/^[0-9a-f]{64}$/.test(row.sha256 || '')
        || !Number.isInteger(row.size_bytes) || row.size_bytes < 0) {
        throw new Error(`${label} durable registry row is invalid`);
      }
      registryPaths.push(row.path);
    }
    if (new Set(registryPaths).size !== registryPaths.length
      || canonicalJson(registryPaths) !== canonicalJson([...registryPaths].sort())) {
      throw new Error(`${label} durable registry roster is not canonical`);
    }
  };
  validateDurableAttestation(receipt.attestation, 'candidate API boot attestation');
  const semantic = { ...receipt };
  delete semantic.receipt_sha256;
  const semanticSha = sha256(Buffer.from(canonicalJson(semantic), 'utf8'));
  const launcherPath = path.join(serviceRoot, 'bin', 'casepath');
  const launcherFile = await requireRegularFile(launcherPath, serviceRoot);
  const launcherBytes = await fs.readFile(launcherFile.resolved);
  const sourceManifestPath = path.join(serviceRoot, receipt.source.source_manifest_path || '');
  const sourceManifestFile = await requireRegularFile(sourceManifestPath, serviceRoot);
  const sourceManifestBytes = await fs.readFile(sourceManifestFile.resolved);
  const sourceManifest = JSON.parse(sourceManifestBytes.toString('utf8'));
  if (sourceManifest?.contract !== 'casepath.source-manifest/2.1.0'
    || !Array.isArray(sourceManifest.files)
    || sourceManifest.file_count !== sourceManifest.files.length) {
    throw new Error('candidate source manifest schema is invalid');
  }
  if (!sourceManifestBytes.equals(authorityManifestBytes)) {
    throw new Error('candidate runtime source manifest differs from source authority');
  }
  const expectedExecutionRoot = path.join(runtimeRoot, 'source-capsules', sha256(sourceManifestBytes));
  await requireCanonicalDirectory(path.join(runtimeRoot, 'source-capsules'), 'candidate source-capsules root', 0o700);
  await requireCanonicalDirectory(expectedExecutionRoot, 'candidate current source capsule', 0o500);
  const sourceManifestRows = [];
  for (const row of sourceManifest.files) {
    exactKeys(row, ['executable', 'path', 'sha256', 'size_bytes'], 'candidate source manifest row');
    const file = await requireRegularFile(path.join(REPOSITORY_ROOT, row.path), REPOSITORY_ROOT);
    const fileBytes = await fs.readFile(file.resolved);
    const mode = (await fs.stat(file.resolved)).mode;
    if (file.relative !== row.path
      || sha256(fileBytes) !== row.sha256
      || fileBytes.length !== row.size_bytes
      || Boolean(mode & 0o100) !== row.executable) {
      throw new Error(`candidate source manifest row drifted: ${row.path}`);
    }
    const installedFile = await requireRegularFile(
      path.join(serviceRoot, row.path),
      serviceRoot,
    );
    const installedBytes = await fs.readFile(installedFile.resolved);
    const installedMode = (await fs.stat(installedFile.resolved)).mode;
    if (installedFile.relative !== row.path
      || sha256(installedBytes) !== row.sha256
      || installedBytes.length !== row.size_bytes
      || Boolean(installedMode & 0o100) !== row.executable
      || (serviceRoot !== REPOSITORY_ROOT && Boolean(installedMode & 0o222))) {
      throw new Error(`candidate installed source row drifted: ${row.path}`);
    }
    const capsuleFile = await requireRegularFile(
      path.join(expectedExecutionRoot, row.path),
      expectedExecutionRoot,
    );
    const capsuleBytes = await fs.readFile(capsuleFile.resolved);
    const capsuleMode = (await fs.stat(capsuleFile.resolved)).mode;
    if (capsuleFile.relative !== row.path
      || sha256(capsuleBytes) !== row.sha256
      || capsuleBytes.length !== row.size_bytes
      || Boolean(capsuleMode & 0o100) !== row.executable
      || Boolean(capsuleMode & 0o222)) {
      throw new Error(`candidate source capsule row drifted: ${row.path}`);
    }
    sourceManifestRows.push(`${row.sha256}  ${row.path}`);
  }
  const artifactManifestPath = path.join(REPOSITORY_ROOT, 'casepath-api', 'artifacts', 'artifact-manifest.json');
  const deploymentPath = path.join(REPOSITORY_ROOT, 'casepath-public', 'deployment.json');
  const capsuleReceiptPath = path.join(expectedExecutionRoot, 'CAPSULE_RECEIPT.json');
  const capsuleReceiptFile = await requireRegularFile(capsuleReceiptPath, expectedExecutionRoot);
  const capsuleReceiptBytes = await fs.readFile(capsuleReceiptFile.resolved);
  const capsuleReceipt = JSON.parse(capsuleReceiptBytes.toString('utf8'));
  exactKeys(capsuleReceipt, ['contract', 'source_manifest_file_sha256', 'source_roster_sha256', 'source_file_count', 'artifact_manifest_file_sha256', 'artifact_file_count', 'static_inventory_sha256', 'static_file_count', 'receipt_sha256'], 'candidate source capsule receipt');
  const capsuleSemantic = { ...capsuleReceipt };
  const capsuleSemanticSha = capsuleSemantic.receipt_sha256;
  delete capsuleSemantic.receipt_sha256;
  const capsuleManifestFile = await requireRegularFile(
    path.join(expectedExecutionRoot, 'casepath', 'source-manifest.json'),
    expectedExecutionRoot,
  );
  const capsuleManifestBytes = await fs.readFile(capsuleManifestFile.resolved);
  const capsuleArtifactManifestFile = await requireRegularFile(
    path.join(expectedExecutionRoot, 'casepath-api', 'artifacts', 'artifact-manifest.json'),
    expectedExecutionRoot,
  );
  const capsuleArtifactManifestBytes = await fs.readFile(capsuleArtifactManifestFile.resolved);
  const dataRoot = path.join(serviceRoot, '.runtime', 'casepath-data-v1');
  await requireCanonicalDirectory(dataRoot, 'candidate durable data root', 0o700);
  const dataRootProvenancePath = path.join(dataRoot, 'DATA_ROOT_PROVENANCE.json');
  const dataRootProvenanceFile = await requireRegularFile(dataRootProvenancePath, dataRoot);
  const dataRootProvenanceBytes = await fs.readFile(dataRootProvenanceFile.resolved);
  const dataRootProvenance = JSON.parse(dataRootProvenanceBytes.toString('utf8'));
  const dataRootProvenanceSemantic = { ...dataRootProvenance };
  const dataRootProvenanceSha = dataRootProvenanceSemantic.receipt_sha256;
  delete dataRootProvenanceSemantic.receipt_sha256;
  const provenanceOrigin = dataRootProvenance.origin;
  exactKeys(provenanceOrigin, ['kind', 'legacy_database_path', 'legacy_database_file_sha256_at_backup', 'claim_loop_event_count', 'claim_loop_event_roster_sha256', 'claim_loop_event_roster', 'legacy_registry_inventory_sha256', 'legacy_registry_inventory', 'legacy_registry_cutover'], 'candidate data-root origin');
  const registryCutover = provenanceOrigin.legacy_registry_cutover;
  validateRegistryCutoverAuthority(provenanceOrigin, dataRoot);
  if (dataRootProvenanceFile.relative !== 'DATA_ROOT_PROVENANCE.json'
    || validateDataRootProvenanceContract(dataRootProvenance.contract) !== dataRootProvenance.contract
    || dataRootProvenance.destination !== dataRoot
    || dataRootProvenanceSha !== sha256(Buffer.from(canonicalJson(dataRootProvenanceSemantic), 'utf8'))
    ) {
    throw new Error('candidate durable data-root provenance is invalid');
  }
  const seedReceiptPath = path.join(runtimeRoot, 'latest-workspace-seed-receipt.json');
  const seedReceiptFile = await requireRegularFile(seedReceiptPath, runtimeRoot);
  const seedReceiptBytes = await fs.readFile(seedReceiptFile.resolved);
  const seedReceipt = JSON.parse(seedReceiptBytes.toString('utf8'));
  exactKeys(seedReceipt, ['contract', 'seed_receipt', 'source_authority', 'receipt_sha256'], 'candidate workspace seed wrapper');
  exactKeys(seedReceipt.source_authority, ['contract', 'source_manifest_file_sha256', 'source_manifest_roster_sha256'], 'candidate workspace seed source authority');
  exactKeys(seedReceipt.seed_receipt, ['contract', 'corpus_identity', 'claim_count', 'new_import_count', 'replayed_import_count', 'event_roster_sha256', 'timestamp', 'model_calls', 'provider_calls', 'credential_reads', 'cost_usd', 'receipt_sha256'], 'candidate workspace seed receipt');
  const seedWrapperSemantic = { ...seedReceipt };
  delete seedWrapperSemantic.receipt_sha256;
  const seedSemantic = { ...seedReceipt.seed_receipt };
  delete seedSemantic.receipt_sha256;
  const expectedClaimCount = seedReceipt.seed_receipt.corpus_identity?.claim_count;
  const sourceManifestRosterSha256 = sha256(Buffer.from(canonicalJson(sourceManifest.files), 'utf8'));
  const attestedSeedReceiptBytes = Buffer.from(receipt.attestation.workspace_seed_receipt_base64, 'base64');
  const attestedWorkspaceBytes = Buffer.from(receipt.attestation.workspace_response_base64, 'base64');
  const attestedWorkspace = JSON.parse(attestedWorkspaceBytes.toString('utf8'));
  const attestedWorkspaceSemantic = { ...attestedWorkspace };
  const attestedWorkspaceProjectionSha = attestedWorkspaceSemantic.projection_sha256;
  delete attestedWorkspaceSemantic.projection_sha256;
  const bootArgvFor = (pythonPath, executionRoot, contract) => [
    pythonPath,
    '-I', ...(contract === 'casepath.local-runtime-boot/2.2.0' ? ['-B'] : []), '-P', '-m', 'uvicorn', 'casepath_api.app:app',
    '--app-dir', path.join(executionRoot, 'casepath-api'),
    '--host', '127.0.0.1', '--port', '4173', '--no-access-log',
  ];
  const bootEnvironmentFor = (sourceCommit, executionRoot) => ({
    CASEPATH_ARTIFACT_REGISTRY_PATH: path.join(dataRoot, 'artifact-registry'),
    CASEPATH_DB_PATH: path.join(dataRoot, 'casepath.db'),
    CASEPATH_LOCAL_RUNTIME_RECEIPT: expectedReceiptPath,
    CASEPATH_LOCAL_STATIC_ROOT: path.join(executionRoot, 'casepath-public'),
    CASEPATH_MODEL_MODE: 'deterministic_reference',
    CASEPATH_SOURCE_COMMIT: sourceCommit,
    HOME: path.join(runtimeRoot, 'home'),
    LANG: 'C.UTF-8',
    LC_ALL: 'C.UTF-8',
    PATH: [path.join(runtimeRoot, 'venv', 'bin'), '/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin'].join(':'),
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONHASHSEED: '0',
    PYTHONNOUSERSITE: '1',
    PYTHONPYCACHEPREFIX: path.join(runtimeRoot, 'pycache'),
    PYTHONSAFEPATH: '1',
    SOURCE_DATE_EPOCH: '1786406400',
    TMPDIR: path.join(runtimeRoot, 'tmp'),
    TZ: 'UTC',
    LANGCHAIN_TRACING: 'false',
    LANGCHAIN_TRACING_V2: 'false',
    LANGSMITH_TRACING: 'false',
  });
  const validateEmbeddedWorkspaceAttestation = (bootReceipt, expectedSourceRosterSha256 = null) => {
    const attestation = bootReceipt.attestation;
    const seedBase64 = attestation.workspace_seed_receipt_base64;
    const workspaceBase64 = attestation.workspace_response_base64;
    if (typeof seedBase64 !== 'string' || typeof workspaceBase64 !== 'string') return false;
    const embeddedSeedBytes = Buffer.from(seedBase64, 'base64');
    const embeddedWorkspaceBytes = Buffer.from(workspaceBase64, 'base64');
    if (embeddedSeedBytes.toString('base64') !== seedBase64
      || embeddedWorkspaceBytes.toString('base64') !== workspaceBase64
      || sha256(embeddedSeedBytes) !== attestation.workspace_seed_receipt_file_sha256
      || sha256(embeddedWorkspaceBytes) !== attestation.workspace_response_sha256) return false;
    let embeddedSeed;
    let embeddedWorkspace;
    try {
      embeddedSeed = JSON.parse(embeddedSeedBytes.toString('utf8'));
      embeddedWorkspace = JSON.parse(embeddedWorkspaceBytes.toString('utf8'));
    } catch (_) {
      return false;
    }
    exactKeys(embeddedSeed, ['contract', 'seed_receipt', 'source_authority', 'receipt_sha256'], 'embedded boot seed wrapper');
    exactKeys(embeddedSeed.source_authority, ['contract', 'source_manifest_file_sha256', 'source_manifest_roster_sha256'], 'embedded boot seed source authority');
    exactKeys(embeddedSeed.seed_receipt, ['contract', 'corpus_identity', 'claim_count', 'new_import_count', 'replayed_import_count', 'event_roster_sha256', 'timestamp', 'model_calls', 'provider_calls', 'credential_reads', 'cost_usd', 'receipt_sha256'], 'embedded boot seed receipt');
    const wrapperSemantic = { ...embeddedSeed };
    delete wrapperSemantic.receipt_sha256;
    const seedMaterial = { ...embeddedSeed.seed_receipt };
    delete seedMaterial.receipt_sha256;
    const workspaceMaterial = { ...embeddedWorkspace };
    const projectionSha = workspaceMaterial.projection_sha256;
    delete workspaceMaterial.projection_sha256;
    const expectedClaimCount = embeddedSeed.seed_receipt.corpus_identity?.claim_count;
    return embeddedSeed.contract === 'casepath.sealed-workspace-seed/1.0.0'
      && embeddedSeed.receipt_sha256 === sha256(Buffer.from(canonicalJson(wrapperSemantic), 'utf8'))
      && embeddedSeed.source_authority.contract === 'casepath.sealed-seed-source-authority/1.0.0'
      && embeddedSeed.source_authority.source_manifest_file_sha256 === bootReceipt.source.source_manifest_file_sha256
      && /^[0-9a-f]{64}$/.test(embeddedSeed.source_authority.source_manifest_roster_sha256)
      && (expectedSourceRosterSha256 === null
        || embeddedSeed.source_authority.source_manifest_roster_sha256 === expectedSourceRosterSha256)
      && embeddedSeed.seed_receipt.contract === 'casepath.claim-workspace-seed/1.0.0'
      && embeddedSeed.seed_receipt.receipt_sha256 === sha256(Buffer.from(canonicalJson(seedMaterial), 'utf8'))
      && Number.isInteger(expectedClaimCount) && expectedClaimCount > 0
      && embeddedSeed.seed_receipt.claim_count === expectedClaimCount
      && embeddedSeed.seed_receipt.new_import_count + embeddedSeed.seed_receipt.replayed_import_count === expectedClaimCount
      && ['model_calls', 'provider_calls', 'credential_reads', 'cost_usd'].every(field => embeddedSeed.seed_receipt[field] === 0)
      && embeddedSeed.receipt_sha256 === attestation.workspace_seed_receipt_sha256
      && embeddedSeed.seed_receipt.event_roster_sha256 === attestation.workspace_seed_event_roster_sha256
      && ['casepath.claim-queue-projection/1.0.0', 'casepath.claim-queue-projection/2.0.0']
        .includes(embeddedWorkspace.contract)
      && projectionSha === sha256(Buffer.from(canonicalJson(workspaceMaterial), 'utf8'))
      && projectionSha === attestation.workspace_projection_sha256
      && embeddedWorkspace.state_roster_sha256 === attestation.workspace_state_roster_sha256
      && embeddedWorkspace.total_count === attestation.workspace_total_count
      && embeddedWorkspace.total_count === expectedClaimCount
      && embeddedWorkspace.authority === attestation.workspace_authority
      && embeddedWorkspace.authority === 'claim_loop_events'
      && canonicalJson(embeddedWorkspace.corpus_identity) === canonicalJson(embeddedSeed.seed_receipt.corpus_identity)
      && sha256(Buffer.from(canonicalJson(embeddedWorkspace.corpus_identity), 'utf8')) === attestation.workspace_corpus_identity_sha256;
  };
  if (!validateEmbeddedWorkspaceAttestation(receipt, sourceManifestRosterSha256)) {
    throw new Error('candidate API boot workspace attestation is invalid');
  }

  const validateSourceCapsuleForBoot = async (bootReceipt, label) => {
    const manifestSha = bootReceipt.source?.source_manifest_file_sha256;
    if (!/^[0-9a-f]{64}$/.test(manifestSha || '')) throw new Error(`${label} source manifest identity is invalid`);
    const executionRoot = path.join(runtimeRoot, 'source-capsules', manifestSha);
    if (bootReceipt.source.execution_root !== executionRoot
      || bootReceipt.source.source_manifest_path !== 'casepath/source-manifest.json') {
      throw new Error(`${label} source capsule path is invalid`);
    }
    const manifestFile = await requireRegularFile(path.join(executionRoot, 'casepath', 'source-manifest.json'), executionRoot);
    const manifestBytes = await fs.readFile(manifestFile.resolved);
    if (sha256(manifestBytes) !== manifestSha) throw new Error(`${label} source manifest bytes drifted`);
    const manifest = JSON.parse(manifestBytes.toString('utf8'));
    const legacyManifest = manifest.contract === 'casepath.source-manifest/2.0.0';
    exactKeys(manifest, [
      'artifact_manifest', 'contract', 'file_count', 'files', 'gate_count', 'gates',
      'inventory_policy', 'release_id', ...(legacyManifest ? ['source_commit'] : []),
    ], `${label} source manifest`);
    if (legacyManifest) exactKeys(manifest.source_commit, ['source', 'value'], `${label} source commit`);
    if (!['casepath.source-manifest/2.0.0', 'casepath.source-manifest/2.1.0'].includes(manifest.contract)
      || typeof manifest.release_id !== 'string' || !manifest.release_id
      || !/^[0-9a-f]{40}$/.test(bootReceipt.source.git_head || '')
      || (legacyManifest && (manifest.source_commit.source !== 'CASEPATH_SOURCE_COMMIT'
        || manifest.source_commit.value !== bootReceipt.source.git_head))
      || !Array.isArray(manifest.files)
      || manifest.file_count !== manifest.files.length) {
      throw new Error(`${label} source manifest schema or identity is invalid`);
    }
    const expectedFiles = new Map();
    const addExpected = (relative, expected, sourceLabel) => {
      const prior = expectedFiles.get(relative);
      if (prior && canonicalJson(prior) !== canonicalJson(expected)) {
        throw new Error(`${label} capsule authorities conflict for ${relative}: ${sourceLabel}`);
      }
      expectedFiles.set(relative, expected);
    };
    const manifestPaths = [];
    for (const row of manifest.files) {
      exactKeys(row, ['executable', 'path', 'sha256', 'size_bytes'], `${label} source row`);
      if (typeof row.path !== 'string' || !row.path || row.path.startsWith('/')
        || row.path.split('/').some(part => !part || part === '.' || part === '..')
        || typeof row.executable !== 'boolean' || !/^[0-9a-f]{64}$/.test(row.sha256 || '')
        || !Number.isInteger(row.size_bytes) || row.size_bytes < 0) {
        throw new Error(`${label} source row is invalid`);
      }
      manifestPaths.push(row.path);
      addExpected(row.path, row, 'source manifest');
      const file = await requireRegularFile(path.join(executionRoot, row.path), executionRoot);
      const fileBytes = await fs.readFile(file.resolved);
      const fileMode = (await fs.stat(file.resolved)).mode;
      if (sha256(fileBytes) !== row.sha256 || fileBytes.length !== row.size_bytes
        || Boolean(fileMode & 0o100) !== row.executable) {
        throw new Error(`${label} capsule source row drifted: ${row.path}`);
      }
    }
    if (new Set(manifestPaths).size !== manifestPaths.length
      || canonicalJson(manifestPaths) !== canonicalJson([...manifestPaths].sort())) {
      throw new Error(`${label} source roster is not canonical`);
    }
    const sourceRowsByPath = new Map(manifest.files.map(row => [row.path, row]));
    const historicalSourceRoots = ['casepath', 'casepath-api', 'casepath-qa', 'docs', 'examples'];
    const historicalExtraFiles = ['.gitattributes', '.gitignore', 'AGENTS.md', 'bin/casepath', 'CONTRIBUTING.md', 'LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md', 'CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md'];
    const historicalGates = manifest.files
      .filter(row => row.path.startsWith('casepath-qa/')
        && ['.mjs', '.py'].includes(path.extname(row.path))
        && ['browser-', 'check-', 'reset-', 'patch_'].some(prefix => path.basename(row.path).startsWith(prefix)))
      .map(row => ({ path: row.path, sha256: row.sha256 }));
    if (canonicalJson(manifest.inventory_policy) !== canonicalJson({
      includes_nonignored_pending_files: true,
      roots: [...historicalSourceRoots, ...historicalExtraFiles],
      self_output_excluded: 'casepath/source-manifest.json',
    }) || canonicalJson(manifest.gates) !== canonicalJson(historicalGates)
      || manifest.gate_count !== historicalGates.length) {
      throw new Error(`${label} source inventory/gate authority is invalid`);
    }
    addExpected('casepath/source-manifest.json', {
      executable: false,
      path: 'casepath/source-manifest.json',
      sha256: manifestSha,
      size_bytes: manifestBytes.length,
    }, 'source manifest authority');
    const artifactManifestFile = await requireRegularFile(
      path.join(executionRoot, 'casepath-api', 'artifacts', 'artifact-manifest.json'),
      executionRoot,
    );
    const artifactManifestBytes = await fs.readFile(artifactManifestFile.resolved);
    const artifactManifest = JSON.parse(artifactManifestBytes.toString('utf8'));
    exactKeys(artifactManifest, ['contract', 'file_count', 'files', 'leakage_policy', 'release_id', 'source_assets', 'source_date_epoch'], `${label} artifact manifest`);
    const historicalModelVisibleFiles = Array.isArray(artifactManifest.files)
      ? artifactManifest.files.filter(row => row?.model_visible === true).map(row => ({ path: row.path, sha256: row.sha256 }))
      : [];
    const historicalLeakagePolicy = {
      markers: ['benchmark', 'casepath', 'demo', 'dummy', 'example_domain', 'expected_action', 'fictional', 'generated', 'ground_truth', 'hidden_label', 'reference_answer', 'sample', 'scenario_template'],
      model_visible_files_scanned: historicalModelVisibleFiles.length,
      status: 'passed',
      surfaces: ['raw bytes', 'PDF extracted text and metadata', 'email headers and body', 'image metadata'],
    };
    if (!Array.isArray(artifactManifest.files)
      || artifactManifest.file_count !== artifactManifest.files.length
      || artifactManifest.contract !== 'casepath.artifact-manifest/1.0.0'
      || artifactManifest.release_id !== manifest.release_id
      || artifactManifest.source_date_epoch !== 1786406400
      || canonicalJson(artifactManifest.leakage_policy) !== canonicalJson(historicalLeakagePolicy)
      || !Array.isArray(artifactManifest.source_assets)
      || bootReceipt.source.artifact_manifest_file_sha256 !== sha256(artifactManifestBytes)
      || canonicalJson(Object.keys(manifest.artifact_manifest || {}).sort()) !== canonicalJson(['model_visible_files', 'path', 'sha256'])
      || manifest.artifact_manifest?.path !== 'casepath-api/artifacts/artifact-manifest.json'
      || manifest.artifact_manifest?.sha256 !== sha256(artifactManifestBytes)
      || canonicalJson(manifest.artifact_manifest?.model_visible_files) !== canonicalJson(historicalModelVisibleFiles)) {
      throw new Error(`${label} artifact manifest authority is invalid`);
    }
    addExpected('casepath-api/artifacts/artifact-manifest.json', {
      executable: false,
      path: 'casepath-api/artifacts/artifact-manifest.json',
      sha256: sha256(artifactManifestBytes),
      size_bytes: artifactManifestBytes.length,
    }, 'artifact manifest authority');
    const historicalArtifactPaths = [];
    for (const row of artifactManifest.files) {
      exactKeys(row, ['leakage_scan', 'media_type', 'model_visible', 'path', 'sha256', 'size_bytes'], `${label} artifact row`);
      const mediaTypes = { '.eml': 'message/rfc822', '.jpg': 'image/jpeg', '.json': 'application/json', '.pdf': 'application/pdf', '.png': 'image/png' };
      if (typeof row.path !== 'string' || !row.path
        || row.path.startsWith('/') || row.path.split('/').some(part => !part || part === '.' || part === '..')
        || !/^[0-9a-f]{64}$/.test(row.sha256 || '')
        || !Number.isInteger(row.size_bytes) || row.size_bytes < 0
        || typeof row.model_visible !== 'boolean'
        || row.leakage_scan !== (row.model_visible ? 'passed' : 'not_model_visible')
        || row.media_type !== mediaTypes[path.extname(row.path)]) {
        throw new Error(`${label} artifact row is invalid`);
      }
      const relative = `casepath-api/artifacts/${row.path}`;
      historicalArtifactPaths.push(row.path);
      addExpected(relative, {
        executable: false,
        path: relative,
        sha256: row.sha256,
        size_bytes: row.size_bytes,
      }, 'artifact manifest');
      const file = await requireRegularFile(path.join(executionRoot, relative), executionRoot);
      const fileBytes = await fs.readFile(file.resolved);
      if (sha256(fileBytes) !== row.sha256 || fileBytes.length !== row.size_bytes) {
        throw new Error(`${label} capsule artifact row drifted: ${row.path}`);
      }
    }
    if (new Set(historicalArtifactPaths).size !== historicalArtifactPaths.length
      || canonicalJson(historicalArtifactPaths) !== canonicalJson([...historicalArtifactPaths].sort())) {
      throw new Error(`${label} artifact roster is not canonical`);
    }
    const sourceAssetPaths = [];
    for (const row of artifactManifest.source_assets) {
      exactKeys(row, ['dimensions', 'path', 'sha256'], `${label} artifact source asset`);
      if (typeof row.path !== 'string' || !row.path || row.path.startsWith('/')
        || row.path.split('/').some(part => !part || part === '.' || part === '..')
        || !/^[0-9a-f]{64}$/.test(row.sha256 || '')
        || !Array.isArray(row.dimensions) || row.dimensions.length !== 2
        || row.dimensions.some(value => !Number.isInteger(value) || value < 1)
        || sourceRowsByPath.get(row.path)?.sha256 !== row.sha256) {
        throw new Error(`${label} artifact source asset is invalid`);
      }
      sourceAssetPaths.push(row.path);
    }
    if (new Set(sourceAssetPaths).size !== sourceAssetPaths.length
      || canonicalJson(sourceAssetPaths) !== canonicalJson([...sourceAssetPaths].sort())) {
      throw new Error(`${label} artifact source-asset roster is not canonical`);
    }
    const staticRows = [];
    const staticPaths = [];
    for (const row of bootReceipt.static.inventory) {
      exactKeys(row, ['path', 'sha256', 'bytes'], `${label} static row`);
      if (typeof row.path !== 'string' || !row.path || row.path.startsWith('/')
        || row.path.split('/').some(part => !part || part === '.' || part === '..')
        || !/^[0-9a-f]{64}$/.test(row.sha256 || '')
        || !Number.isInteger(row.bytes) || row.bytes < 0) {
        throw new Error(`${label} static row is invalid`);
      }
      const relative = `casepath-public/${row.path}`;
      const file = await requireRegularFile(path.join(executionRoot, relative), executionRoot);
      const fileBytes = await fs.readFile(file.resolved);
      if (sha256(fileBytes) !== row.sha256 || fileBytes.length !== row.bytes) {
        throw new Error(`${label} capsule static row drifted: ${row.path}`);
      }
      const authoredRow = sourceRowsByPath.get(`casepath/${row.path}`);
      const expectedExecutable = row.path === 'deployment.json' ? false : authoredRow?.executable;
      if (typeof expectedExecutable !== 'boolean'
        || (row.path !== 'deployment.json'
          && (authoredRow.sha256 !== row.sha256 || authoredRow.size_bytes !== row.bytes))) {
        throw new Error(`${label} static row lacks matching authored authority: ${row.path}`);
      }
      const expected = {
        executable: expectedExecutable,
        path: relative,
        sha256: row.sha256,
        size_bytes: row.bytes,
      };
      addExpected(relative, expected, 'boot static inventory');
      staticRows.push({
        path: row.path,
        sha256: row.sha256,
        size_bytes: row.bytes,
        executable: expected.executable,
      });
      staticPaths.push(row.path);
    }
    if (new Set(staticPaths).size !== staticPaths.length
      || canonicalJson(staticPaths) !== canonicalJson([...staticPaths].sort())) {
      throw new Error(`${label} static roster is not canonical`);
    }
    const historicalRelease = JSON.parse((await fs.readFile(path.join(executionRoot, 'casepath', 'release.json'))).toString('utf8'));
    const historicalDeployment = JSON.parse((await fs.readFile(path.join(executionRoot, 'casepath-public', 'deployment.json'))).toString('utf8'));
    if (historicalRelease.release_id !== manifest.release_id
      || historicalDeployment.contract !== 'casepath.deployment-identity/1.0.0'
      || historicalDeployment.alignment_eligible !== true
      || historicalDeployment.source_commit !== bootReceipt.source.git_head
      || historicalDeployment.release_id !== manifest.release_id
      || historicalDeployment.component_version !== historicalRelease.components?.frontend?.version
      || historicalDeployment.component_contract !== historicalRelease.components?.frontend?.contract) {
      throw new Error(`${label} release/deployment identity is invalid`);
    }
    const receiptFile = await requireRegularFile(path.join(executionRoot, 'CAPSULE_RECEIPT.json'), executionRoot);
    const receiptBytes = await fs.readFile(receiptFile.resolved);
    const capsule = JSON.parse(receiptBytes.toString('utf8'));
    exactKeys(capsule, ['contract', 'source_manifest_file_sha256', 'source_roster_sha256', 'source_file_count', 'artifact_manifest_file_sha256', 'artifact_file_count', 'static_inventory_sha256', 'static_file_count', 'receipt_sha256'], `${label} capsule receipt`);
    const capsuleSemantic = { ...capsule };
    delete capsuleSemantic.receipt_sha256;
    if (bootReceipt.source.source_capsule_receipt_file_sha256 !== sha256(receiptBytes)
      || capsule.contract !== 'casepath.sealed-source-capsule/1.0.0'
      || capsule.receipt_sha256 !== sha256(Buffer.from(canonicalJson(capsuleSemantic), 'utf8'))
      || capsule.source_manifest_file_sha256 !== manifestSha
      || capsule.source_roster_sha256 !== sha256(Buffer.from(canonicalJson(manifest.files), 'utf8'))
      || capsule.source_file_count !== manifest.files.length
      || capsule.artifact_manifest_file_sha256 !== sha256(artifactManifestBytes)
      || capsule.artifact_file_count !== artifactManifest.files.length
      || capsule.static_inventory_sha256 !== sha256(Buffer.from(canonicalJson(staticRows), 'utf8'))
      || capsule.static_file_count !== staticRows.length) {
      throw new Error(`${label} capsule receipt is invalid`);
    }
    addExpected('CAPSULE_RECEIPT.json', {
      executable: false,
      path: 'CAPSULE_RECEIPT.json',
      sha256: sha256(receiptBytes),
      size_bytes: receiptBytes.length,
    }, 'capsule receipt');
    await validateClosedReadOnlyTree(executionRoot, expectedFiles, `${label} capsule`);
    const capsuleLauncher = await requireRegularFile(path.join(executionRoot, 'bin', 'casepath'), executionRoot);
    const capsuleLauncherBytes = await fs.readFile(capsuleLauncher.resolved);
    const capsuleRequirementsFile = await requireRegularFile(path.join(executionRoot, 'casepath-api', 'requirements.lock'), executionRoot);
    const capsuleRequirements = await fs.readFile(capsuleRequirementsFile.resolved);
    const normalizeDistribution = value => value.toLowerCase().replace(/[-_.]+/g, '-');
    const lockedPins = new Map();
    for (const line of capsuleRequirements.toString('utf8').split(/\r?\n/).map(value => value.trim()).filter(value => value && !value.startsWith('#'))) {
      if (line.split('==').length !== 2) throw new Error(`${label} requirements row is unpinned`);
      const [name, version] = line.split('==');
      const normalized = normalizeDistribution(name);
      if (lockedPins.has(normalized)) throw new Error(`${label} requirements roster duplicates a package`);
      lockedPins.set(normalized, version);
    }
    const installedPins = new Map();
    if (!Array.isArray(bootReceipt.runtime.installed_distributions)
      || canonicalJson(bootReceipt.runtime.installed_distributions) !== canonicalJson(canonicalizeInstalledDistributions(bootReceipt.runtime.installed_distributions))) {
      throw new Error(`${label} installed distribution roster is not canonical`);
    }
    for (const value of bootReceipt.runtime.installed_distributions) {
      if (typeof value !== 'string' || value.split('==').length !== 2) throw new Error(`${label} installed distribution is unpinned`);
      const [name, version] = value.split('==');
      const normalized = normalizeDistribution(name);
      if (installedPins.has(normalized)) throw new Error(`${label} installed distribution roster duplicates a package`);
      installedPins.set(normalized, version);
    }
    if (bootReceipt.launcher.path !== 'bin/casepath'
      || bootReceipt.launcher.sha256 !== sha256(capsuleLauncherBytes)
      || bootReceipt.launcher.bytes !== capsuleLauncherBytes.length
      || bootReceipt.runtime.requirements_lock_sha256 !== sha256(capsuleRequirements)
      || bootReceipt.runtime.installed_distributions_sha256 !== sha256(Buffer.from(canonicalJson(bootReceipt.runtime.installed_distributions), 'utf8'))
      || canonicalJson([...installedPins.entries()].sort()) !== canonicalJson([...lockedPins.entries()].sort())) {
      throw new Error(`${label} launcher or runtime authority differs from its capsule`);
    }
    return {
      capsuleReceiptFileSha256: sha256(receiptBytes),
      capsuleRosterSha256: sha256(Buffer.from(canonicalJson(
        [...expectedFiles.entries()]
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([relative, expected]) => ({
            executable: expected.executable,
            path: relative,
            sha256: expected.sha256,
            size_bytes: expected.size_bytes,
            mode: expected.executable ? 0o555 : 0o444,
          })),
      ), 'utf8')),
      executionRoot,
      expectedFiles,
      sourceRosterSha256: sha256(Buffer.from(canonicalJson(manifest.files), 'utf8')),
      staticRosterSha256: sha256(Buffer.from(canonicalJson(bootReceipt.static.inventory), 'utf8')),
    };
  };
  const bootHistoryRoot = path.join(runtimeRoot, 'boots');
  await requireCanonicalDirectory(bootHistoryRoot, 'candidate boot history root', 0o700);
  const bootStagingRoot = path.join(runtimeRoot, 'boot-staging');
  await requireCanonicalDirectory(bootStagingRoot, 'candidate boot staging root', 0o700);
  if ((await fs.readdir(bootStagingRoot)).length !== 0) {
    throw new Error('candidate boot staging root is not empty and canonical');
  }
  const currentHistoryPath = path.join(bootHistoryRoot, `${receipt.boot_id}.json`);
  const currentHistory = await requireRegularFile(currentHistoryPath, bootHistoryRoot);
  const currentHistoryBytes = await fs.readFile(currentHistory.resolved);
  if (!currentHistoryBytes.equals(bytes)) {
    throw new Error('candidate current boot history receipt differs from the published current receipt');
  }
  const bootHistoryByFileSha = new Map();
  const currentReceiptFileSha = sha256(bytes);
  let currentCapsuleIdentity = null;
  const runtimeClosureBySourceManifest = new Map();
  const bootHistoryNames = await fs.readdir(bootHistoryRoot, { withFileTypes: true });
  for (const entry of bootHistoryNames) {
    if (!entry.isFile() || entry.isSymbolicLink() || !/^boot-[A-Za-z0-9TZ-]+\.json$/.test(entry.name)) {
      throw new Error(`candidate boot history contains a noncanonical entry: ${entry.name}`);
    }
    const historyFile = await requireRegularFile(path.join(bootHistoryRoot, entry.name), bootHistoryRoot);
    const historyBytes = await fs.readFile(historyFile.resolved);
    const fileSha = sha256(historyBytes);
    if (bootHistoryByFileSha.has(fileSha)) throw new Error(`candidate boot history duplicates receipt bytes: ${fileSha}`);
    const historyReceipt = JSON.parse(historyBytes.toString('utf8'));
    exactKeys(historyReceipt, receiptKeysFor(historyReceipt.contract), 'candidate historical boot receipt');
    exactKeys(historyReceipt.launcher, ['path', 'sha256', 'bytes'], 'candidate historical boot launcher');
    exactKeys(historyReceipt.process, ['pid', 'listener_owner_pid', 'cwd', 'argv', 'workers'], 'candidate historical boot process');
    exactKeys(historyReceipt.environment, ['values', 'provider_credential_names_present'], 'candidate historical boot environment');
    const expectedHistoricalEnvironment = bootEnvironmentFor(
      historyReceipt.source?.git_head,
      historyReceipt.source?.execution_root,
    );
    exactKeys(historyReceipt.environment.values, Object.keys(expectedHistoricalEnvironment), 'candidate historical boot child environment');
    exactKeys(historyReceipt.source, ['repository', 'git_branch', 'git_head', 'execution_root', 'source_capsule_receipt_file_sha256', 'source_manifest_path', 'source_manifest_before_child_sha256', 'source_manifest_file_sha256', 'source_manifest_after_ready_sha256', 'artifact_manifest_file_sha256'], 'candidate historical boot source');
    exactKeys(historyReceipt.runtime, ['python_path', 'python_real_path', 'python_file_sha256', 'python_version', 'requirements_lock_sha256', 'installed_distributions', 'installed_distributions_sha256', 'data_root', 'data_root_provenance_file_sha256', 'database_path', 'artifact_registry_path'], 'candidate historical boot runtime');
    exactKeys(historyReceipt.static, ['inventory', 'inventory_sha256', 'inventory_before_child_sha256', 'inventory_after_ready_sha256', 'deployment_file_sha256'], 'candidate historical boot static identity');
    for (const row of historyReceipt.static.inventory) exactKeys(row, ['path', 'sha256', 'bytes'], 'candidate historical boot static row');
    if (['casepath.local-runtime-boot/2.1.0', 'casepath.local-runtime-boot/2.2.0'].includes(historyReceipt.contract)) {
      validateDurableAttestation(historyReceipt.attestation, 'candidate historical boot attestation');
      const historyStat = await fs.stat(historyFile.resolved);
      if ((historyStat.mode & 0o7777) !== 0o444 || historyStat.nlink !== 1) {
        throw new Error(`candidate durable boot history is not immutable: ${entry.name}`);
      }
    } else {
      exactKeys(historyReceipt.attestation, legacyAttestationKeys, 'candidate historical boot attestation');
    }
    let historicalRuntimeClosure = null;
    if (historyReceipt.contract === 'casepath.local-runtime-boot/2.2.0') {
      historicalRuntimeClosure = validateBootRuntimeClosure(
        historyReceipt.runtime_closure,
        `candidate historical boot ${entry.name} runtime closure`,
      );
      const sourceManifestSha = historyReceipt.source?.source_manifest_file_sha256;
      const priorClosureSha = runtimeClosureBySourceManifest.get(sourceManifestSha);
      if (priorClosureSha !== undefined && priorClosureSha !== historicalRuntimeClosure.closure_sha256) {
        throw new Error(`candidate runtime closure changed across restart for ${sourceManifestSha}`);
      }
      runtimeClosureBySourceManifest.set(sourceManifestSha, historicalRuntimeClosure.closure_sha256);
    }
    const historyCapsule = await validateSourceCapsuleForBoot(historyReceipt, `candidate historical boot ${entry.name}`);
    if (historicalRuntimeClosure !== null) {
      const closureSections = historicalRuntimeClosure.sections;
      const serviceLaunch = closureSections.launch_context.service;
      const pythonRuntime = closureSections.python_runtime;
      const distributionIntegrity = closureSections.distribution_integrity;
      if (closureSections.capsule.root !== historyCapsule.executionRoot
        || closureSections.site_packages.root !== path.join(runtimeRoot, 'venv', 'lib', 'python3.13', 'site-packages')
        || closureSections.isolated_probe.cwd !== historyCapsule.executionRoot
        || serviceLaunch.cwd !== serviceRoot
        || serviceLaunch.app_dir !== path.join(historyCapsule.executionRoot, 'casepath-api')
        || canonicalJson(serviceLaunch.argv) !== canonicalJson(historyReceipt.process.argv)
        || canonicalJson(serviceLaunch.environment) !== canonicalJson(historyReceipt.environment.values)
        || serviceLaunch.environment_sha256 !== sha256(Buffer.from(canonicalJson(serviceLaunch.environment), 'utf8'))
        || pythonRuntime.stated_path !== historyReceipt.runtime.python_path
        || pythonRuntime.real_path !== historyReceipt.runtime.python_real_path
        || pythonRuntime.real_file?.sha256 !== historyReceipt.runtime.python_file_sha256
        || pythonRuntime.python_version !== historyReceipt.runtime.python_version
        || canonicalJson(distributionIntegrity.installed_distributions) !== canonicalJson(historyReceipt.runtime.installed_distributions)
        || distributionIntegrity.installed_distributions_sha256 !== historyReceipt.runtime.installed_distributions_sha256) {
        throw new Error(`candidate historical runtime closure is not bound to its boot receipt: ${entry.name}`);
      }
    }
    if (fileSha === currentReceiptFileSha) currentCapsuleIdentity = historyCapsule;
    if (!validateEmbeddedWorkspaceAttestation(historyReceipt, historyCapsule.sourceRosterSha256)) {
      throw new Error(`candidate historical workspace attestation is invalid: ${entry.name}`);
    }
    const historySemantic = { ...historyReceipt };
    delete historySemantic.receipt_sha256;
    if (!['casepath.local-runtime-boot/2.0.0', 'casepath.local-runtime-boot/2.1.0', 'casepath.local-runtime-boot/2.2.0'].includes(historyReceipt.contract)
      || historyReceipt.boot_id !== entry.name.slice(0, -5)
      || historyReceipt.receipt_sha256 !== sha256(Buffer.from(canonicalJson(historySemantic), 'utf8'))
      || historyReceipt.url !== 'http://127.0.0.1:4173/'
      || historyReceipt.topology !== 'single_fastapi_same_origin_static_api_and_in_process_worker'
      || historyReceipt.source?.repository !== serviceRoot
      || historyReceipt.source?.execution_root !== historyCapsule.executionRoot
      || !/^[0-9a-f]{40}$/.test(historyReceipt.source?.git_head || '')
      || !/^[0-9a-f]{64}$/.test(historyReceipt.source?.source_manifest_file_sha256 || '')
      || historyReceipt.source?.source_manifest_before_child_sha256 !== historyReceipt.source?.source_manifest_file_sha256
      || historyReceipt.source?.source_manifest_after_ready_sha256 !== historyReceipt.source?.source_manifest_file_sha256
      || canonicalJson(historyReceipt.process?.argv) !== canonicalJson(bootArgvFor(historyReceipt.runtime?.python_path, historyCapsule.executionRoot, historyReceipt.contract))
      || historyReceipt.process?.cwd !== serviceRoot
      || historyReceipt.process?.workers !== 1
      || canonicalJson(historyReceipt.environment?.values) !== canonicalJson(expectedHistoricalEnvironment)
      || historyReceipt.environment?.provider_credential_names_present?.length !== 0
      || historyReceipt.runtime?.data_root !== dataRoot
      || historyReceipt.runtime?.data_root_provenance_file_sha256 !== receipt.runtime.data_root_provenance_file_sha256
      || historyReceipt.runtime?.database_path !== path.join(dataRoot, 'casepath.db')
      || historyReceipt.runtime?.artifact_registry_path !== path.join(dataRoot, 'artifact-registry')
      || historyReceipt.environment?.values?.CASEPATH_DB_PATH !== path.join(dataRoot, 'casepath.db')
      || historyReceipt.environment?.values?.CASEPATH_ARTIFACT_REGISTRY_PATH !== path.join(dataRoot, 'artifact-registry')
      || Object.prototype.hasOwnProperty.call(historyReceipt.environment?.values || {}, 'PYTHONPATH')
      || historyReceipt.static.inventory_sha256 !== sha256(Buffer.from(canonicalJson(historyReceipt.static.inventory), 'utf8'))
      || historyReceipt.static.inventory_before_child_sha256 !== historyReceipt.static.inventory_sha256
      || historyReceipt.static.inventory_after_ready_sha256 !== historyReceipt.static.inventory_sha256
      || historyReceipt.static.deployment_file_sha256 !== historyReceipt.static.inventory.find(row => row.path === 'deployment.json')?.sha256
      || historyReceipt.attestation?.credential_configured !== false
      || historyReceipt.attestation?.model_ledger_records !== 0
      || historyReceipt.attestation?.model_ledger_network_calls !== 0
      || (historyReceipt.prior_boot_receipt_file_sha256 !== null
        && !/^[0-9a-f]{64}$/.test(historyReceipt.prior_boot_receipt_file_sha256))) {
      throw new Error(`candidate historical boot receipt is invalid: ${entry.name}`);
    }
    bootHistoryByFileSha.set(fileSha, { bytes: historyBytes, receipt: historyReceipt });
  }
  if (currentCapsuleIdentity === null) {
    throw new Error('candidate current boot lacks an exact capsule identity');
  }
  let currentRuntimeClosure = null;
  if (receipt.contract === 'casepath.local-runtime-boot/2.2.0') {
    currentRuntimeClosure = validateBootRuntimeClosure(
      receipt.runtime_closure,
      'candidate current boot runtime closure',
    );
    const recomputedRuntimeClosure = await captureExecutableRuntimeClosure({
      serviceRoot,
      runtimeRoot,
      executionRoot: currentCapsuleIdentity.executionRoot,
      pythonPath: receipt.runtime.python_path,
      sourceCommit: receipt.source.git_head,
    });
    if (canonicalJson(recomputedRuntimeClosure) !== canonicalJson(currentRuntimeClosure)) {
      throw new Error('candidate executable runtime closure differs from the current boot authority');
    }
  }
  const installedRosterIdentity = configuredServiceRoot
    ? await validateClosedInstalledTree(
      serviceRoot,
      currentCapsuleIdentity.expectedFiles,
      'candidate installed distribution',
    )
    : null;
  const visitedBootFiles = new Set([sha256(bytes)]);
  const reverseChronologicalBoots = [receipt];
  let priorBootSha = receipt.prior_boot_receipt_file_sha256;
  while (priorBootSha !== null) {
    if (visitedBootFiles.has(priorBootSha)) throw new Error('candidate boot history chain contains a cycle');
    const historical = bootHistoryByFileSha.get(priorBootSha);
    if (!historical) throw new Error(`candidate boot history is missing prior receipt: ${priorBootSha}`);
    visitedBootFiles.add(priorBootSha);
    reverseChronologicalBoots.push(historical.receipt);
    priorBootSha = historical.receipt.prior_boot_receipt_file_sha256;
  }
  if (visitedBootFiles.size !== bootHistoryByFileSha.size) {
    throw new Error('candidate boot history contains an receipt outside the current append-only chain');
  }
  let priorDurableBoot = null;
  let durableBootStarted = false;
  let closedRuntimeBootStarted = false;
  for (const bootReceipt of reverseChronologicalBoots.reverse()) {
    if (!['casepath.local-runtime-boot/2.1.0', 'casepath.local-runtime-boot/2.2.0'].includes(bootReceipt.contract)) {
      if (durableBootStarted) throw new Error('candidate boot history downgraded after durable authority');
      continue;
    }
    durableBootStarted = true;
    if (bootReceipt.contract === 'casepath.local-runtime-boot/2.2.0') {
      closedRuntimeBootStarted = true;
    } else if (closedRuntimeBootStarted) {
      throw new Error('candidate boot history downgraded after runtime-closure authority');
    }
    if (priorDurableBoot !== null) {
      const currentEvents = new Map(bootReceipt.attestation.durable_event_roster.map(row => [
        `${row.session_id}\u0000${row.loop_id}\u0000${row.sequence}`,
        row,
      ]));
      const currentRegistry = new Map(bootReceipt.attestation.durable_registry_inventory.map(row => [row.path, row]));
      for (const row of priorDurableBoot.attestation.durable_event_roster) {
        const key = `${row.session_id}\u0000${row.loop_id}\u0000${row.sequence}`;
        if (canonicalJson(currentEvents.get(key)) !== canonicalJson(row)) {
          throw new Error(`candidate durable event authority rolled back after boot ${priorDurableBoot.boot_id}`);
        }
      }
      for (const row of priorDurableBoot.attestation.durable_registry_inventory) {
        if (canonicalJson(currentRegistry.get(row.path)) !== canonicalJson(row)) {
          throw new Error(`candidate durable registry authority rolled back after boot ${priorDurableBoot.boot_id}`);
        }
      }
    }
    priorDurableBoot = bootReceipt;
  }
  const runtimePythonPath = path.resolve(receipt.runtime.python_path);
  if (runtimePythonPath !== path.join(runtimeRoot, 'venv', 'bin', 'python')) {
    throw new Error('candidate API Python stated path is not canonical');
  }
  await requireCanonicalDirectory(path.join(runtimeRoot, 'venv'), 'candidate Python environment root');
  await requireCanonicalDirectory(path.join(runtimeRoot, 'venv', 'bin'), 'candidate Python environment binary root');
  const runtimePythonLstat = await fs.lstat(runtimePythonPath);
  if (!runtimePythonLstat.isFile() && !runtimePythonLstat.isSymbolicLink()) {
    throw new Error('candidate API Python path is not a file or symlink');
  }
  const runtimePythonRealPath = await fs.realpath(runtimePythonPath);
  const runtimePythonHandle = await fs.open(runtimePythonRealPath, 'r');
  let runtimePythonBytes;
  let runtimePythonRealStat;
  try {
    runtimePythonRealStat = await runtimePythonHandle.stat({ bigint: true });
    if (!runtimePythonRealStat.isFile()) throw new Error('candidate API Python target is not a regular file');
    runtimePythonBytes = await runtimePythonHandle.readFile();
  } finally {
    await runtimePythonHandle.close();
  }
  const runtimePythonRelative = path.relative(runtimeRoot, runtimePythonPath);
  const lockBytes = await fs.readFile(path.join(REPOSITORY_ROOT, 'casepath-api', 'requirements.lock'));
  const installedDistributions = JSON.parse(execFileSync(
    runtimePythonPath,
    ['-I', '-B', '-c', "from importlib import metadata; import json; values=[f\"{d.metadata['Name']}=={d.version}\" for d in metadata.distributions() if d.metadata.get('Name')]; print(json.dumps(sorted(values,key=lambda value:(value.casefold(),value)),separators=(',',':')))"],
    { cwd: REPOSITORY_ROOT, encoding: 'utf8' },
  ));
  const normalizeDistribution = value => value.toLowerCase().replace(/[-_.]+/g, '-');
  const installedPinRows = installedDistributions.map(value => {
    const split = value.lastIndexOf('==');
    if (split <= 0) throw new Error(`installed distribution is unpinned: ${value}`);
    return [normalizeDistribution(value.slice(0, split)), value.slice(split + 2)];
  }).sort(([left], [right]) => left.localeCompare(right));
  if (new Set(installedPinRows.map(([name]) => name)).size !== installedPinRows.length) {
    throw new Error('installed distribution instances duplicate a normalized package');
  }
  const installedPins = Object.fromEntries(installedPinRows);
  const lockedPins = Object.fromEntries(lockBytes.toString('utf8').split(/\r?\n/)
    .map(value => value.trim()).filter(value => value && !value.startsWith('#'))
    .map(value => {
      const split = value.lastIndexOf('==');
      if (split <= 0 || value.indexOf('==') !== split) throw new Error(`requirements row is unpinned: ${value}`);
      return [normalizeDistribution(value.slice(0, split)), value.slice(split + 2)];
    }).sort(([left], [right]) => left.localeCompare(right)));
  const lsofIdentity = await executableIdentity('/usr/sbin/lsof', 'system lsof');
  const psIdentity = await executableIdentity('/bin/ps', 'system ps');
  const launchctlIdentity = await executableIdentity('/bin/launchctl', 'system launchctl');
  const plutilIdentity = await executableIdentity('/usr/bin/plutil', 'system plutil');
  const listenerPids = execFileSync(
    lsofIdentity.path,
    ['-nP', '-iTCP:4173', '-sTCP:LISTEN', '-t'],
    { encoding: 'utf8' },
  ).trim().split(/\s+/).filter(Boolean).map(Number);
  process.kill(receipt.process.pid, 0);
  const liveCwdLines = execFileSync(
    lsofIdentity.path,
    ['-n', '-a', '-p', String(receipt.process.pid), '-d', 'cwd', '-Fn'],
    { encoding: 'utf8' },
  ).trim().split(/\r?\n/);
  const liveCwds = liveCwdLines
    .filter(line => line.startsWith('n'))
    .map(line => line.slice(1));
  const liveProcessCommand = execFileSync(
    psIdentity.path,
    ['-ww', '-p', String(receipt.process.pid), '-o', 'command='],
    { encoding: 'utf8' },
  ).trim();
  const liveProcessStartText = execFileSync(
    psIdentity.path,
    ['-p', String(receipt.process.pid), '-o', 'lstart='],
    { encoding: 'utf8' },
  ).trim();
  const liveProcessStartedAtMs = Date.parse(liveProcessStartText);
  const receiptReadyAtMs = Date.parse(receipt.ready_at_utc);
  if (!Number.isFinite(liveProcessStartedAtMs) || !Number.isFinite(receiptReadyAtMs)
    || liveProcessStartedAtMs > receiptReadyAtMs
    || receiptReadyAtMs - liveProcessStartedAtMs > 300_000) {
    throw new Error('candidate live listener start time is inconsistent with the boot authority');
  }
  const liveTextLines = execFileSync(
    lsofIdentity.path,
    ['-n', '-a', '-p', String(receipt.process.pid), '-d', 'txt', '-F', 'fdDin'],
    { encoding: 'utf8' },
  ).trim().split(/\r?\n/);
  const liveTextRecords = [];
  let liveTextRecord = null;
  for (const line of liveTextLines) {
    if (line.startsWith('f')) {
      if (liveTextRecord !== null) liveTextRecords.push(liveTextRecord);
      liveTextRecord = { descriptor: line.slice(1), device: null, inode: null, path: null };
    } else if (liveTextRecord !== null && line.startsWith('D')) liveTextRecord.device = line.slice(1);
    else if (liveTextRecord !== null && line.startsWith('i')) liveTextRecord.inode = line.slice(1);
    else if (liveTextRecord !== null && line.startsWith('n')) liveTextRecord.path = line.slice(1);
  }
  if (liveTextRecord !== null) liveTextRecords.push(liveTextRecord);
  const mappedPythonRecord = liveTextRecords.find(row => row.path === runtimePythonRealPath);
  if (!mappedPythonRecord
    || BigInt(mappedPythonRecord.device) !== runtimePythonRealStat.dev
    || BigInt(mappedPythonRecord.inode) !== runtimePythonRealStat.ino) {
    throw new Error('candidate live listener executable text differs from the attested Python runtime');
  }
  const liveTextRoster = liveTextRecords
    .map(row => ({ ...row }))
    .sort((left, right) => canonicalJson(left).localeCompare(canonicalJson(right)));
  const expectedLiveProcessCommand = receipt.process.argv.join(' ');
  if (canonicalJson(liveCwds) !== canonicalJson([serviceRoot])) {
    throw new Error('candidate live listener working directory differs from the installed service root');
  }
  if (liveProcessCommand !== expectedLiveProcessCommand) {
    throw new Error('candidate live listener command differs from the boot authority');
  }
  const liveProcessAncestry = [];
  const visitedProcessIds = new Set();
  let ancestorPid = receipt.process.pid;
  for (let depth = 0; depth < 12; depth += 1) {
    if (visitedProcessIds.has(ancestorPid)) throw new Error('candidate live process ancestry contains a cycle');
    visitedProcessIds.add(ancestorPid);
    const raw = execFileSync(
      psIdentity.path,
      ['-ww', '-p', String(ancestorPid), '-o', 'pid=,ppid=,command='],
      { encoding: 'utf8' },
    ).trim();
    const match = raw.match(/^(\d+)\s+(\d+)\s+([\s\S]+)$/);
    if (!match) throw new Error('candidate live process ancestry row is malformed');
    const row = { pid: Number(match[1]), parent_pid: Number(match[2]), command: match[3] };
    liveProcessAncestry.push(row);
    if (row.pid === 1) break;
    if (configuredServiceRoot && row.pid !== receipt.process.pid && !row.command.includes(serviceRoot)) {
      throw new Error('candidate live launcher ancestry escapes the installed service root');
    }
    ancestorPid = row.parent_pid;
  }
  const launchdAncestor = liveProcessAncestry.at(-1);
  if (configuredServiceRoot
    && (launchdAncestor?.pid !== 1 || launchdAncestor.parent_pid !== 0 || launchdAncestor.command !== '/sbin/launchd')) {
    throw new Error('candidate live listener is not owned by the persistent launchd lineage');
  }
  const launchdJobTarget = `gui/${process.getuid()}/com.casepath.local-product`;
  const launchdJobText = execFileSync(
    launchctlIdentity.path,
    ['print', launchdJobTarget],
    { encoding: 'utf8' },
  );
  const launchdField = (expression, label) => {
    const matches = [...launchdJobText.matchAll(expression)];
    if (matches.length !== 1) throw new Error(`candidate launchd job ${label} is not unique`);
    return matches[0][1];
  };
  const launchdJobPlistPath = launchdField(/^\tpath = (.+)$/gm, 'plist path');
  const launchdJobState = launchdField(/^\tstate = (.+)$/gm, 'state');
  const launchdJobProgram = launchdField(/^\tprogram = (.+)$/gm, 'program');
  const launchdJobWorkingDirectory = launchdField(/^\tworking directory = (.+)$/gm, 'working directory');
  const launchdJobPid = Number(launchdField(/^\tpid = (\d+)$/gm, 'PID'));
  const argumentsMatch = launchdJobText.match(/\n\targuments = \{\n([\s\S]*?)\n\t\}\n\n\tworking directory = /);
  if (!argumentsMatch) throw new Error('candidate launchd job arguments are malformed');
  const launchdJobArguments = argumentsMatch[1].split(/\r?\n/).map(line => {
    if (!line.startsWith('\t\t')) throw new Error('candidate launchd job argument is malformed');
    return line.slice(2);
  });
  const expectedLaunchdPlistPath = path.join(
    process.env.HOME || '',
    'Library',
    'LaunchAgents',
    'com.casepath.local-product.plist',
  );
  const launchdPlistStatedPath = path.resolve(expectedLaunchdPlistPath);
  if (await fs.realpath(launchdPlistStatedPath) !== launchdPlistStatedPath) {
    throw new Error('candidate launchd plist has a symlinked path component');
  }
  const launchdPlistHandle = await fs.open(launchdPlistStatedPath, 'r');
  let launchdPlistBytes;
  let launchdPlistStat;
  try {
    launchdPlistStat = await launchdPlistHandle.stat({ bigint: true });
    if (!launchdPlistStat.isFile() || launchdPlistStat.nlink !== 1n) {
      throw new Error('candidate launchd plist is not a single-link regular file');
    }
    launchdPlistBytes = await launchdPlistHandle.readFile();
  } finally {
    await launchdPlistHandle.close();
  }
  const launchdPlistIdentity = {
    path: launchdPlistStatedPath,
    real_path: launchdPlistStatedPath,
    file_sha256: sha256(launchdPlistBytes),
    bytes: launchdPlistBytes.length,
    device: launchdPlistStat.dev.toString(),
    inode: launchdPlistStat.ino.toString(),
  };
  const launchdPlist = JSON.parse(execFileSync(
    plutilIdentity.path,
    ['-convert', 'json', '-o', '-', '--', '-'],
    { encoding: 'utf8', input: launchdPlistBytes },
  ));
  const launchdJobAncestryIndex = liveProcessAncestry.findIndex(row => row.pid === launchdJobPid);
  if (launchdJobPlistPath !== expectedLaunchdPlistPath
    || launchdJobState !== 'running'
    || launchdJobProgram !== launchdPlist.ProgramArguments?.[0]
    || launchdJobWorkingDirectory !== serviceRoot
    || launchdPlist.Label !== 'com.casepath.local-product'
    || launchdPlist.WorkingDirectory !== serviceRoot
    || canonicalJson(launchdJobArguments) !== canonicalJson(launchdPlist.ProgramArguments)
    || launchdPlist.ProgramArguments?.at(-2) !== path.join(serviceRoot, 'bin', 'casepath')
    || launchdPlist.ProgramArguments?.at(-1) !== 'dev'
    || launchdJobAncestryIndex !== liveProcessAncestry.length - 2
    || liveProcessAncestry[launchdJobAncestryIndex]?.parent_pid !== 1) {
    throw new Error('candidate live listener is not bound to the exact persistent launchd job');
  }
  const liveResponses = {};
  for (const [name, url] of Object.entries({
    health_response_sha256: 'http://127.0.0.1:4173/healthz',
    ready_response_sha256: 'http://127.0.0.1:4173/readyz',
    model_ledger_response_sha256: 'http://127.0.0.1:4173/api/model-ledger',
    root_html_sha256: 'http://127.0.0.1:4173/',
  })) {
    const response = await fetch(url, { headers: { Accept: name === 'root_html_sha256' ? 'text/html' : 'application/json' } });
    if (!response.ok) throw new Error(`candidate runtime endpoint is unavailable: ${url}`);
    liveResponses[name] = sha256(Buffer.from(await response.arrayBuffer()));
  }
  const liveWorkspaceResponse = await fetch('http://127.0.0.1:4173/api/claim-loops/v1/workspace/claims?limit=1', { headers: { Accept: 'application/json' } });
  if (!liveWorkspaceResponse.ok) throw new Error('candidate workspace endpoint is unavailable');
  const liveWorkspace = await liveWorkspaceResponse.json();
  const liveWorkspaceSemantic = { ...liveWorkspace };
  const liveWorkspaceProjectionSha = liveWorkspaceSemantic.projection_sha256;
  delete liveWorkspaceSemantic.projection_sha256;
  requireWorkspaceRosterPolicy({
    attestedStateRosterSha256: receipt.attestation.workspace_state_roster_sha256,
    liveStateRosterSha256: liveWorkspace.state_roster_sha256,
    allowValidatedWorkspaceJournalAdvance,
  });
  const staticRows = receipt.static.inventory.map(row => {
    exactKeys(row, ['path', 'sha256', 'bytes'], 'candidate API boot static row');
    return `${row.sha256}  ${row.path}`;
  }).sort();
  for (const row of receipt.static.inventory) {
    const file = await requireRegularFile(path.join(expectedExecutionRoot, 'casepath-public', row.path), path.join(expectedExecutionRoot, 'casepath-public'));
    const fileBytes = await fs.readFile(file.resolved);
    if (file.relative !== row.path || sha256(fileBytes) !== row.sha256 || fileBytes.length !== row.bytes) {
      throw new Error(`candidate API boot static row drifted: ${row.path}`);
    }
    if (row.path !== 'deployment.json') {
      const authored = await requireRegularFile(path.join(REPOSITORY_ROOT, 'casepath', row.path), path.join(REPOSITORY_ROOT, 'casepath'));
      const authoredBytes = await fs.readFile(authored.resolved);
      if (sha256(authoredBytes) !== row.sha256 || authoredBytes.length !== row.bytes) {
        throw new Error(`built static file differs from its authored source: ${row.path}`);
      }
    }
  }
  const deployment = JSON.parse(await fs.readFile(deploymentPath, 'utf8'));
  const release = JSON.parse(await fs.readFile(path.join(REPOSITORY_ROOT, 'casepath', 'release.json'), 'utf8'));
  const expectedArgv = bootArgvFor(receipt.runtime.python_path, expectedExecutionRoot, receipt.contract);
  const expectedEnvironment = bootEnvironmentFor(sourceIdentity.git.head, expectedExecutionRoot);
  const expectedEnvironmentKeys = Object.keys(expectedEnvironment);
  if (!['casepath.local-runtime-boot/2.1.0', 'casepath.local-runtime-boot/2.2.0'].includes(receipt.contract)
    || receipt.url !== 'http://127.0.0.1:4173/'
    || receipt.topology !== 'single_fastapi_same_origin_static_api_and_in_process_worker'
    || receipt.receipt_sha256 !== semanticSha
    || receipt.launcher.path !== 'bin/casepath'
    || receipt.launcher.sha256 !== sha256(launcherBytes)
    || receipt.launcher.bytes !== launcherBytes.length
    || receipt.process.pid !== receipt.process.listener_owner_pid
    || JSON.stringify(listenerPids) !== JSON.stringify([receipt.process.pid])
    || receipt.process.cwd !== serviceRoot
    || JSON.stringify(receipt.process.argv) !== JSON.stringify(expectedArgv)
    || receipt.process.workers !== 1
    || JSON.stringify(Object.keys(receipt.environment.values).sort()) !== JSON.stringify([...expectedEnvironmentKeys].sort())
    || canonicalJson(receipt.environment.values) !== canonicalJson(expectedEnvironment)
    || receipt.environment.provider_credential_names_present.length !== 0
    || receipt.environment.values.CASEPATH_MODEL_MODE !== 'deterministic_reference'
    || receipt.environment.values.CASEPATH_SOURCE_COMMIT !== receipt.source.git_head
    || receipt.environment.values.CASEPATH_LOCAL_STATIC_ROOT !== path.join(expectedExecutionRoot, 'casepath-public')
    || Object.prototype.hasOwnProperty.call(receipt.environment.values, 'PYTHONPATH')
    || receipt.environment.values.CASEPATH_DB_PATH !== path.join(dataRoot, 'casepath.db')
    || receipt.environment.values.CASEPATH_ARTIFACT_REGISTRY_PATH !== path.join(dataRoot, 'artifact-registry')
    || receipt.environment.values.CASEPATH_LOCAL_RUNTIME_RECEIPT !== path.join(runtimeRoot, 'runtime-boot-receipt.json')
    || receipt.environment.values.LANGCHAIN_TRACING !== 'false'
    || receipt.environment.values.LANGCHAIN_TRACING_V2 !== 'false'
    || receipt.environment.values.LANGSMITH_TRACING !== 'false'
    || receipt.source.repository !== serviceRoot
    || receipt.source.execution_root !== expectedExecutionRoot
    || receipt.source.source_capsule_receipt_file_sha256 !== sha256(capsuleReceiptBytes)
    || capsuleReceiptFile.relative !== 'CAPSULE_RECEIPT.json'
    || capsuleReceipt.contract !== 'casepath.sealed-source-capsule/1.0.0'
    || capsuleSemanticSha !== sha256(Buffer.from(canonicalJson(capsuleSemantic), 'utf8'))
    || capsuleReceipt.source_manifest_file_sha256 !== sha256(sourceManifestBytes)
    || !capsuleManifestBytes.equals(sourceManifestBytes)
    || capsuleReceipt.source_roster_sha256 !== sourceManifestRosterSha256
    || capsuleReceipt.source_file_count !== sourceManifest.files.length
    || !capsuleArtifactManifestBytes.equals(await fs.readFile(artifactManifestPath))
    || receipt.source.source_manifest_path !== 'casepath/source-manifest.json'
    || receipt.source.git_branch !== (serviceRoot === REPOSITORY_ROOT
      ? sourceIdentity.git.branch
      : 'source-archive')
    || receipt.source.git_head !== sourceIdentity.git.head
    || receipt.source.source_manifest_file_sha256 !== sha256(sourceManifestBytes)
    || receipt.source.source_manifest_before_child_sha256 !== receipt.source.source_manifest_file_sha256
    || receipt.source.source_manifest_after_ready_sha256 !== receipt.source.source_manifest_file_sha256
    || !sourceManifestRows.length
    || receipt.source.artifact_manifest_file_sha256 !== sha256(await fs.readFile(artifactManifestPath))
    || runtimePythonRealPath !== receipt.runtime.python_real_path
    || sha256(runtimePythonBytes) !== receipt.runtime.python_file_sha256
    || runtimePythonRelative.startsWith('..')
    || path.isAbsolute(runtimePythonRelative)
    || receipt.runtime.python_version !== '3.13.9'
    || receipt.runtime.requirements_lock_sha256 !== sha256(lockBytes)
    || receipt.runtime.installed_distributions_sha256 !== sha256(Buffer.from(canonicalJson(receipt.runtime.installed_distributions), 'utf8'))
    || JSON.stringify(receipt.runtime.installed_distributions) !== JSON.stringify(installedDistributions)
    || JSON.stringify(installedPins) !== JSON.stringify(lockedPins)
    || receipt.runtime.data_root !== dataRoot
    || receipt.runtime.data_root_provenance_file_sha256 !== sha256(dataRootProvenanceBytes)
    || receipt.runtime.database_path !== path.join(dataRoot, 'casepath.db')
    || receipt.runtime.artifact_registry_path !== path.join(dataRoot, 'artifact-registry')
    || JSON.stringify(staticRows) !== JSON.stringify(builtRows)
    || receipt.static.inventory_sha256 !== sha256(Buffer.from(canonicalJson(receipt.static.inventory), 'utf8'))
    || receipt.static.inventory_before_child_sha256 !== receipt.static.inventory_sha256
    || receipt.static.inventory_after_ready_sha256 !== receipt.static.inventory_sha256
    || receipt.static.deployment_file_sha256 !== sha256(await fs.readFile(deploymentPath))
    || deployment.contract !== 'casepath.deployment-identity/1.0.0'
    || deployment.alignment_eligible !== true
    || deployment.source_commit !== sourceIdentity.git.head
    || deployment.release_id !== release.release_id
    || deployment.component_version !== release.components?.frontend?.version
    || deployment.component_contract !== release.components?.frontend?.contract
    || receipt.attestation.credential_configured !== false
    || receipt.attestation.model_ledger_records !== 0
    || receipt.attestation.model_ledger_network_calls !== 0
    || seedReceipt.contract !== 'casepath.sealed-workspace-seed/1.0.0'
    || seedReceipt.receipt_sha256 !== sha256(Buffer.from(canonicalJson(seedWrapperSemantic), 'utf8'))
    || seedReceipt.source_authority.contract !== 'casepath.sealed-seed-source-authority/1.0.0'
    || seedReceipt.source_authority.source_manifest_file_sha256 !== sha256(sourceManifestBytes)
    || seedReceipt.source_authority.source_manifest_roster_sha256 !== sourceManifestRosterSha256
    || seedReceipt.seed_receipt.contract !== 'casepath.claim-workspace-seed/1.0.0'
    || seedReceipt.seed_receipt.receipt_sha256 !== sha256(Buffer.from(canonicalJson(seedSemantic), 'utf8'))
    || !Number.isInteger(expectedClaimCount) || expectedClaimCount <= 0
    || seedReceipt.seed_receipt.claim_count !== expectedClaimCount
    || seedReceipt.seed_receipt.new_import_count + seedReceipt.seed_receipt.replayed_import_count !== expectedClaimCount
    || ['model_calls', 'provider_calls', 'credential_reads', 'cost_usd'].some(field => seedReceipt.seed_receipt[field] !== 0)
    || receipt.attestation.workspace_seed_receipt_file_sha256 !== sha256(seedReceiptBytes)
    || !attestedSeedReceiptBytes.equals(seedReceiptBytes)
    || receipt.attestation.workspace_seed_receipt_sha256 !== seedReceipt.receipt_sha256
    || receipt.attestation.workspace_seed_event_roster_sha256 !== seedReceipt.seed_receipt.event_roster_sha256
    || receipt.attestation.workspace_total_count !== expectedClaimCount
    || receipt.attestation.workspace_authority !== 'claim_loop_events'
    || receipt.attestation.workspace_corpus_identity_sha256 !== sha256(Buffer.from(canonicalJson(seedReceipt.seed_receipt.corpus_identity), 'utf8'))
    || !/^[0-9a-f]{64}$/.test(receipt.attestation.workspace_response_sha256)
    || receipt.attestation.workspace_response_sha256 !== sha256(attestedWorkspaceBytes)
    || receipt.attestation.workspace_projection_sha256 !== attestedWorkspaceProjectionSha
    || attestedWorkspaceProjectionSha !== sha256(Buffer.from(canonicalJson(attestedWorkspaceSemantic), 'utf8'))
    || attestedWorkspace.state_roster_sha256 !== receipt.attestation.workspace_state_roster_sha256
    || attestedWorkspace.total_count !== expectedClaimCount
    || attestedWorkspace.authority !== 'claim_loop_events'
    || canonicalJson(attestedWorkspace.corpus_identity) !== canonicalJson(seedReceipt.seed_receipt.corpus_identity)
    || liveWorkspace.contract !== 'casepath.claim-queue-projection/2.0.0'
    || liveWorkspaceProjectionSha !== sha256(Buffer.from(canonicalJson(liveWorkspaceSemantic), 'utf8'))
    || liveWorkspace.total_count !== expectedClaimCount
    || liveWorkspace.authority !== 'claim_loop_events'
    || canonicalJson(liveWorkspace.corpus_identity) !== canonicalJson(seedReceipt.seed_receipt.corpus_identity)
    || Object.entries(liveResponses).some(([name, value]) => receipt.attestation[name] !== value)
    || receipt.attestation.source_reverified_after_ready !== true) {
    throw new Error('candidate API boot receipt does not bind this source snapshot and zero-activity runtime');
  }
  execFileSync(
    runtimePythonPath,
    [
      '-I',
      '-S',
      '-B',
      '-P',
      path.join(expectedExecutionRoot, 'casepath', 'tools', 'validate_local_runtime_history.py'),
      '--verify-only',
      runtimeRoot,
      dataRoot,
      serviceRoot,
    ],
    {
      cwd: serviceRoot,
      env: {
        LANG: 'C.UTF-8',
        LC_ALL: 'C.UTF-8',
        PATH: '/usr/bin:/bin:/usr/sbin:/sbin',
        PYTHONHASHSEED: '0',
        PYTHONNOUSERSITE: '1',
        PYTHONSAFEPATH: '1',
        PYTHONDONTWRITEBYTECODE: '1',
        TZ: 'UTC',
      },
      stdio: 'pipe',
    },
  );
  execFileSync(
    runtimePythonPath,
    [
      '-I',
      '-B',
      '-P',
      '-c',
      'import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); sys.argv[0]="validate_journal"; runpy.run_module("casepath_api.validate_journal",run_name="__main__",alter_sys=True)',
      path.join(expectedExecutionRoot, 'casepath-api'),
      path.join(dataRoot, 'casepath.db'),
    ],
    {
      cwd: serviceRoot,
      env: {
        HOME: path.join(runtimeRoot, 'home'),
        LANG: 'C.UTF-8',
        LC_ALL: 'C.UTF-8',
        PATH: `${path.join(runtimeRoot, 'venv', 'bin')}:/usr/bin:/bin:/usr/sbin:/sbin`,
        PYTHONHASHSEED: '0',
        PYTHONNOUSERSITE: '1',
        PYTHONSAFEPATH: '1',
        PYTHONDONTWRITEBYTECODE: '1',
        PYTHONPYCACHEPREFIX: path.join(runtimeRoot, 'pycache'),
        SOURCE_DATE_EPOCH: '1786406400',
        TMPDIR: path.join(runtimeRoot, 'tmp'),
        TZ: 'UTC',
      },
      stdio: 'pipe',
    },
  );
  return {
    bytes,
    receipt,
    identity: {
      contract: receipt.contract,
      receipt_file_sha256: sha256(bytes),
      receipt_semantic_sha256: receipt.receipt_sha256,
      source_manifest_file_sha256: receipt.source.source_manifest_file_sha256,
      service_root: serviceRoot,
      execution_root: currentCapsuleIdentity.executionRoot,
      capsule_receipt_file_sha256: currentCapsuleIdentity.capsuleReceiptFileSha256,
      capsule_roster_sha256: currentCapsuleIdentity.capsuleRosterSha256,
      source_roster_sha256: currentCapsuleIdentity.sourceRosterSha256,
      static_roster_sha256: currentCapsuleIdentity.staticRosterSha256,
      installed_non_runtime_roster: installedRosterIdentity,
      runtime_closure_sha256: currentRuntimeClosure?.closure_sha256 || null,
      runtime_subordinate_closure_sha256: currentRuntimeClosure?.subordinate_closure_sha256 || null,
      python_runtime: currentRuntimeClosure?.sections.python_runtime || null,
      permutation_subprocess: currentRuntimeClosure?.sections.launch_context.permutation_subprocess || null,
      process_pid: receipt.process.pid,
      live_process: {
        cwd: liveCwds[0],
        command: liveProcessCommand,
        command_sha256: sha256(Buffer.from(liveProcessCommand, 'utf8')),
        started_at_host_text: liveProcessStartText,
        started_at_epoch_ms: liveProcessStartedAtMs,
        ready_at_epoch_ms: receiptReadyAtMs,
        executable_text_path: runtimePythonRealPath,
        executable_text_sha256: sha256(runtimePythonBytes),
        executable_text_device: mappedPythonRecord.device,
        executable_text_inode: mappedPythonRecord.inode,
        loaded_text_record_count: liveTextRoster.length,
        loaded_text_record_roster_sha256: sha256(Buffer.from(canonicalJson(liveTextRoster), 'utf8')),
        ancestry: liveProcessAncestry,
        ancestry_sha256: sha256(Buffer.from(canonicalJson(liveProcessAncestry), 'utf8')),
      },
      launchd_job: {
        target: launchdJobTarget,
        root_pid: launchdJobPid,
        state: launchdJobState,
        program: launchdJobProgram,
        arguments: launchdJobArguments,
        working_directory: launchdJobWorkingDirectory,
        plist: launchdPlistIdentity,
        job_print_sha256: sha256(Buffer.from(launchdJobText, 'utf8')),
      },
      system_tools: {
        lsof: lsofIdentity,
        ps: psIdentity,
        launchctl: launchctlIdentity,
        plutil: plutilIdentity,
      },
      prior_boot_receipt_file_sha256: receipt.prior_boot_receipt_file_sha256,
      boot_history_entry_count: bootHistoryByFileSha.size,
    },
  };
}

export async function captureCandidateSourceSnapshot({
  requireApiBootReceipt = false,
  allowValidatedWorkspaceJournalAdvance = false,
} = {}) {
  const source = await sourceIdentity();
  const sourceRows = source.rows;
  const builtRows = await regularTreeRows(path.join(REPOSITORY_ROOT, 'casepath-public'));
  const builtPaths = builtRows.map(row => row.slice(66)).sort();
  if (JSON.stringify(builtPaths) !== JSON.stringify(EXPECTED_BUILT_STATIC_PATHS)) {
    throw new Error(`built product inventory mismatch: ${JSON.stringify(builtPaths)}`);
  }
  const identity = {
    contract: 'casepath.candidate-source-identity/1.0.0',
    git: source.git,
    source: manifestIdentity(sourceRows),
    built_static: manifestIdentity(builtRows),
  };
  const apiBoot = await captureApiBootReceipt(
    builtRows,
    identity,
    {
      required: requireApiBootReceipt,
      allowValidatedWorkspaceJournalAdvance,
    },
  );
  return {
    identity,
    sourceRows,
    builtRows,
    apiBootReceipt: apiBoot?.receipt || null,
    apiBootReceiptBytes: apiBoot?.bytes || null,
    apiBootIdentity: apiBoot?.identity || null,
  };
}

export async function captureCandidateSourceIdentity() {
  return (await captureCandidateSourceSnapshot()).identity;
}

async function executableIdentity(candidate, label) {
  if (typeof candidate !== 'string' || !path.isAbsolute(candidate)) {
    throw new Error(`${label} must be an absolute path`);
  }
  const stated = path.resolve(candidate);
  const statedStat = await fs.lstat(stated);
  if (!statedStat.isFile() || statedStat.isSymbolicLink()) {
    throw new Error(`${label} must be a non-symlink regular file: ${stated}`);
  }
  const real = await fs.realpath(stated);
  if (real !== stated) throw new Error(`${label} has a symlinked path component: ${stated}`);
  const bytes = await fs.readFile(real);
  return {
    path: stated,
    real_path: real,
    file_sha256: sha256(bytes),
    bytes: bytes.length,
  };
}

export async function captureBrowserExecutionReceipt({
  gatePath,
  outputPath,
  outputEnvironmentKey,
  browserVersion,
  baseUrl,
  apiUrl,
}) {
  const environmentKeys = Object.keys(process.env).sort();
  const expectedEnvironmentKeys = [
    'API_URL',
    'BASE_URL',
    'HOME',
    'LANG',
    'LC_ALL',
    'PATH',
    'PLAYWRIGHT_EXECUTABLE_PATH',
    'TMPDIR',
    'TZ',
    outputEnvironmentKey,
  ];
  if (process.platform === 'darwin') {
    const expectedTextEncoding = `0x${process.getuid().toString(16).toUpperCase()}:0x0:0x0`;
    if (process.env.__CF_USER_TEXT_ENCODING !== expectedTextEncoding) {
      throw new Error('macOS text-encoding environment identity is not the exact host-derived value');
    }
    expectedEnvironmentKeys.push('__CF_USER_TEXT_ENCODING');
  }
  for (const optionalKey of [
    'CASEPATH_ALLOW_PRODUCTION_MUTATION',
    'CASEPATH_EXPECTED_SOURCE_COMMIT',
    'CASEPATH_EXPECT_REAL_NEMOTRON',
    'CASEPATH_GATE1_QA_ROOT',
    'CASEPATH_QA_API_BOOT_RECEIPT',
    'CASEPATH_QA_RUN_ID',
    'CASEPATH_QA_SERVICE_ROOT',
  ]) {
    if (Object.hasOwn(process.env, optionalKey)) expectedEnvironmentKeys.push(optionalKey);
  }
  expectedEnvironmentKeys.sort();
  if (JSON.stringify(environmentKeys) !== JSON.stringify(expectedEnvironmentKeys)) {
    throw new Error(`browser gate environment is not closed: ${JSON.stringify(environmentKeys)}`);
  }
  const forbiddenEnvironmentKeys = environmentKeys.filter(key => /(?:OPENROUTER|API_KEY|TOKEN|SECRET|CREDENTIAL|PASSWORD)/i.test(key)
    && key !== 'CASEPATH_QA_API_BOOT_RECEIPT');
  if (forbiddenEnvironmentKeys.length) {
    throw new Error(`browser gate environment contains forbidden authority: ${forbiddenEnvironmentKeys.join(',')}`);
  }
  const normalizedBase = new URL(baseUrl);
  const normalizedApi = new URL(apiUrl);
  for (const [label, value] of [['base', normalizedBase], ['api', normalizedApi]]) {
    if (value.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(value.hostname)) {
      throw new Error(`${label} URL is not loopback HTTP: ${value.href}`);
    }
  }
  if (path.resolve(process.env[outputEnvironmentKey] || '') !== path.resolve(outputPath)) {
    throw new Error('browser gate output path does not match its closed environment');
  }
  const gate = await executableIdentity(path.resolve(gatePath), 'browser gate');
  const node = await executableIdentity(process.execPath, 'Node executable');
  const browser = await executableIdentity(process.env.PLAYWRIGHT_EXECUTABLE_PATH || '', 'browser executable');
  const qaPackagePath = path.join(REPOSITORY_ROOT, 'casepath-qa', 'package.json');
  const qaLockPath = path.join(REPOSITORY_ROOT, 'casepath-qa', 'package-lock.json');
  const playwrightPackagePath = path.join(REPOSITORY_ROOT, 'casepath-qa', 'node_modules', 'playwright', 'package.json');
  const [qaPackage, qaLock, playwrightPackage] = await Promise.all([
    executableIdentity(qaPackagePath, 'QA package'),
    executableIdentity(qaLockPath, 'QA package lock'),
    executableIdentity(playwrightPackagePath, 'Playwright package'),
  ]);
  const expectedArgv = [process.execPath, gate.path];
  if (process.execArgv.length || JSON.stringify(process.argv) !== JSON.stringify(expectedArgv)) {
    throw new Error(`browser gate argv is not exact: ${JSON.stringify({ execArgv: process.execArgv, argv: process.argv })}`);
  }
  const environmentValues = Object.fromEntries(environmentKeys.map(key => [key, process.env[key]]));
  const payload = {
    contract: 'casepath.browser-execution-receipt/1.0.0',
    runtime: {
      node,
      node_version: process.version,
      qa_package: qaPackage,
      qa_package_lock: qaLock,
      playwright_package: playwrightPackage,
      browser,
      browser_version: browserVersion,
      launch: {
        headless: true,
        args: ['--no-sandbox', '--disable-dev-shm-usage'],
        service_workers: 'block',
      },
    },
    command: {
      argv: process.argv,
      exec_argv: process.execArgv,
      cwd: process.cwd(),
      gate,
      environment_keys: environmentKeys,
      environment_values: environmentValues,
      output_environment_key: outputEnvironmentKey,
      output_path: path.resolve(outputPath),
      base_url: normalizedBase.origin,
      api_url: normalizedApi.origin,
    },
  };
  return { ...payload, receipt_sha256: sha256(Buffer.from(canonicalJson(payload), 'utf8')) };
}

export async function installLoopbackNetworkGuard(context, { baseUrl, apiUrl, builtRows }) {
  const allowedOrigins = [...new Set([new URL(baseUrl).origin, new URL(apiUrl).origin])].sort();
  for (const origin of allowedOrigins) {
    const parsed = new URL(origin);
    if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(parsed.hostname)) {
      throw new Error(`browser network origin is not loopback HTTP: ${origin}`);
    }
  }
  const builtFiles = new Map(builtRows.map(row => [row.slice(66), { sha256: row.slice(0, 64) }]));
  const observedOrigins = new Set();
  const observedSchemes = new Set();
  const blocked = [];
  const staticResponses = [];
  const responsePromises = [];
  context.on('request', request => {
    try {
      const url = new URL(request.url());
      observedSchemes.add(url.protocol);
      if (url.origin !== 'null') observedOrigins.add(url.origin);
    } catch (_) {}
  });
  context.on('response', response => {
    const promise = (async () => {
      const url = new URL(response.url());
      if (url.origin !== new URL(baseUrl).origin || response.request().method() !== 'GET' || !response.ok()) return;
      if (url.pathname.startsWith('/api/') || ['/healthz', '/readyz'].includes(url.pathname)) return;
      const relative = decodeURIComponent(url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\//, ''));
      const expected = builtFiles.get(relative);
      if (!expected) throw new Error(`browser loaded an unbound static path: ${relative}`);
      const bytes = await response.body();
      const actualSha = sha256(bytes);
      if (actualSha !== expected.sha256) throw new Error(`browser static response drifted from frozen bytes: ${relative}`);
      staticResponses.push({ path: relative, sha256: actualSha, bytes: bytes.length });
    })();
    responsePromises.push(promise);
  });
  await context.route('**/*', async route => {
    const request = route.request();
    let url;
    try {
      url = new URL(request.url());
    } catch (_) {
      blocked.push({ method: request.method(), url: request.url(), reason: 'invalid_url' });
      await route.abort('blockedbyclient');
      return;
    }
    if (['about:', 'blob:', 'data:'].includes(url.protocol) || allowedOrigins.includes(url.origin)) {
      await route.continue();
      return;
    }
    blocked.push({ method: request.method(), origin: url.origin, pathname: url.pathname, reason: 'non_loopback_origin' });
    await route.abort('blockedbyclient');
  });
  return {
    async snapshot() {
      await Promise.all(responsePromises);
      const uniqueStatic = [...new Map(staticResponses.map(row => [`${row.path}:${row.sha256}:${row.bytes}`, row])).values()]
        .sort((left, right) => left.path.localeCompare(right.path));
      const externalOrigins = [...observedOrigins].filter(origin => !allowedOrigins.includes(origin)).sort();
      return {
        contract: 'casepath.loopback-browser-network-boundary/1.0.0',
        allowed_origins: allowedOrigins,
        observed_origins: [...observedOrigins].sort(),
        observed_schemes: [...observedSchemes].sort(),
        blocked_requests: blocked,
        external_origins: externalOrigins,
        external_request_count: externalOrigins.length,
        blocked_request_count: blocked.length,
        static_responses: uniqueStatic,
        loopback_only: externalOrigins.length === 0 && blocked.length === 0,
      };
    },
  };
}

export async function summarizeLoopbackNetworkGuards(guards) {
  const snapshots = await Promise.all(guards.map(guard => guard.snapshot()));
  const staticResponses = [...new Map(snapshots.flatMap(value => value.static_responses)
    .map(row => [`${row.path}:${row.sha256}:${row.bytes}`, row])).values()]
    .sort((left, right) => left.path.localeCompare(right.path));
  return {
    contract: 'casepath.loopback-browser-network-summary/1.0.0',
    guard_count: snapshots.length,
    allowed_origins: [...new Set(snapshots.flatMap(value => value.allowed_origins))].sort(),
    observed_origins: [...new Set(snapshots.flatMap(value => value.observed_origins))].sort(),
    observed_schemes: [...new Set(snapshots.flatMap(value => value.observed_schemes))].sort(),
    external_request_count: snapshots.reduce((total, value) => total + value.external_request_count, 0),
    blocked_request_count: snapshots.reduce((total, value) => total + value.blocked_request_count, 0),
    blocked_requests: snapshots.flatMap(value => value.blocked_requests),
    static_responses: staticResponses,
    loopback_only: snapshots.every(value => value.loopback_only),
  };
}
