#!/usr/bin/env python3
"""Build the transparent, one-page ERD artwork from schema.dbml and erd.md."""

from __future__ import annotations

import heapq
import html
import math
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / "schema.dbml"
GUIDE = ROOT / "erd.md"
OUTPUT = ROOT / "erd.svg"

WIDTH, HEIGHT = 1920, 1080
CARD_W = 340
CARD_X = [30 + 380 * col for col in range(5)]
CARD_Y = [48 + 172 * row for row in range(6)]
GRID = 5

# Related groups stay close so the automatic orthogonal routing can use the
# narrow spaces between cards without drawing across any table.
LAYOUT = [
    ["auth_user", "auth_group", "auth_permission", "django_content_type", "auth.user_user_permissions"],
    ["auth.group_permissions", "auth.user_groups", "core_notification", "core_onboardingdocument", "core_overtimeslip"],
    ["core_authenticatordevice", "core_authenticatorrecoverycode", "core_department", "core_attendancecorrection", "core_grievance"],
    ["core_employeeauditlog", "core_attendance", "core_employee", "core_complaint", "core_shiftroster"],
    ["core_expenseclaim", "core_leaveallocation", "core_leaverequest", "core_payrollitem", "core_shiftswap"],
    ["core_performancereview", "core_salaryadvance", "core_payrollrun", "core_message", "core_claimstatus"],
]

TYPE_LABELS = {
    "auto": "SERIAL",
    "big_auto": "BIGSERIAL",
    "char": "VARCHAR",
    "email": "VARCHAR",
    "date_time": "TIMESTAMP",
    "file": "VARCHAR",
    "boolean": "BOOLEAN",
    "decimal": "NUMERIC",
    "integer": "INTEGER",
}


def parse_schema():
    source = SCHEMA.read_text(encoding="utf-8")
    tables = {}
    refs = []
    table_pattern = re.compile(r"(?ms)^Table ([\w.]+) \{\n(.*?)^\}")
    field_pattern = re.compile(r"^  (\w+) ([\w.]+) \[", re.M)
    for match in table_pattern.finditer(source):
        name, body = match.group(1), match.group(2)
        fields = []
        starts = list(field_pattern.finditer(body))
        for index, field_match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else body.find("  indexes {")
            if end < 0:
                end = len(body)
            stanza = body[field_match.start():end]
            attrs = stanza[stanza.find("[") + 1:]
            fields.append({
                "name": field_match.group(1),
                "type": field_match.group(2),
                "pk": bool(re.search(r"(?:^|,)\s*pk(?:\s*,|\s*$)", attrs)),
                "unique": bool(re.search(r"(?:^|,)\s*unique(?:\s*,|\s*\])", attrs)),
                "nullable": bool(re.search(r"(?:^|,)\s*null(?:\s*,|\s*$)", attrs)),
            })
        tables[name] = fields

    ref_pattern = re.compile(r"(?m)^ref:\s*([\w.]+)\.(\w+)\s+([>-])\s+([\w.]+)\.(\w+)")
    for match in ref_pattern.finditer(source):
        refs.append({
            "left": match.group(1), "left_field": match.group(2),
            "kind": match.group(3), "right": match.group(4), "right_field": match.group(5),
        })
    return tables, refs


def parse_guide():
    relations = []
    pattern = re.compile(
        r"(?m)^\| (R\d+) \| ([\w.]+)\.(\w+) → ([\w.]+)\.(\w+) \| "
        r"([^|]+) \| ([^|]+) \|$"
    )
    for match in pattern.finditer(GUIDE.read_text(encoding="utf-8")):
        cardinality = match.group(6).strip()
        relations.append({
            "id": match.group(1), "parent": match.group(2), "parent_field": match.group(3),
            "child": match.group(4), "child_field": match.group(5),
            "cardinality": cardinality, "why": match.group(7).strip(),
        })
    return relations


