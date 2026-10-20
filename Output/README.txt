GRIM REAPER SCYTHE - Blockbench model
=====================================

ไฟล์ในโฟลเดอร์นี้
-----------------
grim_reaper_scythe.bbmodel       ไฟล์โปรเจกต์ Blockbench (ไฟล์หลัก)
textures/scythe_texture.png      Texture atlas 128x128 (ฝังอยู่ใน .bbmodel ด้วย)
preview_front.png                ภาพมุมหน้า (Orthographic, กล้อง South) เรนเดอร์จาก Blockbench จริง
preview_3quarter.png             ภาพมุม 3/4 (Perspective) เรนเดอร์จาก Blockbench จริง
preview_compare_reference.png    ภาพอ้างอิง (ซ้าย) เทียบกับโมเดลมุมหน้า (ขวา)
preview_blockbench_ui.png        ภาพหน้าจอ Blockbench ที่เปิดไฟล์นี้อยู่ พร้อม Outliner

วิธีเปิดไฟล์
-----------
1. เปิด Blockbench (Desktop 4.10 ขึ้นไป หรือ 5.x หรือ https://web.blockbench.net)
2. File > Open Model แล้วเลือก grim_reaper_scythe.bbmodel
   (หรือลากไฟล์วางในหน้าต่าง Blockbench)
3. โปรเจกต์จะเปิดเป็น "Generic Model"
4. มุมหน้าที่ตรงกับภาพอ้างอิง: View > Camera Angle > South (Numpad 1)

Texture ฝังอยู่ในไฟล์ .bbmodel แล้ว จึงไม่มี Missing texture แม้ย้ายไฟล์ไปที่อื่น
ใน Blockbench Desktop ถ้าวางโฟลเดอร์ textures/ ไว้ข้าง .bbmodel ตามเดิม
Texture จะลิงก์กับ textures/scythe_texture.png (relative path) ด้วย

โครงสร้าง Outliner
------------------
Scythe_Root
  Main_Blade        ใบมีด 1 Mesh (loft 44 ช่วงตามแนวโค้ง, หน้าตัดคมบาง-สันหนา)
  Upper_Frame       โครงหัวเคียว + แกนคอ
  Upper_Horns       เขาโค้งใหญ่ด้านบน, หนามเล็ก, หนามด้านขวา 3 อัน, หนามใต้โคนใบมีด
  Main_Shaft        ด้ามดำ 5 ช่วง + ปลายแหลมด้านล่าง
  Metal_Connectors  ปลอกรัดคอ 2 วง, ลูกปัดสีขาว, ปลอกบานใต้หัว, แหวนปลายด้าม 2 วง
  Head_Chain        โซ่คล้องใบมีด (ห่วงแยกทีละข้อ), โซ่พันรอบคอ, ปลายโซ่ห้อยสั้น
  Hanging_Chain     โซ่ห้อยยาวจากคอลงมา (ห่วงแยกทีละข้อ)
  Chain_Pendant     จี้กางเขนแหลมสีเงิน + ห่วงแขวน

รวม 112 Mesh, ~6,100 faces. ห่วงโซ่ทุกข้อเป็น Mesh วงรีมีรูกลาง หมุนสลับ 90 องศา
ทุกชิ้นตั้งชื่อเป็นภาษาอังกฤษ และแก้ไข/ซ่อน/ย้ายแยกกันได้

ขนาด/พิกัด
----------
- สูงรวม ~71.5 หน่วย Blockbench (Y 0 = ปลายแหลมของด้าม), กว้าง ~50 หน่วย (X -25..25)
- พิกัดทั้งหมดอยู่ในระบบเดียวกัน วัดจากภาพอ้างอิง 1 พิกเซล = 0.12 หน่วย
- ถ้าต้องการขนาดอื่น: เลือก Scythe_Root แล้วใช้ Transform > Scale

การตรวจสอบที่ทำแล้ว
-------------------
- JSON ถูกต้อง, ทุก face มี 3-4 vertices, UV อยู่ในขอบ texture, ทุก element อยู่ใน Outliner
- เปิดไฟล์จริงด้วย Blockbench 5.2.2 (build เว็บจาก source ทางการ รันใน Chromium):
  โหลดเป็น Generic Model, Outliner 9 groups ครบ, 112 meshes, texture โหลดได้ (ไม่มี error),
  ไม่มี face ที่ไม่มี texture, Validator ของ Blockbench: 0 warning / 0 error
- ภาพ preview ทุกภาพถ่ายจาก Blockbench เอง แล้วเทียบ silhouette กับภาพอ้างอิง

ข้อจำกัดที่ยังเหลือ
------------------
- ไม่ได้ทดสอบใน Blockbench Desktop (Electron) โดยตรง ทดสอบใน build เว็บของเวอร์ชัน 5.2.2
  ซึ่งใช้ตัวโหลด .bbmodel ชุดเดียวกัน ไฟล์บันทึกเป็น format 4.10 เพื่อให้เปิดได้ทั้ง 4.10+ และ 5.x
- รูทรงหยดน้ำเล็กๆ บนโครงหัวเคียว (ในภาพอ้างอิงเห็นเป็นช่องสีขาว) ยังไม่ได้เจาะเป็นรู
- แสงเงาสะท้อนสีขาวบนใบมีดทำด้วย texture (ไล่สี) ไม่ใช่ material สะท้อนแสงจริง
- โมเดลเป็น Mesh จึงใช้ได้กับ Generic Model / ส่งออก glTF, OBJ ได้
  ถ้าจะใช้กับ Minecraft Java (block/item model) ต้องแปลงเป็น Cube เพราะ Java ไม่รองรับ Mesh
- ด้านหลังและด้านข้างไม่มีภาพอ้างอิง ความหนาของชิ้นส่วนจึงกำหนดจากสัดส่วนที่สมเหตุสมผล

สร้างใหม่ / แก้ไขด้วยสคริปต์
---------------------------
python3 tools/build_scythe.py
(พิกัดทุกจุดในสคริปต์เป็นพิกเซลของภาพอ้างอิง แก้แล้วรันใหม่ได้ทันที)
