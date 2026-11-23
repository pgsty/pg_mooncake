"""Export the current release commit and its recursive Git submodule trees."""

import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def add_tree(archive, repo, revision, prefix, timestamp):
    entries = git(repo, "ls-tree", "-rz", "--full-tree", revision)
    with subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    ) as blobs:
        for entry in entries.split(b"\0")[:-1]:
            metadata, path = entry.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            name = os.fsdecode(path)
            member = tarfile.TarInfo(f"{prefix}/{name}")
            member.mtime = timestamp
            if kind == b"commit":
                child = repo / name
                if not (child / ".git").exists():
                    raise ValueError(f"Initialize submodule {child} before archiving")
                add_tree(archive, child, oid, member.name, timestamp)
                continue
            blobs.stdin.write(oid + b"\n")
            blobs.stdin.flush()
            object_id, object_type, size = blobs.stdout.readline().split()
            if (object_id, object_type) != (oid, b"blob"):
                raise ValueError(f"Missing blob for {member.name}")
            if mode == b"120000":
                member.type = tarfile.SYMTYPE
                member.mode = 0o777
                member.linkname = os.fsdecode(blobs.stdout.read(int(size)))
                archive.addfile(member)
            else:
                member.mode = int(mode, 8) & 0o777
                member.size = int(size)
                archive.addfile(member, blobs.stdout)
            if blobs.stdout.read(1) != b"\n":
                raise ValueError(f"Incomplete blob for {member.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    repo = Path(__file__).resolve().parents[1]
    revision = git(repo, "rev-parse", "HEAD").strip().decode()
    version = json.loads(git(repo, "show", f"{revision}:versions.json"))["pg_mooncake"]
    timestamp = int(git(repo, "show", "-s", "--format=%ct", revision))
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        compressed = Path(temp) / "source.tar.gz"
        with compressed.open("wb") as stream, gzip.GzipFile(
            filename="", mode="wb", fileobj=stream, mtime=0, compresslevel=6
        ) as zipped, tarfile.open(fileobj=zipped, mode="w|") as archive:
            add_tree(archive, repo, revision, f"pg_mooncake-{version}", timestamp)
        os.link(compressed, output)


if __name__ == "__main__":
    main()