def check_inputs(tables, refs, relations):
    expected = [table for row in LAYOUT for table in row]
    if len(expected) != len(set(expected)) or set(expected) != set(tables):
        raise ValueError("The ERD layout must contain every DBML table exactly once.")
    ref_keys = {tuple(sorted((f"{r['left']}.{r['left_field']}", f"{r['right']}.{r['right_field']}"))) for r in refs}
    guide_keys = {tuple(sorted((f"{r['parent']}.{r['parent_field']}", f"{r['child']}.{r['child_field']}"))) for r in relations}
    if ref_keys != guide_keys or len(refs) != len(relations):
        missing = sorted(ref_keys - guide_keys)
        extra = sorted(guide_keys - ref_keys)
        raise ValueError(f"schema.dbml and erd.md relations differ: missing={missing}; extra={extra}")
    if len(relations) != 31:
        raise ValueError(f"Expected 31 ERD relationships, found {len(relations)}.")
    for relation in relations:
        child_field = next(field for field in tables[relation["child"]]
                           if field["name"] == relation["child_field"])
        parent_min = "0..1 parent per child" if child_field["nullable"] else "1 parent per child"
        child_max = "0..1 children per parent" if child_field["unique"] else "0..* children per parent"
        if parent_min not in relation["cardinality"] or child_max not in relation["cardinality"]:
            raise ValueError(
                f"{relation['id']} cardinality disagrees with DBML constraints on "
                f"{relation['child']}.{relation['child_field']}"
            )


def esc(value):
    return html.escape(str(value), quote=True)


def svg_text(x, y, content, size=12, fill="#111111", weight="400", anchor=None, extra=""):
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}"{anchor_attr} {extra}>'
            f'{esc(content)}</text>')


def path_d(points):
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)


def simplify(points):
    out = []
    for point in points:
        if out and point == out[-1]:
            continue
        while len(out) >= 2:
            ax, ay = out[-2]
            bx, by = out[-1]
            cx, cy = point
            if (bx - ax) * (cy - by) == (by - ay) * (cx - bx):
                out.pop()
            else:
                break
        out.append(point)
    return out


def choose_side(source, target):
    dx, dy = target[0] - source[0], target[1] - source[1]
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def assign_positions(tables, relations):
    positions = {}
    for row_idx, row in enumerate(LAYOUT):
        for col_idx, name in enumerate(row):
            height = 24 + 10 * len(tables[name])
            positions[name] = {"x": CARD_X[col_idx], "y": CARD_Y[row_idx], "w": CARD_W, "h": height,
                               "cx": CARD_X[col_idx] + CARD_W / 2,
                               "cy": CARD_Y[row_idx] + height / 2}

    # Give each relation a distinct exit point on its card edge.
    ports = defaultdict(list)
    for relation in relations:
        for endpoint, other in (("parent", "child"), ("child", "parent")):
            table = relation[endpoint]
            target = relation[other]
            rect = positions[table]
            side = choose_side((rect["cx"], rect["cy"]),
                               (positions[target]["cx"], positions[target]["cy"]))
            key = (table, side)
            ports[key].append((relation, endpoint))

    for (table, side), items in list(ports.items()):
        rect = positions[table]
        if side in ("left", "right"):
            lo, hi = rect["y"] + 15, rect["y"] + rect["h"] - 10
            fixed = rect["x"] if side == "left" else rect["x"] + rect["w"]
            varying = sorted(items, key=lambda item: (
                positions[item[0]["child" if item[1] == "parent" else "parent"]]["cy"],
                item[0]["id"], item[1]))
            for i, (relation, endpoint) in enumerate(varying, 1):
                py = round((lo + (hi - lo) * i / (len(varying) + 1)) / GRID) * GRID
                ports[(relation["id"], endpoint)] = (fixed, py, side)
        else:
            lo, hi = rect["x"] + 18, rect["x"] + rect["w"] - 18
            fixed = rect["y"] if side == "top" else rect["y"] + rect["h"]
            varying = sorted(items, key=lambda item: (
                positions[item[0]["child" if item[1] == "parent" else "parent"]]["cx"],
                item[0]["id"], item[1]))
            for i, (relation, endpoint) in enumerate(varying, 1):
                px = round((lo + (hi - lo) * i / (len(varying) + 1)) / GRID) * GRID
                ports[(relation["id"], endpoint)] = (px, fixed, side)
    return positions, ports


