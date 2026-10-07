# ECLIPSE TWIN SWORDS – Minecraft Bedrock Add-on

ดาบคู่ระดับตำนาน **SOLARIS** (ดวงอาทิตย์ / แสง) และ **NOCTIS** (ดวงจันทร์ / ความว่างเปล่า)
เมื่อใช้ทั้งสองเล่มสลับกันจนพลังเต็ม จะปลดล็อก **ECLIPSE STATE** และอัลติเมต **ECLIPSE: HEAVEN'S ABYSS**

- ไฟล์ติดตั้ง: `dist/EclipseTwinSwords.mcaddon`
- รองรับ Minecraft Bedrock **1.21.90 ขึ้นไป** ใช้ Script API `@minecraft/server` **2.0.0** (stable ไม่ต้องเปิด Beta APIs) — รูปแบบไฟล์ตรวจกับเอกสาร/ตัวอย่างทางการของ Mojang เวอร์ชัน 1.26.50
- ไม่มี Custom Entity เลย: projectile, area และ VFX ทั้งหมดขับด้วย Script + Particle จึงเบาสำหรับมือถือ

## ติดตั้ง
1. เปิด `EclipseTwinSwords.mcaddon` (Minecraft จะ import ทั้ง Resource Pack และ Behavior Pack)
2. เปิดใช้ทั้งสองแพ็กในโลก (ไม่ต้องเปิด Experimental / Beta APIs)
3. รับดาบ: `/function eclipse/give` หรือ `/give @s eclipse:solaris` และ `/give @s eclipse:noctis`
4. คำสั่งช่วยทดสอบ: `/function eclipse/energy_full` (พลังเต็ม 100), `/function eclipse/reset`, `/function eclipse/help`

สูตรคราฟต์ (โต๊ะคราฟต์):
- SOLARIS: Gold Block ×4 + Nether Star (กลาง) + Blaze Rod (ล่าง)
- NOCTIS: Crying Obsidian ×4 + Nether Star (กลาง) + Echo Shard (ล่าง)

## การควบคุม (ปุ่มเดียวต่อหน้าที่ กดง่ายบนมือถือ)
| ปุ่ม | หน้าที่ |
|---|---|
| **ย่อ (Sneak)** กด 1 ครั้ง | **เปลี่ยนสกิล** ไปสกิลถัดไป (วนกลับ) |
| **คลิกขวา / Use** (มือถือ: ปุ่ม **Cast Skill**) | **ใช้สกิลที่เลือกอยู่** |

- วงสกิล SOLARIS: Solar Slash → Radiant Spear → Solar Crown
- วงสกิล NOCTIS: Void Crescent → Abyss Field → Moonfall
- เมื่อ Eclipse Energy ครบ 100: **ECLIPSE STATE** และ **HEAVEN'S ABYSS** จะเพิ่มเข้ามาในวงสกิลเอง (ไม่ต้องกดวนผ่านช่องที่ยังใช้ไม่ได้)
- เลือกสกิลแยกกันต่อดาบ (สลับดาบแล้วยังจำสกิลที่เลือกไว้), ใช้อัลติเมตแล้วจะกลับไปสกิลแรกอัตโนมัติ
- ตอนเปลี่ยนสกิลจะมีเสียง + ท่าควงดาบสั้น ๆ + ชื่อสกิลขึ้นบน HUD
- รองรับทั้งย่อแบบกดค้าง (PC/จอย) และย่อแบบแตะสลับ (มือถือ): กดปุ่มย่อ 1 ครั้ง = เปลี่ยน 1 สกิล

