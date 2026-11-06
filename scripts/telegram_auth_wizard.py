"""
OmniScout-TG: Telegram MTProto Authentication Wizard
Sets up and verifies authenticated Telethon user sessions for zero-cost ($0)
Telegram Native Recommendation Graph querying via channels.getChannelRecommendations.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import get_settings


async def check_session_status(session_name: str, api_id: int, api_hash: str) -> bool:
    """Checks if an existing session file is already authorized."""
    from telethon import TelegramClient

    session_path = Path(f"{session_name}.session")
    if not session_path.exists():
        print(f"[-] No session file found at: {session_path.resolve()}")
        return False

    print(f"[*] Found session file: {session_path.name}. Testing authorization...")
    client = TelegramClient(session_name, api_id, api_hash)
    try:
        await client.connect()
        authorized = await client.is_user_authorized()
        if authorized:
            me = await client.get_me()
            username = f"@{me.username}" if me.username else me.first_name
            print(f"[+] Active authorized session confirmed for: {username} (ID: {me.id})")
        else:
            print("[-] Session file exists but is NOT authorized. Re-authentication required.")
        await client.disconnect()
        return authorized
    except Exception as exc:
        print(f"[-] Failed to verify session: {exc}")
        return False


async def run_auth_wizard(api_id: int | None = None, api_hash: str | None = None, phone: str | None = None):
    """Interactive login wizard for Telegram MTProto."""
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError

    settings = get_settings()

    print("=" * 75)
    print(" OmniScout-TG: Telegram MTProto Session Authentication Wizard")
    print(" Provides access to native channel recommendations (ads.telegram.org graph)")
    print("=" * 75)

    resolved_api_id = api_id or settings.telegram_api_id
    resolved_api_hash = api_hash or settings.telegram_api_hash
    session_name = settings.telegram_session_name

    if not resolved_api_id or not resolved_api_hash:
        print("\n[!] Telegram API credentials not found in environment or .env.")
        print("    Get your free credentials from https://my.telegram.org -> API development tools.")
        raw_id = input("\nEnter your Telegram API ID: ").strip()
        resolved_api_hash = input("Enter your Telegram API Hash: ").strip()
        try:
            resolved_api_id = int(raw_id)
        except ValueError:
            print("[-] API ID must be an integer. Exiting.")
            return False

    # Check if already authenticated
    is_valid = await check_session_status(session_name, resolved_api_id, resolved_api_hash)
    if is_valid:
        print("\n[+] Your Telegram session is already fully authorized and ready to use!")
        return True

    print(f"\n[*] Initiating Telethon client with session '{session_name}'...")
    client = TelegramClient(session_name, resolved_api_id, resolved_api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        phone_number = phone or settings.telegram_phone
        if not phone_number:
            phone_number = input("\nEnter your Telegram phone number (international format e.g. +989123456789): ").strip()

        print(f"[*] Requesting login code for {phone_number}...")
        await client.send_code_request(phone_number)

        code = input("Enter the login code received in Telegram: ").strip()
        try:
            await client.sign_in(phone_number, code)
        except SessionPasswordNeededError:
            print("[*] Two-Step Verification (2FA) is enabled on this account.")
            password = input("Enter your Telegram 2FA password: ").strip()
            await client.sign_in(password=password)

    me = await client.get_me()
    name = f"@{me.username}" if me.username else me.first_name
    print(f"\n[+] Successfully authenticated as: {name} (User ID: {me.id})")
    print(f"[+] Session saved to '{session_name}.session' for zero-cost graph harvesting.")
    await client.disconnect()
    return True


def main():
    parser = argparse.ArgumentParser(description="OmniScout-TG Telegram Auth Wizard")
    parser.add_argument("--check", action="store_true", help="Check existing session authorization without prompting")
    parser.add_argument("--api-id", type=int, default=None, help="Telegram API ID")
    parser.add_argument("--api-hash", type=str, default=None, help="Telegram API Hash")
    parser.add_argument("--phone", type=str, default=None, help="Telegram Phone number")
    args = parser.parse_args()

    settings = get_settings()
    if args.check:
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            print("[-] TELEGRAM_API_ID or TELEGRAM_API_HASH not set in .env.")
            sys.exit(1)
        valid = asyncio.run(check_session_status(settings.telegram_session_name, settings.telegram_api_id, settings.telegram_api_hash))
        sys.exit(0 if valid else 1)

    success = asyncio.run(run_auth_wizard(args.api_id, args.api_hash, args.phone))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
