#!/usr/bin/env python3
"""
Theo dõi Google Sheet lịch học của BKE (nguồn dữ liệu thật đứng sau trang
https://bke.edu.vn/lich/), phát hiện các khóa học có tổ chức OFFLINE tại
HÀ NỘI mà khoảng ngày diễn ra có rơi vào thứ Bảy/Chủ Nhật, và gửi thông
báo qua Zalo Bot khi có lịch MỚI (chưa từng thông báo trước đó).

Cách chạy thủ công:
    ZALO_BOT_TOKEN=xxx ZALO_CHAT_ID=xxx python3 check_bke_weekend.py

Biến môi trường:
    ZALO_BOT_TOKEN   - token của bot (bắt buộc để gửi thông báo thật)
    ZALO_CHAT_ID     - chat_id nhận thông báo (bắt buộc để gửi thông báo thật)
    DRY_RUN          - nếu = "1", chỉ in ra console, không gửi Zalo,
                        và KHÔNG cập nhật state.json (dùng để test)
"""
import csv
import io
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# Sheet đứng sau widget lịch tại https://bke.edu.vn/lich/
# (được nhúng qua https://myluuu190103.github.io/DuPhongCode/)
SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1S6BHr6MFR_-37EHV60ZXfS5_7DdnTAj7zEcCQ12wFsU/gviz/tq?tqx=out:csv&gid=0"
)

STATE_FILE = Path(__file__).parent / "state.json"
ZALO_API_BASE = "https://bot-api.zaloplatforms.com"

WEEKDAY_VN = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

LOCATION_KEYWORD = "Hà Nội"       # chỉ quan tâm địa điểm có chứa từ này
EXCLUDED_FORMATS = {"Zoom"}       # bỏ qua các dòng chỉ tổ chức online


# --------------------------------------------------------------------------
# 1. Tải dữ liệu từ Google Sheet (dạng CSV)
# --------------------------------------------------------------------------
def fetch_schedule_rows():
    resp = requests.get(SHEET_CSV_URL, timeout=30)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def parse_vn_date(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    return datetime.strptime(raw, "%d/%m/%Y").date()


def date_range_has_weekend(start: date, end: date):
    weekend_days = []
    d = start
    while d <= end:
        if d.weekday() >= 5:  # 5 = Thứ Bảy, 6 = Chủ Nhật
            weekend_days.append(d)
        d += timedelta(days=1)
    return weekend_days


# --------------------------------------------------------------------------
# 2. Lọc các sự kiện: Offline tại Hà Nội + rơi vào cuối tuần + sắp diễn ra
# --------------------------------------------------------------------------
def find_hanoi_weekend_events(rows, today: date):
    events = []
    for row in rows:
        location = (row.get("Địa điểm") or "").strip()
        fmt = (row.get("Hình thức") or "").strip()

        if LOCATION_KEYWORD not in location:
            continue
        if fmt in EXCLUDED_FORMATS:
            continue

        start = parse_vn_date(row.get("Từ ngày"))
        if start is None:
            continue
        end = parse_vn_date(row.get("Đến ngày")) or start

        if end < today:
            continue

        weekend_days = date_range_has_weekend(start, end)
        if not weekend_days:
            continue

        events.append(
            {
                "id": row.get("ID record") or f"{start.isoformat()}::{row.get('Khóa học')}",
                "title": (row.get("Khóa học") or "").strip(),
                "speaker": (row.get("Diễn giả") or "").strip(),
                "location": location,
                "format": fmt,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "weekend_days": [d.isoformat() for d in weekend_days],
                "detail_link": (row.get("Chi tiết (link)") or "").strip(),
            }
        )
    return events


# --------------------------------------------------------------------------
# 3. State: tránh gửi thông báo trùng lặp (dùng "ID record" của Sheet)
# --------------------------------------------------------------------------
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"notified": []}
    return {"notified": []}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --------------------------------------------------------------------------
# 4. Gửi thông báo qua Zalo Bot
# --------------------------------------------------------------------------
def send_zalo_message(token: str, chat_id: str, text: str):
    url = f"{ZALO_API_BASE}/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Gửi Zalo thất bại: {data}")
    return data


def format_date_range(start_iso: str, end_iso: str) -> str:
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if start == end:
        return f"{WEEKDAY_VN[start.weekday()]}, {start.strftime('%d/%m/%Y')}"
    return (
        f"{start.strftime('%d/%m')} ({WEEKDAY_VN[start.weekday()]}) "
        f"→ {end.strftime('%d/%m/%Y')} ({WEEKDAY_VN[end.weekday()]})"
    )


def build_message(new_events):
    lines = ["🔔 BKE có lịch học cuối tuần tại Hà Nội!", ""]
    for e in sorted(new_events, key=lambda x: x["start"]):
        lines.append(f"• {e['title']}" + (f" — {e['speaker']}" if e["speaker"] else ""))
        lines.append(f"   {format_date_range(e['start'], e['end'])}")
        if e["detail_link"]:
            lines.append(f"   {e['detail_link']}")
        lines.append("")
    lines.append("Nguồn: https://bke.edu.vn/lich/")
    return "\n".join(lines).strip()


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    today = date.today()
    dry_run = os.environ.get("DRY_RUN") == "1"
    token = os.environ.get("ZALO_BOT_TOKEN")
    chat_id = os.environ.get("ZALO_CHAT_ID")

    rows = fetch_schedule_rows()
    events = find_hanoi_weekend_events(rows, today)

    print(f"[{today.isoformat()}] Tìm thấy {len(events)} khóa học Offline tại Hà Nội, sắp tới, rơi vào cuối tuần:")
    for e in sorted(events, key=lambda x: x["start"]):
        print(f"  - {e['title']} | {e['start']} -> {e['end']} (id={e['id']})")

    state = load_state()
    notified_ids = set(state.get("notified", []))

    new_events = [e for e in events if e["id"] not in notified_ids]

    if not new_events:
        print("Không có sự kiện MỚI nào cần thông báo.")
        return

    message = build_message(new_events)
    print("---- Nội dung sẽ gửi ----")
    print(message)
    print("--------------------------")

    if dry_run:
        print("(DRY_RUN=1 -> không gửi Zalo thật, không lưu state)")
        return

    if not token or not chat_id:
        print(
            "THIẾU ZALO_BOT_TOKEN hoặc ZALO_CHAT_ID -> không thể gửi thông báo.",
            file=sys.stderr,
        )
        sys.exit(1)

    send_zalo_message(token, chat_id, message)
    print("Đã gửi thông báo Zalo thành công.")

    for e in new_events:
        notified_ids.add(e["id"])
    state["notified"] = sorted(notified_ids)
    save_state(state)


if __name__ == "__main__":
    main()