## สกิล
| สกิล | กลไก | Damage | Cooldown |
|---|---|---|---|
| **Solar Slash** | คมแสงรูปพระจันทร์เสี้ยวพุ่งเร็ว 32 บล็อก/วิ ระยะ 15.5 บล็อก ทะลุได้ 2 ตัว (โดนสูงสุด 3) หยุดเมื่อชนบล็อก | 7 | 2 วิ |
| **Radiant Spear** | เล็งพื้น → วงเวททอง + ลำแสงจากฟ้า → หอกตก 0.7 วิ → ระเบิดรัศมี 4 (ไม่ทำลายบล็อก) + knockback | 12 → 8 ที่ขอบ | 8 วิ |
| **Solar Crown** | วงแหวนสุริยะหลังตัว + เส้นแสง 5 เส้นหมุนรอบ 12 วิ: Speed I, Damage ของ Solaris ×1.25, Solar Slash ใหญ่ขึ้น, Particle สว่างขึ้น | – | 20 วิ |
| **Void Crescent** | คมจันทร์เสี้ยวดำม่วง ระยะ 15.5 ทะลุ 2 ตัว ดึงเป้าเข้าหาผู้ใช้เล็กน้อย | 7 | 2 วิ |
| **Abyss Field** | วง Void รัศมี 5 นาน 6 วิ: damage ทุก 0.5 วิ + Slowness + ดูดเข้าศูนย์กลาง | 2 / pulse | 10 วิ |
| **Moonfall** | วงเวท Void → ดวงจันทร์ดำปรากฏ → ชาร์จ 1 วิ → ลำพลังลงพื้น รัศมี 5.5 + knockback + shockwave | 16 → 10 | 15 วิ |
| **Eclipse State** | 15 วิ: Damage ทั้งสองดาบ ×1.3, Cooldown ×0.75 (และลด cooldown ที่ค้างอยู่ 25% ตอนเปิด), ทุกสกิลมี VFX เวอร์ชัน Eclipse (ทอง+ม่วงซ้อนกัน) | – | ใช้พลัง 100 |
| **Heaven's Abyss** | อัลติเมต 5 เฟส (ด้านล่าง) รัศมี 11 + knockback + Slowness | 26 → 16 | 50 วิ |

- Damage ใส่ผู้เล่นคูณ 0.6 (PvP) และใช้ cause `entityAttack` เกราะจึงลดได้ปกติ → ไม่ one-shot ผู้เล่นใส่เกราะดีหรือบอส (Wither 600 HP, Warden 500 HP)
- ไม่ทำร้ายตัวเอง, สัตว์เลี้ยงของตัวเอง, Armor Stand, ไอเทม, ผู้เล่น Creative/Spectator, และ entity ที่มี tag `eclipse_immune`
- เคารพ gamerule `pvp`
- ไม่มีความเป็นอมตะ / Dodge / Parry ใด ๆ

### ECLIPSE: HEAVEN'S ABYSS
1. **Phase 1** ยกดาบทั้งสองขึ้น, วงแหวนครึ่งทองครึ่งม่วงขนาดใหญ่ด้านหลัง, กล้องสั่นเบา ๆ (ผู้ใช้ช้าลงระหว่างร่าย ไม่อมตะ)
2. **Phase 2** ดวงอาทิตย์ทองและดวงจันทร์ดำค่อย ๆ เคลื่อนเข้าหากัน, particle ทอง/ม่วงหมุนวน
3. **Phase 3** Black Eclipse: หมอกมืด (custom fog) + จอมืดชั่วครู่ + **hit-stop 0.3 วิ** (เสียงชาร์จตัดเงียบ, ศัตรูถูกตรึง)
4. **Phase 4** Shockwave ขนาดใหญ่จากศูนย์กลาง: damage + knockback + slow + particle burst + จอแฟลชขาว + กล้องสั่นแรง
5. **Phase 5** วงแหวน Eclipse ขยายช้า ๆ แล้วจางหาย + ฝนเศษดาว

## ECLIPSE ENERGY
- ใช้สกิล SOLARIS → **Solar Energy** (0–50), ใช้สกิล NOCTIS → **Void Energy** (0–50), ฟันโดนด้วยดาบ +2
- **Eclipse Energy = Solar + Void (0–100)** จึงต้องใช้ทั้งสองเล่มถึงจะเต็ม
- โดนศัตรูได้โบนัสเพิ่ม (สูงสุด +3 ต่อครั้ง)
- พลังที่ยังไม่เต็มจะค่อย ๆ ลดลงหลังไม่ได้สู้ 15 วิ แต่ **ถ้าเต็ม 100 แล้วจะเก็บไว้ไม่หาย**
- เก็บใน Scoreboard `eclipse_solar`, `eclipse_void`, `eclipse_energy` (อยู่ข้ามการออกเข้าเกม และแก้ด้วยคำสั่งได้)

## HUD (Actionbar)
```
▶Slash READY | Spear 4.2s | Crown READY        (▶ = สกิลที่เลือกอยู่)
SOL █████ VOID ███░░ 80%
ECLIPSE READY  Sneak to select
```
ระหว่าง Eclipse State แถบจะกลายเป็นเวลาที่เหลือ และบอกว่า Heaven's Abyss พร้อมหรือยัง
กดสกิลตอนติด cooldown จะขึ้นเวลาที่เหลือ, ถือดาบครั้งแรกจะขึ้นคำแนะนำปุ่ม

