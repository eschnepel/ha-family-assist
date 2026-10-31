"""Stand-in for the GitHub CLI used by the tests (ASCII output only)."""
import os
import sys
import time
from pathlib import Path

config = Path(os.environ["GH_CONFIG_DIR"])
config.mkdir(parents=True, exist_ok=True)
hosts = config / "hosts"
args = sys.argv[1:]
unsupported = set(filter(None, os.environ.get("FAKE_GH_UNSUPPORTED", "").split(",")))

if args[:3] == ["auth", "login", "--help"]:
    print("Flags:")
    for flag in ["--hostname", "--git-protocol", "--insecure-storage", "--skip-ssh-key", "--web", "--with-token"]:
        if flag not in unsupported:
            print(f"  {flag}  some description")
    sys.exit(0)
elif args[:2] == ["auth", "login"]:
    for flag in unsupported:
        if flag in args:
            print(f"unknown flag: {flag}\n\nUsage:  gh auth login [flags]\n\nFlags:\n"
                  "  -w, --web   Open a browser to authenticate\n"
                  "      --with-token   Read token from standard input")
            sys.exit(1)
    required = {"--hostname", "github.com", "--web"}
    if not required <= set(args) or os.environ.get("GH_PROMPT_DISABLED") != "1":
        print("unexpected arguments", args)
        sys.exit(2)
    print("! First copy your one-time code: ABCD-1234", flush=True)
    print("Open this URL to continue in your web browser: https://github.com/login/device", flush=True)
    for _ in range(300):
        if (config / "approve").exists():
            hosts.write_text("gho_faketoken")
            print("Authentication complete.", flush=True)
            sys.exit(0)
        if (config / "deny").exists():
            print("authorization denied by user", flush=True)
            sys.exit(1)
        time.sleep(0.05)
    sys.exit(1)
elif args[:2] == ["auth", "token"]:
    if hosts.exists():
        print(hosts.read_text())
        sys.exit(0)
    sys.exit(1)
elif args[:2] == ["auth", "status"]:
    if hosts.exists():
        print("github.com\n  Logged in to github.com account octocat (hosts)")
        sys.exit(0)
    sys.exit(1)
elif args[:2] == ["auth", "logout"]:
    hosts.unlink(missing_ok=True)
    sys.exit(0)
sys.exit(3)
