# Project Overview — IMEI Toolkit (Qualcomm 9008 / Firehose · MediaTek MCT · Apple)
# خلاصه پروژه — IMEI Toolkit (Qualcomm 9008 / Firehose · MediaTek MCT · Apple)

> This file describes what the tool **does**, what it **does not do**, and
> which **features could be added** next. Written in English and Persian.
>
> این فایل توضیح می‌دهد که این ابزار **چه کارهایی را انجام می‌دهد**، **چه کارهایی
> را انجام نمی‌دهد** و **چه امکاناتی می‌تواند در آینده اضافه شود**. به دو زبان
> انگلیسی و فارسی نوشته شده است.

---

## 1. What it DOES / کارهایی که انجام می‌دهد

| # | English | فارسی |
|---|---------|-------|
| 1 | Connects to a Qualcomm phone in **9008/EDL mode** over USB (device `05c6:9008`) | اتصال به گوشی Qualcomm در حالت **9008/EDL** از طریق USB (دستگاه `05c6:9008`) |
| 2 | Performs the **Sahara handshake** and loads a **Firehose programmer** (`.mbn`/`.elf`) | انجام دست‌زدن **Sahara** و بارگذاری **programmer** با پروتکل **Firehose** (فایل `.mbn`/`.elf`) |
| 3 | Speaks the full **Firehose binary protocol** (NOOP, GO, READ/WRITE memory, file ops, NVRAM ops, FLUSH, …) | صحبت با تمام پروتکل باینری **Firehose** (فرمان‌های NOOP, GO, خواندن/نویسندگی حافظه، عملیات فایل، عملیات NVRAM، FLUSH و …) |
| 4 | **Reads the IMEIs** (IMEI1 & IMEI2) directly from the **modem NVRAM** | **خواندن IMEIها** (IMEI1 و IMEI2) مستقیماً از **NVRAM مودم** |
| 5 | **Writes IMEIs**, **auto-computes the Luhn check digit** and validates the result | **نوشتن IMEI**، **محاسبه خودکار رقم کنترل Luhn** و اعتبارسنجی نتیجه |
| 6 | **Verifies the write** by reading the IMEI back and comparing it | **تأیید نوشتن** با خواندن دوباره IMEI و مقایسه آن |
| 7 | Supports **4 IMEI storage formats**: `le84`, `ascii`, `rev`, `u32` | پشتیبانی از **۴ فرمت ذخیره IMEI**: `le84`، `ascii`، `rev`، `u32` |
| 8 | Lets you change the **NVRAM item index** and **format** per programmer | امکان تغییر **شماره آیتم NVRAM** و **فرمت** برای هر programmer |
| 9 | **Fake-device test mode** — runs the whole protocol in-memory, no phone needed | **حالت آزمایش دستگاه مجازی** — اجرای کل پروتکل در حافظه، بدون نیاز به گوشی |
| 10 | **Self-test** that verifies the full Sahara→Firehose→NVRAM round-trip | **تست خودکار** که کل مسیر Sahara→Firehose→NVRAM را بررسی می‌کند |
| 11 | **GUI** (tkinter) with a log panel, browse dialog, and clear error messages | **رابط گرافیکی** (tkinter) با پنل لاگ، دیالوگ انتخاب فایل و پیام‌های خطای روشن |
| 12 | **No root, no Android shell** — talks to the modem directly | **بدون روت و بدون shell اندروید** — مستقیماً با مودم صحبت می‌کند |
| 13 | Works headless (CLI) as well as through the GUI | هم بدون رابط گرافیکی (CLI) و هم از طریق GUI کار می‌کند |
| 14 | **Multi-SIM: 2, 3, or 4 IMEI slots** with per-slot item index and format | **چند-SIM: ۲، ۳ یا ۴ اسلات IMEI** با آیتم و فرمت جداگانه برای هر اسلات |
| 15 | **MediaTek/Unisoc MCT protocol** (NV + AGDB items) for MTK phones in preloader mode | **پروتکل MCT مخصوص MediaTek/Unisoc** (آیتم‌های NV و AGDB) برای گوشی‌های MTK در حالت preloader |
| 16 | **Apple/iPhone support**: reads via `pyim`, write is best-effort (pluggable writer) | **پشتیبانی Apple/iPhone**: خواندن با `pyim`، نوشتن به‌صورت best-effort (قابل اتصال writer) |
| 17 | **Luhn auto-fix**: a 14-digit IMEI body gets its correct check digit | **اصلاح خودکار Luhn**: بدنه ۱۴رقمی IMEI، رقم کنترل صحیح را به‌دست می‌آورد |
| 18 | **Auto-detect storage format** (le84/ascii/rev/u32) from raw NVRAM bytes | **تشخیص خودکار فرمت ذخیره** (le84/ascii/rev/u32) از بایت‌های خام NVRAM |
| 19 | **TAC parse → device maker** + display formats (3x3, TAC style, plain) | **پارس TAC → سازنده دستگاه** + فرمت‌های نمایش (3x3، سبک TAC، ساده) |
| 20 | **Generate a valid IMEI** from a TAC + serial number | **ساخت IMEI معتبر** از روی TAC + شماره سریال |
| 21 | **JSON backup/restore** of all IMEI slots, and **CSV import/export** | **بکاپ/رستور JSON** از همه اسلات‌های IMEI، و **وارد/خروجی CSV** |
| 22 | **Persistent operation history** (`history.jsonl`) + in-app log panel | **سابقه ماندگار عملیات** (`history.jsonl`) + پنل لاگ داخل برنامه |
| 23 | **Read-only / write-lock mode** for safe inspection | **حالت فقط-خواندنی / قفل نوشتن** برای بازرسی امن |
| 24 | **Headless CLI** (`cli.py`) for batch/scripting: read, write, backup, restore, CSV, validate, parse, generate | **CLI بدون رابط** (`cli.py`) برای پردازش گروهی/اسکریپت: خواندن، نوشتن، بکاپ، رستور، CSV، اعتبارسنجی، پارس، ساخت |
| 25 | **Standalone .exe** build via PyInstaller (`build_exe.bat`), no Python needed | **ساخت `.exe` مستقل** با PyInstaller (`build_exe.bat`)، بدون نیاز به Python |
| 26 | **Unified Backend API** — GUI and CLI treat all three families identically | **API یکپارچه Backend** — GUI و CLI هر سه خانواده را به یک شکل می‌بینند |
| 27 | **Samsung Exynos variants (S7–S24)** — Exynos SoCs are paired with a separate Qualcomm MDM/X modem, so the same 9008/Firehose path works; just use the per-model Exynos programmer (`.mbn`) | **نسخه‌های Exynos سامسونگ (S7 تا S24)** — پردازنده‌های Exynos همراه با یک مودم جداگانه Qualcomm (MDM/X) هستند، پس همان مسیر 9008/Firehose کار می‌کند؛ فقط از programmer مخصوص همان مدل (`.mbn`) استفاده کنید |

