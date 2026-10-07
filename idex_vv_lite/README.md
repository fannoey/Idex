# Idex VV Lite – Vibrant Visuals เบา ๆ สำหรับมือถือสเปคต่ำ

Resource pack สำหรับ **Vibrant Visuals** (VV) ของ Minecraft Bedrock 1.21.120 ขึ้นไป ทำมาสำหรับมือถือแบบ Helio G99 (Mali-G57 MC2)
ไฟล์ติดตั้ง: `dist/Idex_VV_Lite.mcpack`

## ⚠️ อ่านก่อน: ส่วนที่หนักที่สุดของ VV แพ็คคุมไม่ได้
VV กระตุกส่วนใหญ่เพราะ **ความละเอียดภาพ, เงา, แสงสะท้อน, หมอก volumetric** ซึ่งปรับได้จาก **ตั้งค่าวิดีโอของเกม** เท่านั้น
resource pack ไหนก็ปรับให้ไม่ได้ เพราะฉะนั้น **ต้องตั้งค่าตามตารางด้านล่างคู่กับแพ็คนี้** ถึงจะได้ผลจริง

## แพ็คนี้ทำอะไร
| ไฟล์ | เปลี่ยนอะไร | ผล |
|---|---|---|
| `water/water.json` | ปิด caustics (ลายแสงใต้น้ำ) และคลื่น | เบาลงตอนอยู่ใกล้/ในน้ำ |
| `fogs/*.json` (49 ไฟล์) | หมอกระยะไกลเหมือนเดิม แต่ความหนาแน่นหมอก volumetric = 0 | ปิด Volumetric Fog ในตั้งค่าแล้วภาพยังดูเหมือนเดิม ไม่แปลก |
| `lighting/global.json` | แสงแดด/จันทร์เหมือน vanilla แต่แสง ambient 0.02 → 0.05 | ตอนลดเงาให้ต่ำ ที่ร่มกับในถ้ำจะไม่มืดตื๋อ |
| `color_grading/color_grading.json` | contrast 1.18, saturation 1.15, อุณหภูมิสี 6000K | สีสดขึ้น โทนอุ่นแบบชิเดอร์ (ไม่กิน FPS เพิ่ม) |

## ตั้งค่าที่แนะนำสำหรับ Helio G99
ไปที่ ตั้งค่า → Video → Graphics Mode: **Vibrant Visuals** แล้วปรับดังนี้ (ถ้ามีปุ่ม preset ให้กด **Favor Performance** ก่อน แล้วค่อยปรับตาม)

| ตั้งค่า | ค่า | หมายเหตุ |
|---|---|---|
| Upscaling / Resolution (ความละเอียด) | **ต่ำสุดที่ยังรับได้ (~50–60%)** | ได้ FPS คืนมาเยอะที่สุด |
| Shadow Quality | **Low** | ยังเห็นเงาบล็อก/ตัวละคร |
| Point Light Shadows | **Off** | เงาจากคบเพลิง หนักมาก |
| Reflections | **Off** หรือ Low | |
| Volumetric Fog | **Off** | แพ็คนี้ทำให้ภาพไม่ต่างเดิม |
| Bloom | Low | |
| Render Distance | **6–8 ชังก์** | |
| Max Framerate | 30 | เครื่องร้อนน้อยลง เฟรมนิ่งกว่า |

ทิปเพิ่ม: ปิดโหมดประหยัดแบต, ปิดแอปพื้นหลัง, อย่าเล่นตอนชาร์จ (เครื่องร้อนแล้ว CPU/GPU จะลดความเร็ว)

## ติดตั้ง
1. เปิด `dist/Idex_VV_Lite.mcpack`
2. ตั้งค่า → Global Resources → เปิด **Idex VV Lite** ไว้บนสุด
3. **อย่าเปิดพร้อม Idex Lite Shader** (แพ็คนั้นทำมาสำหรับโหมดภาพธรรมดา)

## ปรับแต่ง / สร้างใหม่
ค่าต่าง ๆ อยู่ที่ต้นไฟล์ `tools/build_vv_lite.py` (`AMBIENT`, `COLOR_GRADING`) สคริปต์อ่านค่า vanilla จาก [Mojang/bedrock-samples](https://github.com/Mojang/bedrock-samples):
```
git clone --depth 1 https://github.com/Mojang/bedrock-samples ../mojang/bedrock-samples
python3 tools/build_vv_lite.py
```
