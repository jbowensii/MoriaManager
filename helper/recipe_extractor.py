#!/usr/bin/env python3
"""
Helper script to extract weapons/armor recipes with display names and materials.

Loads:
- Items.json: String table (internal name → display name)
- DT_Weapons.json / DT_Armor.json: Weapon/armor definitions
- DT_ItemRecipes.json: Crafting recipes with materials
"""

import json
from pathlib import Path

GAMESOURCE_DIR = Path(__file__).parent.parent / "gamesource"


def load_json(filename: str):
    """Load a JSON file from gamesource directory."""
    path = GAMESOURCE_DIR / filename
    print(f"Loading {path}...")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_string_table(items_data: list) -> dict[str, str]:
    """Build internal name → display name mapping from Items.json."""
    string_table = {}
    
    # Items.json is a list with a StringTable entry
    for entry in items_data:
        if entry.get("Type") == "StringTable":
            keys_to_entries = entry.get("StringTable", {}).get("KeysToEntries", {})
            for key, value in keys_to_entries.items():
                string_table[key] = value
    
    print(f"  Loaded {len(string_table)} string table entries")
    return string_table


def extract_weapon_names(weapons_data: dict) -> list[str]:
    """Extract weapon row names from DT_Weapons.json."""
    names = []
    
    exports = weapons_data.get("Exports", [])
    for export in exports:
        table = export.get("Table", {})
        data = table.get("Data", [])
        for item in data:
            name = item.get("Name")
            if name:
                names.append(name)
    
    print(f"  Found {len(names)} weapons")
    return names


def extract_armor_names(armor_data: dict) -> list[str]:
    """Extract armor row names from DT_Armor.json."""
    names = []
    
    exports = armor_data.get("Exports", [])
    for export in exports:
        table = export.get("Table", {})
        data = table.get("Data", [])
        for item in data:
            name = item.get("Name")
            if name:
                names.append(name)
    
    print(f"  Found {len(names)} armor pieces")
    return names


def build_recipe_map(recipes_data: list) -> dict:
    """Build recipe name → materials mapping from DT_ItemRecipes.json.
    
    Returns a dict with both DefaultRequiredMaterials and SandboxRequiredMaterials.
    """
    recipes = {}
    
    for entry in recipes_data:
        if entry.get("Type") == "DataTable":
            rows = entry.get("Rows", {})
            for recipe_name, recipe_data in rows.items():
                default_materials = []
                sandbox_materials = []
                
                # Extract DefaultRequiredMaterials
                for mat in recipe_data.get("DefaultRequiredMaterials", []):
                    mat_handle = mat.get("MaterialHandle", {})
                    row_name = mat_handle.get("RowName", "")
                    count = mat.get("Count", 0)
                    if row_name and row_name != "None":
                        default_materials.append({
                            "item": row_name,
                            "quantity": count
                        })
                
                # Extract SandboxRequiredMaterials
                for mat in recipe_data.get("SandboxRequiredMaterials", []):
                    mat_handle = mat.get("MaterialHandle", {})
                    row_name = mat_handle.get("RowName", "")
                    count = mat.get("Count", 0)
                    if row_name and row_name != "None":
                        sandbox_materials.append({
                            "item": row_name,
                            "quantity": count
                        })
                
                # Keep recipe if either list has data
                if default_materials or sandbox_materials:
                    recipes[recipe_name] = {
                        "default": default_materials,
                        "sandbox": sandbox_materials
                    }
    
    print(f"  Loaded {len(recipes)} recipes with materials")
    return recipes


