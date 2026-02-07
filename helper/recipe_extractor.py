#!/usr/bin/env python3
"""
Helper script to extract weapons/armor recipes with display names and materials.

Loads:
- Items.json: String table (internal name → display name)
- DT_ItemRecipes.json: Crafting recipes with materials

Uses direct mapping from display name to recipe internal name.
"""

import json
from pathlib import Path

GAMESOURCE_DIR = Path(__file__).parent.parent / "gamesource"

# Direct mapping from display name to recipe internal name
# This is more reliable than pattern matching given inconsistent game data
# Note: Some items from user's original list don't have crafting recipes
WEAPON_RECIPES = {
    # Basic tier weapons (t0-t5)
    "Improvised Axe": "WarAxe_1h_t0",
    "Iron Sword": "Sword_1h_t1",
    "Iron War Axe": "WarAxe_1h_t1",
    "Steel Sword": "Sword_1h_t2",
    "Steel War Axe": "WarAxe_1h_t2",
    "Steel Battleaxe": "Battleaxe_2h_t2",
    "Iron Spear": "Spear_1h_t1_TU2",  # Named _TU2 in recipes
    "First Age Sword": "Sword_1h_t4",
    "First Age Greatsword": "Sword_2h_t3",
    "First Age Battleaxe": "Battleaxe_2h_t4",
    
    # Khazâd tier weapons (t3)
    "Last Alliance Maul": "Mattock_1h_t3",
    "Khazâd War Mattock": "Restoration_Hammer_Starmetal",  # Special item
    "Khazâd War Axe": "WarAxe_1h_t3",
    "Khazâd Maul": "Mattock_1h_t2",
    "Khazâd Army Halberd": "Halberd_2h_t3",
    "Khazâd Army Greatsword": "Sword_2h_t3",
    
    # Belegost weapons
    "Belegost Halberd": "Halberd_2h_t2",
    "Belegost War Axe": "Durins_Axe",
    
    # Spears
    "Eregion Spear": "Spear_1h_t2",
    "Rohirrim Spear": "RohanPack_Spear_1h",
    "Dimrill Spear": "Spear_1h_t3",
    
    # Shields
    "Iron Hills Shield": "IronHills_APSet_Shield",
    "Heirloom Shield": "Amazing_TBDSet_Shield",
    "Ram's Head Shield": "Awesome_TBDSet_Shield",
    "Rohirrim Shield": "RohanPack_Shield",
    "Eregion Shield": "EregionElf_Set_Shield",
    "Belegost Shield": "Belegost_Set_Shield",
    "Shieldwall": "OakenShield_TBDSet_Shield",
    "Mithril Shield": "Mithril_TBDSet_Shield",
    "Ornamental Shield": "Grand_TBDSet_Shield",
    "Gondorian Shield": "Durin_TBDSet_Shield",
    "Last Alliance Shield": "Stunning_TBDSet_Shield",
    "Durin's Guard Shield": "Taunting_TBDSet_Shield",
    "Nogrod Shield": "NogrodShield",
    "Ent-craft Shield": "EntPack_Shield",
    
    # Named/Legendary Mithril weapons (t5-t6)
    # Based on Items.json: Shaz'akhnaman=WarAxe.Mithril, Rukhnaman=Sword.Mithril
    "Shaz'akhnaman": "Mithril_WarAxe_1h_t6",  # Mithril War Axe
    "Sagrûrisâbun": "Mithril_Battlehammer",  # Battlehammer.Mithril - no recipe exists
    "Barôkamlut": "Mithril_Battleaxe_2h",  # Battleaxe.Mithril - no recipe exists
    "Muasgadnûr": "Mithril_Mattock_1h_t6",  # Mattock.Mithril
    "Khushnabrak": "Spear_1h_t4",
    "Lafarnîzîn": "Mithril_Halberd_2h_t6",  # Halberd.Mithril
    "Rukhnaman": "Mithril_Sword_1h_t6",  # Sword.Mithril
    "Thanazbad": "Mithril_GreatSword_2h_t6",  # Greatsword.Mithril
    "Drakhbarzin": "Weapon_Starlight",
    
    # Ranged weapons
    "Hunting Bow": "Shortbow_Bow",  # Named Shortbow_Bow in recipes
    "Arrows": "Arrow_Basic_t1",
    "Elven Arrows": "Arrow_Elven_t2",
    "Khazâd Arrows": "Arrow_Khazad_t3",
    "First Age Crossbow": "Crossbow",
    "First Age Bolts": "CrossbowBolt_Basic_t1",
    "Khazâd Bolts": "CrossbowBolt_Khazad_t2",
    "Nogrod Bolts": "CrossbowBolt_Nogrod_t3",
    
    # Special named weapons
    "Dagamarth": "FamousElvenSword",
    "Red Sword of Nogrod": "Nogrod_Sword_1h",  # May not have recipe
    "Red Axe of Nogrod": "Nogrod_Axe_1h",  # May not have recipe
    "Ironbough Greatsword": "Greenbeard_Sword_2h",
    "Frightener's Battleaxe": "OrcHunter_GreatAxe_2h",
    "Gimli's Axe": "Battleaxe_2h_Gimli",
}

