# OLRE Daily Changelog

## 2026-05-20 - Controlled pilot handoff and traversal planning docs refresh

- Added `docs/CURRENT_STATUS_HANDOFF.md` as the recommended new-chat starting document.
- Added `docs/status_v0.9.8_epic3_traversal_planning.md` for Epic 3 Phase 2A status.
- Updated admin guidance from the older `v0.9.7` storage milestone to `release/v0.9.8-controlled-pilot`.
- Updated traversal architecture, policy, and ADR docs to reflect that Phase 2A planning runtime is implemented.
- Reaffirmed that traversal remains planning-only: no downloader, no URL-following traversal, no child document creation, no recursive processing, and no HTML crawling.

## 2026-05-19 - Dynamic release metadata panel

- Added centralized release metadata in `app/release.py`.
- Added release fields to `Settings` with environment overrides:
  `OLRE_APP_VERSION`, `OLRE_RELEASE_NAME`, `OLRE_RELEASE_DATE`, `OLRE_RELEASE_CHANNEL`,
  `OLRE_RELEASE_STATUS`, `OLRE_RELEASE_NOTE`, `OLRE_RELEASE_HIGHLIGHTS`,
  and `OLRE_RELEASE_METADATA_FILE`.
- Added a home/imports release panel that renders only from `release_info`.
- Documented env/file override flow and `.env` examples.
- Added unit and integration coverage for defaults, overrides, highlights parsing, i18n labels,
  and missing metadata handling.

## Current Stable Milestone

Current stable milestone/tag:

```text
release/v0.9.8-controlled-pilot
```

Current architecture progression:

- `v0.9.5` runtime determinism
- `v0.9.6` storage identity and lifecycle foundation
- `v0.9.7` storage boundary integration
- `v0.9.8` controlled pilot: lifecycle registry, ops visibility, release identity, traversal planning runtime

Latest operational verification:

- `APP_ENV=testing uv run pytest` -> `121 passed, 6 warnings` after traversal planning runtime handoff
- `APP_ENV=development uv run ruff check app tests migrations` -> `All checks passed`

Next recommended phase:

```text
operational validation of traversal planning runtime
```

Suggested scope:

- deploy latest branch on Linux server
- rebuild container
- run migration
- verify traversal UI/API
- confirm traversal remains inert
- confirm no downloader side effects
- confirm no child document creation
- confirm lifecycle/ops still stable
- collect pilot operator feedback

Explicit non-goals:

- object storage
- distributed storage
- Kubernetes
- microservices
- queue orchestration
- blob registry/reference counting unless future operational pain justifies it
- automatic recursive traversal
- downloader execution runtime
- background traversal workers
- HTML crawling
- AI/RAG/vector database work

---

# OLRE Daily Changelog - 2026-05-03

## Project

**Official Letter Reference Extractor (OLRE)**

---

## 1. ภาพรวมวันนี้

วันนี้เป็นวันที่เรา "ยกระดับ OLRE" จากระบบที่เริ่มใช้งานได้ ไปสู่ระบบที่ใกล้เคียงผลิตภัณฑ์จริงมากขึ้น โดยไล่ทำเป็น milestone ชัดเจน:

```text
v0.6  OAuth Final Baseline
v0.7  Public Non-OAuth
v0.8  Real-world Reliability
v0.9  Intelligence & Reporting
v0.9.1 Thai UI Localization
v0.9.2 Thai-English Language Switcher
```

สรุปแบบไม่อ้อม:

```text
จากระบบ extract QR/URL
→ กลายเป็นระบบนำเข้าเอกสาร ตรวจจับอ้างอิง วิเคราะห์ผล ส่งออกข้อมูล และรองรับภาษาไทย/อังกฤษ
```

---

## 2. สิ่งที่ทำสำเร็จวันนี้

### 2.1 ปิด milestone OAuth เดิม

เราเริ่มจากการปิดสถานะระบบเดิมที่มี OAuth/login/session/auth integration

**สิ่งที่ทำ**

- ปิดสถานะ OAuth-enabled version
- commit/tag เป็น baseline แยกไว้
- ตั้ง tag:

```text
v0.6-oauth-final
```

**เหตุผล**

เพื่อเก็บระบบเดิมไว้เป็น reference สำหรับกรณีที่ต้องใช้ auth/internal deployment ในอนาคต

