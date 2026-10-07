# VLONE Outfit – Minecraft Bedrock Add-on

> ในรีโปนี้ยังมี **Idex Lite Shader** แพ็คแสงเงาเบา ๆ สำหรับมือถือสเปคต่ำ → ดู [`idex_lite_shader/README.md`](idex_lite_shader/README.md) (ไฟล์ติดตั้ง `dist/Idex_Lite_Shader.mcpack`)
>
> และ **Idex VV Lite** สำหรับเปิด Vibrant Visuals บนมือถือสเปคต่ำ → ดู [`idex_vv_lite/README.md`](idex_vv_lite/README.md) (ไฟล์ติดตั้ง `dist/Idex_VV_Lite.mcpack`)

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