def make_obstacles(positions):
    obstacles = set()
    for rect in positions.values():
        left = math.floor((rect["x"] - 6) / GRID)
        right = math.ceil((rect["x"] + rect["w"] + 6) / GRID)
        top = math.floor((rect["y"] - 6) / GRID)
        bottom = math.ceil((rect["y"] + rect["h"] + 6) / GRID)
        for gx in range(left, right + 1):
            for gy in range(top, bottom + 1):
                obstacles.add((gx, gy))
    return obstacles


def astar(start, goal, obstacles, used):
    start_node = (start[0] // GRID, start[1] // GRID)
    goal_node = (goal[0] // GRID, goal[1] // GRID)
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))
    queue = [(0, 0, start_node, -1)]
    distance = {(start_node, -1): 0}
    previous = {}
    serial = 0
    final_state = None
    while queue:
        _, cost, node, previous_direction = heapq.heappop(queue)
        state = (node, previous_direction)
        if cost != distance.get(state):
            continue
        if node == goal_node:
            final_state = state
            break
        for direction_id, (dx, dy) in enumerate(directions):
            nxt = (node[0] + dx, node[1] + dy)
            px, py = nxt[0] * GRID, nxt[1] * GRID
            if not (0 <= px <= WIDTH and 0 <= py <= HEIGHT):
                continue
            if nxt in obstacles and nxt not in (start_node, goal_node):
                continue
            step_cost = GRID + (3 if previous_direction not in (-1, direction_id) else 0)
            if nxt in used and nxt not in (start_node, goal_node):
                step_cost += 18
            next_cost = cost + step_cost
            next_state = (nxt, direction_id)
            if next_cost >= distance.get(next_state, float("inf")):
                continue
            distance[next_state] = next_cost
            previous[next_state] = state
            heuristic = GRID * (abs(goal_node[0] - nxt[0]) + abs(goal_node[1] - nxt[1]))
            serial += 1
            heapq.heappush(queue, (next_cost + heuristic, next_cost, nxt, direction_id))
    if final_state is None:
        raise RuntimeError(f"No clear route from {start} to {goal}")
    path = []
    state = final_state
    while state in previous:
        path.append((state[0][0] * GRID, state[0][1] * GRID))
        state = previous[state]
    path.append((start_node[0] * GRID, start_node[1] * GRID))
    path.reverse()
    return path


def stub(point, side, distance=20):
    x, y = point
    return {
        "left": (x - distance, y), "right": (x + distance, y),
        "top": (x, y - distance), "bottom": (x, y + distance),
    }[side]