**ผลลัพธ์**

- มี OAuth baseline แยกชัดเจน
- ไม่เอา auth เดิมมาปนกับ public version
- สามารถย้อนกลับไปดู version เดิมได้

### 2.2 สร้าง Public Non-OAuth Version

จากนั้นเราเริ่มสายพัฒนาใหม่:

```text
non-oauth-public
```

**สิ่งที่ dev ทำ**

- เพิ่ม config:

```env
ENABLE_AUTH=false
APP_TOKEN=
```

- ปิด MariaDB/session manager เมื่อ auth off
- ไม่ mount `/login`, `/logout` เมื่อ auth ปิด
- route หลักเปิด public:
  - `/imports`
  - `/batch`
  - `/results`
  - `/exports`
- `/` redirect ไป `/imports`
- เพิ่ม optional `X-API-KEY` guard สำหรับ `/batch/process`
- เอา user/login/logout display ออกจาก UI

**Verification**

```text
pytest -> 38 passed
ruff check app tests -> All checks passed
```

**Commit/tag**

```text
commit: feat: introduce non-OAuth public mode (stable)
tag: v0.7-public-beta
```

**ผลลัพธ์**

- ผู้ใช้ทั่วไปเข้าใช้งานได้โดยไม่ต้อง login
- core pipeline ยังเหมือนเดิม
- ระบบเบาขึ้น ใช้ง่ายขึ้น
- เหมาะกับ public/internal lightweight deployment

---

## 3. ปัญหาที่เจอและแก้ไข

### 3.1 Git ไม่รู้จักคำสั่ง

**Error**

```text
'git' is not recognized as an internal or external command
```

**สาเหตุ**

Windows ยังไม่มี Git CLI หรือ Git ไม่อยู่ใน PATH

**แนวทางแก้**

ติดตั้ง Git for Windows และเลือก:

```text
Use Git from the Windows Command Prompt
```

### 3.2 สร้าง venv แล้ว activate ผิด path

**คำสั่งที่ผิด**

```powershell
venv\bin\Activate
```

**สาเหตุ**

เป็น path แบบ Linux/macOS แต่ใช้งาน Windows

**คำสั่งที่ถูก**

```powershell
.venv\Scripts\activate
```

**ผลลัพธ์**

```powershell
(.venv) D:\git\official-letter-reference-extractor>
```

### 3.3 uvicorn ไม่พบ

**Error**

```text
'uvicorn' is not recognized
```

**สาเหตุ**

ยังไม่ได้ติดตั้ง dependency ใน venv

**วิธีแก้**

```powershell
python -m pip install uvicorn
python -m uvicorn app.main:app --reload
```

### 3.4 FastAPI ไม่พบ

**Error**

```text
ModuleNotFoundError: No module named 'fastapi'
```

**สาเหตุ**

ติดตั้งแค่ uvicorn แต่ยังไม่ได้ติดตั้ง dependency หลักของโปรเจ็กต์

**วิธีแก้**

```powershell
python -m pip install .
```

หรือ install dependency ที่ขาดเพิ่มเติม

### 3.5 Database schema ไม่ตรงกับ ORM

**Error**

```text
column documents.processing_error_type does not exist
```

**สาเหตุ**

โค้ด ORM คาดว่า schema มี structured error fields แล้ว แต่ PostgreSQL จริงยังไม่ได้ migrate

**สิ่งที่ dev แก้**

เพิ่ม migration:

```text
20260503_0006_verify_structured_error_fields.py
```

เติม column ที่ขาด:

- `documents.processing_error_type`
- `documents.processing_error_detail`
- `document_references.resolution_error_type`
- `document_references.resolution_error_detail`

**Verification**

```text
alembic current -> 20260503_0006 (head)
pytest -> 42 passed
ruff check app tests migrations -> All checks passed
```

**ผลลัพธ์**

- `/batch/process` ไม่ 500 แล้ว
- schema ตรงกับ ORM
- batch pipeline กลับมาทำงาน

---

## 4. Phase v0.8 - Real-world Reliability

เป้าหมายของ phase นี้คือทำให้ OLRE ใช้กับเอกสารจริงได้ดีขึ้น ไม่ใช่แค่ผ่าน test ในห้องแล็บ