## ระบบดาบคู่ (Dual Wield)
- **Visual Dual-Wield:** ถือ SOLARIS มือขวา → NOCTIS ปรากฏในมือซ้ายอัตโนมัติ (และกลับกัน) ผ่าน Attachable ที่ผูกกระดูกแขนซ้าย
  ดาบเงาในมือซ้ายจะแสดงเมื่อมือรองว่างเท่านั้น (ถ้าถือโล่/โทเทมจะไม่ทับกัน)
- **Native Off-hand:** ดาบทั้งสองใส่มือรองได้จริง (`minecraft:allow_off_hand`) มีโมเดลมือซ้ายของตัวเอง
- **ท่ายืน (Stance):** ถือดาบแล้วตัวละครจะตั้งท่าถือดาบคู่ (idle_solaris / idle_noctis / eclipse_idle) ผ่าน `playAnimation` ทุกคนในเซิร์ฟเห็น และหยุดเองทันทีเมื่อเปลี่ยนไอเทม (stop expression ฝั่ง client)
- โมเดลดาบเป็น `poly_mesh` จากภาพอ้างอิง: SOLARIS ใบดาบเรืองแสงขาวทอง, แผ่นทองฝังดาว, วงแหวนรัศมี, พัดรังสีสุริยะ, ริบบิ้นเปลวไฟ, ด้ามลายข้าวหลามตัด, หัวด้ามดวงอาทิตย์ — NOCTIS ใบดาบเหล็กดำ, จันทร์เสี้ยวเงิน, อัญมณีดาวสีน้ำเงิน, จันทร์เสี้ยวเล็กสองข้าง, เถาวัลย์สีกรมท่าเรืองแสง, ด้ามพันดำ, หัวด้ามวงแหวน
- ส่วนที่เรืองแสงใช้ material `entity_emissive_alpha` (สว่างทั้งกลางวันและกลางคืน)

## Animation
| หมวด | Animation | ทำงานเมื่อ |
|---|---|---|
| ถือดาบ | `idle_solaris`, `idle_noctis`, `eclipse_idle` | ยืนนิ่งถือดาบคู่ (ท่าหายใจ) |
| เดิน | `walk` | เดิน: ถือดาบสองเล่มต่ำพร้อมฟัน ตัดการแกว่งแขนแบบ vanilla ออก แกว่งตามจังหวะก้าว |
| วิ่ง | `run` | Sprint: โน้มตัว ดาบสองเล่มกวาดไปด้านหลัง (วิ่งแบบอนิเมะ) ตัวเด้งตามก้าว |
| โจมตี | `attack`, `attack_left`, `attack_cross` | ตีปกติ: ฟันเฉียงมือขวา → ครั้งที่ 2 ฟันมือซ้าย → ครั้งที่ 3 ฟันไขว้สองดาบ |
| เปลี่ยนสกิล | `skill_select` | กดย่อ: ควงข้อมือสองดาบ |
| ปล่อยสกิล | `solar_cast`, `radiant_spear`, `solar_crown`, `void_crescent`, `abyss_field`, `moonfall`, `eclipse_activate`, `eclipse_ultimate` | ตอนใช้สกิลแต่ละท่า |

- ถือ/เดิน/วิ่ง/โจมตี เล่นซ้อนกันเป็น layer และค่อย ๆ ผสมกันเองตาม `blend_weight` (ความเร็วเดิน, sprint) จึงเปลี่ยนท่าลื่นโดยไม่ต้อง override `player.entity.json` (ไม่ชนกับแอดออนอื่น)
- ท่าโจมตีพื้นฐานผูกกับจังหวะฟันของเกม (`variable.attack_time`) จึงทำงานแม้ฟันอากาศ
- ไม่ทำงานตอนขี่สัตว์ ว่ายน้ำ หรือร่อน Elytra, และปิดในมุมมองบุคคลที่ 1 เพื่อให้จอสะอาด

