from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ChannelNode:
    id: str
    name: str
    type: int
    parent_id: Optional[str] = None
    children: List["ChannelNode"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

def build_channel_tree(channels: list) -> List[ChannelNode]:
    nodes = {ch["id"]: ChannelNode(
        id=ch["id"],
        name=ch["name"],
        type=ch["type"],
        parent_id=ch.get("parent_id"),
    ) for ch in channels}
    roots = []
    for ch in channels:
        node = nodes[ch["id"]]
        parent_id = ch.get("parent_id")
        if parent_id and parent_id in nodes:
            nodes[parent_id].children.append(node)
        elif parent_id is None:
            roots.append(node)
    return roots

def format_channel_tree(channels: list, indent: str = "") -> str:
    lines = []
    roots = build_channel_tree(channels)
    for root in roots:
        lines.append(_fmt_node(root, indent))
    return "\n".join(lines)

def _fmt_node(node: ChannelNode, indent: str) -> str:
    type_icons = {
        0: "#",
        2: "@",
        4: "\\",
    }
    icon = type_icons.get(node.type, "?")
    line = f"{indent}{icon} {node.name}"
    if node.children:
        child_lines = [_fmt_node(c, indent + "  ") for c in node.children]
        line += "\n" + "\n".join(child_lines)
    return line

@dataclass
class PermissionOverwrite:
    id: str
    type: int  # 0 = role, 1 = member
    allow: str
    deny: str

def parse_overwrites(raw: list) -> List[PermissionOverwrite]:
    return [PermissionOverwrite(
        id=o["id"],
        type=o["type"],
        allow=o.get("allow", "0"),
        deny=o.get("deny", "0"),
    ) for o in raw]

def format_overwrite(ov: PermissionOverwrite, role_names: dict = None) -> str:
    name = role_names.get(ov.id, ov.id) if role_names else ov.id
    target = "role" if ov.type == 0 else "member"
    parts = []
    if ov.allow != "0":
        parts.append(f"allow={ov.allow}")
    if ov.deny != "0":
        parts.append(f"deny={ov.deny}")
    detail = ", ".join(parts) if parts else "default"
    return f"  [{target}] {name}: {detail}"

def format_role_diff(old: dict, new: dict) -> str:
    changes = []
    for key in ("name", "permissions", "color", "hoist", "mentionable"):
        if old.get(key) != new.get(key):
            changes.append(f"{key}: {old.get(key)} -> {new.get(key)}")
    return "; ".join(changes) if changes else "no change"