### 4.1 QR Debug Export + Debug UI

**สิ่งที่เพิ่ม**

- เพิ่ม config:

```env
QR_DEBUG_EXPORT=false
QR_DEBUG_DIR=data/debug/qr
```

- เพิ่ม module:

```text
app/batch/qr_debug.py
```

- export ภาพ debug เป็น PNG
- export metadata เป็น JSON sidecar
- mount static path:

```text
/debug/qr
```

- เพิ่มหน้า:

```text
/debug/document/{document_id}
```

- เพิ่มปุ่ม Debug ในหน้า `/results`

**Debug passes ที่รองรับ**

- `full_original`
- `grayscale`
- `upscaled_6x`
- `threshold`
- `adaptive_threshold`
- `bottom_crop`
- `bottom_left`
- `bottom_center`
- `bottom_right`

**ประโยชน์**

จากเดิม:

```text
QR อ่านไม่ได้ → เดาเอาว่าทำไม
```

เป็น:

```text
QR อ่านไม่ได้ → เปิด debug crop ดูได้ว่าภาพพังตรงไหน
```

**ผลลัพธ์**

- ตรวจสอบ QR detection ได้จริง
- เห็น crop/variant ที่ระบบลอง decode
- แยกได้ว่า fail เพราะ crop ไม่โดน, ภาพเบลอ, QR เล็ก, หรือ decoder ไม่ไหว

### 4.2 Retry Failed Documents

**สิ่งที่เพิ่ม**

- เพิ่ม endpoint:

```text
POST /documents/{document_id}/retry
```

- เพิ่ม service:

```text
app/services/retry_service.py
```

- เพิ่มปุ่ม Retry ใน `/results`
- แสดง failed documents ที่ไม่มี references เพื่อให้ retry ได้

**Behavior**

```text
failed document → retry → กลับเข้า input queue → process ใหม่ได้
```

**Safety**

- ไม่ overwrite record เดิม
- ไม่ลบ failed record เดิม
- ถ้าชื่อไฟล์ชนกัน ต้อง rename safely
- ถ้า file missing ต้องแจ้ง error ชัดเจน

**ผลลัพธ์**

- ผู้ใช้ไม่ต้องย้ายไฟล์เอง
- กู้ flow จาก failed case ได้ง่ายขึ้น
- เหมาะกับงานจริงที่เอกสารมีปัญหาบ่อย

### 4.3 Optional QR Fallback Decoder

**สิ่งที่เพิ่ม**

เพิ่ม config:

```env
QR_FALLBACK_DECODER=none
```

รองรับ:

- `none`
- `pyzbar`

**Behavior**

1. OpenCV decode ก่อน
2. ถ้าไม่เจอ และเปิด pyzbar ให้ลอง pyzbar fallback

**ข้อดี**

- ไม่บังคับ dependency
- ถ้า pyzbar/zbar ไม่มี ระบบต้องไม่ crash
- เพิ่มโอกาสอ่าน QR จาก scan จริง

**สถานะ**

- รองรับ fallback แล้ว
- ยังต้องติดตั้ง zbar/pyzbar จริง หากจะใช้งาน

### 4.4 Search / Filter Results

**สิ่งที่เพิ่มใน `/results`**

filter ตาม:

- `filename`
- `processing_status`
- `processing_error_type`
- `source_type`
- `resolution_status`
- `resolution_error_type`
- date range
- URL/domain

**ประโยชน์**

จากเดิม:

```text
มีเอกสารเยอะ → ไล่ดูยาก
```

เป็น:

```text
ค้นหาเฉพาะ failed / QR / URL บาง domain / ช่วงวันที่ ได้
```

### 4.5 Repo Hygiene

**สิ่งที่เพิ่มใน `.gitignore`**

```gitignore
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.env
data/input/
data/processed/
data/error/
data/debug/
.thclaws/sessions/
*.log
```

**สิ่งที่ untrack**

- `.thclaws/sessions`
- `data/debug`

**ผลลัพธ์**

- ลดโอกาส commit runtime artifacts
- ลดความเสี่ยงข้อมูลหลุด
- repo สะอาดขึ้น

### 4.6 Verification v0.8

**Automated**

```text
pytest -> 47 passed
ruff check app tests migrations -> All checks passed
```

**Manual**

