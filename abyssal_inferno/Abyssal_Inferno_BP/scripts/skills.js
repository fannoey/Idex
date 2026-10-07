import {
    SKILLS, COMBO_HITS, COMBO_STEP_WINDOW, CHARGE, VOID_ZONE, REND, SUN, FLARE, SPEAR, ULT, INTRO, OUTRO,
} from "./config.js";
import {
    now, later, repeat, fx, fxDir, sound, shake, playAnim, knock, effect, cmd, add, sub, mul, v3, norm, dist, hdist,
    flatForward, flatRight, eye, chest, onGround, isSolid, circle, rand,
} from "./util.js";
import {
    getState, addInferno, addVoid, resetGauges, gaugesFull, cdLeft, setCd,
} from "./state.js";
import {
    isValid, hit, getTargets, addMarks, addBurn, marksOf, blackFlameExplosion, registerAttack,
} from "./combat.js";

// ------------------------------------------------------------ helpers
function spawnFx(dim, id, loc) {
    try {
        return dim.spawnEntity(id, loc);
    } catch {
        return null;
    }
}
function removeFx(e) {
    if (!isValid(e)) return;
    try {
        e.remove();
    } catch {
        try {
            e.triggerEvent("abyss:despawn");
        } catch {
            // already gone
        }
    }
}
export function flash(st, text, ticks = 40) {
    st.msg = text;
    st.msgUntil = now() + ticks;
}
function deny(p, st, text) {
    flash(st, text, 30);
    try {
        p.playSound("note.bass", { volume: 0.6, pitch: 0.5 });
    } catch {
        // ignore
    }
}
function title(p, main, subtitle = "") {
    try {
        p.onScreenDisplay.setTitle(main, { subtitle, fadeInDuration: 2, stayDuration: 30, fadeOutDuration: 10 });
    } catch {
        // ignore
    }
}
function pillarRing(dim, center, radius, n, height, ids, phase = 0) {
    let k = 0;
    for (const q of circle(center, radius, n, phase)) {
        const g = onGround(dim, q);
        fx(dim, ids[k % ids.length], g, { height });
        k++;
    }
}

// ============================================================ BASIC: BLACK FLAME COMBO
const SLASH_ANGLES = [40, -140, 90, -30, 180];

export function castBasic(p, st, target) {
    const t = now();
    st.step = t <= st.stepExpire ? (st.step % 5) + 1 : 1;
    st.stepExpire = t + COMBO_STEP_WINDOW;
    const step = st.step;
    const H = COMBO_HITS[step - 1];
    const dim = p.dimension;
    const c = chest(target);
    const f = flatForward(p);

    playAnim(p, `animation.abyss.combo_${step}`, 0.15);
    // vanilla swing already dealt the item damage; this tops it up to the combo value
    hit(p, st, target, H.dmg, { kind: "fire" });
    addInferno(p, st, H.inferno);
    registerAttack(p, st);

    const slashAt = add(c, mul(f, -0.4));
    const slash = (size, angle) => {
        fx(dim, "abyss:slash_dark", slashAt, { size, angle });
        fx(dim, "abyss:slash", slashAt, { size, angle });
    };
    fx(dim, "abyss:hit_spark", c);
    fx(dim, "abyss:hit_flash", c);
    sound(dim, "mob.blaze.shoot", c, 0.35, 1.5 + step * 0.08);
    sound(dim, "fire.ignite", c, 0.7, 1.2);

    switch (step) {
        case 1:
            slash(2.2, SLASH_ANGLES[0]);
            fx(dim, "abyss:black_flame", c);
            break;
        case 2:
            slash(2.3, SLASH_ANGLES[1]);
            fx(dim, "abyss:crimson_flame", c);
            fx(dim, "abyss:black_flame", c);
            break;
        case 3: {
            slash(2.4, SLASH_ANGLES[2]);
            // short flame wave along the facing direction
            const start = p.location;
            const hitIds = new Set([target.id]);
            for (let i = 0; i < 8; i++) {
                later(Math.floor(i / 2), () => {
                    const q = add(start, mul(f, 1 + i * 0.5));
                    const g = onGround(dim, q);
                    const at = add(g, v3(0, 0.3, 0));
                    fx(dim, "abyss:crimson_flame", at);
                    fx(dim, "abyss:black_flame", at);
                    if (i % 3 === 0) fx(dim, "abyss:ember", at);
                    for (const e of getTargets(dim, add(g, v3(0, 1, 0)), 1.3, p)) {
                        if (hitIds.has(e.id)) continue;
                        hitIds.add(e.id);
                        hit(p, st, e, H.wave.dmg, { kind: "fire", dir: f, kb: 0.5, up: 0.25 });
                    }
                });
            }
            later(4, () => fx(dim, "abyss:ring_wave_red", onGround(dim, add(start, mul(f, 4))), { radius: 1.5, life: 0.3 }));
            break;
        }
        case 4:
            slash(2.8, SLASH_ANGLES[3]);
            fx(dim, "abyss:void_flame", c);
            fx(dim, "abyss:void_mote", c);
            if (Math.random() < H.markChance) {
                addMarks(p, target, 1);
                fx(dim, "abyss:shards", c);
            }
            break;
        case 5:
            // the slam lands at 0.32 s in the animation
            later(6, () => {
                if (!isValid(p)) return;
                const at = isValid(target) ? chest(target) : add(p.location, add(mul(f, 1.5), v3(0, 1, 0)));
                slash(3.2, SLASH_ANGLES[4]);
                fx(dim, "abyss:sigil_red", onGround(dim, at), { radius: 2.4, life: 0.8 });
                pillarRing(dim, at, 1.6, 6, 2.2, ["abyss:pillar", "abyss:pillar_dark"], rand(0, 6));
                blackFlameExplosion(dim, p, st, at, H.blast.dmg, H.blast.radius, { burn: true, kb: 0.8 });
                // the primary target is still in its hurt cooldown, so give it the burn directly
                addBurn(p, target);
                shake(p, 0.3, 0.25);
            });
            break;
        default:
            break;
    }
}