def find_display_name(internal_name: str, string_table: dict, item_type: str = "weapon") -> str | None:
    """
    Try to find display name for an item using various key patterns.
    
    Patterns tried:
    - DT_Weapons.{name}.DisplayName
    - DT_Armor.{name}.DisplayName  
    - Weapons.{pattern}.Name (parsed from name)
    - Armor.{pattern}.Name (parsed from name)
    """
    # Try DT_Weapons/DT_Armor pattern
    dt_prefix = "DT_Weapons" if item_type == "weapon" else "DT_Armor"
    key = f"{dt_prefix}.{internal_name}.DisplayName"
    if key in string_table:
        return string_table[key]
    
    # Try without DT_ prefix
    prefix = "Weapons" if item_type == "weapon" else "Armor"
    key = f"{prefix}.{internal_name}.Name"
    if key in string_table:
        return string_table[key]
    
    # Parse the internal name to build possible key patterns
    # e.g., "Belegost_APSet_BootsArmor" -> look for "Armor.Belegost.Boots.Name"
    # e.g., "Sword_1h_t1" -> look for "Weapons.*.Sword*.Name"
    
    # For armor: Parse the name pattern
    if item_type == "armor":
        parts = internal_name.split("_")
        # Filter out common non-meaningful parts
        meaningful_parts = [p for p in parts if p.lower() not in ("set", "apset", "armor")]
        
        # Extract the set name and armor type
        set_name = parts[0] if parts else None
        armor_type = None
        for part in parts:
            part_lower = part.lower()
            if "boots" in part_lower:
                armor_type = "Boots"
            elif "gloves" in part_lower or "gauntlet" in part_lower:
                armor_type = "Gloves"
            elif "helmet" in part_lower or "helm" in part_lower:
                armor_type = "Helmet"
            elif "torso" in part_lower:
                armor_type = "Torso"
            elif "shield" in part_lower:
                armor_type = "Shield"
        
        # Find best match with most parts matching
        best_match = None
        best_match_count = 0
        
        for key, value in string_table.items():
            key_lower = key.lower()
            if not key_lower.startswith("armor.") or not key_lower.endswith(".name"):
                continue
            if "broken" in key_lower or "broken" in value.lower():
                continue
            
            key_parts = key_lower.replace(".name", "").split(".")
            # Count how many meaningful parts match
            matches = sum(1 for p in meaningful_parts if p.lower() in key_parts)
            
            # Bonus for matching armor type
            if armor_type and armor_type.lower() in key_parts:
                matches += 1
            
            if matches > best_match_count:
                best_match = value
                best_match_count = matches
        
        if best_match:
            return best_match
    
    # For weapons: Parse the name pattern
    if item_type == "weapon":
        parts = internal_name.split("_")
        # Filter out tier indicators like "1h", "2h", "t1", "t2", etc.
        meaningful_parts = [p for p in parts if not p.lower().startswith("t") 
                          and p.lower() not in ("1h", "2h")]
        
        # Find the best match (most parts matching)
        best_match = None
        best_match_count = 0
        
        # Try each meaningful part as the weapon type
        for weapon_type in meaningful_parts:
            # Search for any key that has this weapon type and ends with .Name
            for key, value in string_table.items():
                key_lower = key.lower()
                # Skip recipe fragments and broken items
                if "recipefragment" in key_lower:
                    continue
                if "craft plans" in value.lower():
                    continue
                if "broken" in key_lower or "broken" in value.lower():
                    continue
                if (weapon_type.lower() in key_lower and 
                    key_lower.endswith(".name") and 
                    key_lower.startswith("weapons.")):
                    # For patterns like Weapons.Mattock.Mithril.Name, check if other parts match
                    key_parts = key_lower.replace(".name", "").split(".")
                    # Check if multiple meaningful parts appear in the key
                    matches = sum(1 for p in meaningful_parts if p.lower() in key_parts)
                    if matches > best_match_count:
                        best_match = value
                        best_match_count = matches
        
        if best_match:
            return best_match
    
    return None