ทดสอบ flow:

```text
upload → batch → results → debug → retry
```

**Commit/tag**

```text
commit: feat: improve OLRE real-world reliability (v0.8)
tag: v0.8-real-world-reliability
```

---

## 5. Phase v0.9 - Intelligence & Reporting Layer

เป้าหมายคือทำให้ OLRE ไม่ใช่แค่ extractor แต่กลายเป็นระบบวิเคราะห์ข้อมูล

### 5.1 Dashboard

เพิ่มหน้า:

```text
/dashboard
```

**KPI ที่เพิ่ม**

- Total documents
- Total references
- Processed documents
- Failed documents
- Duplicate documents
- Resolved URLs
- Failed URL resolutions
- QR references
- Text references
- OCR references
- Broken link rate
- OCR usage rate
- QR detection rate

**ประโยชน์**

ผู้ใช้เห็นภาพรวมทันทีว่า:

- นำเข้าเอกสารเท่าไร
- อ่าน reference ได้เท่าไร
- URL เสียกี่รายการ
- เอกสาร fail กี่ฉบับ
- ข้อมูลมาจาก QR/Text/OCR สัดส่วนเท่าไร

### 5.2 Analytics Service Layer

เพิ่ม service:

```text
app/services/analytics_service.py
```

หน้าที่:

- `get_dashboard_summary()`
- `get_domain_summary()`
- `get_reference_source_summary()`
- `get_error_summary()`
- `get_daily_document_trend()`

**ผลลัพธ์**

- logic รายงานแยกจาก route
- test ได้ง่าย
- ต่อ dashboard/BI ได้ง่ายขึ้น

### 5.3 Domain Analytics

**สิ่งที่ทำได้**

สรุป domain จาก:

- `resolved_url`
- `raw_reference`

normalize domain เช่น:

```text
https://example.go.th/path?a=1
→ example.go.th
```

**Metrics**

- domain
- total references
- resolved count
- failed count
- success rate
- source breakdown: text / qr / ocr

**ประโยชน์**

ตอบคำถามแบบนี้ได้:

- เอกสารอ้างอิงเว็บไหนมากที่สุด
- domain ไหน link เสียบ่อย
- QR ส่วนใหญ่พาไป domain อะไร

### 5.4 Daily Trend

เพิ่ม aggregation รายวัน:

- documents per day
- references per day
- failed documents per day
- resolved URLs per day

**ประโยชน์**

ใช้ดู volume งานรายวัน และแนวโน้มความผิดพลาด

### 5.5 Error Analytics

เพิ่ม summary:

- `processing_error_type`
- `processing_error_detail`
- `resolution_error_type`
- `resolution_error_detail`

แสดง:

- Top processing errors
- Top resolution errors
- Recent failed documents
- Recent failed URL resolutions

### 5.6 Quality Report

เพิ่มหน้า:

```text
/quality
```

ตรวจ:

- documents with zero references
- image-only PDFs
- OCR failed documents
- failed documents
- references with failed resolution
- duplicate documents
- documents missing page_count
- references missing resolved_url

**ประโยชน์**

เป็นหน้า "เช็กสุขภาพข้อมูล" ก่อนเอาผลไปใช้งานจริง

### 5.7 Filtered Export

จาก `/results` ถ้ามี filter เช่น:

```text
/results?processing_status=failed&source_type=qr
```

export link จะ preserve filter ไปด้วย:

- CSV
- Markdown
- Excel

**ผลลัพธ์**

- export เฉพาะข้อมูลที่ filter อยู่ได้
- ใช้ทำรายงานเฉพาะกลุ่มง่ายขึ้น

### 5.8 Excel Export

เพิ่ม route:

```text
/exports/excel
```

ใช้:

```text
openpyxl
```

สร้าง `.xlsx` หลาย sheet:

1. Summary
2. Documents
3. References
4. Domains
5. Errors

**ปัญหาที่เจอ**

ตอนแรก export excel แล้ว error:

```text
ModuleNotFoundError: No module named 'openpyxl'
```

**วิธีแก้**

ติดตั้ง dependency:

```powershell
python -m pip install openpyxl
```

และควร ensure ว่า openpyxl อยู่ใน `pyproject.toml`

**ผลลัพธ์**

- Excel export ใช้งานได้
- เปิดไฟล์ได้จริง

