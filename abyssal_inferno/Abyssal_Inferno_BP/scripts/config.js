// Abyssal Inferno - tuning table. All times are in ticks (20 ticks = 1 s).

export const ITEM_ID = "abyss:abyssal_inferno";
export const COMPONENT_ID = "abyss:inferno_weapon";

// Skill wheel. Sneak (press) cycles forward, Use (right click) casts the selected one.
export const SKILLS = [
    { key: "rend", name: "ABYSS REND", color: "§5", cd: 100, hint: "รอยแยกความว่างเปล่า 8 บล็อก" },
    { key: "sun", name: "BLACK SUN", color: "§4", cd: 240, hint: "ดวงอาทิตย์ดำ ดูดศัตรู 5 วิ" },
    { key: "flare", name: "ABYSSAL FLARE", color: "§c", cd: 160, hint: "ระเบิดไฟดำรอบตัว" },
    { key: "spear", name: "VOID SPEAR", color: "§d", cd: 120, hint: "หอกความว่างเปล่า 12 บล็อก" },
    { key: "charge", name: "VOID COMBUSTION", color: "§9", cd: 20, hint: "กดค้างเพื่อชาร์จ ปล่อยเพื่อระเบิด" },
    { key: "ult", name: "END OF ALL FLAMES", color: "§6", cd: 0, hint: "ต้องการ Inferno 100 + Void 100" },
];

export const GAUGE_MAX = 100;

// Basic attack: BLACK FLAME COMBO (left click on an enemy)
export const ITEM_BASE_DAMAGE = 6;
export const COMBO_HITS = [
    { dmg: 6, inferno: 4 },
    { dmg: 7, inferno: 4 },
    { dmg: 8, inferno: 5, wave: { range: 4, dmg: 8 } },
    { dmg: 10, inferno: 7, markChance: 0.35 },
    { dmg: 15, inferno: 10, blast: { radius: 3, dmg: 15 } },
];
export const COMBO_STEP_WINDOW = 30;

// Combo counter
export const COMBO_MAX = 15;
export const COMBO_TIMEOUT = 30; // 1.5 s without hitting -> reset
export const COMBO_BURST = { radius: 4, dmg: 20, fallbackTo: 10 };

// Charged attack: VOID COMBUSTION
export const CHARGE = {
    fullTicks: 30,       // time to reach full charge
    holdGap: 7,          // no "use" pulse for this long -> button released
    maxHold: 200,        // auto release safety
    normal: { dmg: 15, radius: 3 },
    full: { dmg: 25, radius: 5, void: 20, marks: 1 },
};
export const VOID_ZONE = { duration: 80, every: 10, dmg: 2, radius: 4, markChance: 0.3 };

export const REND = { range: 8, width: 1.6, dmg: 18, void: 15, marks: 1 };
export const SUN = { distance: 4, height: 1.6, duration: 100, every: 10, radius: 5, dmg: 4, marks: 1,
                     collapse: { dmg: 30, radius: 6 }, void: 25 };
export const FLARE = { radius: 5, dmg: 20, inferno: 15, void: 10, marks: 1 };
export const SPEAR = { range: 12, speed: 2, dmg: 22, markedBonus: 10, marks: 2, void: 20, hitRadius: 1.3 };

// Status effects on enemies
export const BURN = { duration: 60, every: 10, dmg: 2, abyssDmg: 3, inferno: 2,
                      blackFlameChance: 0.15, blackFlame: { dmg: 4, radius: 2 },
                      voidExplosionChance: 0.2, voidExplosion: { dmg: 5, radius: 2.5 } };
export const MARK = { max: 5, expire: 200, dominanceAt: 3, voidBonus: 0.15,
                      voidBreak: { dmg: 30, radius: 4, void: 20 } };

// Gauges
export const KILL_GAIN = { inferno: 10, void: 10 };
export const KILL_GAIN_MARKED = { inferno: 15, void: 20 };

// Abyss Ignition
export const IGNITION = { duration: 200, dmgBonus: 0.25, burnBonus: 0.25, breakBonus: 0.25, markChance: 0.25 };

// Ultimate
export const ULT = { height: 6.5, pullStart: 10, collapseAt: 50, blastAt: 70, radius: 12, dmg: 60, marks: 3 };

// Intro / outro
export const INTRO = { cooldown: 400, delay: 10, dmg: 15, radius: 3, marks: 1 };
export const OUTRO = { combatWindow: 300, duration: 100, every: 10, dmg: 2, radius: 4 };

export const SCOREBOARDS = [
    ["abyss_inferno", "Inferno"],
    ["abyss_void", "Void"],
    ["abyss_combo", "Combo"],
    ["abyss_mark", "Void Mark"],
    ["abyss_burn", "Burn"],
    ["abyss_skill1", "Abyss Rend CD"],
    ["abyss_skill2", "Black Sun CD"],
    ["abyss_skill3", "Abyssal Flare CD"],
    ["abyss_skill4", "Void Spear CD"],
    ["abyss_select", "Selected Skill"],
];

export const LORE = [
    "§r§8Black Flame - Void - Abyss",
    "§r§7ย่อ (Sneak): §fสลับสกิล",
    "§r§7คลิกขวา: §fใช้สกิลที่เลือก",
    "§r§7คลิกซ้ายใส่ศัตรู: §fBlack Flame Combo 5 จังหวะ",
    "§r§7Void Combustion: §fกดค้างคลิกขวาเพื่อชาร์จ",
    "§r§cInferno 100 §7+ §5Void 100 §7= §6End of All Flames",
];