// ============================================================ USE (right click)
export function handleUse(p) {
    const st = getState(p);
    const t = now();
    const tap = t - st.lastUse > 8;
    st.lastUse = t;
    const sk = SKILLS[st.sel];

    if (sk.key === "charge") {
        useCharge(p, st, t);
        return;
    }
    if (t < st.busyUntil || st.charge) return;
    if (sk.key === "ult") {
        if (!gaugesFull(st)) {
            if (tap) deny(p, st, "§c! ต้องการ Inferno 100 และ Void 100");
            return;
        }
        castUltimate(p, st);
        return;
    }
    const left = cdLeft(st, sk.key);
    if (left > 0) {
        if (tap) deny(p, st, `§7${sk.name} §cคูลดาวน์ ${(left / 20).toFixed(1)}s`);
        return;
    }
    setCd(st, sk.key, sk.cd);
    st.lastCombat = t;
    CASTERS[sk.key](p, st);
}

// ============================================================ SKILL 1: ABYSS REND
function castRend(p, st) {
    const dim = p.dimension;
    const f = flatForward(p);
    st.busyUntil = now() + 10;
    playAnim(p, "animation.abyss.rend", 0.2);
    fx(dim, "abyss:charge_gather", add(p.location, v3(0, 2.7, 0)));
    fx(dim, "abyss:void_flame", add(eye(p), v3(0, 1.1, 0)));
    sound(dim, "mob.evocation_illager.cast_spell", p.location, 0.8, 0.7);

    later(5, () => {
        if (!isValid(p)) return;
        const start = p.location;
        sound(dim, "mob.wither.shoot", start, 0.9, 0.55);
        sound(dim, "random.glass", start, 0.8, 0.5);
        sound(dim, "mob.warden.sonic_boom", start, 0.35, 1.5);
        shake(p, 0.3, 0.35);
        fx(dim, "abyss:explosion_flash", add(start, add(mul(f, 1.2), v3(0, 0.6, 0))), { radius: 1.6 });

        for (let i = 0; i < 16; i++) {
            later(Math.floor(i / 4), () => {
                const d = 0.6 + i * 0.5;
                const g = onGround(dim, add(start, mul(f, d)));
                if (i % 2 === 0) {
                    fx(dim, "abyss:rift", g);
                    fx(dim, "abyss:rift_dark", g);
                    fx(dim, "abyss:crack", g, { radius: 0.9 + Math.random() * 0.5, life: 1.6 });
                    fx(dim, "abyss:crack_dark", g, { radius: 1.0 + Math.random() * 0.5, life: 1.8 });
                } else {
                    fx(dim, "abyss:void_flame", add(g, v3(0, 0.3, 0)));
                }
                fx(dim, "abyss:black_flame", add(g, v3(0, 0.3, 0)));
                if (i % 3 === 0) fx(dim, "abyss:dark_smoke", add(g, v3(0, 0.5, 0)));
                if (i % 4 === 3) fx(dim, "abyss:shards", add(g, v3(0, 0.4, 0)));
            });
        }

        let any = false;
        for (const e of getTargets(dim, add(start, mul(f, REND.range / 2)), REND.range / 2 + 2.5, p)) {
            const rel = sub(e.location, start);
            const along = rel.x * f.x + rel.z * f.z;
            const perp = Math.abs(rel.x * f.z - rel.z * f.x);
            if (along < -0.5 || along > REND.range + 0.5 || perp > REND.width || Math.abs(rel.y) > 3) continue;
            any = true;
            later(Math.max(0, Math.floor(along / 2)), () => {
                if (hit(p, st, e, REND.dmg, { kind: "void", dir: f, kb: 1.2, up: 0.45, marks: REND.marks })) {
                    fx(dim, "abyss:hit_spark", chest(e));
                    fx(dim, "abyss:void_flame", chest(e));
                }
            });
        }
        if (any) {
            addVoid(p, st, REND.void);
            registerAttack(p, st);
        }
    });
}