def port_options(table, relation, endpoint, positions, primary, relations):
    """Return distinct edge exits, preferring the side facing the other card."""
    rect = positions[table]
    other = relation["child" if endpoint == "parent" else "parent"]
    other_rect = positions[other]
    preferred = choose_side((rect["cx"], rect["cy"]), (other_rect["cx"], other_rect["cy"]))
    if preferred in ("left", "right"):
        order = [preferred, "top", "bottom", "left" if preferred == "right" else "right"]
    else:
        order = [preferred, "right", "left", "top" if preferred == "bottom" else "bottom"]
    results = [primary]
    for side in order:
        if side == primary[2]:
            continue
        # Stable per-table slot allocation keeps sibling relations separate.
        incident = []
        for item in relations:
            if item["parent"] == table:
                incident.append((item["id"], "parent"))
            if item["child"] == table:
                incident.append((item["id"], "child"))
        incident.sort()
        slot_index = incident.index((relation["id"], endpoint))
        slots = []
        if side in ("left", "right"):
            low = math.ceil((rect["y"] + 15) / GRID) * GRID
            high = math.floor((rect["y"] + rect["h"] - 15) / GRID) * GRID
            fixed = rect["x"] if side == "left" else rect["x"] + rect["w"]
            slots = [(fixed, y, side) for y in range(low, high + 1, GRID)]
        else:
            low = math.ceil((rect["x"] + 20) / GRID) * GRID
            high = math.floor((rect["x"] + rect["w"] - 20) / GRID) * GRID
            fixed = rect["y"] if side == "top" else rect["y"] + rect["h"]
            slots = [(x, fixed, side) for x in range(low, high + 1, GRID)]
        if slots:
            # Spread all links across a side and keep the selected port stable.
            slot_index_in_side = round((slot_index + 1) * (len(slots) - 1) / max(1, len(incident) - 1))
            slot = slots[max(0, min(len(slots) - 1, slot_index_in_side))]
            results.append(slot)
    return results


def point_clear_of_cards(cx, cy, width, height, positions):
    for rect in positions.values():
        if cx + width / 2 > rect["x"] - 2 and cx - width / 2 < rect["x"] + rect["w"] + 2 \
                and cy + height / 2 > rect["y"] - 2 and cy - height / 2 < rect["y"] + rect["h"] + 2:
            return False
    return True


def label_candidates(points, positions, used_labels):
    options = []
    for a, b in zip(points, points[1:]):
        length = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if length < 36:
            continue
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        width, height = 30, 14
        if not point_clear_of_cards(cx, cy, width, height, positions):
            continue
        if any(abs(cx - ux) < 24 and abs(cy - uy) < 17 for ux, uy in used_labels):
            continue
        options.append((length, cx, cy))
    options.sort(reverse=True)
    return options


