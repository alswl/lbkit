#!/usr/bin/env python3
"""Preview or apply a human-selected version bump to lbkit metadata."""
import argparse
import re
from pathlib import Path

VERSION_PATTERN = r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-dev)?'


def target_version(current, target):
    if not re.fullmatch(VERSION_PATTERN, current):
        raise ValueError(f'Invalid current version: {current}')
    if target in ('major', 'minor', 'patch'):
        parts = list(map(int, current.removesuffix('-dev').split('.')))
        index = ('major', 'minor', 'patch').index(target)
        parts[index] += 1
        parts[index + 1:] = [0] * (2 - index)
        return '.'.join(map(str, parts)) + ('-dev' if current.endswith('-dev') else '')
    if not re.fullmatch(VERSION_PATTERN, target):
        raise ValueError('Target must be major, minor, patch, or x.y.z[-dev]')
    return target


def prepare(root, version):
    """Validate all metadata before producing any writes."""
    changes = {root / 'VERSION': version + '\n'}
    skills = sorted(root.glob('skills/lb-*/SKILL.md'))
    if not skills:
        raise ValueError('No owned lb-* skills found')
    for path in skills:
        text = path.read_text()
        front = text.split('---', 2)
        if not text.startswith('---\n') or len(front) != 3:
            raise ValueError(f'Missing skill frontmatter: {path}')
        front[1], count = re.subn(r'^version: .+$', f'version: {version}', front[1], flags=re.M)
        if count != 1:
            raise ValueError(f'Expected one skill version: {path}')
        changes[path] = '---'.join(front)
    package_version = version.replace('-dev', '.dev0')
    for name, pattern in [
        ('pyproject.toml', r'(\[project\]\n(?:(?!\[)[^\n]*\n)*?version = ")[^"]+("[^\n]*)(?=\n|$)'),
        ('uv.lock', r'(\[\[package\]\]\nname = "lbkit"\nversion = ")[^"]+(")'),
    ]:
        path = root / name
        text, count = re.subn(pattern, lambda m: m[1] + package_version + m[2], path.read_text())
        if count != 1:
            raise ValueError(f'Expected one package version: {path}')
        changes[path] = text
    return changes


def bump(root, target='patch', apply=False):
    current = (root / 'VERSION').read_text().strip()
    version = target_version(current, target)
    changes = prepare(root, version)
    print(f'{current} -> {version}')
    for path, text in changes.items():
        if path.read_text() != text:
            print(path.relative_to(root))
            if apply:
                path.write_text(text)
    print('Version files updated.' if apply else 'Preview only; pass --apply to update version files.')
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?', default='patch', help='major, minor, patch (default), or x.y.z[-dev]')
    parser.add_argument('--apply', action='store_true', help='write the selected version to metadata files')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        bump(root, args.target, args.apply)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Bump failed: {exc}\n')


if __name__ == '__main__':
    main()