// ============================================================ SKILL 2: BLACK SUN
function castSun(p, st) {
    const dim = p.dimension;
    const f = flatForward(p);
    const o = p.location;
    let center = add(o, v3(f.x * 1.5, SUN.height, f.z * 1.5));
    for (let d = SUN.distance; d >= 1.5; d -= 0.5) {
        const c = add(o, v3(f.x * d, SUN.height, f.z * d));
        if (!isSolid(dim, c)) {
            center = c;
            break;
        }
    }
    st.busyUntil = now() + 8;
    playAnim(p, "animation.abyss.black_sun", 0.25);
    fx(dim, "abyss:implode", center, { radius: 2.5 });
    sound(dim, "mob.evocation_illager.prepare_summon", o, 0.8, 0.6);

    later(6, () => {
        const ent = spawnFx(dim, "abyss:black_sun", center);
        for (const id of ["sun_corona_void", "sun_corona", "sun_core", "sun_ring_a", "sun_ring_b", "sun_ring_c",
                          "sun_rim_flames", "sun_inflow"]) {
            fx(dim, `abyss:${id}`, center);
        }
        fx(dim, "abyss:explosion_flash", center, { radius: 1.8 });
        const ground = onGround(dim, sub(center, v3(0, 1.2, 0)));
        fx(dim, "abyss:ground_shadow", ground, { radius: 3.5, life: 5.2 });
        fx(dim, "abyss:sigil_red", ground, { radius: 2.6, life: 5.2 });
        sound(dim, "mob.wither.shoot", center, 0.8, 0.45);
        sound(dim, "beacon.activate", center, 1, 0.5);

        repeat(SUN.every, SUN.duration / SUN.every, (i) => {
            fx(dim, "abyss:ring_contract", center, { radius: SUN.radius, life: 0.45 });
            fx(dim, "abyss:suction", center, { radius: SUN.radius });
            if (i % 2 === 0) sound(dim, "beacon.ambient", center, 1, 0.5);
            let any = false;
            for (const e of getTargets(dim, center, SUN.radius, p)) {
                const d = sub(center, e.location);
                const h = Math.hypot(d.x, d.z);
                if (h > 0.4) knock(e, d.x, d.z, Math.min(0.55, 0.12 + h * 0.1), d.y > 0.5 ? 0.14 : 0.02);
                if (hit(p, st, e, SUN.dmg, { kind: "void", marks: SUN.marks })) {
                    any = true;
                    fx(dim, "abyss:void_flame", chest(e));
                }
            }
            if (any && isValid(p)) registerAttack(p, st);
        }, () => {
            // VOID COLLAPSE
            fx(dim, "abyss:implode", center, { radius: 3.2 });
            sound(dim, "mob.warden.sonic_charge", center, 0.8, 1.6);
            later(2, () => {
                fx(dim, "abyss:explosion_flash", center, { radius: 4.5 });
                fx(dim, "abyss:explosion_void", center, { radius: 4 });
                fx(dim, "abyss:explosion_black", center, { radius: 3.6 });
                fx(dim, "abyss:explosion_crimson", center, { radius: 3 });
                fx(dim, "abyss:shards", center);
                fx(dim, "abyss:ring_shatter", ground, { radius: 6, life: 0.6 });
                fx(dim, "abyss:ring_wave", ground, { radius: 6.5, life: 0.5 });
                later(2, () => fx(dim, "abyss:ring_wave_dark", ground, { radius: 6, life: 0.7 }));
                fx(dim, "abyss:crack", ground, { radius: 2.8, life: 2 });
                fx(dim, "abyss:crack_dark", ground, { radius: 2.8, life: 2.2 });
                pillarRing(dim, ground, 3, 8, 3, ["abyss:pillar_void", "abyss:pillar_dark"]);
                later(2, () => pillarRing(dim, ground, 5.5, 12, 2.4, ["abyss:pillar", "abyss:pillar_void"], 0.3));
                sound(dim, "random.explode", center, 1, 0.6);
                sound(dim, "mob.warden.sonic_boom", center, 1, 0.8);
                if (isValid(p)) shake(p, 0.45, 0.5);
                let any = false;
                for (const e of getTargets(dim, center, SUN.collapse.radius, p)) {
                    if (hit(p, st, e, SUN.collapse.dmg, { kind: "void", from: center, kb: 1.6, up: 0.55 })) any = true;
                }
                if (isValid(p)) {
                    addVoid(p, st, SUN.void);
                    if (any) registerAttack(p, st);
                }
                removeFx(ent);
            });
        });
    });
}

