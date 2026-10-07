# VLONE Outfit – Minecraft Bedrock Add-on

ชุดเสื้อผ้า 3 ชิ้นสำหรับ Minecraft Bedrock (ใส่ได้จริงผ่านช่องเกราะ):

| ไอเท็ม | ID | ช่องใส่ |
|---|---|---|
| VLONE Hoodie (ฮู้ดพับลง) | `idex:vlone_hoodie` | เสื้อ (chest) |
| VLONE Hoodie (Hood Up / สวมฮู้ด) | `idex:vlone_hoodie_up` | เสื้อ (chest) |
| Chain Cargo Pants (กางเกงคาร์โก้โซ่) | `idex:vlone_cargo_pants` | กางเกง (legs) |

## การต่อกันของเสื้อกับกางเกง
- ชายเสื้อฮู้ด (ขอบยางยืด) ลงมาถึง y=9 และพองกว่าตัวเสื้อ จึง **ซ้อนทับขอบเอวกางเกง** (y≈10.4–13.6) พอดี ไม่มีช่องว่างเห็นผิว
- ขอบเอวกางเกงอยู่บน bone `body` ส่วนขากางเกงอยู่บน `rightLeg`/`leftLeg` เหมือนผิวผู้เล่น จึงขยับตามการเดินได้ปกติ
- โซ่ห้อยออกมาจากใต้ชายเสื้อเหมือนในรูปอ้างอิง กระเป๋าคาร์โก้ถูกวางให้อยู่ใต้ชายเสื้อพอดี ไม่ทะลุ
- ใส่กางเกงอย่างเดียวจะเห็นขอบเอวยางยืด สายคาดพร้อมหัวเข็มขัด และเชือกผูกด้านหน้า

## ตัว V ด้านหลังเรืองแสง
- ตัว V ด้านหลังเสื้อ (ทั้งแบบใส่ฮู้ดและไม่ใส่) สว่างเต็มที่ตลอดเวลา ไม่ขึ้นกับแสงในเกม กลางวันก็สว่าง กลางคืน/ในถ้ำก็ยังเห็นชัด มีแสงฟุ้งสีฟ้ารอบขอบตัวอักษร
- ทำโดยแผ่น `geometry.idex.vlone_hoodie_glow` วางทับหลังเสื้อ ใช้ material `entity_emissive_alpha` (พิกเซลที่ alpha = 0 ใน `vlone_hoodie_glow.png` จะเรืองแสง ส่วนพิกเซลทึบเป็นผ้าปกติ) ผ่าน render controller `controller.render.idex.vlone_glow`
- เรืองแสงที่ตัวเสื้อเท่านั้น ไม่ได้ส่องแสงให้บล็อกรอบตัวสว่าง (Bedrock ไม่รองรับให้ชุดที่สวมปล่อยแสงออกไปรอบ ๆ)

## ติดตั้ง
1. ดาวน์โหลด `dist/Vlone_Outfit.mcaddon` แล้วเปิดไฟล์ (Minecraft จะ import RP + BP ให้เอง)
2. เปิดใช้ทั้ง Behavior Pack และ Resource Pack ในโลก
3. รับไอเท็ม:
   ```
   /give @s idex:vlone_hoodie
   /give @s idex:vlone_hoodie_up
   /give @s idex:vlone_cargo_pants
   ```

## สลับฮู้ด (สวม / ไม่สวม)
- ระหว่างใส่อยู่: `/function hood_up` และ `/function hood_down`
- หรือวางเสื้อในโต๊ะคราฟต์ 1 ตัว → ได้อีกแบบ (สลับไปมาได้)

## สูตรคราฟต์
- ฮู้ด: ขนแกะดำ 7 ก้อน รูปเสื้อเกราะ
- กางเกง: ขนแกะดำ 6 ก้อน + โซ่ 1 อัน (โซ่อยู่ตรงกลางแถวบน) รูปกางเกงเกราะ

## โครงสร้างไฟล์
```
tools/build_outfit.py         สคริปต์สร้างทุกอย่าง (geometry + texture + pack + preview)
vlone_outfit/Vlone_Outfit_RP  resource pack (models/entity/*.geo.json, attachables, textures)
vlone_outfit/Vlone_Outfit_BP  behavior pack (items, recipes, functions)
dist/Vlone_Outfit.mcaddon     ไฟล์ติดตั้ง
preview/                      ภาพตัวอย่างและ texture atlas
```
ไฟล์ `.geo.json` เปิดแก้ใน Blockbench ได้ (Bedrock Entity, box UV, texture 8 พิกเซลต่อ 1 หน่วยโมเดล)

แก้แล้วสร้างใหม่ด้วย:
```
python3 tools/build_outfit.py
```

## หมายเหตุ
- รองรับ Minecraft Bedrock 1.21.40 ขึ้นไป
- โมเดลอิงสัดส่วนแขนแบบ classic (4 พิกเซล) ถ้าสกินแขนเล็ก (slim) แขนเสื้อจะหลวมขึ้นเล็กน้อย
- ตอนถือไว้ในมือจะไม่แสดงโมเดล 3D (แสดงเฉพาะตอนสวมใส่)

---

# Abyssal Inferno – Minecraft Bedrock Add-on

พลังธาตุ **ไฟ + ความมืด + ความว่างเปล่า** แนว Action RPG / Burst / Combo ผูกกับอาวุธ `abyss:abyssal_inferno`

ไฟล์ติดตั้ง: `dist/Abyssal_Inferno.mcaddon` (Bedrock 1.21.60+, ไม่ต้องเปิด Experimental)