## VFX (62 effects, 22 textures วาดด้วยโค้ดทั้งหมด)
| VFX ที่ขอ | Effect ในแพ็ก |
|---|---|
| Solar Ring | `solar_crown_halo`, `solar_crown_burst`, `solar_rune_ring` |
| Void Ring | `void_hit_ring`, `void_pulse`, `void_field_lines` |
| Eclipse Ring | `eclipse_halo`, `eclipse_split_ring`, `eclipse_final_ring`, `eclipse_shock_wall` |
| Solar Spark | `solar_stars`, `solar_passive`, `solar_debris` |
| Void Spark | `void_stars`, `void_implode`, `void_field_inflow` |
| Crescent Trail | `void_crescent_body/rim/aura`, `void_trail`, `void_lines` |
| Solar Slash Trail | `solar_slash_glow/core/ring`, `solar_streaks` |
| Magic Circle | `solar_circle`, `void_circle`, `void_field_circle` |
| Shockwave | `solar_shockwave`, `void_shockwave`, `eclipse_shockwave` |
| Eclipse Explosion | `eclipse_disc`, `eclipse_corona`, `eclipse_flash`, `eclipse_burst`, `eclipse_pillar` |
| Star Particles | `eclipse_stardust`, `eclipse_star_rain`, `void_field_stars` |
| Void Core | `void_field_core`, `void_hit_core`, `void_moon`, `void_moon_corona` |
| Solar Core | `eclipse_sun`, `solar_flash`, `solar_spear_fall/stuck`, `solar_sky_beam` |

ทุก effect อ่าน Molang variable จากสคริปต์ จึงปรับขนาด/จำนวนได้ทันทีโดยไม่แก้ JSON:
`variable.scale`, `variable.density`, `variable.life`, `variable.alpha`, `variable.radius`, `variable.height`, `variable.speed`, `variable.dir`, `variable.vel`, `variable.tilt`, `variable.phase`

- Projectile ใช้ billboard `direction_z` หันตามทิศพุ่ง, วงเวทนอนราบ `emitter_transform_xz`, หอก/ลำแสงตั้งตรง `lookat_y`
- วงแหวนที่ติดตัวผู้เล่น (Crown / Eclipse) ส่งความเร็วผู้เล่นเข้า particle (`variable.vel`) จึงเกาะตัวลื่นแม้กำลังวิ่ง
- สไตล์ Wuthering Waves: คมแสงมีเส้นสปีด, flash ขอบคม, วงแหวน shockwave, hit-stop, จอแฟลช, กล้องสั่น

## เสียง (19 เสียง สังเคราะห์จากโค้ด ไม่ใช้ไฟล์เสียงภายนอก)
- Solar: `solaris.slash` (shing คริสตัล), `solaris.slash_hit`, `solaris.spear_cast` (ระฆังไล่โน้ต), `solaris.spear_fall`, `solaris.spear_impact` (ระฆังใหญ่ + บูม), `solaris.crown` (คอรัส)
- Void: `noctis.crescent` (ซูมต่ำ), `noctis.crescent_hit`, `noctis.field`, `noctis.field_pulse`, `noctis.moonfall_charge`, `noctis.moonfall_impact` (sub-bass)
- Eclipse: `eclipse.activate`, `eclipse.charge` (ชาร์จใหญ่ ตัดเงียบตอน hit-stop), `eclipse.rumble`, `eclipse.impact`, `eclipse.burst` (magical burst), `eclipse.ready`, `eclipse.select` (เปลี่ยนสกิล)
- เล่นแบบสุ่ม pitch ±4% ทุกครั้ง

## Performance (มือถือมาก่อน)
- ไม่ spawn entity เลย, ไม่สแกน entity ทั้งโลก: ค้นหาเฉพาะในรัศมีสกิลของ dimension ที่ผู้เล่นอยู่ (`getEntities` + `closest`) จำกัดเป้า 16 ตัว
- Projectile เป็นจุดในสคริปต์ คำนวณชนบล็อกครั้งเดียวด้วย raycast ตอนปล่อย ตรวจ entity เฉพาะรอบ segment ของ tick นั้น แล้วลบทิ้งทันทีเมื่อจบ
- Abyss Field / วงเวท / ดวงจันทร์ spawn ครั้งเดียว ให้ client เล่นเองทั้งอายุ (ไม่ส่ง particle ทุก tick)
- งบ particle emitter สูงสุด 48 ตัวต่อ tick ทั้งเซิร์ฟ (ทดสอบจริงเฉลี่ย ~0.9 ตัว/tick)
- HUD ส่งเฉพาะตอนข้อความเปลี่ยน, cooldown เก็บเป็น "tick ที่พร้อม" (ไม่มีงานต่อ tick)
- ลบข้อมูลผู้เล่นทั้งหมดตอนออกเกม (ไม่ memory leak), ทุก timeout ห่อ try/catch
- เครื่องสเปกต่ำ: ตั้ง `VFX.DENSITY = 0.5` ใน `behavior_pack/scripts/config.js` (ปิดจอแฟลช/สั่น/หมอกด้วย `VFX.CAMERA_EFFECTS = false`)

