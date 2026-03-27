import argparse
import getpass
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Configure SMTP settings in .env")
    parser.add_argument("--email", required=True, help="SMTP email/account (e.g. your@gmail.com)")
    parser.add_argument("--app-password", help="SMTP app password (Gmail App Password)")
    parser.add_argument("--host", default="smtp.gmail.com", help="SMTP host")
    parser.add_argument("--port", default="587", help="SMTP port")
    parser.add_argument("--tls", default="true", choices=["true", "false"], help="Use TLS")
    return parser.parse_args()


def upsert_env_value(lines, key, value):
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{prefix}{value}"
            return
    lines.append(f"{prefix}{value}")


def main():
    args = parse_args()
    app_password = args.app_password or getpass.getpass("Enter SMTP app password: ")

    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"

    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    upsert_env_value(lines, "SMTP_HOST", args.host)
    upsert_env_value(lines, "SMTP_PORT", args.port)
    upsert_env_value(lines, "SMTP_USER", args.email)
    upsert_env_value(lines, "SMTP_PASSWORD", app_password)
    upsert_env_value(lines, "SMTP_FROM_EMAIL", args.email)
    upsert_env_value(lines, "SMTP_USE_TLS", args.tls)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"✅ SMTP settings updated in: {env_path}")
    print("Next: restart backend, then run: python backend/test_smtp_email.py <your_email>")


if __name__ == "__main__":
    main()
