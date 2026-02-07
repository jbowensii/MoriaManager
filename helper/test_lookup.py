#!/usr/bin/env python3
"""Quick script to understand the data structure."""

import json
from pathlib import Path

GAMESOURCE = Path(__file__).parent.parent / "gamesource"

# Load data
weapons = json.load(open(GAMESOURCE / "DT_Weapons.json"))
recipes = json.load(open(GAMESOURCE / "DT_ItemRecipes.json"))
items = json.load(open(GAMESOURCE / "Items.json"))

# Get string table
st = items[0]["StringTable"]["KeysToEntries"]

# Get recipe names
recipe_rows = recipes[0]["Rows"]
recipe_names = set(recipe_rows.keys())

# Build reverse string table lookup
reverse_st = {}
for k, v in st.items():
    if v not in reverse_st:
        reverse_st[v] = []
    reverse_st[v].append(k)

# Define tier mapping based on the pattern
# From string table keys like "Weapons.Sword.Iron.Name" we can extract material
# From recipe names like "Sword_1h_t1" we get weapon type and tier
# Tier → Material mapping:
TIER_TO_MATERIAL = {
    "t0": ["improvised", "wooden"],
    "t1": ["iron"],
    "t2": ["steel"],
    "t3": ["khazad", "khazâd", "bronze"],
    "t4": ["firstage", "first age", "darkalloy"],
    "t5": ["mithril"],
    "t6": ["mithril"],
}

# Weapon type mapping
WEAPON_TYPES = {
    "sword_1h": "Sword",
    "sword_2h": "Greatsword",
    "waraxe_1h": "War Axe",
    "battleaxe_2h": "Battleaxe",
    "mattock_1h": "Mattock",
    "hammer_2h": "Hammer",
    "maul": "Maul",
    "halberd_2h": "Halberd",
    "spear_1h": "Spear",
    "crossbow": "Crossbow",
    "arrow": "Arrows",
    "crossbowbolt": "Bolts",
}

print("=== FINDING DISPLAY NAME → RECIPE MAPPINGS ===")

# Test some specific items
test_items = [
    "Iron Sword",
    "Steel Sword",
    "Iron War Axe",
    "Steel Battleaxe",
    "First Age Sword",
    "Khazâd War Mattock",
]

for display_name in test_items:
    print(f"\n{display_name}:")
    
    # Find string table keys for this display name
    keys = reverse_st.get(display_name, [])
    print(f"  String table keys: {keys}")
    
    # Parse the key to understand the weapon
    for key in keys:
        # Key format: Weapons.Sword.Iron.Name
        parts = key.replace(".Name", "").split(".")
        if parts[0] == "Weapons" and len(parts) >= 3:
            weapon_type = parts[1].lower()  # sword, waraxe, etc.
            material = parts[2].lower() if len(parts) > 2 else ""
            print(f"  Parsed: type={weapon_type}, material={material}")
            
            # Find matching tier
            for tier, materials in TIER_TO_MATERIAL.items():
                if any(m in material.lower() for m in materials):
                    # Build potential recipe name
                    if weapon_type == "sword":
                        recipe = f"Sword_1h_{tier}"
                        if recipe in recipe_names:
                            print(f"  MATCH: {recipe}")
                    elif weapon_type == "greatsword":
                        recipe = f"Sword_2h_{tier}"
                        if recipe in recipe_names:
                            print(f"  MATCH: {recipe}")
                    elif weapon_type == "waraxe":
                        recipe = f"WarAxe_1h_{tier}"
                        if recipe in recipe_names:
                            print(f"  MATCH: {recipe}")
                    elif weapon_type == "battleaxe":
                        recipe = f"Battleaxe_2h_{tier}"
                        if recipe in recipe_names:
                            print(f"  MATCH: {recipe}")

print("\n=== DT_Weapons structure ===")
print(f"Type: {type(weapons)}")
if isinstance(weapons, dict):
    print(f"Keys: {list(weapons.keys())[:10]}")
elif isinstance(weapons, list):
    print(f"Length: {len(weapons)}")
    if weapons:
        print(f"First element keys: {list(weapons[0].keys()) if isinstance(weapons[0], dict) else 'not dict'}")

# Find Exports in weapons
weapons_data = []
for item in weapons if isinstance(weapons, list) else [weapons]:
    if isinstance(item, dict) and "Exports" in item:
        exports = item["Exports"]
        print(f"\nExports found, length: {len(exports)}")
        for exp in exports:
            if "Table" in exp:
                table = exp["Table"]
                if "Data" in table:
                    data = table["Data"]
                    weapons_data = data
                    print(f"Table Data length: {len(data)}")
                    # Find swords
                    for row in data:
                        name = row.get("Name", "")
                        if "sword" in name.lower():
                            print(f"  Sword in DT_Weapons: {name}")

# Check if weapon names directly match recipe names
print("\n=== Weapon names that ARE recipe names ===")
for row in weapons_data:
    name = row.get("Name", "")
    if name in recipe_names:
        print(f"  {name}")
