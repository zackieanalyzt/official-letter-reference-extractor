# pyzbar/zbar QR Fallback Setup on Windows

OLRE reads QR codes with OpenCV first. `pyzbar` is an optional fallback decoder for cases where OpenCV cannot decode a scanned QR image.

## What pyzbar Is

`pyzbar` is a Python wrapper for the zbar barcode/QR decoder.

## What zbar Is

zbar is the native runtime library that actually performs the decode. Installing `pyzbar` alone may not be enough on Windows if zbar DLLs are missing.

## Default Behavior

OLRE defaults to:

```env
QR_FALLBACK_DECODER=none
```

This keeps OpenCV as the only QR decoder and avoids requiring zbar on normal installs.

## Install Python QR Extra

Inside the project venv:

```powershell
python -m pip install -e ".[dev,qr]"
```

## Install zbar Runtime

Install a Windows-compatible zbar runtime and make sure its DLL directory is available to the application process through PATH or the installation method recommended by that runtime package.

Because zbar packaging on Windows varies, verify on the same machine that runs OLRE.

## Enable Fallback

In `.env`:

```env
QR_FALLBACK_DECODER=pyzbar
```

Restart the server after changing `.env`.

## How to Verify Fallback

1. Use a PDF where OpenCV QR detection fails or is unreliable.
2. Enable logs at INFO level:

```env
LOG_LEVEL=INFO
```

3. Process the document.
4. Check logs for:

```text
[QR_FALLBACK_START] decoder=pyzbar
[QR_FALLBACK_SUCCESS] decoder=pyzbar
```

If zbar or pyzbar is unavailable, OLRE should log:

```text
[QR_FALLBACK_UNAVAILABLE] decoder=pyzbar
```

and continue without crashing.

## Windows Limitations

- zbar DLL discovery can differ by installer.
- A PowerShell session may need to be reopened after PATH changes.
- If fallback is unstable, set `QR_FALLBACK_DECODER=none` and keep OpenCV-only behavior.