### 5.9 Reporting Indexes

เพิ่ม migration:

```text
20260503_0007_add_reporting_indexes.py
```

เป็น additive indexes สำหรับ reporting/search performance

**Verification**

```text
alembic current -> 20260503_0007 (head)
pytest -> 53 passed
ruff check app tests migrations -> All checks passed
```

---

## 6. Phase v0.9.1 - Thai UI Localization

หลังจาก dashboard/results ใช้ได้แล้ว พบว่า UI ภาษาอังกฤษยังไม่เหมาะกับผู้ใช้ทั่วไปในบริบทไทย

### 6.1 สิ่งที่ทำ

เพิ่ม centralized i18n label system:

```text
app/i18n/th.py
app/i18n/en.py
app/web/context.py
```

ปรับ template ให้ใช้ labels:

```jinja
{{ labels.dashboard }}
{{ labels.results }}
{{ labels.quality }}
```

แทนการ hardcode text

### 6.2 หน้าที่ localize

- navigation
- dashboard
- results
- quality
- exports
- debug
- imports
- batch
- batch runs
- batch detail

### 6.3 ตัวอย่างคำแปล

| English | Thai |
| --- | --- |
| Dashboard | แดชบอร์ด |
| Results | ผลการประมวลผล |
| Quality | ตรวจสอบคุณภาพข้อมูล |
| Exports | ส่งออกข้อมูล |
| Batch | ประมวลผลชุด |
| Imports | นำเข้าไฟล์ |
| Apply | ค้นหา |
| Reset | ล้างค่า |
| Retry | ลองใหม่ |
| Debug | ตรวจสอบ |

### 6.4 Status Mapping

backend ยังคงใช้ค่าเดิม:

```text
processed
failed
pending
```

แต่ UI แสดงผลเป็นไทย:

```text
สำเร็จ
ล้มเหลว
รอดำเนินการ
```

**ข้อดี**

- ไม่กระทบ database
- ไม่กระทบ API
- UI อ่านง่ายขึ้น

### 6.5 Verification

```text
pytest -> 53 passed
ruff check app tests migrations -> All checks passed
```

---

## 7. Phase v0.9.2 - Thai-English Language Switcher

หลังจากแปล UI เป็นไทย คำถามสำคัญคือ ถ้าอยากกลับไปใช้ภาษาอังกฤษต้องทำอย่างไร

ดังนั้นจึงเพิ่ม language switcher

### 7.1 สิ่งที่เพิ่ม

เพิ่ม config:

```env
APP_LANG=th
```

เพิ่ม i18n resolver:

```text
app/i18n/__init__.py
```

เพิ่ม logic ใน:

```text
app/web/context.py
```

ให้เลือก labels จาก:

1. cookie `lang`
2. ถ้าไม่มี cookie ให้ใช้ `APP_LANG`

### 7.2 Language Switch Route

เพิ่ม:

```text
POST /settings/language
```

รับ:

```text
lang=th|en
next=/current/path
```

**Behavior**

- ตั้ง cookie `lang`
- redirect กลับหน้าเดิม
- กัน external URL

**Security**

กัน open redirect โดยอนุญาตเฉพาะ relative path ที่ขึ้นต้นด้วย `/`

### 7.3 UI Switcher

เพิ่มปุ่มใน `base.html`:

```text
ไทย | English
```

**Behavior ที่ต้องได้**

- กด English แล้ว UI เปลี่ยนเป็นอังกฤษ
- กด ไทย แล้ว UI กลับเป็นไทย
- อยู่หน้าเดิมหลังเปลี่ยนภาษา

### 7.4 Verification

```text
pytest -> 60 passed
ruff check app tests migrations -> All checks passed
```

---

## 8. สถานะปัจจุบันล่าสุด

### Automated verification ล่าสุด

```text
pytest -> 60 passed
ruff check app tests migrations -> All checks passed
```

### Alembic

```text
head -> 20260503_0007
```

### Features ที่มีแล้ว

- Public non-OAuth mode
- Optional APP_TOKEN guard
- Upload PDF
- Batch process
- Text/QR/OCR extraction pipeline
- URL resolution
- Structured error fields
- Batch monitoring
- Results UI
- CSV/Markdown export
- Excel export
- QR debug export
- QR debug UI
- Retry failed documents
- Search/filter results
- Dashboard KPI
- Domain analytics
- Daily trend
- Error analytics
- Quality report
- Thai UI
- Thai-English language switcher
- Repo hygiene