// ============================================================ SKILL 3: ABYSSAL FLARE
function castFlare(p, st) {
    const dim = p.dimension;
    st.busyUntil = now() + 10;
    playAnim(p, "animation.abyss.flare", 0.2);
    fx(dim, "abyss:implode", chest(p), { radius: 2.2 });
    fx(dim, "abyss:charge_gather", chest(p));
    sound(dim, "mob.blaze.breathe", p.location, 0.9, 0.6);

    later(8, () => {
        if (!isValid(p)) return;
        const c = chest(p);
        const g = onGround(dim, p.location);
        fx(dim, "abyss:sigil_red", g, { radius: FLARE.radius, life: 0.9 });
        fx(dim, "abyss:ground_shadow", g, { radius: FLARE.radius, life: 1.1 });
        fx(dim, "abyss:explosion_flash", c, { radius: 3 });
        fx(dim, "abyss:explosion_black", c, { radius: 4 });
        fx(dim, "abyss:explosion_crimson", c, { radius: 4 });
        fx(dim, "abyss:flame_wave", g, { radius: FLARE.radius });
        fx(dim, "abyss:flame_wave_dark", g, { radius: FLARE.radius });
        fx(dim, "abyss:ring_wave_red", g, { radius: FLARE.radius + 0.5, life: 0.4 });
        later(2, () => fx(dim, "abyss:ring_wave", g, { radius: FLARE.radius, life: 0.45 }));
        later(3, () => fx(dim, "abyss:ring_wave_dark", g, { radius: FLARE.radius, life: 0.6 }));
        for (let k = 0; k < 3; k++) {
            later(k * 2, () => pillarRing(dim, g, 1.8 + k * 1.4, 6 + k * 3, 2.6 - k * 0.3,
                                          ["abyss:pillar", "abyss:pillar_dark"], k * 0.4));
        }
        fx(dim, "abyss:ember", c);
        fx(dim, "abyss:dark_smoke", c);
        sound(dim, "random.explode", c, 0.9, 1.0);
        sound(dim, "mob.blaze.shoot", c, 1, 0.5);
        sound(dim, "fire.ignite", c, 1, 0.6);
        shake(p, 0.35, 0.35);
        let any = false;
        for (const e of getTargets(dim, c, FLARE.radius, p)) {
            if (hit(p, st, e, FLARE.dmg, { kind: "fire", from: c, kb: 0.9, up: 0.4, burn: true, marks: FLARE.marks })) {
                any = true;
            }
        }
        if (any) {
            addInferno(p, st, FLARE.inferno);
            addVoid(p, st, FLARE.void);
            registerAttack(p, st);
        }
    });
}

// ============================================================ SKILL 4: VOID SPEAR
function castSpear(p, st) {
    const dim = p.dimension;
    st.busyUntil = now() + 10;
    playAnim(p, "animation.abyss.void_spear", 0.2);
    sound(dim, "mob.evocation_illager.cast_spell", p.location, 0.7, 1.2);
    const handPos = () => add(eye(p), add(mul(flatRight(p), 0.45), v3(0, 0.55, 0)));

    repeat(1, 8, (i) => {
        if (!isValid(p)) return false;
        const hand = handPos();
        const dir = p.getViewDirection();
        fxDir(dim, "abyss:spear_head", hand, dir);
        fxDir(dim, "abyss:spear_dark", hand, dir);
        if (i % 3 === 0) fx(dim, "abyss:implode", hand, { radius: 1.2 });
        return true;
    }, () => {
        if (!isValid(p)) return;
        const dir = p.getViewDirection();
        let pos = add(eye(p), mul(dir, 0.8));
        sound(dim, "item.trident.throw", pos, 1, 0.6);
        sound(dim, "mob.wither.shoot", pos, 0.5, 1.4);
        const hitIds = new Set();
        let any = false;
        const step = SPEAR.speed / 4;
        repeat(1, Math.ceil(SPEAR.range / SPEAR.speed), () => {
            let blocked = false;
            for (let s = 0; s < 4; s++) {
                const np = add(pos, mul(dir, step));
                if (isSolid(dim, np)) {
                    blocked = true;
                    break;
                }
                pos = np;
                fxDir(dim, "abyss:spear_head", pos, dir);
                if (s % 2 === 0) fxDir(dim, "abyss:spear_dark", pos, dir);
                fxDir(dim, "abyss:spear_trail", pos, dir);
                if (s === 0) fx(dim, "abyss:void_mote", pos);
            }
            for (const e of getTargets(dim, pos, SPEAR.speed + 1.5, p)) {
                if (hitIds.has(e.id)) continue;
                const c = chest(e);
                const back = sub(pos, mul(dir, SPEAR.speed / 2));
                if (dist(c, pos) > SPEAR.hitRadius + 0.6 && dist(c, back) > SPEAR.hitRadius + 0.6 &&
                    dist(c, sub(pos, mul(dir, SPEAR.speed))) > SPEAR.hitRadius + 0.6) continue;
                hitIds.add(e.id);
                const bonus = marksOf(e) > 0 ? SPEAR.markedBonus : 0;
                if (hit(p, st, e, SPEAR.dmg + bonus, { kind: "void", dir, kb: 1.3, up: 0.35, marks: SPEAR.marks })) {
                    any = true;
                    fx(dim, "abyss:hit_spark", c);
                    fx(dim, "abyss:hit_flash", c);
                    fx(dim, "abyss:explosion_void", c, { radius: 1 });
                    sound(dim, "item.trident.hit", c, 1, 0.6);
                }
            }
            return !blocked;
        }, () => {
            fx(dim, "abyss:explosion_flash", pos, { radius: 1.6 });
            fx(dim, "abyss:explosion_void", pos, { radius: 1.6 });
            fx(dim, "abyss:explosion_black", pos, { radius: 1.2 });
            fx(dim, "abyss:shards", pos);
            fx(dim, "abyss:ring_wave", onGround(dim, pos), { radius: 2.2, life: 0.35 });
            sound(dim, "random.explode", pos, 0.5, 1.4);
            if (any && isValid(p)) {
                addVoid(p, st, SPEAR.void);
                registerAttack(p, st);
            }
        });
    });
}

