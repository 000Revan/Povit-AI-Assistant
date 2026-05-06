from hashlib import md5
from pathlib import Path


def file_md5(path: str | Path) -> str:
    digest = md5()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

