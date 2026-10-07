import { BURN, MARK, IGNITION, KILL_GAIN, KILL_GAIN_MARKED, COMBO_BURST } from "./config.js";
import {
    now, later, fx, fxDir, sound, shake, knock, effect, chest, eye, sub, norm, dist, add, v3,
    onGround, circle, rand,
} from "./util.js";
import {
    getState, peekState, damageMult, inIgnition, addInferno, addVoid, bumpCombo, setScore,
} from "./state.js";

export const isValid = (e) => {
    try {
        return !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
    } catch {
        return false;
    }
};

// ------------------------------------------------------------ targeting
export function validTarget(e, owner) {
    if (!isValid(e)) return false;
    try {
        if (owner && e.id === owner.id) return false;
        if (e.typeId.startsWith("abyss:")) return false;
        if (!e.getComponent("health")) return false;
        if (e.typeId === "minecraft:player") {
            const gm = String(e.getGameMode()).toLowerCase();
            if (gm === "creative" || gm === "spectator") return false;
        }
        const tame = e.getComponent("tameable");
        if (tame && tame.isTamed) return false;
    } catch {
        // components unavailable -> still a target
    }
    return true;
}

export function getTargets(dim, center, radius, owner) {
    let list = [];
    try {
        list = dim.getEntities({ location: center, maxDistance: radius, excludeFamilies: ["abyss_fx", "inanimate"] });
    } catch {
        return [];
    }
    return list.filter((e) => validTarget(e, owner));
}

// ------------------------------------------------------------ status table (marks + burn)
const status = new Map();
let phaseSeed = 0;

function ensure(e) {
    let s = status.get(e.id);
    if (!s) {
        s = { e, marks: 0, markUntil: 0, markOwner: null, burnUntil: 0, burnOwner: null, nextBurn: 0,
              breaking: false, lastLoc: e.location, phase: phaseSeed++ % 8, burnShown: false };
        status.set(e.id, s);
    }
    return s;
}
export function marksOf(e) {
    const s = status.get(e.id);
    return s ? s.marks : 0;
}

/**
 * Deal skill damage.
 *  o.kind: "void" | "fire"   (void gets +15% vs targets with >=3 marks)
 *  o.cause: damage cause (default entityAttack)
 *  o.from + o.kb (+o.up): knockback away from a point; o.dir + o.kb: knockback along a direction
 *  o.marks, o.burn, o.stagger: status effects; o.raw: ignore combo/ignition bonus; o.mult: extra multiplier
 *  o.noProc: no ignition proc (DoT / chain explosions)
 */
export function hit(owner, st, target, amount, o = {}) {
    if (!validTarget(target, owner)) return false;
    const s = status.get(target.id);
    let mult = st && !o.raw ? damageMult(st) : 1;
    if (o.kind === "void" && s && s.marks >= MARK.dominanceAt) mult += MARK.voidBonus;
    if (o.mult) mult *= o.mult;
    const dmg = Math.max(1, Math.round(amount * mult));
    const opts = isValid(owner) ? { cause: o.cause || "entityAttack", damagingEntity: owner } : { cause: o.cause || "entityAttack" };
    try {
        target.applyDamage(dmg, opts);
    } catch {
        return false;
    }
    if (o.kb) {
        if (o.dir) knock(target, o.dir.x, o.dir.z, o.kb, o.up ?? 0.3);
        else if (o.from) {
            const d = sub(target.location, o.from);
            knock(target, d.x, d.z, o.kb, o.up ?? 0.3);
        }
    }
    if (o.burn) addBurn(owner, target);
    if (o.marks) addMarks(owner, target, o.marks);
    if (o.stagger) stagger(target);
    if (st && !o.noProc && inIgnition(st)) {
        try {
            fx(target.dimension, "abyss:black_flame", chest(target));
        } catch {
            // dead
        }
        if (!o.marks && Math.random() < IGNITION.markChance) addMarks(owner, target, 1);
    }
    if (st) st.lastCombat = now();
    return true;
}

export function stagger(e) {
    effect(e, "slowness", 30, 3);
    effect(e, "weakness", 30, 1);
}

// ------------------------------------------------------------ void mark
export function addMarks(owner, target, n) {
    if (!isValid(target)) return;
    const s = ensure(target);
    s.marks = Math.min(MARK.max, s.marks + n);
    s.markUntil = now() + MARK.expire;
    if (owner) s.markOwner = owner;
    setScore("abyss_mark", target, s.marks);
    try {
        fx(target.dimension, "abyss:mark_rune", add(eye(target), v3(0, 0.75, 0)), { stack: s.marks });
    } catch {
        // dead
    }
    if (s.marks >= MARK.max && !s.breaking) {
        s.breaking = true;
        later(2, () => voidBreak(s.markOwner, target, s));
    }
}