// ============================================================ CHARGED: VOID COMBUSTION
function useCharge(p, st, t) {
    if (st.charge) {
        st.charge.last = t;
        return;
    }
    if (t < st.busyUntil || cdLeft(st, "charge") > 0) return;
    st.charge = { start: t, last: t, full: false };
    playAnim(p, "animation.abyss.charge", 0.15);
    sound(p.dimension, "respawn_anchor.charge", p.location, 0.8, 0.6);
}

export function tickCharge(p, st) {
    const c = st.charge;
    const t = now();
    const age = t - c.start;
    const lvl = Math.min(1, age / CHARGE.fullTicks);
    const dim = p.dimension;
    const base = p.location;
    const held = t - c.last <= CHARGE.holdGap;

    // black flames spiral around the body, getting denser and tighter with charge
    const rad = 1.35 - 0.45 * lvl;
    const perArm = 1 + Math.floor(lvl * 2);
    if (t % 2 === 0) {
        for (let k = 0; k < 3; k++) {
            for (let j = 0; j < perArm; j++) {
                const ang = t * 0.35 + k * 2.094 - j * 0.35;
                const h = ((t * 0.06 + k / 3 + j * 0.08) % 1) * 2.0;
                const q = { x: base.x + Math.cos(ang) * rad, y: base.y + 0.15 + h, z: base.z + Math.sin(ang) * rad };
                fx(dim, "abyss:black_flame", q);
                if (lvl > 0.4) fx(dim, lvl >= 1 ? "abyss:void_flame" : "abyss:crimson_flame", q);
            }
        }
    }
    if (t % 4 === 0) fx(dim, "abyss:charge_gather", chest(p));
    if (t % 6 === 0) fx(dim, "abyss:ember", chest(p));
    if (!c.full && lvl >= 1) {
        c.full = true;
        const g = onGround(dim, base);
        fx(dim, "abyss:ring_wave", g, { radius: 1.8, life: 0.35 });
        fx(dim, "abyss:hit_flash", chest(p));
        fx(dim, "abyss:sigil", g, { radius: 2, life: 1.05 });
        sound(dim, "beacon.activate", base, 1, 1.6);
        flash(st, "§l§9FULL CHARGE §7- ปล่อยคลิกขวาเพื่อระเบิด", 30);
    } else if (c.full && (t - c.start) % 20 === 0) {
        fx(dim, "abyss:sigil", onGround(dim, base), { radius: 2, life: 1.05 });
    }
    if (!held || age > CHARGE.maxHold) releaseCharge(p, st, c.full);
}

export function cancelCharge(p, st) {
    if (!st.charge) return;
    st.charge = null;
    playAnim(p, "animation.abyss.none", 0.2);
}

function releaseCharge(p, st, full) {
    st.charge = null;
    setCd(st, "charge", SKILLS[4].cd);
    const P = full ? CHARGE.full : CHARGE.normal;
    const dim = p.dimension;
    const c = chest(p);
    const g = onGround(dim, p.location);
    playAnim(p, "animation.abyss.charge_release", 0.2);
    fx(dim, "abyss:explosion_flash", c, { radius: P.radius * 0.8 });
    fx(dim, "abyss:explosion_black", c, { radius: P.radius * 0.85 });
    fx(dim, full ? "abyss:explosion_void" : "abyss:explosion_crimson", c, { radius: P.radius * 0.85 });
    fx(dim, "abyss:ring_wave", g, { radius: P.radius + 0.5, life: 0.4 });
    fx(dim, "abyss:ring_wave_dark", g, { radius: P.radius, life: 0.55 });
    fx(dim, full ? "abyss:flame_wave_void" : "abyss:flame_wave", g, { radius: P.radius });
    fx(dim, "abyss:flame_wave_dark", g, { radius: P.radius });
    sound(dim, "random.explode", c, 0.8, full ? 0.7 : 1.1);
    if (full) {
        fx(dim, "abyss:shards", c);
        fx(dim, "abyss:ring_shatter", g, { radius: P.radius, life: 0.5 });
        pillarRing(dim, g, 2.5, 8, 2.6, ["abyss:pillar_void", "abyss:pillar_dark"]);
        sound(dim, "mob.warden.sonic_boom", c, 0.7, 1.1);
    }
    shake(p, full ? 0.45 : 0.25, 0.35);
    let any = false;
    for (const e of getTargets(dim, c, P.radius, p)) {
        if (hit(p, st, e, P.dmg, { kind: "void", from: c, kb: full ? 1.2 : 0.8, up: 0.35, marks: full ? P.marks : 0 })) {
            any = true;
        }
    }
    if (any) registerAttack(p, st);
    if (full) {
        addVoid(p, st, P.void);
        spawnVoidZone(p, st, g);
    }
}