---

## 2. What it does NOT do / کارهایی که انجام نمی‌دهد

| # | English | فارسی |
|---|---------|-------|
| 1 | **Cannot put the phone into 9008/EDL or MCT/preloader mode by itself** — you must use `adb reboot edl`, a test-point short, or `fastboot oem edl` (Qualcomm) / preloader mode (MediaTek) first | **خود گوشی را به حالت 9008/EDL یا preloader نمی‌کند** — باید اول با `adb reboot edl` یا کوتاه کردن test-point (Qualcomm) یا حالت preloader (MediaTek) انجام شود |
| 2 | **No full EFS / modem-filesystem backup or restore** — it only touches the IMEI NVRAM items, not the whole modem filesystem | **بکاپ یا رستور کامل EFS / filesystem مودم ندارد** — فقط آیتم‌های NVRAM مربوط به IMEI را لمس می‌کند، نه کل filesystem مودم |
| 3 | **No full flash (firmware update)** — it can `load_file`/`write_file`, but there is no `firehose.xml`-driven full-flash automation | **فلش کامل (آپدیت فرم‌افور) ندارد** — می‌تواند `load_file`/`write_file` بکند، اما اتوماسیون فلش کامل مبتنی بر `firehose.xml` ندارد |
| 4 | **No IMEI extraction from a donor phone's EFS** — you must already know the IMEI you want to write | **استخراج IMEI از EFS گوشی اهدایی ندارد** — باید IMEI موردنظر را از قبل داشته باشید |
| 5 | **Apple write is best-effort only** — iPhone restricts IMEI writing; a writer (e.g. iTunes restore with IMEI) must be plugged in | **نوشتن در iPhone فقط best-effort است** — iPhone نوشتن IMEI را محدود می‌کند؛ باید writer (مثلاً Restore در iTunes با IMEI) وصل شود |
| 6 | **No carrier/band data (CDMA, PLMN, etc.)** handling — only IMEIs | **مدیریت دیتای اپراتور/باند (CDMA, PLMN و…) ندارد** — فقط IMEIها |
| 7 | **No USB hot-plug / auto-reconnect** — if the USB drops, you must reconnect manually | **hot-plug / اتصال مجدد خودکار USB ندارد** — اگر USB قطع شود، باید دستی دوباره وصل شوید |
| 8 | **No GSMA TAC validation** — it checks Luhn + a coarse TAC→maker map, not the official GSMA TAC database | **اعتبارسنجی TAC نسبت به GSMA ندارد** — فقط Luhn و یک نقشه درشت TAC→سازنده را چک می‌کند، نه بانک رسمی GSMA |
| 9 | **One phone at a time** — CSV enables batch IMEIs, but you still connect one device at a time | **هر بار یک گوشی** — CSV پردازش گروهی IMEIها را ممکن می‌کند، اما باز هم هر بار یک دستگاه متصل می‌شود |
| 10 | **Fully-integrated-SoC phones without a Qualcomm modem** (rare, older/budget Exynos basebands) — they don't speak Firehose; use Samsung download mode (ODIN) or a repair box for those | **گوشی‌هایی که مودم Qualcomm جدا ندارند** (کمیاب؛ Exynos‌های قدیمی/ارزان) — با Firehose صحبت نمی‌کنند؛ برای آن‌ها از حالت download سامسونگ (ODIN) یا تعمیر‌کس استفاده کنید |