---

## 9. สิ่งที่ยังขาด / ควรทำต่อ

### 9.1 Manual browser verification ยังต้องทำให้ครบ

หลาย phase ผ่าน automated test แล้ว แต่บางจุดยังควรเปิดดูจริง:

- `/dashboard`
- `/results`
- `/quality`
- `/exports`
- `/imports`
- `/batch`
- `/batch/runs`
- `/debug/document/{id}`

ต้องเช็ค:

- เมนูไทย/อังกฤษทำงาน
- Excel export เปิดได้
- Filter แล้ว export ได้จริง
- Debug image แสดงจริง
- Retry ใช้งานจริง
- ไม่มี raw labels เช่น `{{ labels.xxx }}`

### 9.2 Tesseract ยังไม่ได้ติดตั้งในเครื่องทดสอบ

log ก่อนหน้าพบ:

```text
OCR_FAIL: tesseract is not installed or it's not in your PATH
```

**ผลกระทบ**

image-only PDF จะ OCR ไม่ทำงาน และ `total_refs` อาจเป็น 0

**ต้องทำ**

ติดตั้ง Tesseract OCR บน Windows แล้วเพิ่ม PATH:

```text
C:\Program Files\Tesseract-OCR
```

เช็ค:

```powershell
tesseract --version
```

**เหตุผล**

ถ้ายังไม่ติด Tesseract ระบบยังใช้ได้ แต่ OCR fallback จะไม่สมบูรณ์

### 9.3 pyzbar/zbar fallback ยังต้องทดสอบจริง

ตอนนี้มี config:

```env
QR_FALLBACK_DECODER=none|pyzbar
```

แต่ถ้าจะใช้จริงต้องติดตั้ง runtime dependency:

- pyzbar
- zbar

**งานต่อ**

- ทดสอบ OpenCV fail แล้ว pyzbar ช่วยอ่านได้หรือไม่
- ensure ถ้า zbar ไม่อยู่ ระบบไม่ crash
- เพิ่ม document วิธีติดตั้งบน Windows

### 9.4 Dependency bootstrap ยังควรปรับให้จบ

ระหว่างวันพบปัญหาหลายครั้ง:

- uvicorn ไม่พบ
- pytest ไม่พบ
- ruff ไม่พบ
- openpyxl ไม่พบ
- fastapi ไม่พบ

**สาเหตุ**

dev environment ยังไม่ได้ bootstrap เป็นชุดเดียว

**ควรทำ**

เพิ่มหรือปรับ `pyproject.toml` ให้ครบ:

- fastapi
- uvicorn
- sqlalchemy
- psycopg
- jinja2
- python-multipart
- openpyxl
- pytest
- ruff

และเพิ่ม dev install guide:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

**ผลที่ต้องการ**

```text
clone repo → run one command → dev environment พร้อม
```

### 9.5 README / User Manual ยังควรทำจริงจัง

ตอนนี้ระบบโตเร็วมาก แต่คู่มืออาจตามไม่ทัน

ควรเพิ่ม:

- `README.md`
- `INSTALL_WINDOWS.md`
- `USER_MANUAL_TH.md`
- `ADMIN_GUIDE.md`
- `TROUBLESHOOTING.md`

หัวข้อที่ควรมี:

- ติดตั้ง Python/venv
- ติดตั้ง PostgreSQL
- ตั้งค่า `.env`
- รัน alembic
- รัน server
- นำเข้า PDF
- ประมวลผล batch
- ดูผลลัพธ์
- ใช้ Dashboard
- ส่งออก Excel
- ใช้ Debug
- Retry failed document
- ติดตั้ง Tesseract
- ติดตั้ง pyzbar/zbar

### 9.6 Docker Compose Public Version

ถ้าต้องการให้คนทั่วไปหรือทีม IT deploy ง่ายขึ้น ควรเพิ่ม:

```text
docker-compose.public.yml
```

ประกอบด้วย:

- web app
- postgres
- volume data
- volume debug

เป้าหมาย:

```powershell
docker compose -f docker-compose.public.yml up -d
```