function spawnVoidZone(p, st, ground) {
    const dim = p.dimension;
    const ent = spawnFx(dim, "abyss:void_zone", ground);
    const life = VOID_ZONE.duration / 20;
    fx(dim, "abyss:sigil", ground, { radius: VOID_ZONE.radius, life });
    fx(dim, "abyss:ground_shadow", ground, { radius: VOID_ZONE.radius, life: life + 0.1 });
    fx(dim, "abyss:zone_mist", ground, { radius: VOID_ZONE.radius, life });
    fx(dim, "abyss:zone_motes", ground, { radius: VOID_ZONE.radius, life });
    const mid = add(ground, v3(0, 1, 0));
    repeat(VOID_ZONE.every, VOID_ZONE.duration / VOID_ZONE.every, (i) => {
        if (i % 2 === 0) fx(dim, "abyss:rune_float", ground, { radius: VOID_ZONE.radius * 0.7 });
        fx(dim, "abyss:ring_contract", ground, { radius: VOID_ZONE.radius, life: 0.45 });
        for (const e of getTargets(dim, mid, VOID_ZONE.radius + 1, p)) {
            if (hdist(e.location, ground) > VOID_ZONE.radius || Math.abs(e.location.y - ground.y) > 3) continue;
            if (hit(p, st, e, VOID_ZONE.dmg, { kind: "void", cause: "magic", noProc: true })) {
                fx(dim, "abyss:void_flame", chest(e));
                if (Math.random() < VOID_ZONE.markChance) addMarks(p, e, 1);
            }
        }
    }, () => {
        fx(dim, "abyss:ring_wave", ground, { radius: VOID_ZONE.radius, life: 0.35 });
        removeFx(ent);
    });
}