---

## 3. Features we CAN add / امکاناتی که می‌توان اضافه کرد

> Items marked ✅ are already implemented in this codebase.
> مواردی که ✅ دارند، در همین کد پیاده‌سازی شده‌اند.

| # | Feature | English | فارسی |
|---|---------|---------|-------|
| 1 | ✅ **Auto-detect storage format** | `auto_detect()` tries le84/ascii/rev/u32 until a Luhn-valid IMEI is found | ✅ **تشخیص خودکار فرمت ذخیره** — امتحان le84/ascii/rev/u32 تا IMEI معتبر Luhn پیدا شود |
| 2 | **Full EFS backup & restore** | Dump all NVRAM items to a file, and restore them later — protects the whole modem filesystem, not just IMEIs | **بکاپ و رستور کامل EFS** — ذخیره همه آیتم‌های NVRAM در یک فایل و رستور دوباره — کل filesystem مودم حفظ می‌شود، نه فقط IMEIها |
| 3 | **Auto 9008/preloader entry** | Call `adb reboot edl` (or `fastboot oem edl`) from the GUI so the phone enters 9008 automatically | **ورود خودکار به 9008/preloader** — فراخوانی `adb reboot edl` (یا `fastboot oem edl`) از GUI تا گوشی خودکار وارد حالت بوت شود |
| 4 | **Programmer file library** | A built-in catalog of Firehose programmers indexed by SoC/model, with one-click selection | **کتابخانه فایل‌های programmer** — فهرست داخلی از programmerهای Firehose طبق SoC/مدل، با انتخاب یک‌کلیکی |
| 5 | ✅ **Standalone `.exe`** | `build_exe.py`/`build_exe.bat` package the GUI with PyInstaller, no Python needed | ✅ **`.exe` مستقل** — `build_exe.py`/`build_exe.bat` با PyInstaller، بدون نیاز به Python |
| 6 | ✅ **TAC / IMEI body editor** | `generate --tac --serial` builds the full 15-digit Luhn-valid IMEI for you | ✅ **ساخت IMEI از TAC** — `generate --tac --serial` کل IMEI ۱۵رقمی معتبر Luhn را می‌سازد |
| 7 | **GSMA TAC validation** | Check the TAC against the official GSMA TAC database (current map is coarse 2-digit prefixes) | **اعتبارسنجی TAC نسبت به GSMA** — بررسی TAC در بانک رسمی GSMA (نقشه فعلی فقط پیشوند ۲رقمی است) |
| 8 | ✅ **File logging & history** | `history.jsonl` persists every operation with a timestamp; in-app log panel | ✅ **لاگ به فایل و سابقه** — `history.jsonl` همه عملیات را با زمان ثبت می‌کند + پنل لاگ |
| 9 | ✅ **MediaTek (MCT) support** | MCT NV/AGDB protocol implemented with the same unified Backend API | ✅ **پشتیبانی MediaTek (MCT)** — پروتکل NV/AGDB با همان API یکپارچه Backend |
| 10 | ✅ **More IMEI slots** | 2/3/4 SIM slots with per-slot item and format | ✅ **اسلات‌های بیشتر IMEI** — ۲/۳/۴ اسلات با آیتم و فرمت جداگانه |
| 11 | **Drag-and-drop programmer file** | Drop the `.mbn`/`.elf` onto the window instead of using the Browse dialog | **کشیدن و رها کردن فایل programmer** — کشیدن فایل `.mbn`/`.elf` روی پنجره به‌جای دیالوگ Browse |
| 12 | **USB timeout / auto-retry** | Retry a read/write a few times on transient USB hiccups before failing | **تایم‌اوت / تلاش مجدد USB** — چند بار تلاش دوباره برای خواندن/نوشتن در صورت خطای گذرای USB |
| 13 | ✅ **Read-only / lock mode** | a GUI checkbox blocks all writes for safe inspection | ✅ **حالت فقط-خواندنی / قفل** — یک گزینه در GUI همه نوشتن‌ها را برای بازرسی امن قفل می‌کند |
| 14 | ✅ **Import IMEIs from CSV** | `csv-import` loads target IMEIs and writes them to the device | ✅ **وارد کردن IMEIها از CSV** — `csv-import` IMEIهای مقصد را می‌خواند و در دستگاه می‌نویسد |
| 15 | **EFS checksum verification** | Verify the written NVRAM bytes match what was intended (catches partial writes) | **بررسی چک‌سوم EFS** — تأیید اینکه بایت‌های نوشته‌شده در NVRAM با آنچه می‌خواستید یکی هستند (نویسندگی ناقص را پیدا می‌کند) |
| 16 | ✅ **Headless / repair-shop mode** | `cli.py` — console-only, scriptable, no GUI | ✅ **حالت بدون-رابط / حالت تعمیرگاه** — `cli.py` — کنسولی، قابل اسکریپت، بدون GUI |
| 17 | **Carrier / band data** | Read and write PLMN, CDMA, band-lock, and other carrier-specific NVRAM items | **دیتای اپراتور / باند** — خواندن و نوشتن PLMN، CDMA، قفل باند و سایر آیتم‌های NVRAM اختصاصی اپراتور |
| 18 | **Apple write path** | Wire a real writer (iTunes restore-with-IMEI or an Apple-specific tool) into `AppleBackend.writer` | **مسیر نوشتن Apple** — اتصال یک writer واقعی (Restore در iTunes با IMEI یا ابزار اختصاصی Apple) به `AppleBackend.writer` |

