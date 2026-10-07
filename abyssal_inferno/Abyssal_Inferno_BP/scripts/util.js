import { system, MolangVariableMap } from "@minecraft/server";

// ---------------------------------------------------------------- scheduling
export function safe(fn) {
    try {
        return fn();
    } catch (e) {
        console.warn(`[abyss] ${e}`);
        return undefined;
    }
}

/** Run fn after `ticks` ticks (0 = next tick). */
export function later(ticks, fn) {
    return system.runTimeout(() => safe(fn), Math.max(0, Math.floor(ticks)));
}

/** Run fn(i) every `interval` ticks, `count` times; fn returning false stops early. Then end(). */
export function repeat(interval, count, fn, end) {
    let i = 0;
    const id = system.runInterval(() => {
        if (i >= count) {
            system.clearRun(id);
            if (end) safe(end);
            return;
        }
        const r = safe(() => fn(i));
        i++;
        if (r === false) {
            system.clearRun(id);
            if (end) safe(end);
        }
    }, interval);
    return id;
}

export const now = () => system.currentTick;

// ---------------------------------------------------------------- vectors
export const v3 = (x, y, z) => ({ x, y, z });
export const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
export const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
export const mul = (a, s) => ({ x: a.x * s, y: a.y * s, z: a.z * s });
export const len = (a) => Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
export const dist = (a, b) => len(sub(a, b));
export const hdist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
export function norm(a) {
    const l = len(a);
    return l > 1e-6 ? mul(a, 1 / l) : { x: 0, y: 0, z: 1 };
}

/** Horizontal forward unit vector from the player's yaw. */
export function flatForward(e) {
    const yaw = (e.getRotation().y * Math.PI) / 180;
    return { x: -Math.sin(yaw), y: 0, z: Math.cos(yaw) };
}
/** Horizontal right unit vector. */
export function flatRight(e) {
    const f = flatForward(e);
    return { x: -f.z, y: 0, z: f.x };
}
export function eye(e) {
    try {
        return e.getHeadLocation();
    } catch {
        return add(e.location, v3(0, 1.62, 0));
    }
}
/** Middle of an entity's body (between feet and head). */
export function chest(e) {
    const l = e.location;
    const h = eye(e);
    return { x: l.x, y: (l.y + h.y) / 2 + 0.1, z: l.z };
}

// ---------------------------------------------------------------- world
function solid(dim, x, y, z) {
    try {
        const b = dim.getBlock({ x: Math.floor(x), y: Math.floor(y), z: Math.floor(z) });
        return !!b && !b.isAir && !b.isLiquid;
    } catch {
        return false;
    }
}
export function isSolid(dim, p) {
    return solid(dim, p.x, p.y, p.z);
}
/** Y of the walkable surface near (x, y, z) so ground decals hug the terrain. */
export function groundY(dim, x, y, z) {
    const fy = Math.floor(y);
    if (solid(dim, x, fy, z)) {
        for (let i = 1; i <= 3; i++) if (!solid(dim, x, fy + i, z)) return fy + i;
        return y;
    }
    for (let i = 1; i <= 4; i++) if (solid(dim, x, fy - i, z)) return fy - i + 1;
    return y;
}
export function onGround(dim, p) {
    return { x: p.x, y: groundY(dim, p.x, p.y, p.z), z: p.z };
}

// ---------------------------------------------------------------- effects
/** Spawn a particle. vars: { radius: 3, life: 1 } -> variable.radius / variable.life */
export function fx(dim, id, loc, vars) {
    try {
        if (vars) {
            const m = new MolangVariableMap();
            for (const k in vars) m.setFloat(`variable.${k}`, vars[k]);
            dim.spawnParticle(id, loc, m);
        } else {
            dim.spawnParticle(id, loc);
        }
    } catch {
        // unloaded chunk / dimension gone - ignore
    }
}
export function fxDir(dim, id, loc, dir, extra) {
    fx(dim, id, loc, Object.assign({ dx: dir.x, dy: dir.y, dz: dir.z }, extra || {}));
}

export function sound(dim, id, loc, volume = 1, pitch = 1) {
    try {
        dim.playSound(id, loc, { volume, pitch });
    } catch {
        // ignore unknown sound / unloaded
    }
}

export function cmd(e, c) {
    try {
        if (e.runCommand) return e.runCommand(c);
        return e.runCommandAsync(c);
    } catch {
        return undefined;
    }
}

export function shake(e, intensity, seconds) {
    cmd(e, `camerashake add @s ${intensity} ${seconds} positional`);
}

export function playAnim(p, name, blendOut = 0.2) {
    try {
        p.playAnimation(name, { blendOutTime: blendOut, controller: "abyss_action" });
    } catch {
        cmd(p, `playanimation @s ${name} default ${blendOut} "0" abyss_action`);
    }
}

/** applyKnockback across Script API versions (1.x: 4 numbers, 2.x: VectorXZ + vertical). */
export function knock(e, dx, dz, h, v) {
    const l = Math.hypot(dx, dz) || 1;
    dx /= l;
    dz /= l;
    try {
        e.applyKnockback(dx, dz, h, v);
        return;
    } catch {
        // fall through to the 2.x signature
    }
    try {
        e.applyKnockback({ x: dx * h, z: dz * h }, v);
    } catch {
        // knockback immune
    }
}

export function effect(e, id, ticks, amp = 0) {
    try {
        e.addEffect(id, ticks, { amplifier: amp, showParticles: false });
    } catch {
        // invalid entity
    }
}

export const rand = (a, b) => a + Math.random() * (b - a);

/** Points on a horizontal circle. */
export function circle(center, r, n, phase = 0) {
    const out = [];
    for (let i = 0; i < n; i++) {
        const a = phase + (i / n) * Math.PI * 2;
        out.push({ x: center.x + Math.cos(a) * r, y: center.y, z: center.z + Math.sin(a) * r });
    }
    return out;
}