ARMOR_RECIPES = {
    # Iron Hills set
    "Iron Hills Armor": "IronHills_APSet_TorsoArmor",
    "Iron Hills Gloves": "IronHills_APSet_GlovesArmor",
    
    # Erebor set
    "Erebor Ringmail": "EreborSteel_APSet_TorsoArmor",
    "Erebor Planked Gauntlets": "EreborSteel_APSet_GlovesArmor",
    "Erebor Boots": "EreborSteel_APSet_BootsArmor",
    "Erebor City Watch Helmet": "EreborSteel_APSet_HelmetArmor",
    
    # Belegost set
    "Belegost Boots": "Belegost_APSet_BootsArmor",
    "Belegost Helmet": "Belegost_APSet_HelmetArmor",
    "Belegost Gauntlets": "Belegost_APSet_GlovesArmor",
    "Belegost Ringmail": "Belegost_APSet_TorsoArmor",
    
    # Khazâd Army set
    "Khazâd Army Armor": "Khazad_Set_TorsoArmor",
    "Khazâd Army Gauntlets": "Khazad_Set_GlovesArmor",
    "Khazâd Army Boots": "Khazad_Set_BootsArmor",
    "Khazâd Army Helmet": "Khazad_Set_HelmArmor",
    
    # Mithril set
    "Mithril Helmet": "Mithril_Set_HelmetArmor",
    "Mithril Armor": "Mithril_Set_TorsoArmor",
    "Mithril Gloves": "Mithril_Set_GlovesArmor",
    "Mithril Slippers": "Mithril_Set_BootsArmor",
    
    # Hats
    "Trapper Hat": "Stunning_Set_HelmetArmor",
    "Longbottom Hat": "Grand_Set_HelmetArmor",
    "Miner's Helmet": "RedMountains_MinerSet_HelmetArmor",
    "Gatherer's Hat": "NPC_Outfit_Gatherer_Hat",  # Special NPC outfit name
    "Wolf Skin Hat": "Wonderful_Set_HelmetArmor",
    
    # Blue Mountains Hunter set
    "Blue Mountains Hunter's Armor": "BlueMountainsHunter_Set_TorsoArmor",
    "Blue Mountains Hunter's Boots": "BlueMountainsHunter_Set_BootsArmor",
    "Blue Mountains Hunter's Gloves": "RangeBonus_Set_GlovesArmor",  # Different internal name
    
    # Grey Mountain set (uses AntiCold prefix in recipe keys)
    "Grey Mountain Overcoat": "AntiColdTorso",
    "Grey Mountains Boots": "AntiColdBoots",
    "Grey Mountain Gloves": "AntiColdGloves",
    "Grey Mountain Hat": "AntiColdHelm",
    
    # Eregion set (no "Armor" suffix in recipe name)
    "Eregion Armor": "EregionElf_Set_Torso",
    
    # Durin's Guard set
    "Durin's Guard Helmet": "Durin_Set_HelmetArmor",
    "Durin's Guard Armor": "Durin_Set_TorsoArmor",
    "Durin's Gloves": "Durin_Set_GlovesArmor",
    "Durin's Guard Boots": "Durin_Set_BootsArmor",
    
    # Nogrod set
    "Nogrod Armor": "Nogrod_Set_TorsoArmor",
    "Nogrod Gauntlets": "Nogrod_Set_GlovesArmor",
    
    # Special helmets
    "Last Alliance Helmet": "Classic_Set_HelmetArmor",
    "Crested Helmet": "Taunting_TBDSet_Helm",  # Internal name is Taunting
    "Spiked Helmet": "SouthernmostFireProof_Set_HelmetArmor",
    "Dimrill Helmet": "Awesome_Set_HelmetArmor",
    
    # Special armor
    "Expeditioner's Armor": "Orcbane_Set_TorsoArmor",
}


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


def build_reverse_lookup(string_table: dict[str, str]) -> dict[str, list[str]]:
    """Build display name → list of internal key patterns.
    
    This allows us to find all string table keys that have a specific display name.
    """
    reverse = {}
    for key, value in string_table.items():
        if value not in reverse:
            reverse[value] = []
        reverse[value].append(key)
    return reverse


