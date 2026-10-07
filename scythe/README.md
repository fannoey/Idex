# Crimson Thorn Scythe (โมเดล)

โมเดลเคียวจากรูปอ้างอิง `reference/scythe_ref.jpg` สำหรับเปิดดูใน Blockbench ก่อน (ยังไม่ได้ทำเป็นแอดออน)

| ไฟล์ | |
|---|---|
| `crimson_scythe.geo.json` | โมเดล Bedrock (`geometry.idex.crimson_scythe`) ทำจากคิวบ์ 858 ชิ้น |
| `crimson_scythe.png` | เท็กซ์เจอร์ 488×848 (16 พิกเซลต่อ 1 หน่วยโมเดล) |
| `preview/` | ภาพ render ด้านหน้า / เฉียง / ด้านข้าง / ด้านหลัง |

## เปิดใน Blockbench
1. File → Open Model → เลือก `crimson_scythe.geo.json`
2. ถ้าเท็กซ์เจอร์ไม่ขึ้นเอง ให้ลาก `crimson_scythe.png` ใส่ช่อง Textures

## โครงสร้าง
- bone `scythe` (pivot 0,0,0) → ลูก `shaft`, `pommel`, `head`, `blade`
- สูง 52 พิกเซล (~3.25 บล็อก) ด้ามตั้งตรง ปลายหัวด้ามอยู่ที่ y = 0 ใบเคียวโค้งลงทางซ้าย
- หนาเป็นชั้น: ใบคม ~0.75 px, ด้าม ~1.5 px, หัวเคียว ~2.25 px

ทำไมใช้คิวบ์ ไม่ใช้ `poly_mesh`: Blockbench (รูปแบบ Bedrock) เปิด `poly_mesh` ไม่ได้ โมเดลจะว่างเปล่า

## สร้างใหม่
```
pip install numpy pillow scipy
python3 tools/build_scythe.py
```
ปรับขนาด (`HEIGHT`), ความละเอียด (`G`), ความหนา (`DEPTH`) ได้ที่หัวไฟล์ script
