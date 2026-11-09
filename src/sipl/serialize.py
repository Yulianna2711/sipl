from __future__ import annotations

from dataclasses import fields, is_dataclass

from .interpreter.events import span_to_dict


def ast_to_dict(node):
    if isinstance(node, tuple):
        return [ast_to_dict(n) for n in node]
    if is_dataclass(node):
        data = {"type": type(node).__name__}
        for f in fields(node):
            if f.name != "span":
                data[f.name] = ast_to_dict(getattr(node, f.name))
        data["span"] = span_to_dict(node.span)
        return data
    return node


def _where(span: dict) -> str:
    return (f"{span['start_line']}:{span['start_column']}-"
            f"{span['end_line']}:{span['end_column']}")


def format_tree(node: dict, indent: int = 0) -> str:
    pad = "  " * indent
    scalars = [f"{k}={v}" for k, v in node.items()
               if k not in ("type", "span") and not isinstance(v, (dict, list))]
    head = " ".join([node["type"], *scalars])
    lines = [f"{pad}{head}  [{_where(node['span'])}]"]
    for key, value in node.items():
        if key == "span":
            continue
        if isinstance(value, dict):
            lines.append(f"{pad}  {key}:")
            lines.append(format_tree(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{pad}  {key}:")
            lines.extend(format_tree(item, indent + 2) for item in value)
    return "\n".join(lines)