## โครงสร้างไฟล์
```
EclipseTwinSwords/
├── behavior_pack/
│   ├── manifest.json            (data + script module, @minecraft/server 2.0.0)
│   ├── items/solaris.json, noctis.json
│   ├── recipes/solaris.json, noctis.json
│   ├── functions/eclipse/{give,energy_full,reset,help}.mcfunction
│   ├── texts/ (en_US, th_TH)
│   └── scripts/
│       ├── main.js        ตรวจผู้เล่น / ไอเทม / input (ย่อ = เปลี่ยนสกิล, Use = ใช้) แล้วเรียกสกิล, loop ต่อ tick
│       ├── skills.js      วงสกิล: เลือก / วน / ใช้สกิลที่เลือก
│       ├── solaris.js     Solar Slash, Radiant Spear, Solar Crown, passive
│       ├── noctis.js      Void Crescent, Abyss Field, Moonfall, passive
│       ├── eclipse.js     Eclipse Energy, Eclipse State, Heaven's Abyss
│       ├── cooldown.js    cooldown ต่อผู้เล่น + ready state
│       ├── damage.js      area damage, target filter, knockback, pull, effect
│       ├── projectile.js  projectile แบบไม่มี entity (pierce, block clip)
│       ├── hud.js         actionbar
│       ├── vfx.js         particle / sound / camera helpers + งบ particle
│       ├── aim.js         เล็งตำแหน่งบนพื้น
│       ├── state.js, vec.js, config.js (ตัวเลขทั้งหมดปรับที่นี่)
└── resource_pack/
    ├── manifest.json
    ├── attachables/solaris.json, noctis.json
    ├── models/entity/eclipse_*.geo.json        (poly_mesh: มือขวา + ดาบคู่มือซ้าย + มุมมองบุคคลที่ 1 + มือรอง)
    ├── animations/ eclipse_player.animation.json, eclipse_blade.animation.json
    ├── animation_controllers/eclipse_blade.animation_controllers.json
    ├── render_controllers/eclipse_blade.render_controllers.json
    ├── particles/ solar_*.particle.json, void_*.particle.json, eclipse_*.particle.json  (Bedrock ต้อง 1 effect ต่อ 1 ไฟล์)
    ├── sounds/sound_definitions.json + sounds/eclipse/*.ogg
    ├── fogs/black_eclipse.json
    ├── textures/items/solaris.png, noctis.png
    ├── textures/models/eclipse/eclipse_swords.png
    ├── textures/particle/eclipse/*.png
    └── texts/ (en_US, th_TH)
```

## Build และทดสอบ
```
python3 tools/eclipse/build.py        # สร้างทุกอย่าง + validate + dist/EclipseTwinSwords.mcaddon
node tools/eclipse/smoke_test.mjs     # รันสคริปต์จริงกับ mock API ยิงทุกสกิลแล้วตรวจผล
```
- `build.py` ต้องมี numpy, Pillow และ ffmpeg (libvorbis) — สร้าง texture, particle, โมเดล, เสียง, แพ็ก และ preview ใน `preview/eclipse/`
- Validator ตรวจ: JSON ทุกไฟล์, poly_mesh (จำนวน/ดัชนี/UV), parent bone, attachable → geometry/animation/render controller/texture, icon, lang key, manifest/UUID/script entry, และทุก particle/sound/animation/fog ที่สคริปต์เรียกต้องมีอยู่จริง
- สคริปต์ผ่านการ type-check (`tsc --checkJs --strict`) กับ typings ทางการของ `@minecraft/server` 2.0.0
- Smoke test ตรวจ 37 ข้อ: การเปลี่ยน/ใช้สกิลด้วยย่อ+คลิกขวา, layer animation, ทะลุ 2 ตัว, ดึง, DoT ของ Abyss Field, พลัง, Eclipse State, อัลติเมตครบ 5 เฟส (fog push/remove), ไม่มี error

## สิ่งที่ควรเช็คในเกม (ทดสอบนอกเกมไม่ได้)
- มุมและตำแหน่งดาบในมือ (third person ใช้ rig แบบเดียวกับดาบคาทานะที่เคยผ่าน, first person ใช้ตำแหน่งเดียวกับตรีศูล vanilla) — ถ้าต้องขยับ แก้ `TILT`, `GRIP_R/L` ใน `tools/eclipse/swords.py` หรือค่า `blade_fp` ใน `anims.py`
- ความแรงของท่า animation และขนาด VFX (ปรับเร็วที่สุดผ่าน `VFX.SCALE` / `variable.scale` ใน `config.js`)
- ความดังของเสียงแต่ละตัว (ปรับ `volume` ใน `tools/eclipse/sounds.py`)
