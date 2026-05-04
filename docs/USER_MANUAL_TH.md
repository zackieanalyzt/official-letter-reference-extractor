# คู่มือผู้ใช้ OLRE

คู่มือนี้อธิบายการใช้งาน OLRE สำหรับผู้ใช้ทั่วไป ตั้งแต่นำเข้า PDF จนถึงดูผลและส่งออกข้อมูล

## เปิดระบบ

เปิด browser ไปที่:

```text
http://127.0.0.1:8000/imports
```

ถ้าระบบตั้งค่า public mode แล้ว ผู้ใช้เข้าได้โดยไม่ต้อง login

## นำเข้า PDF

1. ไปที่เมนู `นำเข้าไฟล์`
2. เลือกไฟล์ PDF หนึ่งไฟล์หรือหลายไฟล์
3. กด upload
4. ตรวจว่ารายชื่อไฟล์อยู่ใน inbox

ระบบรองรับเฉพาะไฟล์ `.pdf`

## ประมวลผล Batch

1. ไปที่เมนู `ประมวลผลชุด`
2. ตรวจจำนวนไฟล์รอดำเนินการ
3. กดปุ่มเริ่มประมวลผล
4. รอจนระบบแสดง summary

ระบบจะอ่าน text layer, QR code, และ OCR fallback เมื่อเปิดใช้งาน OCR

## ดูผลลัพธ์

ไปที่เมนู `ผลการประมวลผล`

ข้อมูลที่เห็นประกอบด้วย:

- ชื่อไฟล์
- สถานะเอกสาร
- reference ที่พบ
- source type เช่น text, qr, ocr
- URL ที่ resolve แล้ว
- สถานะการ resolve
- error type ถ้ามี

## Filter และ Search

ในหน้า `ผลการประมวลผล` สามารถกรองข้อมูลได้ เช่น:

- ชื่อไฟล์
- สถานะเอกสาร
- source type
- error type
- domain
- ช่วงวันที่

หลัง filter แล้ว export จะใช้ filter เดียวกัน

## ส่งออกข้อมูล

ไปที่เมนู `ส่งออกข้อมูล` หรือใช้ปุ่ม export จากหน้า results

รูปแบบที่รองรับ:

- CSV
- Markdown
- Excel

Excel export มีหลาย sheet เช่น Summary, Documents, References, Domains, Errors

## Dashboard

หน้า `แดชบอร์ด` แสดงภาพรวม เช่น:

- จำนวนเอกสารทั้งหมด
- จำนวน references
- เอกสารสำเร็จและล้มเหลว
- QR/Text/OCR references
- broken link rate
- OCR usage rate
- QR detection rate

## Quality Report

หน้า `ตรวจสอบคุณภาพข้อมูล` ใช้ดูข้อมูลที่ควรตรวจเพิ่ม เช่น:

- เอกสารที่ไม่พบ reference
- image-only PDF
- OCR failed
- failed documents
- failed URL resolution
- duplicate documents
- เอกสารที่ไม่มี page count

## Debug QR

ถ้า admin เปิด:

```env
QR_DEBUG_EXPORT=true
```

ระบบจะบันทึกภาพ debug ของ QR แล้วดูได้ที่หน้า:

```text
/debug/document/{document_id}
```

ใช้ตรวจว่า QR อ่านไม่ได้เพราะ crop ไม่โดน, ภาพเบลอ, QR เล็ก, หรือ decoder อ่านไม่ได้

## Retry Failed Document

ในหน้า results ถ้าเอกสารล้มเหลวและ retry ได้ ให้กด `ลองใหม่`

ระบบจะนำไฟล์กลับเข้า inbox โดยไม่ลบ record เดิม ถ้าไฟล์ต้นทางหาย ระบบจะแสดง error ที่เข้าใจได้แทน traceback

## เปลี่ยนภาษา

กด `ไทย` หรือ `English` บริเวณแถบเมนู

หลังเปลี่ยนภาษา ระบบจะอยู่หน้าเดิมและจำค่าผ่าน cookie `lang`