def route_all(relations, positions, ports):
    obstacles = make_obstacles(positions)
    used = set()
    routes = {}
    # Long connections get first choice of the wide exterior channels.
    ordered = sorted(relations, key=lambda rel: (-(
        abs(positions[rel["parent"]]["cx"] - positions[rel["child"]]["cx"])
        + abs(positions[rel["parent"]]["cy"] - positions[rel["child"]]["cy"])), rel["id"]))
    for relation in ordered:
        starts = port_options(relation["parent"], relation, "parent", positions,
                              ports[(relation["id"], "parent")], relations)
        ends = port_options(relation["child"], relation, "child", positions,
                            ports[(relation["id"], "child")], relations)
        combinations = sorted(((i+j, i, j) for i in range(len(starts)) for j in range(len(ends))))
        chosen = None
        for _, i, j in combinations:
            start, end = starts[i], ends[j]
            start_point, start_side = start[:2], start[2]
            end_point, end_side = end[:2], end[2]
            start_stub, end_stub = stub(start_point, start_side, 25), stub(end_point, end_side, 25)
            start_node = (start_stub[0] // GRID, start_stub[1] // GRID)
            end_node = (end_stub[0] // GRID, end_stub[1] // GRID)
            if start_node in obstacles or end_node in obstacles:
                continue
            try:
                middle = astar(start_stub, end_stub, obstacles, used)
                chosen = (start_point, end_point, start_stub, end_stub, middle)
                break
            except RuntimeError:
                continue
        if chosen is None:
            raise RuntimeError(f"No clear route for {relation['id']} {relation['parent']} -> {relation['child']}")
        start_point, end_point, start_stub, end_stub, middle = chosen
        points = simplify([start_point, start_stub, *middle, end_stub, end_point])
        routes[relation["id"]] = points
        for x, y in middle:
            used.add((x // GRID, y // GRID))
    labels = {}
    used_labels = []
    for relation in sorted(relations, key=lambda item: item["id"]):
        candidates = label_candidates(routes[relation["id"]], positions, used_labels)
        if candidates:
            _, cx, cy = candidates[0]
            labels[relation["id"]] = (cx, cy)
            used_labels.append((cx, cy))
    return routes, labels


def endpoint_svg(point, outward_point, cardinality, color="#323941", scale=1):
    x, y = point
    ox, oy = outward_point
    dx, dy = ox - x, oy - y
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux

    def at(distance, lateral=0):
        return x + ux * distance + px * lateral, y + uy * distance + py * lateral

    parts = []
    if cardinality == "one":
        for distance in (4, 10):
            ax, ay = at(distance)
            parts.append(f'<path d="M {ax-px*5:.1f} {ay-py*5:.1f} L {ax+px*5:.1f} {ay+py*5:.1f}"/>')
    elif cardinality == "zero_one":
        ax, ay = at(4)
        parts.append(f'<path d="M {ax-px*5:.1f} {ay-py*5:.1f} L {ax+px*5:.1f} {ay+py*5:.1f}"/>')
        cx, cy = at(14)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.6" fill="#FFFFFF"/>')
    elif cardinality == "zero_many":
        # Crow's-foot prongs point into the endpoint; the branch meets the route.
        bx, by = at(11)
        for lateral in (-5, 0, 5):
            ex, ey = at(3, lateral)
            parts.append(f'<path d="M {bx:.1f} {by:.1f} L {ex:.1f} {ey:.1f}"/>')
        cx, cy = at(18)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.6" fill="#FFFFFF"/>')
    elif cardinality == "one_many":
        bx, by = at(11)
        for lateral in (-5, 0, 5):
            ex, ey = at(3, lateral)
            parts.append(f'<path d="M {bx:.1f} {by:.1f} L {ex:.1f} {ey:.1f}"/>')
        ax, ay = at(3)
        parts.append(f'<path d="M {ax-px*5:.1f} {ay-py*5:.1f} L {ax+px*5:.1f} {ay+py*5:.1f}"/>')
    return f'<g fill="none" stroke="{color}" stroke-width="2.0" stroke-linecap="square" stroke-linejoin="round">' + "".join(parts) + "</g>"


def cardinalities(relation):
    parent_count = "zero_one" if "0..1 parent per child" in relation["cardinality"] else "one"
    if "0..1 children per parent" in relation["cardinality"]:
        child_count = "zero_one"
    elif "1..* children per parent" in relation["cardinality"]:
        child_count = "one_many"
    else:
        child_count = "zero_many"
    return parent_count, child_count


def render_svg(tables, relations, routes, labels):
    field_relations = defaultdict(list)
    for relation in relations:
        field_relations[(relation["child"], relation["child_field"])].append(relation["id"])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
           '<g shape-rendering="geometricPrecision" text-rendering="geometricPrecision">',
           svg_text(24, 31, "30 tables • 31 relations • PK/FK tags identify keys • ? marks nullable fields • connector IDs match the relation list in erd.md", 10.5, "#33383E"),
           '<g id="relations" fill="none" stroke="#616A73" stroke-width="2.0" stroke-linejoin="round" stroke-linecap="round">']
    for relation in sorted(relations, key=lambda item: item["id"]):
        points = routes[relation["id"]]
        out.append(f'<path id="{relation["id"]}" d="{path_d(points)}"/>')
    out.append('</g>')

    # Draw full crow's-foot endpoint marks on top of the route strokes.
    for relation in sorted(relations, key=lambda item: item["id"]):
        points = routes[relation["id"]]
        parent_type, child_type = cardinalities(relation)
        out.append(endpoint_svg(points[0], points[1], parent_type))
        out.append(endpoint_svg(points[-1], points[-2], child_type))

    # Line labels are kept in clear portions of each route; FK field rows also
    # carry the matching ID when an unusually short edge has no label space.
    for relation in sorted(relations, key=lambda item: item["id"]):
        if relation["id"] not in labels:
            continue
        cx, cy = labels[relation["id"]]
        out.append(f'<rect x="{cx-15:.1f}" y="{cy-7:.1f}" width="30" height="14" rx="6" fill="#FFFFFF" stroke="#6B737B" stroke-width="0.8"/>')
        out.append(svg_text(cx, cy+3.4, relation["id"], 8.3, "#20252A", "700", "middle"))

    # Card bodies are painted last so every connector ends cleanly at its edge.
    for row in LAYOUT:
        for name in row:
            rect = card_positions[name]
            x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
            fields = tables[name]
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="#FFFFFF" stroke="#20252A" stroke-width="1.5"/>')
            out.append(f'<path d="M {x+5} {y} H {x+w-5} Q {x+w} {y} {x+w} {y+5} V {y+23} H {x} V {y+5} Q {x} {y} {x+5} {y}" fill="#FFFFFF"/>')
            out.append(svg_text(x+w/2, y+16.3, name, 10.5, "#111111", "700", "middle"))
            out.append(f'<path d="M {x+1} {y+23.5} H {x+w-1}" stroke="#71777D" stroke-width="0.8"/>')
            for index, field in enumerate(fields):
                baseline = y + 32 + index * 10
                field_ids = field_relations.get((name, field["name"]), [])
                tag = ("PK/FK" if field["pk"] and field_ids else "PK" if field["pk"] else "FK" if field_ids else "")
                tag_text = tag + (" " + ",".join(field_ids) if field_ids else "")
                tag_color = "#111111" if tag else "#555B61"
                name_x = x + 10
                if tag_text:
                    out.append(svg_text(x+8, baseline, tag_text, 7.5 if field_ids else 8.0, tag_color, "700"))
                    name_x = x + (61 if field_ids else 43)
                field_name = field["name"] + (" ?" if field["nullable"] else "")
                field_type = TYPE_LABELS.get(field["type"], field["type"].replace("core.", "").upper())
                if field["type"].startswith("core.char_"):
                    field_type = "ENUM"
                out.append(svg_text(name_x, baseline, field_name, 8.7, "#111111"))
                out.append(svg_text(x+w-8, baseline, field_type, 7.8, "#555B61", "400", "end"))
                if index < len(fields)-1:
                    out.append(f'<path d="M {x+8} {baseline+2.4} H {x+w-8}" stroke="#D9DDE1" stroke-width="0.55"/>')
    out.extend(['</g>', '</svg>'])
    return "\n".join(out)


tables, dbml_refs = parse_schema()
relations = parse_guide()
check_inputs(tables, dbml_refs, relations)
card_positions, port_positions = assign_positions(tables, relations)
routes, route_labels = route_all(relations, card_positions, port_positions)

# Exact route audit: each connector and its endpoint symbols stay outside every
# table interior. The 6px guard is also wider than the connector stroke.
for relation in relations:
    points = routes[relation["id"]]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        for name, rect in card_positions.items():
            if x1 == x2 and rect["x"] < x1 < rect["x"] + rect["w"] and max(min(y1, y2), rect["y"]) < min(max(y1, y2), rect["y"]+rect["h"]):
                raise ValueError(f"{relation['id']} crosses {name}")
            if y1 == y2 and rect["y"] < y1 < rect["y"] + rect["h"] and max(min(x1, x2), rect["x"]) < min(max(x1, x2), rect["x"]+rect["w"]):
                raise ValueError(f"{relation['id']} crosses {name}")

OUTPUT.write_text(render_svg(tables, relations, routes, route_labels), encoding="utf-8")
print(f"Wrote {OUTPUT}; tables={len(tables)}, relations={len(relations)}, labeled={len(route_labels)}")
print("Largest tables:", ", ".join(f"{name} ({len(fields)} fields)" for name, fields in sorted(tables.items(), key=lambda item: -len(item[1]))[:5]))
