GRIM REAPER SCYTHE - Blockbench model (v2)
==========================================

v2 สร้างใหม่ทั้งหมดจากภาพอ้างอิงความละเอียดสูง (1075x1463, มีพื้นหลังโปร่งใส)
ไฟล์ภาพอ้างอิงเก็บไว้ที่ tools/reference/scythe_reference.png

ไฟล์ในโฟลเดอร์นี้
-----------------
grim_reaper_scythe.bbmodel        ไฟล์โปรเจกต์ Blockbench (ไฟล์หลัก)
textures/scythe_texture.png       Texture atlas 512x512 (ฝังอยู่ใน .bbmodel ด้วย)
preview_front.png                 มุมหน้า (Orthographic, กล้อง South) เรนเดอร์จาก Blockbench
preview_3quarter.png              มุม 3/4 เรนเดอร์จาก Blockbench
preview_compare_reference.png     ภาพอ้างอิง (ซ้าย) เทียบกับโมเดลมุมหน้า (ขวา)
preview_head_closeup.png          ภาพซูมหัวเคียว/โซ่/คริสตัล จาก Blockbench
preview_blockbench_ui.png         หน้าจอ Blockbench ที่เปิดไฟล์นี้ พร้อม Outliner
preview_blender_front.png         เรนเดอร์ด้วย Blender (Cycles) จากเรขาคณิตชุดเดียวกัน
preview_blender_3quarter.png      เรนเดอร์ Blender มุม 3/4

วิธีเปิดไฟล์
-----------
1. เปิด Blockbench (Desktop 4.10 ขึ้นไป หรือ 5.x หรือ https://web.blockbench.net
   ซึ่งเปิดในเบราว์เซอร์มือถือ/แท็บเล็ตได้)
2. File > Open Model แล้วเลือก grim_reaper_scythe.bbmodel (หรือลากไฟล์วาง)
3. โปรเจกต์เปิดเป็น "Generic Model"
4. มุมหน้าที่ตรงกับภาพอ้างอิง: View > Camera Angle > South (Numpad 1)

Texture ฝังอยู่ในไฟล์ .bbmodel แล้ว จึงไม่ขึ้น Missing texture แม้ย้ายไฟล์ไปที่อื่น

โครงสร้าง Outliner
------------------
Scythe_Root
  Main_Blade        ใบมีด: ผิวดำเงา + คมเงิน (bevel) แยกชิ้นผิว ทำให้เส้นคมชัด
                    รูปร่างและความกว้างคมวัดจากภาพอ้างอิงทีละคอลัมน์
  Upper_Frame       แผ่นหัวเคียวทรงปีกค้างคาว (มีรูหยดน้ำ, ติ่งโค้ง, หนามใต้โคน) + แกนตั้ง
  Upper_Horns       เขาโค้งใหญ่ด้านบน + หนามชี้ซ้าย + หนามด้านขวา + ดาวสีเงินบนเขา
  Main_Shaft        ด้ามดำ + ปลายด้ามแบบปล้องนูน 3 ปล้อง + ปลายแหลม
  Metal_Connectors  แหวนรัดแกน 3 วง, ด้ามจับพันพร้อมหมุดดาว, คริสตัลเจียระไน,
                    ข้อต่อคดใต้คริสตัล, กรงลวดรูปข้าวหลามตัด, ปลอกรัดด้าม, หมุดดาวปลายด้าม
  Head_Chain        โซ่คล้องสันใบมีด, โซ่พันรอบด้ามจับ, โซ่จากด้ามจับลงไปที่กรงลวด,
                    โซ่สั้นห้อยข้างใบมีด
  Hanging_Chain     โซ่ยาวห้อยลงจากกรงลวด
  Chain_Pendant     จี้กางเขนแหลมสีเงิน (มีอัญมณีดำตรงกลาง) + จี้หนามคู่ที่โซ่สั้น

รวม 93 Mesh ประมาณ 11,300 faces ห่วงโซ่ทุกข้อเป็น Mesh วงรีมีรูกลาง หมุนสลับ 90 องศา
ทุกชิ้นตั้งชื่อเป็นภาษาอังกฤษ และแก้ไข/ซ่อน/ย้ายแยกกันได้

ขนาด/พิกัด
----------
- สูงรวม ~71 หน่วย Blockbench (Y 0 = ปลายแหลมของด้าม), กว้าง ~51 หน่วย
- 1 พิกเซลของภาพอ้างอิง = 0.05 หน่วย พิกัดทุกชิ้นอยู่ในระบบเดียวกัน
- ต้องการขนาดอื่น: เลือก Scythe_Root แล้วใช้ Transform > Scale

การตรวจสอบที่ทำแล้ว
-------------------
- JSON ถูกต้อง, ทุก face มี 3-4 vertices, UV อยู่ในขอบ texture, ทุก element อยู่ใน Outliner
- เปิดไฟล์จริงด้วย Blockbench 5.2.2 (build จาก source ทางการ รันบน Chromium ในเซิร์ฟเวอร์):
  โหลดเป็น Generic Model, Outliner 9 groups ครบ, 93 meshes, texture โหลดได้,
  ไม่มี face ที่ไม่มี texture, Validator ของ Blockbench: 0 warning / 0 error
- ภาพ preview_*.png ของ Blockbench ถ่ายจากโปรแกรมเอง แล้วเทียบ silhouette กับภาพอ้างอิง

ข้อจำกัดที่ยังเหลือ
------------------
- ทดสอบใน Blockbench 5.2.2 เวอร์ชันเว็บ (ตัวโหลด .bbmodel ชุดเดียวกับ Desktop)
  ยังไม่ได้เปิดใน Blockbench Desktop บนเครื่องจริง ไฟล์บันทึกเป็น format 4.10
- ความเงาแบบโลหะในภาพอ้างอิงทำด้วย texture (Blockbench ไม่มี material สะท้อนแสงจริง)
  ภาพ Blender ใช้ material โลหะจึงดูเงากว่าในหน้าต่าง Blockbench
- ส่วนที่ภาพอ้างอิงถูกโซ่บัง (ขอบล่างของแผ่นหัวเคียว) ประมาณรูปร่างเอา
- ไม่มีภาพด้านข้าง/ด้านหลัง ความหนาของชิ้นส่วนจึงกำหนดจากสัดส่วนที่สมเหตุสมผล
- เป็น Mesh จึงใช้กับ Generic Model / ส่งออก glTF, OBJ ได้
  ถ้าจะใช้เป็น Minecraft Java block/item model ต้องแปลงเป็น Cube (Java ไม่รองรับ Mesh)

สร้างใหม่ / แก้ไขด้วยสคริปต์
---------------------------
python3 tools/build_scythe.py                 (ต้องมี numpy, pillow, scipy, opencv-python)
python3 tools/render_blender.py Output/grim_reaper_scythe.bbmodel Output   (ต้องมี bpy)