แล้วเปิดใช้งานได้เลย

### 9.7 Backup / Restore

ตอนนี้เริ่มมีข้อมูลจริง:

- documents
- document_references
- batch_runs
- debug artifacts
- exports

ควรเพิ่ม:

- backup database
- restore database
- backup data directory
- retention policy

### 9.8 Security สำหรับ Public Mode

แม้ไม่มี OAuth แล้ว แต่ production ควรมีอย่างน้อย:

- APP_TOKEN สำหรับ batch/process
- file size limit
- allowed file type PDF only
- rate limit upload/process
- safe filename handling
- max upload count

บางอย่างอาจมีแล้วบางส่วน แต่ควร audit เป็นรอบ security hardening

### 9.9 Async Batch Processing

ตอนนี้ batch ยังเหมือน synchronous เป็นหลัก

หากเอกสารเยอะ เช่น PDF 90+ หน้า จะช้าและ block request

ควรทำ phase ถัดไป:

```text
v1.0 Async Batch
```

แนวทาง:

- RQ + Redis
- หรือ Celery + Redis

Flow:

```text
Upload → Queue Job → Worker Process → DB Status → UI Polling
```

### 9.10 Better Progress UI

ควรเพิ่ม:

- Processing progress
- current file
- current page
- success/failed count
- estimated remaining

ตอนนี้ log มีละเอียด แต่ user ยังไม่เห็น progress แบบชัดเจน

### 9.11 Data Retention / Cleanup

QR debug export อาจสร้างไฟล์เยอะมาก

ควรเพิ่ม:

```env
QR_DEBUG_MAX_DAYS=7
QR_DEBUG_MAX_FILES=5000
```

และปุ่ม:

- Clear debug files
- Clear processed files

### 9.12 Production Logging

ควรจัด log ให้เหมาะกับ production:

- request_id
- batch_run_id
- document_id
- duration_ms
- structured JSON logs optional

จะ debug ง่ายขึ้นมากเมื่อใช้จริง

---

## 10. Roadmap แนะนำต่อจากวันนี้

### v0.9.3 - Manual QA & Documentation

- Manual browser verification
- README update
- Windows install guide
- Tesseract install guide
- pyzbar/zbar install guide
- dependency bootstrap fix

### v1.0 - Production Packaging

- Docker compose public deployment
- setup guide
- backup/restore
- environment validation
- healthcheck/readiness

### v1.1 - Async Processing

- RQ/Celery worker
- job queue
- live progress
- cancel/retry job

### v1.2 - Advanced Intelligence

- document categorization
- agency/domain classification
- suspicious/broken link report
- trend analysis
- BI integration

---

## 11. สิ่งที่ต้อง commit/tag ถ้าผ่าน manual verification

### v0.9 Intelligence

```text
tag: v0.9-intelligence-reporting
```

### v0.9.1 Thai UI

```text
tag: v0.9.1-thai-ui
```

### v0.9.2 Language Switcher

```text
tag: v0.9.2-language-switcher
```

ถ้ารวม commit เดียวหรือหลาย commit ขึ้นกับสถานะ git ปัจจุบัน แต่ควรให้ tag ชี้ commit ที่ผ่าน manual verification แล้วเท่านั้น

---

## 12. สรุปสุดท้าย

วันนี้ OLRE ขยับจาก:

```text
ระบบอ่าน QR/URL จาก PDF
```

เป็น:

```text
ระบบจัดการเอกสารอ้างอิงราชการแบบครบวงจร
```

ตอนนี้ระบบมี:

- นำเข้าไฟล์
- ประมวลผล
- ตรวจจับ reference
- resolve URL
- debug QR
- retry failed document
- search/filter
- dashboard
- quality report
- export CSV/Markdown/Excel
- UI ภาษาไทย
- switch ไทย/อังกฤษ

แต่ก่อนจะเรียกว่า production เต็มตัว ยังควรเก็บ:

- manual browser QA
- dependency bootstrap
- Tesseract/OCR setup
- pyzbar/zbar real test
- documentation
- Docker deployment
- backup/restore
- async processing

สรุปแบบบ้าน ๆ:

```text
วันนี้ OLRE ไม่ใช่แค่ "อ่าน QR ได้ไหม" แล้ว
แต่เริ่มกลายเป็น "ระบบงานเอกสารจริง" ที่มี dashboard, export, debug, retry และรองรับผู้ใช้ไทยได้แล้ว
```