---

> **Libraries used (usage + GitHub): see [`LIBRARIES.md`](LIBRARIES.md)**
> **کتابخانه‌های استفاده‌شده (کاربرد + آدرس GitHub): فایل [`LIBRARIES.md`](LIBRARIES.md)**

## Quick start / شروع سریع

```
# 1. Install
pip install -r requirements.txt

# 2. Self-test (no phone needed)
"C:\Program Files\Python312\python.exe" test_protocol.py

# 3. GUI
run.bat

# 4. Headless CLI (fake mode needs no phone)
"C:\Program Files\Python312\python.exe" cli.py --family firehose --mode fake --fake read
"C:\Program Files\Python312\python.exe" cli.py --family firehose --mode fake --fake write --imei 353555001400006
"C:\Program Files\Python312\python.exe" cli.py --family mct --mode fake --fake read
"C:\Program Files\Python312\python.exe" cli.py --family apple --mode fake --fake read
"C:\Program Files\Python312\python.exe" cli.py parse --imei 353555001400006
"C:\Program Files\Python312\python.exe" cli.py validate 353555001400008        # auto-fixes Luhn
"C:\Program Files\Python312\python.exe" cli.py generate --tac 353555 --serial 00140000
"C:\Program Files\Python312\python.exe" cli.py backup --family firehose --mode fake --fake --out backup.json
"C:\Program Files\Python312\python.exe" cli.py csv-export --family firehose --mode fake --fake --out imeis.csv

# 5. Standalone .exe (no Python needed at runtime)
build_exe.bat        # -> dist\imei-toolkit\imei-toolkit.exe
```

```
# ۱. نصب
pip install -r requirements.txt

# ۲. تست خودکار (بدون نیاز به گوشی)
"C:\Program Files\Python312\python.exe" test_protocol.py

# ۳. رابط گرافیکی
run.bat

# ۴. حالت CLI بدون رابط (حالت fake نیاز به گوشی ندارد)
"C:\Program Files\Python312\python.exe" cli.py --family firehose --mode fake --fake read
"C:\Program Files\Python312\python.exe" cli.py --family firehose --mode fake --fake write --imei 353555001400006
"C:\Program Files\Python312\python.exe" cli.py --family mct --mode fake --fake read
"C:\Program Files\Python312\python.exe" cli.py --family apple --mode fake --fake read
"C:\Program Files\Python312\python.exe" cli.py parse --imei 353555001400006
"C:\Program Files\Python312\python.exe" cli.py validate 353555001400008        # اصلاح خودکار Luhn
"C:\Program Files\Python312\python.exe" cli.py generate --tac 353555 --serial 00140000
"C:\Program Files\Python312\python.exe" cli.py backup --family firehose --mode fake --fake --out backup.json
"C:\Program Files\Python312\python.exe" cli.py csv-export --family firehose --mode fake --fake --out imeis.csv

# ۵. ساخت .exe مستقل (در زمان اجرا Python لازم نیست)
build_exe.bat        # -> dist\imei-toolkit\imei-toolkit.exe
```