/** VOID BREAK: 5 marks detonate. */
function voidBreak(owner, target, s) {
    s.marks = 0;
    s.breaking = false;
    let dim;
    let loc;
    try {
        dim = target.dimension;
        loc = target.location;
    } catch {
        loc = s.lastLoc;
        dim = isValid(owner) ? owner.dimension : null;
    }
    if (!dim || !loc) return;
    setScore("abyss_mark", target, 0);
    const st = isValid(owner) ? getState(owner) : null;
    const mult = st && inIgnition(st) ? 1 + IGNITION.breakBonus : 1;
    const ground = onGround(dim, loc);
    const mid = add(loc, v3(0, 1, 0));
    fx(dim, "abyss:explosion_flash", mid, { radius: 2.6 });
    fx(dim, "abyss:ring_shatter", ground, { radius: 4, life: 0.55 });
    fx(dim, "abyss:ring_wave", ground, { radius: 4.6, life: 0.45 });
    fx(dim, "abyss:ring_wave_dark", ground, { radius: 4.2, life: 0.6 });
    fx(dim, "abyss:explosion_void", mid, { radius: 2.2 });
    fx(dim, "abyss:explosion_black", mid, { radius: 1.8 });
    fx(dim, "abyss:shards", mid);
    fx(dim, "abyss:rift", ground);
    fx(dim, "abyss:rift_dark", ground);
    fx(dim, "abyss:crack", ground, { radius: 2.2, life: 1.6 });
    fx(dim, "abyss:crack_dark", ground, { radius: 2.2, life: 1.8 });
    for (const q of circle(ground, 2.6, 6, rand(0, 6))) fx(dim, "abyss:pillar_void", q, { height: 1.8 });
    sound(dim, "random.glass", loc, 1, 0.55);
    sound(dim, "mob.warden.sonic_boom", loc, 0.6, 1.3);
    sound(dim, "random.explode", loc, 0.7, 0.8);
    if (isValid(owner)) shake(owner, 0.25, 0.3);
    for (const e of getTargets(dim, loc, MARK.voidBreak.radius, owner)) {
        hit(owner, st, e, MARK.voidBreak.dmg, { kind: "void", from: loc, kb: 1.1, up: 0.45, stagger: true, mult,
                                               noProc: true });
    }
    if (st && isValid(owner)) {
        addVoid(owner, st, MARK.voidBreak.void);
        try {
            owner.onScreenDisplay.setActionBar("§l§5VOID BREAK!");
        } catch {
            // ignore
        }
    }
}

// ------------------------------------------------------------ burn
export function addBurn(owner, target, ticks = BURN.duration) {
    if (!isValid(target)) return;
    const s = ensure(target);
    const t = now();
    if (s.burnUntil <= t) s.nextBurn = t + BURN.every;
    s.burnUntil = Math.max(s.burnUntil, t + ticks);
    if (owner) s.burnOwner = owner;
    s.burnShown = true;
    setScore("abyss_burn", target, Math.ceil((s.burnUntil - t) / 20));
}

function burnTick(s) {
    const e = s.e;
    const owner = isValid(s.burnOwner) ? s.burnOwner : null;
    const st = owner ? peekState(owner.id) : null;
    const abyss = s.marks >= MARK.dominanceAt;
    let dmg = abyss ? BURN.abyssDmg : BURN.dmg;
    if (st && inIgnition(st)) dmg *= 1 + IGNITION.burnBonus;
    const dim = e.dimension;
    const c = chest(e);
    fx(dim, abyss ? "abyss:void_flame" : "abyss:crimson_flame", c);
    fx(dim, "abyss:black_flame", c);
    fx(dim, "abyss:dark_smoke", add(c, v3(0, 0.4, 0)));
    hit(owner, null, e, dmg, { cause: "magic", raw: true, noProc: true });
    if (st) addInferno(owner, st, BURN.inferno);
    if (Math.random() < BURN.blackFlameChance) {
        blackFlameExplosion(dim, owner, st, c, BURN.blackFlame.dmg, BURN.blackFlame.radius,
                            { raw: true, noProc: true, small: true });
    }
    if (abyss && Math.random() < BURN.voidExplosionChance) voidExplosion(dim, owner, c);
}

function voidExplosion(dim, owner, c) {
    fx(dim, "abyss:explosion_flash", c, { radius: 1.4 });
    fx(dim, "abyss:explosion_void", c, { radius: 1.3 });
    fx(dim, "abyss:shards", c);
    fx(dim, "abyss:ring_wave", onGround(dim, c), { radius: 2.5, life: 0.35 });
    sound(dim, "mob.wither.break_block", c, 0.35, 1.6);
    for (const e of getTargets(dim, c, BURN.voidExplosion.radius, owner)) {
        hit(owner, null, e, BURN.voidExplosion.dmg, { kind: "void", cause: "magic", raw: true, noProc: true });
    }
}