// ============================================================ ULTIMATE: END OF ALL FLAMES
function castUltimate(p, st) {
    const dim = p.dimension;
    const ground = onGround(dim, p.location);
    let core = add(ground, v3(0, ULT.height, 0));
    for (let h = ULT.height; h >= 3; h -= 0.5) {
        const q = add(ground, v3(0, h, 0));
        if (!isSolid(dim, q)) {
            core = q;
            break;
        }
    }
    resetGauges(st);
    // the ultimate's own kills must not refill the gauges it just spent
    st.gaugeLockUntil = now() + ULT.blastAt + 20;
    st.busyUntil = now() + ULT.blastAt + 8;
    effect(p, "resistance", ULT.blastAt + 30, 3);
    playAnim(p, "animation.abyss.ultimate", 0.3);
    title(p, "§l§6END OF ALL FLAMES", "§5The abyss devours everything");

    // PHASE 1 - Void Core
    const ent = spawnFx(dim, "abyss:void_core", core);
    for (const id of ["core_halo", "core_orb", "core_ring_a", "core_ring_b", "core_ring_c", "core_lightning",
                      "core_inflow"]) {
        fx(dim, `abyss:${id}`, core);
    }
    fx(dim, "abyss:explosion_flash", core, { radius: 2.5 });
    fx(dim, "abyss:sigil", ground, { radius: ULT.radius, life: 4 });
    fx(dim, "abyss:sigil_red", ground, { radius: ULT.radius * 0.65, life: 4 });
    fx(dim, "abyss:ground_shadow", ground, { radius: ULT.radius + 1, life: 4.2 });
    fx(dim, "abyss:ground_shadow", ground, { radius: ULT.radius * 0.6, life: 4.2 });
    for (let h = 0.5; h < core.y - ground.y; h += 0.6) {
        fx(dim, "abyss:void_flame", add(ground, v3(0, h, 0)));
    }
    sound(dim, "mob.enderdragon.growl", core, 0.9, 0.6);
    sound(dim, "beacon.activate", core, 1, 0.4);
    sound(dim, "mob.evocation_illager.cast_spell", ground, 1, 0.6);
    shake(p, 0.2, 0.6);

    // PHASE 2 + 3 - pull everything into the core, then collapse
    for (let t = ULT.pullStart; t < ULT.blastAt; t += 5) {
        const tt = t;
        later(tt, () => {
            const collapsing = tt >= ULT.collapseAt;
            const strength = collapsing ? 0.55 : 0.35;
            for (const e of getTargets(dim, add(ground, v3(0, 2, 0)), ULT.radius + 1, p)) {
                const d = sub(core, e.location);
                const h = Math.hypot(d.x, d.z);
                if (h > 0.5) knock(e, d.x, d.z, Math.min(strength, 0.1 + h * 0.06), d.y > 1 ? 0.22 : 0.04);
                fx(dim, "abyss:void_mote", chest(e));
            }
            if (tt % 10 === 0) {
                fx(dim, "abyss:ring_contract", ground, { radius: ULT.radius, life: 0.5 });
                fx(dim, "abyss:rune_float", ground, { radius: ULT.radius * 0.6 });
                sound(dim, "beacon.ambient", core, 1, 0.4);
            }
            if (collapsing) {
                fx(dim, "abyss:implode", core, { radius: 4 });
                if (tt % 10 === 0) sound(dim, "mob.warden.sonic_charge", core, 1, 0.7);
                if (isValid(p)) shake(p, 0.15, 0.3);
            }
            if (tt === ULT.collapseAt) {
                sound(dim, "respawn_anchor.deplete", core, 1, 0.5);
                sound(dim, "beacon.deactivate", core, 1, 0.5);
                if (isValid(p)) flash(st, "§l§5VOID CORE COLLAPSING...", 25);
            }
        });
    }
    later(ULT.blastAt - 4, () => isValid(p) && cmd(p, "camera @s fade time 0.1 0.15 0.35 color 18 0 28"));

    // PHASE 4 - the big one
    later(ULT.blastAt, () => {
        fx(dim, "abyss:explosion_flash", core, { radius: 8 });
        fx(dim, "abyss:explosion_flash", add(ground, v3(0, 1, 0)), { radius: 6 });
        fx(dim, "abyss:explosion_void", core, { radius: 6 });
        fx(dim, "abyss:explosion_black", core, { radius: 6 });
        fx(dim, "abyss:explosion_crimson", add(ground, v3(0, 1, 0)), { radius: 5 });
        fx(dim, "abyss:explosion_black", add(ground, v3(0, 1, 0)), { radius: 5 });
        fx(dim, "abyss:shards", core);
        fx(dim, "abyss:shards", add(ground, v3(0, 1, 0)));
        fx(dim, "abyss:ring_wave", ground, { radius: ULT.radius, life: 0.6 });
        fx(dim, "abyss:ring_shatter", ground, { radius: ULT.radius, life: 0.7 });
        later(2, () => fx(dim, "abyss:ring_wave_red", ground, { radius: ULT.radius * 0.85, life: 0.6 }));
        later(4, () => fx(dim, "abyss:ring_wave_dark", ground, { radius: ULT.radius, life: 0.9 }));
        fx(dim, "abyss:flame_wave", ground, { radius: ULT.radius });
        fx(dim, "abyss:flame_wave_dark", ground, { radius: ULT.radius });
        fx(dim, "abyss:flame_wave_void", ground, { radius: ULT.radius * 0.8 });
        for (let k = 0; k < 10; k++) {
            const a = Math.random() * Math.PI * 2;
            const r = 1 + Math.random() * (ULT.radius - 2);
            const g = onGround(dim, add(ground, v3(Math.cos(a) * r, 0, Math.sin(a) * r)));
            const size = 1.4 + Math.random();
            fx(dim, "abyss:crack", g, { radius: size, life: 2.5 });
            fx(dim, "abyss:crack_dark", g, { radius: size, life: 2.8 });
        }
        pillarRing(dim, ground, 3, 8, 4, ["abyss:pillar_void", "abyss:pillar_dark"]);
        later(2, () => pillarRing(dim, ground, 6.5, 12, 3.4, ["abyss:pillar", "abyss:pillar_dark", "abyss:pillar_void"], 0.2));
        later(4, () => pillarRing(dim, ground, 10, 16, 3, ["abyss:pillar", "abyss:pillar_void"], 0.1));
        for (let i = 0; i < 3; i++) later(i * 3, () => fx(dim, "abyss:pillar_void", ground, { height: 7 }));
        fx(dim, "abyss:field_flames", ground, { radius: 8, life: 3 });
        fx(dim, "abyss:field_flames_red", ground, { radius: 8, life: 3 });
        fx(dim, "abyss:field_embers", ground, { radius: 8, life: 3 });
        fx(dim, "abyss:ground_shadow", ground, { radius: ULT.radius, life: 3 });
        sound(dim, "random.explode", ground, 1, 0.5);
        sound(dim, "mob.warden.sonic_boom", ground, 1, 0.6);
        sound(dim, "ambient.weather.thunder", ground, 0.8, 0.6);
        try {
            for (const pl of dim.getPlayers({ location: ground, maxDistance: 30 })) shake(pl, 0.8, 1.2);
        } catch {
            // ignore
        }
        let any = false;
        for (const e of getTargets(dim, add(ground, v3(0, 1.5, 0)), ULT.radius, p)) {
            if (hit(p, st, e, ULT.dmg, { kind: "void", from: ground, kb: 2.2, up: 0.6, burn: true, marks: ULT.marks,
                                        stagger: true })) any = true;
        }
        if (any && isValid(p)) registerAttack(p, st);
        removeFx(ent);
    });
}

