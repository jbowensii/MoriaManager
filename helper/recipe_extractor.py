#!/usr/bin/env python3
"""
Helper script to extract weapons/armor recipes with display names and materials.

Uses a 3-phase algorithm:
  Phase 1 — Load string table from Items.json (with underscore aliasing)
  Phase 2 — Resolve DisplayName from definition tables (DT_Weapons, DT_Armor,
            DT_Items) by following each row's DisplayName property into the
            string table, then mapping the row name to the resolved text.
  Phase 3 — Build recipe data by intersecting DT_ItemRecipes with weapon/armor
            definitions, looking up display names for both items and materials.

Outputs:
  - helper/recipes_output.json       (for inspection)
  - src/.../core/recipes_data_embedded.py  (consumed at runtime)
"""

import json
import textwrap
from pathlib import Path

GAMESOURCE_DIR = Path(__file__).parent.parent / "gamesource"
EMBEDDED_PY = (
    Path(__file__).parent.parent
    / "src" / "moria_manager" / "core" / "recipes_data_embedded.py"
)

KNOWN_FIELD_SUFFIXES = {"Name", "Description", "DisplayName"}


# ---------------------------------------------------------------
# Phase 1: String Table
# ---------------------------------------------------------------

def load_string_table(items_path: Path) -> dict[str, dict]:
    """Parse Items.json and build a string table with underscore aliases.

    Each entry is stored as ``{game_name: {"name": ..., "description": ...}}``.
    An underscore-aliased duplicate (dots → underscores) is also created so
    that ``"Weapons_Spear_Iron"`` resolves the same way as ``"Weapons.Spear.Iron"``.
    """
    with open(items_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    keys_to_entries: dict[str, str] = {}
    for entry in data:
        if entry.get("Type") == "StringTable":
            keys_to_entries = entry.get("StringTable", {}).get("KeysToEntries", {})
            break

    string_table: dict[str, dict] = {}

    for key, value in keys_to_entries.items():
        # Determine field type from the last segment
        if "." in key:
            game_name, field = key.rsplit(".", 1)
        else:
            game_name, field = key, "Name"

        field_lower = field.lower()
        if field_lower in ("name", "displayname"):
            field_key = "name"
        elif field_lower == "description":
            field_key = "description"
        else:
            # Not a recognised suffix — treat the whole key as a direct name
            game_name = key
            field_key = "name"

        # Merge into existing entry
        string_table.setdefault(game_name, {})[field_key] = value

        # Underscore alias
        alias = game_name.replace(".", "_")
        if alias != game_name:
            string_table.setdefault(alias, {})[field_key] = value

    print(f"  Phase 1: {len(keys_to_entries)} raw entries "
          f"-> {len(string_table)} string-table entries (with aliases)")
    return string_table


# ---------------------------------------------------------------
# Phase 2: Resolve DisplayName from Definition Tables
# ---------------------------------------------------------------

def _extract_display_name_key(row_value: list) -> str | None:
    """Find the DisplayName property inside a UAssetAPI row Value array."""
    for prop in row_value:
        if prop.get("Name") == "DisplayName" and "Value" in prop:
            val = prop["Value"]
            if isinstance(val, str):
                return val
    return None


def _extract_weapon_tier(row_value: list) -> int | None:
    """Extract the Tier byte property from a weapon row."""
    for prop in row_value:
        if prop.get("Name") == "Tier" and "Value" in prop:
            val = prop["Value"]
            if isinstance(val, (int, float)):
                return int(val)
    return None


def _extract_armor_tier(row_value: list) -> int | None:
    """Extract tier from an armor row's Tags → UI.Armor.*.Tier{N} tag."""
    import re
    for prop in row_value:
        if prop.get("Name") != "Tags":
            continue
        # Tags is a GameplayTagContainer struct; the tag strings are
        # nested: prop.Value[0].Value = ["UI.Armor.Boots.Tier2", ...]
        for inner in prop.get("Value", []):
            for tag in inner.get("Value", []):
                if isinstance(tag, str):
                    m = re.search(r"UI\.Armor\.\w+\.Tier(\d+)", tag)
                    if m:
                        return int(m.group(1))
    return None


def _cascade_lookup(st_key: str, string_table: dict) -> dict | None:
    """4-step cascade lookup from a string-table reference key.

    1.  Direct: string_table[st_key]
    1b. Underscore variant of st_key
    2.  Strip .Name/.Description suffix: string_table[game_name]
    2b. Underscore variant of game_name
    """
    # 1 — direct
    if st_key in string_table:
        return string_table[st_key]

    # 1b — underscore variant
    us = st_key.replace(".", "_")
    if us in string_table:
        return string_table[us]

    # 2 — strip last segment
    if "." in st_key:
        game_name = st_key.rsplit(".", 1)[0]
        if game_name in string_table:
            return string_table[game_name]

        # 2b — underscore variant of stripped
        us2 = game_name.replace(".", "_")
        if us2 in string_table:
            return string_table[us2]

    return None


def _load_uasset_rows(path: Path) -> list[tuple[str, list]]:
    """Load row (name, value_array) pairs from a UAssetAPI DataTable JSON."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    rows: list[tuple[str, list]] = []
    for export in data.get("Exports", []):
        table_data = export.get("Table", {}).get("Data", [])
        for row in table_data:
            name = row.get("Name")
            value = row.get("Value", [])
            if name:
                rows.append((name, value))
    return rows


def resolve_definitions(
    string_table: dict[str, dict],
    gamesource: Path,
) -> tuple[set[str], set[str], set[str]]:
    """Phase 2 — resolve DisplayName from definition tables.

    Iterates DT_Weapons, DT_Armor, DT_Items and maps each row name into the
    string table using the DisplayName property as a bridge.

    Returns (weapon_names, armor_names, item_names) — the sets of row names
    found in each definition table.
    """
    tables = {
        "DT_Weapons.json": "weapon",
        "DT_Armor.json":   "armor",
        "DT_Items.json":   "item",
    }

    weapon_names: set[str] = set()
    armor_names:  set[str] = set()
    item_names:   set[str] = set()

    name_sets = {
        "weapon": weapon_names,
        "armor":  armor_names,
        "item":   item_names,
    }

    resolved = 0
    skipped = 0

    for filename, category in tables.items():
        path = gamesource / filename
        if not path.exists():
            print(f"  Warning: {filename} not found, skipping")
            continue

        rows = _load_uasset_rows(path)
        name_sets[category].update(name for name, _ in rows)

        for row_name, row_value in rows:
            # Extract tier (weapons use a Tier byte, armor uses Tags)
            if category == "weapon":
                tier = _extract_weapon_tier(row_value)
            elif category == "armor":
                tier = _extract_armor_tier(row_value)
            else:
                tier = None

            # Skip if already resolved
            if row_name in string_table:
                # Still store tier even if name was already known
                if tier is not None:
                    string_table[row_name]["tier"] = tier
                skipped += 1
                continue

            st_key = _extract_display_name_key(row_value)
            if not st_key:
                continue

            entry = _cascade_lookup(st_key, string_table)
            if entry:
                new_entry = dict(entry)
                if tier is not None:
                    new_entry["tier"] = tier
                string_table[row_name] = new_entry
                resolved += 1

        print(f"  Phase 2: {filename} — {len(rows)} rows, "
              f"category={category}")

    print(f"  Phase 2 totals: resolved {resolved} new mappings, "
          f"{skipped} already known")
    return weapon_names, armor_names, item_names


# ---------------------------------------------------------------
# Phase 3: Build Recipe Data
# ---------------------------------------------------------------

def _strip_handle_prefix(row_name: str) -> str:
    """Strip category prefixes like 'Weapon.', 'Armor.', 'Tool.', 'Item.'."""
    for prefix in ("Weapon.", "Armor.", "Tool.", "Item.", "Ore.", "Consumable."):
        if row_name.startswith(prefix):
            return row_name[len(prefix):]
    return row_name


def _lookup_display(internal: str, string_table: dict) -> str:
    """Look up a display name, returning the internal name as fallback."""
    entry = string_table.get(internal)
    if entry and "name" in entry:
        return entry["name"]
    # Try stripping prefix
    stripped = _strip_handle_prefix(internal)
    entry = string_table.get(stripped)
    if entry and "name" in entry:
        return entry["name"]
    return internal


def build_recipes(
    string_table: dict[str, dict],
    weapon_names: set[str],
    armor_names: set[str],
    gamesource: Path,
) -> tuple[list[dict], list[dict]]:
    """Phase 3 — build weapons and armor recipe lists.

    Only recipes whose result item appears in both the recipe table AND
    a weapon/armor definition table are included.
    """
    recipes_path = gamesource / "DT_ItemRecipes.json"
    with open(recipes_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    rows: dict = {}
    for entry in data:
        if entry.get("Type") == "DataTable":
            rows = entry.get("Rows", {})
            break

    weapons: list[dict] = []
    armor:   list[dict] = []
    w_miss = 0
    a_miss = 0

    for recipe_name, recipe_data in rows.items():
        result_row = recipe_data.get("ResultItemHandle", {}).get("RowName", "")
        stripped = _strip_handle_prefix(result_row)

        # Determine if this is a weapon or armor recipe
        is_weapon = stripped in weapon_names or recipe_name in weapon_names
        is_armor  = stripped in armor_names  or recipe_name in armor_names

        if not is_weapon and not is_armor:
            continue

        # Resolve display name for the item itself
        display = _lookup_display(recipe_name, string_table)
        if display == recipe_name:
            display = _lookup_display(stripped, string_table)

        # Build material lists
        def _convert_materials(mat_list):
            out = []
            for mat in mat_list:
                mat_row = mat.get("MaterialHandle", {}).get("RowName", "")
                count = mat.get("Count", 0)
                if not mat_row or mat_row == "None":
                    continue
                mat_display = _lookup_display(mat_row, string_table)
                out.append({
                    "internal": mat_row,
                    "display": mat_display,
                    "quantity": count,
                })
            return out

        default_mats = _convert_materials(
            recipe_data.get("DefaultRequiredMaterials", []))
        sandbox_mats = _convert_materials(
            recipe_data.get("SandboxRequiredMaterials", []))

        # Look up tier from string_table (stored during Phase 2)
        tier = None
        st_entry = string_table.get(recipe_name)
        if st_entry and "tier" in st_entry:
            tier = st_entry["tier"]
        if tier is None:
            st_entry = string_table.get(stripped)
            if st_entry and "tier" in st_entry:
                tier = st_entry["tier"]
        # Default to 0 for armor with no tier tag (NPC outfits, etc.)
        if tier is None and is_armor:
            tier = 0

        entry = {
            "internal_name": recipe_name,
            "display_name": display,
            "tier": tier,
            "default_materials": default_mats,
            "sandbox_materials": sandbox_mats,
        }

        if is_weapon:
            weapons.append(entry)
        else:
            armor.append(entry)

    # Sort by display name
    weapons.sort(key=lambda e: e["display_name"].lower())
    armor.sort(key=lambda e: e["display_name"].lower())

    print(f"  Phase 3: {len(weapons)} weapons, {len(armor)} armor pieces "
          f"with recipes")
    return weapons, armor


# ---------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------

def write_json_output(weapons, armor, out_path: Path):
    """Write recipes_output.json for manual inspection."""
    output = {
        "weapons": weapons,
        "armor": armor,
        "stats": {
            "weapons_found": len(weapons),
            "armor_found": len(armor),
        },
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)
    print(f"  Wrote {out_path}")


def _format_list(items: list[dict], indent: int = 4) -> str:
    """Format a list of recipe dicts as Python source."""
    pad = " " * indent
    lines: list[str] = ["["]
    for item in items:
        lines.append(f"{pad}{{")
        lines.append(f'{pad}    "internal_name": {item["internal_name"]!r},')
        lines.append(f'{pad}    "display_name": {item["display_name"]!r},')
        lines.append(f'{pad}    "tier": {item["tier"]!r},')

        # default_materials
        if item["default_materials"]:
            lines.append(f'{pad}    "default_materials": [')
            for m in item["default_materials"]:
                lines.append(
                    f'{pad}        {{"internal": {m["internal"]!r}, '
                    f'"display": {m["display"]!r}, '
                    f'"quantity": {m["quantity"]!r}}},'
                )
            lines.append(f"{pad}    ],")
        else:
            lines.append(f'{pad}    "default_materials": [],')

        # sandbox_materials
        if item["sandbox_materials"]:
            lines.append(f'{pad}    "sandbox_materials": [')
            for m in item["sandbox_materials"]:
                lines.append(
                    f'{pad}        {{"internal": {m["internal"]!r}, '
                    f'"display": {m["display"]!r}, '
                    f'"quantity": {m["quantity"]!r}}},'
                )
            lines.append(f"{pad}    ],")
        else:
            lines.append(f'{pad}    "sandbox_materials": [],')

        lines.append(f"{pad}}},")
    lines.append("]")
    return "\n".join(lines)


def write_embedded_py(weapons, armor, out_path: Path):
    """Generate recipes_data_embedded.py consumed at runtime."""
    content = textwrap.dedent('''\
        """Embedded recipes data for the Materials Calculator.

        Auto-generated by helper/recipe_extractor.py — do not edit by hand.
        """

        # Weapons with crafting recipes
        WEAPONS = {weapons}

        # Armor with crafting recipes
        ARMOR = {armor}


        def get_recipes_data() -> dict:
            """Get the complete recipes data structure.

            Returns:
                Dictionary with 'weapons' and 'armor' keys containing lists of recipes.
            """
            return {{
                "weapons": WEAPONS,
                "armor": ARMOR,
            }}
    ''').format(
        weapons=_format_list(weapons),
        armor=_format_list(armor),
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  Wrote {out_path}")


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main():
    print("=" * 60)
    print("Recipe Extractor — 3-Phase Algorithm")
    print("=" * 60)

    # Phase 1
    print("\n--- Phase 1: String Table ---")
    string_table = load_string_table(GAMESOURCE_DIR / "Items.json")

    # Phase 2
    print("\n--- Phase 2: Definition Tables ---")
    weapon_names, armor_names, item_names = resolve_definitions(
        string_table, GAMESOURCE_DIR)

    # Phase 3
    print("\n--- Phase 3: Recipes ---")
    weapons, armor = build_recipes(
        string_table, weapon_names, armor_names, GAMESOURCE_DIR)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Weapons with recipes: {len(weapons)}")
    for w in weapons:
        tag = w["display_name"]
        if tag == w["internal_name"]:
            tag += "  ** (no display name resolved)"
        tier_str = f"T{w['tier']}" if w["tier"] is not None else "T?"
        print(f"    [{tier_str}] {tag}  [{w['internal_name']}]")

    print(f"\n  Armor with recipes:   {len(armor)}")
    for a in armor:
        tag = a["display_name"]
        if tag == a["internal_name"]:
            tag += "  ** (no display name resolved)"
        tier_str = f"T{a['tier']}" if a["tier"] is not None else "T?"
        print(f"    [{tier_str}] {tag}  [{a['internal_name']}]")

    # Output
    print("\n--- Writing output files ---")
    json_out = Path(__file__).parent / "recipes_output.json"
    write_json_output(weapons, armor, json_out)
    write_embedded_py(weapons, armor, EMBEDDED_PY)

    print("\nDone.")


if __name__ == "__main__":
    main()