def find_recipe_name_from_string_key(string_key: str) -> str | None:
    """Extract likely recipe name from a string table key.
    
    e.g., "Weapons.Spear.Khazad.Name" → "Spear_Khazad" or similar patterns
    e.g., "Armor.Belegost.Boots.Name" → "Belegost_APSet_BootsArmor" or similar
    """
    # Remove common suffixes
    key = string_key.replace(".Name", "").replace(".DisplayName", "")
    parts = key.split(".")
    
    # Skip prefix like "Weapons" or "Armor"
    if parts and parts[0] in ("Weapons", "Armor", "Items"):
        parts = parts[1:]
    
    # Return joined parts
    return "_".join(parts) if parts else None


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
        
        # Require at least 2 matching parts for a valid match
        # This prevents generic items from matching incorrectly
        if best_match_count < 2:
            return None
        
        if best_match:
            return best_match
    
    # For weapons: Parse the name pattern
    if item_type == "weapon":
        parts = internal_name.split("_")
        
        # Extract tier info to help with matching
        tier = None
        for p in parts:
            p_lower = p.lower()
            if p_lower.startswith("t") and len(p_lower) >= 2 and p_lower[1:].isdigit():
                tier = int(p_lower[1:])
                break
        
        # Map tiers to material types for string table matching
        tier_materials = {
            1: ["iron"],
            2: ["steel"],
            3: ["khazad", "khazâd", "bronze"],
            4: ["firstage", "darkalloy"],
            5: ["mithril"],
            6: ["mithril"]  # Highest tier also uses mithril
        }
        
        # Filter out tier indicators like "1h", "2h", "t1", "t2", etc.
        meaningful_parts = [p for p in parts if not p.lower().startswith("t") 
                          and p.lower() not in ("1h", "2h")]
        
        # For tier-based weapons, add the expected material to meaningful parts
        if tier and tier in tier_materials:
            meaningful_parts.extend(tier_materials[tier])
        
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
        
        # Require at least 2 matching parts for tier-based weapons
        # This prevents generic tier weapons from matching to wrong named weapons
        if tier and best_match_count < 2:
            return None
        
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
    print("Recipe Extractor - Direct Mapping Approach")
    print("=" * 60)
    
    # Load all data files
    items_data = load_json("Items.json")
    recipes_data = load_json("DT_ItemRecipes.json")
    
    print()
    
    # Build lookups
    string_table = build_string_table(items_data)
    recipes = build_recipe_map(recipes_data)
    
    print(f"  Total recipes available: {len(recipes)}")
    
    print()
    print("=" * 60)
    print("Finding weapons using direct mapping...")
    print("=" * 60)
    
    weapons_result = []
    weapons_not_found = []
    
    for display_name, recipe_name in sorted(WEAPON_RECIPES.items()):
        if recipe_name in recipes:
            recipe = recipes[recipe_name]
            
            # Convert materials
            default_mats = []
            for mat in recipe.get("default", []):
                mat_display = find_material_display_name(mat["item"], string_table)
                default_mats.append({
                    "internal": mat["item"],
                    "display": mat_display,
                    "quantity": mat["quantity"]
                })
            
            sandbox_mats = []
            for mat in recipe.get("sandbox", []):
                mat_display = find_material_display_name(mat["item"], string_table)
                sandbox_mats.append({
                    "internal": mat["item"],
                    "display": mat_display,
                    "quantity": mat["quantity"]
                })
            
            weapons_result.append({
                "internal_name": recipe_name,
                "display_name": display_name,
                "default_materials": default_mats,
                "sandbox_materials": sandbox_mats
            })
            print(f"  Found: {display_name} -> {recipe_name}")
        else:
            weapons_not_found.append((display_name, recipe_name))
            print(f"  NOT FOUND: {display_name} -> {recipe_name}")
    
    print()
    print("=" * 60)
    print("Finding armor using direct mapping...")
    print("=" * 60)
    
    armor_result = []
    armor_not_found = []
    
    for display_name, recipe_name in sorted(ARMOR_RECIPES.items()):
        if recipe_name in recipes:
            recipe = recipes[recipe_name]
            
            # Convert materials
            default_mats = []
            for mat in recipe.get("default", []):
                mat_display = find_material_display_name(mat["item"], string_table)
                default_mats.append({
                    "internal": mat["item"],
                    "display": mat_display,
                    "quantity": mat["quantity"]
                })
            
            sandbox_mats = []
            for mat in recipe.get("sandbox", []):
                mat_display = find_material_display_name(mat["item"], string_table)
                sandbox_mats.append({
                    "internal": mat["item"],
                    "display": mat_display,
                    "quantity": mat["quantity"]
                })
            
            armor_result.append({
                "internal_name": recipe_name,
                "display_name": display_name,
                "default_materials": default_mats,
                "sandbox_materials": sandbox_mats
            })
            print(f"  Found: {display_name} -> {recipe_name}")
        else:
            armor_not_found.append((display_name, recipe_name))
            print(f"  NOT FOUND: {display_name} -> {recipe_name}")
    
    # Output results
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    print(f"\nWeapons found: {len(weapons_result)}/{len(WEAPON_RECIPES)}")
    if weapons_not_found:
        print(f"  Missing recipe names: {[x[1] for x in weapons_not_found]}")
    
    print(f"\nArmor found: {len(armor_result)}/{len(ARMOR_RECIPES)}")
    if armor_not_found:
        print(f"  Missing recipe names: {[x[1] for x in armor_not_found]}")
    
    # Save to output file
    output = {
        "weapons": weapons_result,
        "armor": armor_result,
        "stats": {
            "weapons_found": len(weapons_result),
            "weapons_missing": len(weapons_not_found),
            "armor_found": len(armor_result),
            "armor_missing": len(armor_not_found)
        },
        "missing": {
            "weapons": [{"display": d, "recipe": r} for d, r in weapons_not_found],
            "armor": [{"display": d, "recipe": r} for d, r in armor_not_found]
        }
    }
    
    output_path = Path(__file__).parent / "recipes_output.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()
