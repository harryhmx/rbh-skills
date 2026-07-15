#!/usr/bin/env python3
"""CLI entry point for rbh-core.

Provides command-line interface for authentication and project management.
"""

import argparse
import json
import sys
import importlib.util
from pathlib import Path

# Add skills/ root to Python path for config, common imports
_skills_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_skills_root))

# Dynamically import modules from rbh-core (kebab-case directory)
_script_dir = Path(__file__).parent

def _load_module(module_name: str, file_name: str):
    """Load a module from rbh-core/scripts/ using importlib."""
    spec = importlib.util.spec_from_file_location(module_name, _script_dir / file_name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# Load modules
_auth_mod = _load_module("rbh_core_auth", "auth.py")
_user_mod = _load_module("rbh_core_user", "user.py")
_session_mod = _load_module("rbh_core_session", "session.py")
_project_mod = _load_module("rbh_core_project", "project.py")
_decorators_mod = _load_module("rbh_core_decorators", "decorators.py")

# Import functions
send_sms_verify_code = _auth_mod.send_sms_verify_code
register_user = _user_mod.register_user
login_with_password = _user_mod.login_with_password
login_with_sms = _user_mod.login_with_sms
get_current_user = _session_mod.get_current_user
clear_session = _session_mod.clear_session
save_session = _session_mod.save_session
generate_and_sync_project = _project_mod.generate_and_sync_project
AuthenticationError = _decorators_mod.AuthenticationError


def main():
    parser = argparse.ArgumentParser(description="RBH Core CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ========== auth 子命令 ==========
    auth_parser = subparsers.add_parser("auth", help="Authentication")
    auth_sub = auth_parser.add_subparsers(dest="auth_command")

    # register
    register_parser = auth_sub.add_parser("register", help="Register new user")
    register_parser.add_argument("--username", required=True, help="Username (min 3 chars)")
    register_parser.add_argument("--password", required=True, help="Password (min 6 chars)")

    # login
    login_parser = auth_sub.add_parser("login", help="Login with username + password")
    login_parser.add_argument("--username", required=True, help="Username")
    login_parser.add_argument("--password", required=True, help="Password")

    # login-sms
    login_sms_parser = auth_sub.add_parser("login-sms", help="Login with SMS code")
    login_sms_parser.add_argument("--username", required=True, help="Username")
    login_sms_parser.add_argument("--phone", required=True, help="Phone number")
    login_sms_parser.add_argument("--code", required=True, help="SMS verification code")

    # send-sms
    send_parser = auth_sub.add_parser("send-sms", help="Send SMS verification code")
    send_parser.add_argument("--phone", required=True, help="Phone number")

    # logout
    auth_sub.add_parser("logout", help="Logout current user")

    # whoami
    auth_sub.add_parser("whoami", help="Show current logged-in user")

    # ========== project 子命令 ==========
    project_parser = subparsers.add_parser("project", help="Project management")
    project_sub = project_parser.add_subparsers(dest="project_command")

    gen_parser = project_sub.add_parser("generate", help="Generate project (requires login)")
    gen_parser.add_argument("--prompt", required=True, help="Project topic or idea")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # ========== 路由到具体实现 ==========
    try:
        if args.command == "auth":
            if args.auth_command == "register":
                result = register_user(args.username, args.password)
                print(json.dumps(result, indent=2, ensure_ascii=False))

                # Auto-login after successful registration
                if result["success"] and result["user"]:
                    save_session(result["user"])
                    print("\n✓ Auto-login successful. Session saved to ~/.rbh/session.json")

                sys.exit(0 if result["success"] else 1)

            elif args.auth_command == "login":
                result = login_with_password(args.username, args.password)
                print(json.dumps(result, indent=2, ensure_ascii=False))

                # Save session on successful login
                if result["success"] and result["user"]:
                    save_session(result["user"])
                    print("\n✓ Session saved to ~/.rbh/session.json")

                sys.exit(0 if result["success"] else 1)

            elif args.auth_command == "login-sms":
                result = login_with_sms(args.username, args.phone, args.code)
                print(json.dumps(result, indent=2, ensure_ascii=False))

                # Save session on successful login
                if result["success"] and result["user"]:
                    save_session(result["user"])
                    print("\n✓ Session saved to ~/.rbh/session.json")

                sys.exit(0 if result["success"] else 1)

            elif args.auth_command == "send-sms":
                result = send_sms_verify_code(args.phone)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                sys.exit(0 if result["success"] else 1)

            elif args.auth_command == "logout":
                clear_session()
                print("Logged out successfully")
                sys.exit(0)

            elif args.auth_command == "whoami":
                user = get_current_user()
                if user:
                    print(json.dumps(user, indent=2, ensure_ascii=False))
                    sys.exit(0)
                else:
                    print("Not logged in")
                    sys.exit(1)

        elif args.command == "project":
            if args.project_command == "generate":
                # generate_and_sync_project has @require_auth decorator
                result = generate_and_sync_project(args.prompt)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                sys.exit(0)

    except AuthenticationError as e:
        print(f"Error: {e}")
        print("\nPlease login first:")
        print("  python rbh-core/scripts/cli.py auth login --username <username> --password <password>")
        sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
