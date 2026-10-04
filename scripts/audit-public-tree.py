"""Audit staged/tracked blobs (and optionally history); never print matched values."""
import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

FORBIDDEN = {"source-snapshot", "private-discovery", "runtime", "data", "state", "backups",
             "logs", "exports", "imports", "tmp", "cache", "saves", "savegames", "db", "lua",
             "workshop", "steamapps", "steamcmd", "secrets", ".venv", "__pycache__"}
PLACEHOLDER = re.compile(r"^(?:|CHANGEME|PLACEHOLDER|EXAMPLE|TEST_ONLY|FAKE|unit-test-placeholder|<[^>]+>|\$\{[A-Z_0-9]+:-\})$", re.I)


def inspect_blob(name, data):
    p = PurePosixPath(name)
    reasons = []
    if any(x.lower() in FORBIDDEN for x in p.parts):
        reasons.append("private-runtime-path")
    if p.name.startswith(".env") and p.name not in {'.env.example', '.env.test.example', '.env.live.example', '.env.versioncheck.example'}:
        reasons.append("real-env")
    if p.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".token", ".secret", ".key", ".pem", ".zip", ".gz", ".tar"}:
        reasons.append("private-or-binary-file")
    if data.startswith(b"SQLite format 3\0") or len(data) > 2 * 1024 * 1024:
        reasons.append("database-or-large-runtime")
    text = data.decode("utf-8", errors="replace")
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", text):
        reasons.append("private-key")
    if re.search(r"\b(?:mfa\.[\w-]{40,}|[\w-]{23,28}\.[\w-]{6}\.[\w-]{27,})\b", text):
        reasons.append("discord-token")
    if re.search(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})\b", text):
        reasons.append("access-token")
    if re.search(r"C:[\\/]Users[\\/][^\s<]+", text, re.I):
        reasons.append("private-user-path")
    for m in re.finditer(r"^[ \t]*(?:RCONPassword|Password|DiscordToken|PZ_API_TOKEN|API_TOKEN|DISCORD_TOKEN)[ \t]*=[ \t]*(.*)$", text, re.M | re.I):
        value = m[1].strip().strip('"\'')
        if not PLACEHOLDER.fullmatch(value):
            reasons.append("credential-assignment")
    for m in re.finditer(r'''^[ \t]*["']?(?:RCONPassword|Password|DiscordToken|PZ_API_TOKEN|API_TOKEN|DISCORD_TOKEN|api_token|discord_token)["']?[ \t]*[=:][ \t]*["']([^"'\r\n]*)["']''', text, re.M | re.I):
        if not PLACEHOLDER.fullmatch(m[1]):
            reasons.append("credential-literal")
    for m in re.finditer(r"^[ \t]*(?:RCONPassword|Password|DiscordToken|PZ_API_TOKEN|API_TOKEN|DISCORD_TOKEN)[ \t]*:[ \t]*([A-Za-z0-9_+/=.-]+)[ \t]*$", text, re.M | re.I):
        if not PLACEHOLDER.fullmatch(m[1]):
            reasons.append("credential-yaml-scalar")
    for m in re.finditer(r"^[ \t]*(?:PZ_ADVERTISE_\w+|GuildId|PZ_DISCORD_GUILD_ID)[ \t]*[=:][ \t]*(.+)$", text, re.M):
        if not PLACEHOLDER.fullmatch(m[1].strip().strip('"\'')):
            reasons.append("operator-address-or-id")
    return sorted(set(reasons))


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    failures = []
    rows = git("ls-files", "--stage", "-z").split(b"\0")
    for row in rows:
        if not row:
            continue
        meta, name = row.split(b"\t", 1)
        mode, sha, stage = meta.split()
        path = name.decode()
        reasons = inspect_blob(path, git("cat-file", "blob", sha.decode()))
        if mode != b"100644" and mode != b"100755":
            reasons.append("symlink-or-submodule")
        if reasons:
            failures.append((path, reasons))
    if args.history:
        for row in git("rev-list", "--objects", "--all").decode().splitlines():
            sha, sep, name = row.partition(" ")
            if sep and git("cat-file", "-t", sha).strip() == b"blob":
                reasons = inspect_blob(name, git("cat-file", "blob", sha))
                if reasons:
                    failures.append((name, reasons))
    for path, reasons in failures:
        print("FAIL", path, ",".join(reasons))
    print("Public tree audit:", "FAILED" if failures else "PASS", "(staged/tracked blobs" + (" and history)" if args.history else ")"))
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
