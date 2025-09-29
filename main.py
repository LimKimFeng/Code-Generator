#!/usr/bin/env python3
import argparse
import itertools
import os
import string
import sys
import time
from pathlib import Path

# ====== KARAKTER SET ======
UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase
# Ubah ke "0123456789" jika kamu ingin menyertakan 0
DIGITS = "123456789"  # default mengikuti permintaan awal
SYMBOLS = string.punctuation
CHARSET = UPPER + LOWER + DIGITS + SYMBOLS  # total ~93 (tergantung versi Python)

# ====== UTIL ======
def scan_existing_by_len(filepath: Path, target_len: int) -> set:
    """Ambil semua kode existing dengan panjang target_len dari file (di-memori)."""
    exists = set()
    if filepath.exists():
        with filepath.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.rstrip("\n\r")
                if len(s) == target_len:
                    exists.add(s)
    return exists

def human(n: float) -> str:
    """Format angka besar/bytes jadi lebih enak dibaca."""
    try:
        return f"{n:,.0f}"
    except Exception:
        return str(n)

def file_size(path: Path) -> str:
    try:
        sz = path.stat().st_size
    except FileNotFoundError:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(sz)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.2f} {units[i]}"

# ====== REPORT WRITER ======
def write_report_txt(report_path: Path, totals: dict, per_len: dict):
    lines = []
    lines.append("=== GENERATION REPORT ===")
    lines.append(f"Output File      : {totals['output']}")
    lines.append(f"Charset Size     : {totals['charset_size']}")
    lines.append(f"Length Range     : {totals['min_len']}..{totals['max_len']}")
    lines.append(f"Started At       : {totals['start_ts']}")
    lines.append(f"Elapsed          : {totals['elapsed']:.1f}s")
    lines.append(f"File Size        : {totals['file_size']}")
    lines.append("")
    lines.append(f"Total Attempts   : {human(totals['attempts'])}")
    lines.append(f"Total Success    : {human(totals['success'])}")
    lines.append(f"Total Failed     : {human(totals['failed'])}")
    rate = (totals['success'] / totals['elapsed']) if totals['elapsed'] > 0 else 0.0
    lines.append(f"Write Rate       : {rate:.1f} lines/sec")
    lines.append("")
    lines.append("Per-Length Progress:")
    lines.append("Len | Possible           | Existing/Done      | New Written       | Failed           | Progress")
    lines.append("----+--------------------+--------------------+-------------------+------------------+---------")
    for L in range(totals['min_len'], totals['max_len'] + 1):
        st = per_len.get(L, {"possible": 0, "existing": 0, "written": 0, "failed": 0})
        possible = st["possible"]
        existing = st["existing"]  # total unik len L yang ada di file (sebelum + sesudah sesi ini)
        written = st["written"]    # yang ditulis di sesi ini
        failed  = st["failed"]
        prog = (existing / possible * 100.0) if possible else 0.0
        lines.append(
            f"{L:>3} | {human(possible):>18} | {human(existing):>18} | {human(written):>17} | {human(failed):>16} | {prog:6.2f}%"
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")

def write_report_html(report_path: Path, totals: dict, per_len: dict):
    # Simple inline HTML (tanpa CSS eksternal)
    rows = []
    for L in range(totals['min_len'], totals['max_len'] + 1):
        st = per_len.get(L, {"possible": 0, "existing": 0, "written": 0, "failed": 0})
        possible = st["possible"]
        existing = st["existing"]
        written = st["written"]
        failed  = st["failed"]
        prog = (existing / possible * 100.0) if possible else 0.0
        rows.append(f"""
        <tr>
            <td style="text-align:right;">{L}</td>
            <td style="text-align:right;">{human(possible)}</td>
            <td style="text-align:right;">{human(existing)}</td>
            <td style="text-align:right;">{human(written)}</td>
            <td style="text-align:right;">{human(failed)}</td>
            <td style="text-align:right;">{prog:.2f}%</td>
        </tr>
        """)

    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Generation Report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 20px;">
<h1>Generation Report</h1>
<table>
<tr><td><b>Output File</b></td><td>{totals['output']}</td></tr>
<tr><td><b>Charset Size</b></td><td>{totals['charset_size']}</td></tr>
<tr><td><b>Length Range</b></td><td>{totals['min_len']}..{totals['max_len']}</td></tr>
<tr><td><b>Started At</b></td><td>{totals['start_ts']}</td></tr>
<tr><td><b>Elapsed</b></td><td>{totals['elapsed']:.1f}s</td></tr>
<tr><td><b>File Size</b></td><td>{totals['file_size']}</td></tr>
<tr><td><b>Total Attempts</b></td><td>{human(totals['attempts'])}</td></tr>
<tr><td><b>Total Success</b></td><td>{human(totals['success'])}</td></tr>
<tr><td><b>Total Failed</b></td><td>{human(totals['failed'])}</td></tr>
<tr><td><b>Write Rate</b></td><td>{(totals['success']/totals['elapsed'] if totals['elapsed']>0 else 0.0):.1f} lines/sec</td></tr>
</table>

<h2>Per-Length Progress</h2>
<table border="1" cellspacing="0" cellpadding="6">
<thead>
<tr style="background:#f4f4f4;">
  <th>Len</th><th>Possible</th><th>Existing/Done</th><th>New Written</th><th>Failed</th><th>Progress</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
<p style="color:#666;">Existing/Done = total unik len L yang sudah ada di file (termasuk yang ditulis sesi ini).</p>
</body></html>"""
    report_path.write_text(html, encoding="utf-8")

def write_report(report_path: Path, fmt: str, totals: dict, per_len: dict):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "txt":
        write_report_txt(report_path, totals, per_len)
    else:
        write_report_html(report_path, totals, per_len)

# ====== MAIN ======
def main():
    ap = argparse.ArgumentParser(
        description="Enumerasi semua kombinasi CHARSET panjang 1..N, tulis ke file, pindah panjang berikutnya hanya jika kombinasi panjang saat ini sudah habis."
    )
    ap.add_argument("-o", "--output", default="codes.txt", help="File output (default: codes.txt)")
    ap.add_argument("--min", dest="min_len", type=int, default=1, help="Panjang minimal (default: 1)")
    ap.add_argument("--max", dest="max_len", type=int, default=30, help="Panjang maksimal (default: 30)")
    ap.add_argument("--flush-every", type=int, default=1000, help="Flush ke disk tiap N tulis (default: 1000)")
    ap.add_argument("--shuffle", action="store_true",
                    help="Acak urutan CHARSET per posisi (urutan terlihat random tapi tetap exhaustive).")
    # Report options
    ap.add_argument("--report", default=None, help="Path file report (default: <output>.report.html)")
    ap.add_argument("--report-format", choices=["html", "txt"], default="html", help="Format laporan (default: html)")
    ap.add_argument("--report-every", type=int, default=2000, help="Update report tiap N baris baru (default: 2000)")
    args = ap.parse_args()

    if args.min_len < 1 or args.max_len < args.min_len:
        print("Panjang tidak valid. Pastikan 1 <= min <= max.", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Tentukan path report
    if args.report:
        report_path = Path(args.report)
    else:
        # default: di folder yang sama dengan output, nama: <output>.report.html/txt
        suffix = ".report." + args.report_format
        report_path = out_path.with_suffix(out_path.suffix + suffix)

    # Siapkan file append
    f = out_path.open("a", encoding="utf-8")
    print(f"[INFO] Output: {out_path.resolve()}")
    print(f"[INFO] Charset size: {len(CHARSET)} ; Range panjang: {args.min_len}..{args.max_len}")
    print(f"[INFO] Report: {report_path.resolve()} ({args.report_format})")

    from random import Random
    rng = Random()  # nondeterministic
    base_charset = list(CHARSET)

    # Statistik global & per-length
    start_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.time()
    total_attempts = 0     # semua kombinasi yang diiterasi (existing + baru)
    total_written = 0      # success: baris baru yang ditulis
    total_failed = 0       # failed: duplikat (sudah ada di file)
    per_len_stats = {}     # L -> dict(possible, existing, written, failed)

    try:
        for L in range(args.min_len, args.max_len + 1):
            print(f"[INFO] Memindai file untuk panjang {L} ...")
            have = scan_existing_by_len(out_path, L)
            possible = (len(CHARSET) ** L)
            per_len_stats[L] = {
                "possible": possible,
                "existing": len(have),  # akan kita update ketika menulis baru
                "written": 0,
                "failed": 0
            }
            print(f"[INFO] Sudah ada unik (len={L}): {len(have):,} dari {possible:,}")

            # Siapkan iterator enumerasi untuk panjang L
            if args.shuffle:
                per_pos = []
                for _ in range(L):
                    chars = base_charset[:]
                    rng.shuffle(chars)
                    per_pos.append(chars)
                iter_product = itertools.product(*per_pos)
            else:
                iter_product = itertools.product(CHARSET, repeat=L)

            # Loop enumerasi
            written_since_last_report = 0
            last_flush_written = 0
            t_len_start = time.time()

            for tup in iter_product:
                total_attempts += 1
                s = "".join(tup)
                if s in have:
                    total_failed += 1
                    per_len_stats[L]["failed"] += 1
                    continue

                # tulis baru
                f.write(s + "\n")
                have.add(s)
                total_written += 1
                per_len_stats[L]["written"] += 1
                per_len_stats[L]["existing"] += 1
                written_since_last_report += 1

                # flush periodik
                if total_written % args.flush_every == 0:
                    f.flush()
                    os.fsync(f.fileno())
                    last_flush_written = total_written
                    dt = time.time() - t0
                    rate = total_written / dt if dt > 0 else 0.0
                    print(f"[{time.strftime('%H:%M:%S')}] len={L} | written: {human(total_written)} | failed: {human(total_failed)} | rate: {rate:.1f}/s")

                # update report periodik
                if written_since_last_report >= args.report_every:
                    written_since_last_report = 0
                    totals = {
                        "output": str(out_path.resolve()),
                        "charset_size": len(CHARSET),
                        "min_len": args.min_len,
                        "max_len": args.max_len,
                        "start_ts": start_ts,
                        "elapsed": time.time() - t0,
                        "file_size": file_size(out_path),
                        "attempts": total_attempts,
                        "success": total_written,
                        "failed": total_failed,
                    }
                    write_report(report_path, args.report_format, totals, per_len_stats)

            # selesai satu panjang
            if total_written != last_flush_written:
                f.flush()
                os.fsync(f.fileno())

            dt_len = time.time() - t_len_start
            print(f"[SELESAI LEN={L}] baru ditulis: {human(per_len_stats[L]['written'])} | "
                  f"dupe: {human(per_len_stats[L]['failed'])} | "
                  f"total len{L}: {human(per_len_stats[L]['existing'])}/{human(per_len_stats[L]['possible'])} | "
                  f"durasi: {dt_len:.1f}s")

            # tulis report setelah menyelesaikan satu panjang
            totals = {
                "output": str(out_path.resolve()),
                "charset_size": len(CHARSET),
                "min_len": args.min_len,
                "max_len": args.max_len,
                "start_ts": start_ts,
                "elapsed": time.time() - t0,
                "file_size": file_size(out_path),
                "attempts": total_attempts,
                "success": total_written,
                "failed": total_failed,
            }
            write_report(report_path, args.report_format, totals, per_len_stats)

        print("[DONE] Semua panjang dalam rentang telah diselesaikan.")
    except KeyboardInterrupt:
        print("\n[STOP] Dihentikan oleh pengguna (Ctrl+C).")
    finally:
        try:
            f.flush()
            os.fsync(f.fileno())
            f.close()
        except Exception:
            pass
        # laporan final saat berhenti
        totals = {
            "output": str(out_path.resolve()),
            "charset_size": len(CHARSET),
            "min_len": args.min_len,
            "max_len": args.max_len,
            "start_ts": start_ts,
            "elapsed": time.time() - t0,
            "file_size": file_size(out_path),
            "attempts": total_attempts,
            "success": total_written,
            "failed": total_failed,
        }
        write_report(report_path, args.report_format, totals, per_len_stats)
        rate = (total_written / totals["elapsed"]) if totals["elapsed"] > 0 else 0.0
        print(f"[RINGKAS] success: {human(total_written)} | failed: {human(total_failed)} | "
              f"attempts: {human(total_attempts)} | rate: {rate:.1f}/s | report: {report_path.resolve()}")

if __name__ == "__main__":
    main()
