# کتابخانه‌های مورد استفاده در پروژه
# (Libraries used in this project — with usage and GitHub addresses)

> این فایل لیست کامل کتابخانه‌هایی است که کد پروژه از آن‌ها استفاده می‌کند،
> محل استفاده و آدرس GitHub هرکدام را نشان می‌دهد.
>
> This file lists every library the project uses, where each one is used, and
> its GitHub address.

---

## ۱. کتابخانه‌های خارجی (نیاز به `pip install`)

فقط **سه** کتابخانه خارجی در این پروژه استفاده شده است:

| کتابخانه | نام در PyPI | محل استفاده | GitHub |
|---|---|---|---|
| **pyusb** | `pyusb` | `protocol/transport.py`، `protocol/mct.py` | [trezbot/pyusb](https://github.com/trezbot/pyusb) |
| **PyInstaller** | `pyinstaller` | `build_exe.py` | [pyinstaller/pyinstaller](https://github.com/pyinstaller/pyinstaller) |
| **pyim** (اختیاری) | `pyim` | `main.py` و `cli.py` (فقط حالت Apple/USB) | [صفحه PyPI](https://pypi.org/project/pyim/) — آدرس GitHub رسمی تأیید نشده (چند بسته هم‌نام دارد) |

### pyusb
- **کاربرد:** ارتباط مستقیم با گوشی از طریق USB.
  - در `USBTransport` (فایل `protocol/transport.py`) دستگاه Qualcomm در حالت
    9008/EDL (شناسه `05c6:9008`) را پیدا می‌کند و روی endpoint‌های
    USB خواندن/نوشتن می‌کند — یعنی کل پروتکل Sahara/Firehose از این مسیر
    رد می‌شود.
  - در `MctUSB` (فایل `protocol/mct.py`) دستگاه‌های preloader مخصوص
    MediaTek/Unisoc را پیدا می‌کند: `0e8d:00e0`، `0e8d:00e3`، `0e8d:00e5`،
    `2b70:055e`، `2b70:055f`، `1004:6000`، `1004:6001` — یعنی کل پروتکل MCT.
- **نکته:** `trezbot/pyusb` فورک رسمی و نگهداری‌شده از پروژه اصلی
  [wilbur/pyusb](https://github.com/wilbur/pyusb) است. در `requirements.txt`
  به صورت `pyusb>=1.2.0` نصب می‌شود.

### PyInstaller
- **کاربرد:** ساخت **`.exe` مستقل** بدون نیاز به Python در زمان اجرا.
  - `build_exe.py` دستور زیر را اجرا می‌کند:
    `python -m PyInstaller --noconfirm --clean --onedir --windowed --name imei-toolkit ...`
  - خروجی: `dist\imei-toolkit\imei-toolkit.exe`
- **نکته:** فقط برای زمان **build** لازم است؛ برنامه نهایی بدون آن اجرا می‌شود.

### pyim (اختیاری)
- **کاربرد:** خواندن IMEI از **iPhone** به‌صورت best-effort.
  - در `main.py` و `cli.py` داخل `try/except` import می‌شود؛ اگر نصب نباشد
    یا روی ویندوز خطا بدهد، برنامه از آن استفاده نمی‌کند و خطا نمی‌اندازد
    (در حالت USB/Apple خواندن خالی برمی‌گردد و GUI پیشنهاد می‌کند از iTunes
    استفاده شود).
  - در حالت **fake** اصلاً نیازی نیست.
- **نکته:** این کتابخانه عمدتاً برای Unix/Linux است؛ روی ویندوز ممکن است
  در دسترس نباشد — به‌همین‌خاطر اختیاری است.

---

## ۲. کتابخانه‌های استاندارد پایتون (نیازی به نصب ندارند)

| ماژول | کاربرد در پروژه |
|---|---|
| `struct` | **کل پروتکل‌های باینری:** انکد IMEI به فرمت `le84`/`u32`/`rev`/`ascii` (`protocol.py`)، فریم بسته‌های Sahara/Firehose، و فریم درخواست/پاسخ پروتکل MCT (`mct.py`)، و دستگاه‌های fake |
| `tkinter` | **کل رابط گرافیکی** (`main.py`، `smoke_gui.py`) — با نصب Python ویندوز همراه است و نیازی به pip ندارد |
| `json` | ثبت **سابقه عملیات** در `history.jsonl`، فایل‌های **بکاپ/رستور** JSON، و خروجی JSON دستور `parse` در CLI |
| `csv` | **خروجی/ورودی CSV** IMEIها (`export_csv`/`import_csv` در `imei_toolkit.py`) |
| `argparse` | **زیردستورات CLI** در `cli.py` (parse، validate، generate، format، read، write، backup، restore، csv-export، csv-import، test) |
| `re` | نرمال‌سازی و پارس IMEI (حذف خط/فاصله، استخراج TAC/بدنه) |
| `abc` | کلاس‌های پایه انتزاعی: `Backend` در `backends.py` و `Transport` در `transport.py` |
| `dataclasses`،`typing` | ساختار داده‌ها مثل `ParsedImei` + type hints |
| `tempfile` | ساخت فایل programmer موقت (`.mbn`) در حالت fake (`_new_fake_firehose` در `main.py`) |
| `random` | ساخت IMEIهای نمونه در `_demo_imei` برای حالت fake |
| `time` | مهر زمانی ورودی‌های لاگ و `history.jsonl` |
| `os`،`sys` | مسیرهای فایل + افزودن ریشه پروژه به `sys.path` (برای اجرای مستقیم `main.py`/`cli.py` و برای بیلد PyInstaller) |
| `shutil`،`subprocess` | در `build_exe.py`: پاکسازی `dist/` و `build/`، نصب خودکار PyInstaller، و اجرای دستورات build |

---

## ۳. نصب

```
pip install -r requirements.txt
```

محتوای `requirements.txt`:

```
pyusb>=1.2.0          # ارتباط USB (Qualcomm 9008 + MediaTek MCT)
pyinstaller>=5.0      # فقط برای ساخت .exe مستقل
```

`pyim` در `requirements.txt` نیست چون اختیاری است — فقط اگر خواندن IMEI از
iPhone روی Unix مدنظر باشد:

```
pip install pyim
```
