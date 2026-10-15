#!/usr/bin/env python3
"""Human-invoked local releases; inspired by makefile-go's bump workflow."""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def sync(root, version):
    """Synchronize only owned release metadata; schema versions are independent."""
    paths = [root / 'VERSION', *sorted(root.glob('skills/lb-*/SKILL.md'))]
    (root / 'VERSION').write_text(version + '\n')
    for path in paths[1:]:
        text = path.read_text()
        front = text.split('---', 2)
        if len(front) != 3 or not re.search(r'^version: .+$', front[1], re.M):
            raise ValueError(f'Missing skill frontmatter version: {path}')
        front[1] = re.sub(r'^version: .+$', f'version: {version}', front[1], flags=re.M)
        path.write_text('---'.join(front))
    package_version = version.replace('-dev', '.dev0')
    for name, pattern in [
        ('pyproject.toml', r'(\[project\][\s\S]*?\nversion = ")[^"]+(")'),
        ('uv.lock', r'(\[\[package\]\]\nname = "lbkit"\nversion = ")[^"]+(")'),
    ]:
        path = root / name
        if not path.exists():
            continue
        text, count = re.subn(pattern, lambda m: m[1] + package_version + m[2], path.read_text(), count=1)
        if count != 1:
            raise ValueError(f'Missing package version: {path}')
        path.write_text(text)
        paths.append(path)
    return [str(path.relative_to(root)) for path in paths]


def commit(root, paths, message):
    git(root, 'add', '--', *paths)
    git(root, 'commit', '-m', message)
    return git(root, 'rev-parse', 'HEAD')


def release(root, version, apply=False, ref=None, next_dev=None, since=None):
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise ValueError('Release version must be x.y.z without a prefix or suffix')
    if git(root, 'status', '--porcelain'):
        raise ValueError('Working tree must be clean')
    if git(root, 'branch', '--show-current') != 'master':
        raise ValueError('Run releases from master')
    tag = 'v' + version
    if tag in git(root, 'tag', '--list').splitlines():
        raise ValueError(f'Tag already exists: {tag}')
    base = git(root, 'rev-parse', '--verify', (ref or 'HEAD') + '^{commit}')
    if ref:
        git(root, 'merge-base', '--is-ancestor', base, 'master')
    next_dev = next_dev or '.'.join([*version.split('.')[:2], str(int(version.split('.')[2]) + 1)])
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', next_dev):
        raise ValueError('Next development version must be x.y.z')
    if tuple(map(int, next_dev.split('.'))) <= tuple(map(int, version.split('.'))):
        raise ValueError('Next development version must follow the release')
    print(f'{tag}: baseline {base}; ' + ('historical release, master unchanged' if ref else f'master -> {next_dev}-dev'))
    if not apply:
        print('Preview only. Pass --apply to create commits and the annotated local tag.')
        return
    # Prepare in isolation: metadata/hook failures cannot leave master half-released.
    old_head = git(root, 'rev-parse', 'HEAD')
    with tempfile.TemporaryDirectory(prefix='lbkit-release-') as tmp:
        work = Path(tmp) / 'worktree'
        git(root, 'worktree', 'add', '--detach', str(work), base)
        try:
            paths = sync(work, version)
            config = root / 'cliff.toml'
            if config.exists():
                start = since
                if not ref:
                    versions = [t for t in git(root, 'tag').splitlines() if re.fullmatch(r'v\d+\.\d+\.\d+', t)]
                    if versions:
                        previous = max(versions, key=lambda t: tuple(map(int, t[1:].split('.'))))
                        if tuple(map(int, version.split('.'))) <= tuple(map(int, previous[1:].split('.'))):
                            raise ValueError('Release must follow the latest version tag')
                        start = git(root, 'merge-base', previous + '^{commit}', base)
                span = f'{start}..{base}' if start else base
                notes = subprocess.check_output(['git-cliff', span, '--config', str(config), '--offline', '--no-exec', '--tag', tag], cwd=root, text=True)
                existing = work / 'CHANGELOG.md'
                if not ref and existing.exists():
                    old = existing.read_text()
                    first = re.search(r'^## \d+\.\d+\.\d+', old, re.M)
                    if first:
                        notes = notes.rstrip() + '\n\n' + old[first.start():]
                existing.write_text(notes)
                paths.append('CHANGELOG.md')
            released = commit(work, paths, f'chore: release {tag}')
            final = released
            if not ref:
                paths = sync(work, next_dev + '-dev')
                final = commit(work, paths, f'chore: prepare {next_dev}-dev')
            # Atomic ref transaction: neither an existing tag nor a moved master is overwritten.
            if git(root, 'status', '--porcelain'):
                raise ValueError('Working tree changed during release preparation')
            commands = ['start', f'create refs/tags/{tag} {released}']
            # Create the annotation object without publishing a ref yet.
            identity = git(root, 'var', 'GIT_COMMITTER_IDENT')
            annotation = f'object {released}\ntype commit\ntag {tag}\ntagger {identity}\n\nRelease {tag}\n'
            obj = subprocess.check_output(['git', '-C', str(root), 'mktag'], input=annotation, text=True).strip()
            commands[1] = f'create refs/tags/{tag} {obj}'
            if not ref:
                commands.append(f'update refs/heads/master {final} {old_head}')
            commands += ['prepare', 'commit', '']
            subprocess.run(['git', '-C', str(root), 'update-ref', '--stdin'], input='\n'.join(commands), text=True, check=True)
            if not ref:
                git(root, 'reset', '--hard', final)
        finally:
            git(root, 'worktree', 'remove', '--force', str(work))
    print(f'Created {tag} locally; no push performed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', help='human-selected release version, e.g. 0.4.0')
    parser.add_argument('--apply', action='store_true', help='create release/tag and development commits')
    parser.add_argument('--ref', help='historical baseline; tag an isolated metadata commit, leave master unchanged')
    parser.add_argument('--since', help='historical changelog baseline (exclusive)')
    parser.add_argument('--next-dev', help='next master version without -dev; default: release patch + 1')
    args = parser.parse_args()
    root = Path(git(Path.cwd(), 'rev-parse', '--show-toplevel'))
    try:
        release(root, args.version, args.apply, args.ref, args.next_dev, args.since)
    except (ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Release failed: {exc}\n')


if __name__ == '__main__':
    main()