def find_material_display_name(material_internal: str, string_table: dict) -> str | None:
    """Try to find display name for a material."""
    # Materials often have patterns like "Item.IronIngot" → lookup Items.Items.IronIngot.Name
    if material_internal.startswith("Item."):
        item_part = material_internal[5:]  # Remove "Item." prefix
        # Try Items.Items.{name}.Name pattern
        key = f"Items.Items.{item_part}.Name"
        if key in string_table:
            return string_table[key]
        # Try Items.{name}.Name pattern
        key = f"Items.{item_part}.Name"
        if key in string_table:
            return string_table[key]
    
    if material_internal.startswith("Ore."):
        ore_part = material_internal[4:]
        # Try Items.Item.PreciousGem.{name}.Name pattern (for gems like Ruby, Diamond)
        key = f"Items.Item.PreciousGem.{ore_part}.Name"
        if key in string_table:
            return string_table[key]
        # Try Items.Item.SemiPreciousGem.{name}.Name pattern
        key = f"Items.Item.SemiPreciousGem.{ore_part}.Name"
        if key in string_table:
            return string_table[key]
        # Try Items.Ores.{name}.Name pattern
        key = f"Items.Ores.{ore_part}.Name"
        if key in string_table:
            return string_table[key]
        key = f"Ores.{ore_part}.Name"
        if key in string_table:
            return string_table[key]
    
    if material_internal.startswith("Consumable."):
        consumable_part = material_internal[11:]
        # Try Items.Consumables.{name}.Name pattern
        key = f"Items.Consumables.{consumable_part}.Name"
        if key in string_table:
            return string_table[key]
        key = f"Consumables.{consumable_part}.Name"
        if key in string_table:
            return string_table[key]
    
    # Try direct lookup
    key = f"{material_internal}.Name"
    if key in string_table:
        return string_table[key]
    
    key = f"{material_internal}.DisplayName"
    if key in string_table:
        return string_table[key]
    
    return material_internal  # Return internal name as fallback