```
/give @s abyss:abyssal_inferno
```
สูตรคราฟต์: Echo Shard (บน) + Crying Obsidian ×2 + Netherite Sword (กลาง) + Blaze Rod (ล่าง)

## การควบคุม (ระบบสลับสกิล)
| ปุ่ม | ผล |
|---|---|
| **ย่อ (Sneak) กด 1 ครั้ง** | สลับสกิลถัดไป วนเป็นวง 1 → 6 → 1 (ชื่อสกิลขึ้นกลางจอ + HUD) |
| **คลิกขวา (Use)** | ใช้สกิลที่เลือกอยู่ |
| **กดค้างคลิกขวา** (ตอนเลือก Void Combustion) | ชาร์จ — ปล่อยปุ่มเพื่อระเบิด (ชาร์จเต็ม 1.5 วิ) |
| **คลิกซ้ายใส่ศัตรู** | Black Flame Combo 5 จังหวะ |

ลำดับสกิลในวง: 1 Abyss Rend → 2 Black Sun → 3 Abyssal Flare → 4 Void Spear → 5 Void Combustion → 6 End of All Flames

HUD (actionbar) แสดง: สกิลที่เลือก + คูลดาวน์, เกจ Inferno/Void 20 ช่อง, Combo, เวลา Abyss Ignition, ULTIMATE READY

## สกิล
| สกิล | CD | สรุป |
|---|---|---|
| Black Flame Combo | – | 6/7/8/10/15 dmg, ฮิต 3 คลื่นไฟ 4 บล็อก, ฮิต 4 มีโอกาส Void Mark 35%, ฮิต 5 กระโดดฟาดระเบิดไฟดำ r3 + Burn |
| Abyss Rend | 5s | รอยแยก void วิ่งไปข้างหน้า 8 บล็อก 18 dmg, knockback, Mark +1, Void +15 |
| Black Sun | 12s | ดวงอาทิตย์ดำ 5 วิ ดูดศัตรู r5 ทุก 0.5 วิ (4 dmg + Mark) → Void Collapse 30 dmg r6, Void +25 |
| Abyssal Flare | 8s | ระเบิดไฟดำรอบตัว r5 20 dmg, Burn, Mark +1, Inferno +15, Void +10 |
| Void Spear | 6s | หอกพุ่งทะลุ 12 บล็อก 22 dmg (+10 ถ้ามี Mark), Mark +2, Void +20 |
| Void Combustion | ชาร์จ | ปกติ 15 dmg r3 / เต็ม 25 dmg r5 + Void +20 + Void Zone 4 วิ (2 dmg ทุก 0.5 วิ, 30% Mark) |
| End of All Flames | เกจ 100/100 | Void Core ลอยเหนือหัว → ดูดศัตรู r12 → ยุบตัว → ระเบิด 60 dmg r12 + Burn + Mark +3 + Stagger, เกจรีเซ็ตเป็น 0 |

ระบบสถานะ: Burn 3 วิ (2 dmg/0.5 วิ, Mark ≥3 → Abyss Burn 3 dmg + โอกาส Void Explosion), Void Mark 0–5 (ครบ 5 → Void Break 30 dmg r4),
Combo 0–15 (หลุดถ้าไม่ตี 1.5 วิ; 3 = +5% dmg, 5 = haste, 10 = +15% dmg, 15 = Black Flame Explosion แล้วลดเหลือ 10),
Abyss Ignition 10 วิ เมื่อเกจเต็มทั้งคู่ (+25% dmg, haste II, Burn/Void Break +25%), Passive Black Flame / Abyss Consumption / Void Dominance,
Intro *From the Abyss* (ตอนชักอาวุธขึ้นมือ, CD 20 วิ), Outro *Ashes Remain* (ตอนเก็บอาวุธหลังต่อสู้ → สนามไฟดำ r4 5 วิ)

Scoreboard: `abyss_inferno abyss_void abyss_combo abyss_mark abyss_burn abyss_skill1-4 abyss_select` · Dynamic property เก็บเกจ/สกิลที่เลือกข้ามการออกเกม

## เอฟเฟกต์
63 particle (ไฟดำ = ชั้น blend สีดำ + ชั้น additive แดง/ม่วงซ้อนกัน เพื่อให้ "ดำแต่เรืองขอบ") เช่น วงเวทนัยน์ตาแห่งห้วงเหว, รอยแยก void, วงแหวนแตก, หอก void, ดวงอาทิตย์ดำ + วงแหวนไฟหมุน 3 ระนาบ, Void Core ม่วง, คลื่นไฟแผ่รอบทิศ, เสาไฟ, รูน Void Mark บอกจำนวน stack เหนือหัวศัตรู
และท่าทาง 16 ท่า (`animation.abyss.*`) ตัวอย่าง texture: `preview/abyssal_particles_preview.png`

## โครงสร้างไฟล์
```
tools/build_abyssal.py                     สร้าง texture, particle, animation, entity, item, manifest, .mcaddon
abyssal_inferno/Abyssal_Inferno_BP/scripts  Script API (main, config, state, combat, skills, hud)
abyssal_inferno/Abyssal_Inferno_RP          particles/, animations/, textures/particle/abyss/
```
ปรับตัวเลข damage/CD ได้ที่ `scripts/config.js` แล้วสร้างใหม่ด้วย `python3 tools/build_abyssal.py`
(ถ้าลงทับเวอร์ชันเก่า ให้ลบ pack เดิมออกจากโลกก่อน หรือเพิ่ม VERSION ใน build script)