const CASTERS = { rend: castRend, sun: castSun, flare: castFlare, spear: castSpear };

// ============================================================ INTRO / OUTRO
/** FROM THE ABYSS - drawing the weapon opens a portal under the player. */
export function castIntro(p, st) {
    const t = now();
    if (t < st.introReady) return;
    st.introReady = t + INTRO.cooldown;
    const dim = p.dimension;
    const g = onGround(dim, p.location);
    playAnim(p, "animation.abyss.intro", 0.25);
    fx(dim, "abyss:ground_shadow", g, { radius: 2.6, life: 1.5 });
    fx(dim, "abyss:sigil", g, { radius: 2.2, life: 1.4 });
    fx(dim, "abyss:sigil_red", g, { radius: 1.5, life: 1.4 });
    fx(dim, "abyss:portal_rise", g);
    fx(dim, "abyss:rune_float", g, { radius: 1.8 });
    sound(dim, "mob.endermen.portal", g, 1, 0.5);
    sound(dim, "mob.evocation_illager.cast_spell", g, 0.8, 0.5);
    later(INTRO.delay, () => {
        if (!isValid(p)) return;
        const c = chest(p);
        pillarRing(dim, g, 1.3, 6, 2.6, ["abyss:pillar", "abyss:pillar_dark", "abyss:pillar_void"]);
        const n = blackFlameExplosion(dim, p, st, c, INTRO.dmg, INTRO.radius, { burn: true, marks: INTRO.marks, kb: 0.9 });
        if (n > 0) registerAttack(p, st);
        shake(p, 0.3, 0.3);
    });
}

/** ASHES REMAIN - putting the weapon away after a fight leaves a black flame field. */
export function castOutro(p, st) {
    const t = now();
    if (t - st.lastCombat > OUTRO.combatWindow) return;
    st.lastCombat = -100000;
    const dim = p.dimension;
    const g = onGround(dim, p.location);
    const life = OUTRO.duration / 20;
    const ent = spawnFx(dim, "abyss:black_flame", g);
    fx(dim, "abyss:ground_shadow", g, { radius: OUTRO.radius, life });
    fx(dim, "abyss:sigil_red", g, { radius: OUTRO.radius * 0.8, life });
    fx(dim, "abyss:field_flames", g, { radius: OUTRO.radius, life });
    fx(dim, "abyss:field_flames_red", g, { radius: OUTRO.radius, life });
    fx(dim, "abyss:field_embers", g, { radius: OUTRO.radius, life });
    fx(dim, "abyss:crack_dark", g, { radius: 2.5, life });
    playAnim(p, "animation.abyss.outro", 0.25);
    sound(dim, "fire.ignite", g, 1, 0.5);
    sound(dim, "mob.blaze.breathe", g, 0.7, 0.5);
    flash(st, "§8ASHES REMAIN", 30);
    const mid = add(g, v3(0, 1, 0));
    repeat(OUTRO.every, OUTRO.duration / OUTRO.every, (i) => {
        if (i % 3 === 0) fx(dim, "abyss:dark_smoke", add(g, v3(rand(-2, 2), 0.4, rand(-2, 2))));
        for (const e of getTargets(dim, mid, OUTRO.radius + 1, p)) {
            if (hdist(e.location, g) > OUTRO.radius || Math.abs(e.location.y - g.y) > 3) continue;
            hit(p, st, e, OUTRO.dmg, { kind: "fire", cause: "magic", burn: true, noProc: true });
        }
    }, () => removeFx(ent));
}

// ============================================================ ambient
export function tickAura(p, st, t, ignition) {
    const dim = p.dimension;
    if (t % 6 === 0) {
        const hand = add(eye(p), add(add(mul(flatRight(p), 0.42), mul(flatForward(p), 0.25)), v3(0, -0.75, 0)));
        fx(dim, t % 12 === 0 ? "abyss:black_flame" : "abyss:ember", hand);
    }
    if (!ignition) return;
    const base = p.location;
    if (t % 3 === 0) {
        for (let k = 0; k < 2; k++) {
            const a = Math.random() * Math.PI * 2;
            fx(dim, "abyss:black_flame", add(base, v3(Math.cos(a) * 0.55, 0.2, Math.sin(a) * 0.55)));
        }
        fx(dim, "abyss:void_mote", add(base, v3(rand(-0.5, 0.5), rand(0.3, 1.6), rand(-0.5, 0.5))));
    }
    if (t % 6 === 0) fx(dim, "abyss:crimson_flame", add(base, v3(rand(-0.4, 0.4), 0.2, rand(-0.4, 0.4))));
    if (t % 10 === 0) fx(dim, "abyss:dark_smoke", add(base, v3(0, 0.3, 0)));
    if (t % 20 === 0) fx(dim, "abyss:ring_wave", onGround(dim, base), { radius: 1.4, life: 0.5 });
}