---

## 13. Addendum - v0.9.4 SQLite Runtime Option

หลังจาก v0.9.3 QA & Documentation Baseline เราแยก phase ใหม่เพื่อทำให้ OLRE ใช้งานง่ายขึ้นสำหรับเครื่องทั่วไปและเตรียมไปสู่ public/container distribution

### 13.1 เป้าหมาย

เพิ่ม SQLite เป็น runtime database option โดยไม่ลบ PostgreSQL support เดิม

```text
tag: v0.9.4-sqlite-runtime-option
commit: 60ef66f feat: add SQLite runtime database option
```

### 13.2 สิ่งที่เพิ่ม

- เพิ่ม `DATABASE_URL` เป็น source of truth สำหรับ database runtime
- default lightweight runtime:

```env
DATABASE_URL=sqlite:///data/olre.sqlite3
```

- PostgreSQL ยังใช้ได้ผ่าน:

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
```

- เพิ่ม central database engine/session wiring
- ปรับ Alembic ให้อ่าน config เดียวกับ app
- ปรับ migration เก่าให้สร้าง schema บน SQLite ได้
- เพิ่ม `/healthz` ให้แสดง backend:

```json
{"status":"ok","database_backend":"sqlite"}
```

### 13.3 SQLite Runtime Hardening

เมื่อใช้ SQLite ระบบเปิด PRAGMA:

```text
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

### 13.4 Verification

ยืนยันแล้วว่า:

- `python -m alembic upgrade head` สร้าง SQLite schema ได้ถึง `20260503_0007 (head)`
- app start ด้วย SQLite ได้
- upload PDF แล้ว batch process เขียนข้อมูลลง `data/olre.sqlite3` จริง
- query SQLite เห็นข้อมูลใน `documents`
- `/results` แสดงเอกสารจาก SQLite
- export CSV/Markdown/Excel ยังทำงาน
- PostgreSQL compatibility ยังไม่ถูกลบ

### 13.5 เอกสารที่เพิ่ม/ปรับ

- `docs/SQLITE_RUNTIME.md`
- `docs/BACKUP_RESTORE.md`
- `docs/RELEASE_NOTES_v0.9.4.md`
- `docs/QA_SQLITE_RUNTIME_v0.9.4.md`
- ปรับ `README.md`
- ปรับ `docs/INSTALL_WINDOWS.md`
- ปรับ `docs/ADMIN_GUIDE.md`
- ปรับ `docs/TROUBLESHOOTING.md`
- ปรับ `docs/USER_MANUAL_TH.md`

### 13.6 ข้อจำกัด

SQLite เหมาะกับงานเล็ก เครื่องเดียว หรือ deployment แบบง่าย แต่ยังเป็น single-writer database หากใช้งาน concurrent หนักหรือหลายผู้ใช้พร้อมกันมาก ควรใช้ PostgreSQL ต่อไป

---

## 14. Addendum - v0.9.8 Epic 2 Phase 1 Runtime Introspection

เพิ่ม foundation สำหรับ runtime introspection และ diagnostics แบบ read-only โดยยังคงข้อจำกัดเดิมของ OLRE:

- synchronous
- SQLite-compatible
- deterministic
- ไม่เพิ่ม event bus / distributed queue / background reconciliation

สิ่งที่เพิ่ม:

- `app/ops` module
- `GET /ops/runtime`
- `GET /ops/storage/orphans`
- `GET /ops/lifecycle/consistency-summary`
- `GET /ops`
- runtime snapshot พร้อม redacted database target
- storage orphan summary แบบ count + sample
- lifecycle consistency aggregate summary แบบ defensive scan limit

สิ่งที่ยังไม่ทำ:

- auto repair
- delete/quarantine workflow
- scheduled reconciliation
- telemetry/dashboard platform

การยืนยันเบื้องต้น:

```text
APP_ENV=development uv run ruff check app tests migrations -> All checks passed
APP_ENV=testing uv run pytest tests/unit/test_ops_runtime.py tests/unit/test_ops_orphan_detection.py tests/unit/test_ops_diagnostics.py tests/integration/test_ops_flow.py -> 5 passed
```