// ------------------------------------------------------------ black flame explosion (shared)
export function blackFlameExplosion(dim, owner, st, center, dmg, radius, o = {}) {
    const ground = onGround(dim, { x: center.x, y: center.y - 0.6, z: center.z });
    fx(dim, "abyss:explosion_flash", center, { radius: radius * 0.75 });
    fx(dim, "abyss:explosion_black", center, { radius: radius * 0.85 });
    fx(dim, "abyss:explosion_crimson", center, { radius: radius * 0.85 });
    fx(dim, "abyss:ring_wave_red", ground, { radius: radius + 0.5, life: 0.35 });
    if (!o.small) {
        fx(dim, "abyss:ring_wave_dark", ground, { radius: radius + 0.3, life: 0.55 });
        fx(dim, "abyss:flame_wave", ground, { radius });
        fx(dim, "abyss:flame_wave_dark", ground, { radius });
        fx(dim, "abyss:dark_smoke", center);
        fx(dim, "abyss:ember", center);
        fx(dim, "abyss:crack", ground, { radius: radius * 0.6, life: 1.2 });
        fx(dim, "abyss:crack_dark", ground, { radius: radius * 0.6, life: 1.4 });
        sound(dim, "random.explode", center, 0.8, 1.15);
        sound(dim, "mob.blaze.shoot", center, 1, 0.6);
    } else {
        sound(dim, "mob.blaze.shoot", center, 0.4, 1.4);
    }
    let count = 0;
    for (const e of getTargets(dim, center, radius, owner)) {
        if (o.exclude && o.exclude.has(e.id)) continue;
        if (hit(owner, st, e, dmg, { kind: "fire", from: center, kb: o.kb ?? 0.55, up: 0.3, burn: o.burn,
                                    marks: o.marks, raw: o.raw, noProc: o.noProc })) count++;
    }
    return count;
}

// ------------------------------------------------------------ combo
export function registerAttack(p, st) {
    if (bumpCombo(st)) later(1, () => comboBurst(p, st));
}

function comboBurst(p, st) {
    if (!isValid(p)) return;
    const c = chest(p);
    blackFlameExplosion(p.dimension, p, st, c, COMBO_BURST.dmg, COMBO_BURST.radius, { burn: true, kb: 1 });
    fx(p.dimension, "abyss:sigil_red", onGround(p.dimension, p.location), { radius: 3, life: 0.9 });
    shake(p, 0.3, 0.35);
    st.combo = COMBO_BURST.fallbackTo;
    try {
        p.onScreenDisplay.setActionBar("§l§cCOMBO 15 §4- BLACK FLAME EXPLOSION");
    } catch {
        // ignore
    }
}

// ------------------------------------------------------------ per tick
export function tickStatus() {
    const t = now();
    for (const [id, s] of status) {
        const e = s.e;
        if (!isValid(e)) {
            status.delete(id);
            continue;
        }
        try {
            s.lastLoc = e.location;
            if (s.marks > 0 && t > s.markUntil && !s.breaking) {
                s.marks = 0;
                setScore("abyss_mark", e, 0);
            }
            const burning = s.burnUntil > t;
            if (burning && t >= s.nextBurn) {
                s.nextBurn = t + BURN.every;
                burnTick(s);
            } else if (burning && (t + s.phase) % 5 === 0) {
                fx(e.dimension, "abyss:black_flame", chest(e));
            }
            if (!burning && s.burnShown) {
                s.burnShown = false;
                setScore("abyss_burn", e, 0);
            }
            if (s.marks > 0 && (t + s.phase) % 8 === 0) {
                fx(e.dimension, "abyss:mark_rune", add(eye(e), v3(0, 0.75, 0)), { stack: s.marks });
                if (s.marks >= MARK.dominanceAt) {
                    // VOID DOMINANCE: slowed + void aura
                    effect(e, "slowness", 20, 0);
                    fx(e.dimension, "abyss:void_mote", chest(e));
                }
            }
            if (s.marks === 0 && !burning && !s.breaking) status.delete(id);
        } catch {
            status.delete(id);
        }
    }
}

// ------------------------------------------------------------ kills (Abyss Consumption)
export function onDeath(dead, source) {
    const s = status.get(dead.id);
    status.delete(dead.id);
    let killer = source && source.damagingEntity;
    if (!killer || killer.typeId !== "minecraft:player") killer = s ? s.burnOwner || s.markOwner : null;
    if (!isValid(killer)) return;
    const st = peekState(killer.id);
    if (!st) return;
    const marked = !!s && s.marks > 0;
    const gain = marked ? KILL_GAIN_MARKED : KILL_GAIN;
    addInferno(killer, st, gain.inferno);
    addVoid(killer, st, gain.void);
    let from;
    try {
        from = chest(dead);
    } catch {
        from = s ? add(s.lastLoc, v3(0, 1, 0)) : null;
    }
    if (!from) return;
    const dim = killer.dimension;
    const to = chest(killer);
    const d = dist(from, to);
    if (d < 40) {
        fxDir(dim, "abyss:soul_stream", from, norm(sub(to, from)), { dist: d });
        fx(dim, "abyss:void_flame", from);
        fx(dim, "abyss:dark_smoke", from);
        later(10, () => isValid(killer) && fx(dim, marked ? "abyss:void_mote" : "abyss:ember", chest(killer)));
        sound(dim, "mob.endermen.portal", from, 0.5, 0.6);
    }
}