def main():
    print("=" * 60)
    print("Recipe Extractor - Loading game data...")
    print("=" * 60)
    
    # Load all data files
    items_data = load_json("Items.json")
    weapons_data = load_json("DT_Weapons.json")
    armor_data = load_json("DT_Armor.json")
    recipes_data = load_json("DT_ItemRecipes.json")
    
    print()
    
    # Build lookups
    string_table = build_string_table(items_data)
    weapon_names = set(extract_weapon_names(weapons_data))
    armor_names = set(extract_armor_names(armor_data))
    recipes = build_recipe_map(recipes_data)
    
    # Also include recipes that look like weapons/armor even if not in the data tables
    weapon_keywords = ["sword", "mattock", "spear", "battleaxe", "halberd", "hammer", 
                       "shield", "axe", "weapon", "crossbow", "bow", "dagger"]
    armor_keywords = ["armor", "boots", "gloves", "helmet", "torso", "gauntlet", "helm"]
    
    # Find all recipe names that might be weapons or armor
    for recipe_name in recipes.keys():
        name_lower = recipe_name.lower()
        if any(kw in name_lower for kw in weapon_keywords) and recipe_name not in weapon_names:
            weapon_names.add(recipe_name)
        if any(kw in name_lower for kw in armor_keywords) and recipe_name not in armor_names:
            armor_names.add(recipe_name)
    
    print(f"  Total weapon candidates (including recipes): {len(weapon_names)}")
    print(f"  Total armor candidates (including recipes): {len(armor_names)}")
    
    print()
    print("=" * 60)
    print("Processing weapons...")
    print("=" * 60)
    
    # Process weapons
    weapons_with_recipes = []
    weapons_no_display = []
    weapons_no_recipe = []
    
    for name in weapon_names:
        display_name = find_display_name(name, string_table, "weapon")
        
        if not display_name:
            weapons_no_display.append(name)
            continue
        
        # Look for recipe
        recipe = recipes.get(name)
        if not recipe:
            weapons_no_recipe.append((name, display_name))
            continue
        
        # Convert default material internal names to display names
        default_materials_with_display = []
        for mat in recipe.get("default", []):
            mat_display = find_material_display_name(mat["item"], string_table)
            default_materials_with_display.append({
                "internal": mat["item"],
                "display": mat_display,
                "quantity": mat["quantity"]
            })
        
        # Convert sandbox material internal names to display names
        sandbox_materials_with_display = []
        for mat in recipe.get("sandbox", []):
            mat_display = find_material_display_name(mat["item"], string_table)
            sandbox_materials_with_display.append({
                "internal": mat["item"],
                "display": mat_display,
                "quantity": mat["quantity"]
            })
        
        weapons_with_recipes.append({
            "internal_name": name,
            "display_name": display_name,
            "default_materials": default_materials_with_display,
            "sandbox_materials": sandbox_materials_with_display
        })
    
    print(f"\nWeapons with display names and recipes: {len(weapons_with_recipes)}")
    print(f"Weapons without display names (removed): {len(weapons_no_display)}")
    print(f"Weapons without recipes (removed): {len(weapons_no_recipe)}")
    
    print()
    print("=" * 60)
    print("Processing armor...")
    print("=" * 60)
    
    # Process armor
    armor_with_recipes = []
    armor_no_display = []
    armor_no_recipe = []
    
    for name in armor_names:
        display_name = find_display_name(name, string_table, "armor")
        
        if not display_name:
            armor_no_display.append(name)
            continue
        
        # Look for recipe
        recipe = recipes.get(name)
        if not recipe:
            armor_no_recipe.append((name, display_name))
            continue
        
        # Convert default material internal names to display names
        default_materials_with_display = []
        for mat in recipe.get("default", []):
            mat_display = find_material_display_name(mat["item"], string_table)
            default_materials_with_display.append({
                "internal": mat["item"],
                "display": mat_display,
                "quantity": mat["quantity"]
            })
        
        # Convert sandbox material internal names to display names
        sandbox_materials_with_display = []
        for mat in recipe.get("sandbox", []):
            mat_display = find_material_display_name(mat["item"], string_table)
            sandbox_materials_with_display.append({
                "internal": mat["item"],
                "display": mat_display,
                "quantity": mat["quantity"]
            })
        
        armor_with_recipes.append({
            "internal_name": name,
            "display_name": display_name,
            "default_materials": default_materials_with_display,
            "sandbox_materials": sandbox_materials_with_display
        })
    
    print(f"\nArmor with display names and recipes: {len(armor_with_recipes)}")
    print(f"Armor without display names (removed): {len(armor_no_display)}")
    print(f"Armor without recipes (removed): {len(armor_no_recipe)}")
    
    # Output results
    print()
    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    print("\n--- WEAPONS ---")
    for item in weapons_with_recipes[:10]:  # First 10
        print(f"\n{item['display_name']} ({item['internal_name']})")
        if item['default_materials']:
            print("  Default Materials:")
            for mat in item['default_materials']:
                print(f"    - {mat['quantity']}x {mat['display']} ({mat['internal']})")
        if item['sandbox_materials']:
            print("  Sandbox Materials:")
            for mat in item['sandbox_materials']:
                print(f"    - {mat['quantity']}x {mat['display']} ({mat['internal']})")
    
    if len(weapons_with_recipes) > 10:
        print(f"\n... and {len(weapons_with_recipes) - 10} more weapons")
    
    print("\n--- ARMOR ---")
    for item in armor_with_recipes[:10]:  # First 10
        print(f"\n{item['display_name']} ({item['internal_name']})")
        if item['default_materials']:
            print("  Default Materials:")
            for mat in item['default_materials']:
                print(f"    - {mat['quantity']}x {mat['display']} ({mat['internal']})")
        if item['sandbox_materials']:
            print("  Sandbox Materials:")
            for mat in item['sandbox_materials']:
                print(f"    - {mat['quantity']}x {mat['display']} ({mat['internal']})")
    
    if len(armor_with_recipes) > 10:
        print(f"\n... and {len(armor_with_recipes) - 10} more armor pieces")
    
    # Save to output file
    output = {
        "weapons": weapons_with_recipes,
        "armor": armor_with_recipes,
        "stats": {
            "total_weapons": len(weapon_names),
            "weapons_with_recipes": len(weapons_with_recipes),
            "weapons_no_display": len(weapons_no_display),
            "weapons_no_recipe": len(weapons_no_recipe),
            "total_armor": len(armor_names),
            "armor_with_recipes": len(armor_with_recipes),
            "armor_no_display": len(armor_no_display),
            "armor_no_recipe": len(armor_no_recipe)
        }
    }
    
    output_path = Path(__file__).parent / "recipes_output.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()
