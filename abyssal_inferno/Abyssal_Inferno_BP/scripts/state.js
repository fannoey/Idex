import { world } from "@minecraft/server";
import { GAUGE_MAX, IGNITION, SCOREBOARDS, SKILLS, COMBO_MAX, COMBO_TIMEOUT } from "./config.js";
import { now, fx, sound, shake, chest, onGround, circle, later, repeat } from "./util.js";

// ------------------------------------------------------------ player state
const players = new Map();

export function getState(p) {
    let st = players.get(p.id);
    if (!st) {
        st = {
            inferno: num(p.getDynamicProperty("abyss:inferno")),
            void: num(p.getDynamicProperty("abyss:void")),
            sel: Math.min(SKILLS.length - 1, num(p.getDynamicProperty("abyss:sel"))),
            combo: 0,
            comboExpire: 0,
            step: 0,
            stepExpire: 0,
            cd: {},
            busyUntil: 0,
            ignitionUntil: 0,
            ignited: false,
            charge: null,
            lastUse: -100,
            wasSneaking: false,
            lastSwitch: 0,
            holding: false,
            lastCombat: -10000,
            introReady: 0,
            dirty: false,
        };
        players.set(p.id, st);
    }
    return st;
}
export function peekState(id) {
    return players.get(id);
}
export function dropState(id) {
    players.delete(id);
}

function num(v) {
    return typeof v === "number" && isFinite(v) ? Math.max(0, Math.floor(v)) : 0;
}

export function savePlayer(p, st) {
    if (!st.dirty) return;
    st.dirty = false;
    try {
        p.setDynamicProperty("abyss:inferno", st.inferno);
        p.setDynamicProperty("abyss:void", st.void);
        p.setDynamicProperty("abyss:sel", st.sel);
    } catch {
        // player left
    }
}

// ------------------------------------------------------------ gauges
export const inIgnition = (st) => now() < st.ignitionUntil;
export const gaugesFull = (st) => st.inferno >= GAUGE_MAX && st.void >= GAUGE_MAX;

const gaugeLocked = (st) => now() < (st.gaugeLockUntil || 0);

export function addInferno(p, st, n) {
    if (n <= 0 || gaugeLocked(st)) return;
    st.inferno = Math.min(GAUGE_MAX, st.inferno + n);
    st.dirty = true;
    checkIgnition(p, st);
}
export function addVoid(p, st, n) {
    if (n <= 0 || gaugeLocked(st)) return;
    st.void = Math.min(GAUGE_MAX, st.void + n);
    st.dirty = true;
    checkIgnition(p, st);
}
export function resetGauges(st) {
    st.inferno = 0;
    st.void = 0;
    st.ignited = false;
    st.dirty = true;
}

function checkIgnition(p, st) {
    if (st.ignited || !gaugesFull(st)) return;
    st.ignited = true;
    startIgnition(p, st);
}

/** ABYSS IGNITION: 10 s power state, triggered once each time both gauges fill up. */
function startIgnition(p, st) {
    st.ignitionUntil = now() + IGNITION.duration;
    const dim = p.dimension;
    const base = onGround(dim, p.location);
    const c = chest(p);
    fx(dim, "abyss:sigil", base, { radius: 3, life: 1.6 });
    fx(dim, "abyss:sigil_red", base, { radius: 2.2, life: 1.6 });
    fx(dim, "abyss:ground_shadow", base, { radius: 3.5, life: 1.8 });
    fx(dim, "abyss:explosion_flash", c, { radius: 2.5 });
    fx(dim, "abyss:explosion_black", c, { radius: 2.2 });
    fx(dim, "abyss:explosion_void", c, { radius: 2.2 });
    fx(dim, "abyss:ring_wave", base, { radius: 4.5, life: 0.5 });
    later(3, () => fx(dim, "abyss:ring_wave_red", base, { radius: 3.5, life: 0.45 }));
    let k = 0;
    repeat(2, 6, () => {
        for (const q of circle(base, 1.4 + k * 0.5, 6, k * 0.5)) {
            fx(dim, k % 2 ? "abyss:pillar_void" : "abyss:pillar", q, { height: 2.2 + k * 0.2 });
            fx(dim, "abyss:pillar_dark", q, { height: 2.2 });
        }
        k++;
    });
    sound(dim, "mob.enderdragon.growl", p.location, 0.7, 1.3);
    sound(dim, "beacon.power", p.location, 1, 0.6);
    sound(dim, "mob.blaze.shoot", p.location, 1, 0.5);
    shake(p, 0.35, 0.6);
    try {
        p.onScreenDisplay.setTitle("§l§5ABYSS §4IGNITION", {
            subtitle: "§7Damage +25%  Speed +15%  Burn +25%",
            fadeInDuration: 2,
            stayDuration: 30,
            fadeOutDuration: 10,
        });
    } catch {
        // ignore
    }
}

// ------------------------------------------------------------ combo
/** Damage multiplier from combo + ignition (additive). */
export function damageMult(st) {
    let m = 1;
    if (st.combo >= 10) m += 0.15;
    else if (st.combo >= 3) m += 0.05;
    if (inIgnition(st)) m += IGNITION.dmgBonus;
    return m;
}

/** Returns true when the combo just reached the maximum. */
export function bumpCombo(st) {
    const t = now();
    if (t > st.comboExpire) st.combo = 0;
    st.combo = Math.min(COMBO_MAX, st.combo + 1);
    st.comboExpire = t + COMBO_TIMEOUT;
    st.lastCombat = t;
    return st.combo === COMBO_MAX;
}

// ------------------------------------------------------------ cooldowns
export function cdLeft(st, key) {
    return Math.max(0, (st.cd[key] || 0) - now());
}
export function setCd(st, key, ticks) {
    st.cd[key] = now() + ticks;
}

// ------------------------------------------------------------ scoreboards
let objectives = null;
export function initScoreboards() {
    objectives = {};
    for (const [id, name] of SCOREBOARDS) {
        try {
            objectives[id] = world.scoreboard.getObjective(id) || world.scoreboard.addObjective(id, name);
        } catch {
            // ignore
        }
    }
}
export function setScore(id, entity, value) {
    if (!objectives) return;
    const o = objectives[id];
    if (!o) return;
    try {
        o.setScore(entity, Math.floor(value));
    } catch {
        // entity not a valid participant yet
    }
}
export function syncPlayerScores(p, st) {
    setScore("abyss_inferno", p, st.inferno);
    setScore("abyss_void", p, st.void);
    setScore("abyss_combo", p, st.combo);
    setScore("abyss_select", p, st.sel + 1);
    setScore("abyss_skill1", p, cdLeft(st, "rend"));
    setScore("abyss_skill2", p, cdLeft(st, "sun"));
    setScore("abyss_skill3", p, cdLeft(st, "flare"));
    setScore("abyss_skill4", p, cdLeft(st, "spear"));
}
