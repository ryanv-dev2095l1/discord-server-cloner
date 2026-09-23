import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

from fmt import format_channel_tree, format_role_diff

API_BASE = "https://discord.com/api/v10"

class DiscordClient:
    def __init__(self, token: str):
        self.token = token
        self.session = httpx.Client(
            headers={
                "Authorization": token,
                "User-Agent": "DiscordBot (https://github.com/clone, 0.1.0)",
            },
            timeout=30.0,
        )

    def request(self, method: str, path: str, **kwargs):
        url = f"{API_BASE}{path}"
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", 1)
            time.sleep(float(retry_after))
            resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    def get_guild(self, guild_id: str):
        return self.request("GET", f"/guilds/{guild_id}").json()

    def get_channels(self, guild_id: str):
        return self.request("GET", f"/guilds/{guild_id}/channels").json()

    def get_roles(self, guild_id: str):
        return self.request("GET", f"/guilds/{guild_id}/roles").json()

    def create_guild(self, name: str):
        return self.request("POST", "/guilds", json={"name": name}).json()

    def create_channel(self, guild_id: str, payload: dict):
        return self.request("POST", f"/guilds/{guild_id}/channels", json=payload).json()

    def create_role(self, guild_id: str, payload: dict):
        return self.request("POST", f"/guilds/{guild_id}/roles", json=payload).json()

    def modify_role_positions(self, guild_id: str, positions: list):
        return self.request("PATCH", f"/guilds/{guild_id}/roles", json=positions).json()

def snapshot_guild(client: DiscordClient, guild_id: str) -> dict:
    guild = client.get_guild(guild_id)
    channels = client.get_channels(guild_id)
    roles = client.get_roles(guild_id)
    return {
        "name": guild.get("name", "cloned-server"),
        "channels": channels,
        "roles": roles,
    }

def restore_guild(client: DiscordClient, data: dict, target_guild_id: str = None, dry_run: bool = False):
    if target_guild_id is None:
        if dry_run:
            print("dry-run: would create new guild")
            target_guild_id = "DRYRUN"
        else:
            new_guild = client.create_guild(data["name"])
            target_guild_id = new_guild["id"]
            print(f"created guild {new_guild['name']} ({target_guild_id})")
    else:
        print(f"restoring into existing guild {target_guild_id}")

    role_map = {}
    for role in sorted(data.get("roles", []), key=lambda r: r.get("position", 0)):
        if role["name"] == "@everyone":
            continue
        payload = {
            "name": role["name"],
            "permissions": role["permissions"],
            "color": role["color"],
            "hoist": role["hoist"],
            "mentionable": role["mentionable"],
        }
        if dry_run:
            print(f"  would create role {role['name']}")
            role_map[role["id"]] = f"DRYRUN_ROLE_{role['id']}"
            continue
        new_role = client.create_role(target_guild_id, payload)
        role_map[role["id"]] = new_role["id"]
        print(f"  created role {role['name']}")

    channels_by_parent = {}
    for ch in data.get("channels", []):
        parent_id = ch.get("parent_id")
        channels_by_parent.setdefault(parent_id, []).append(ch)

    def create_channel_recursive(parent_id, depth=0):
        for ch in channels_by_parent.get(parent_id, []):
            payload = {
                "name": ch["name"],
                "type": ch["type"],
            }
            if ch.get("topic"):
                payload["topic"] = ch["topic"]
            if ch.get("nsfw"):
                payload["nsfw"] = ch["nsfw"]
            if ch.get("bitrate"):
                payload["bitrate"] = ch["bitrate"]
            if ch.get("user_limit"):
                payload["user_limit"] = ch["user_limit"]
            if ch.get("rate_limit_per_user"):
                payload["rate_limit_per_user"] = ch["rate_limit_per_user"]
            if ch.get("permission_overwrites"):
                payload["permission_overwrites"] = ch["permission_overwrites"]

            if dry_run:
                print(f"  would create {'  ' * depth}#{ch['name']}")
                create_channel_recursive(ch["id"], depth + 1)
                continue
            new_ch = client.create_channel(target_guild_id, payload)
            print(f"  created {'  ' * depth}#{ch['name']}")
            create_channel_recursive(ch["id"], depth + 1)

    create_channel_recursive(None)
    return target_guild_id

def main():
    parser = argparse.ArgumentParser(
        prog="clone",
        usage="python clone.py --token <token> --guild <id> [--output file.json]",
        description="snapshot and restore discord server structures",
    )
    parser.add_argument("--token", default=os.environ.get("DISCORD_TOKEN"))
    parser.add_argument("--guild", required=True, help="guild id to snapshot")
    parser.add_argument("--output", help="json file to write snapshot to")
    parser.add_argument("--restore-to", help="guild id to restore into (creates new guild if omitted)")
    parser.add_argument("--from-file", help="read snapshot from file instead of fetching")
    parser.add_argument("--dry-run", action="store_true", help="show what would be done without creating anything")
    parser.add_argument("--json", action="store_true", dest="json_output", help="output raw json even when showing tree view")
    args = parser.parse_args()

    if not args.token:
        print("set DISCORD_TOKEN or pass --token", file=sys.stderr)
        sys.exit(2)

    client = DiscordClient(args.token)

    if args.from_file:
        with open(args.from_file) as f:
            data = json.load(f)
        restore_guild(client, data, args.restore_to, dry_run=args.dry_run)
        return 0

    data = snapshot_guild(client, args.guild)
    if args.output:
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2)
        print(f"wrote snapshot to {args.output}")
    elif args.json_output:
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps(data, indent=2))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        sys.exit(130)
