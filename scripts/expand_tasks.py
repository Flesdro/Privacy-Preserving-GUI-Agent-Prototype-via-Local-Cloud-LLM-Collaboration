"""Generate the v0.8 synthetic task expansion (12 -> 36 tasks).

Each new task is laid out as four first-level containers under the root so the
LayoutAwarePartitioner produces >=3 blocks: the target control sits in its own
"action" container while sensitive distractors live in a separate "content"
container.  This makes collaborative mode upload only the target block (low
exposure) while cloud-only must upload everything (100% exposure).

Run from the prototype root:
    python3 scripts/expand_tasks.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = ROOT / "data" / "sample_tasks.json"

# Screen is a 1080x2400 phone. Four stacked first-level containers.
SCREEN = [0, 0, 1080, 2400]
BANDS = {
    "top": [0, 0, 1080, 300],
    "content": [0, 300, 1080, 1400],
    "action": [0, 1400, 1080, 1900],
    "nav": [0, 2100, 1080, 2400],
}


def el(
    eid,
    parent,
    role,
    *,
    text="",
    desc="",
    rid="",
    bounds,
    clickable=False,
    editable=False,
    sensitive=False,
):
    return {
        "id": eid,
        "parent": parent,
        "role": role,
        "text": text,
        "description": desc,
        "resource_id": rid or eid,
        "bounds": bounds,
        "clickable": clickable,
        "editable": editable,
        "sensitive": sensitive,
    }


def _row(band_key, index, count, pad=20):
    """Carve a horizontal slot inside a band so bounds stay valid and distinct."""
    x1, y1, x2, y2 = BANDS[band_key]
    h = (y2 - y1) // count
    top = y1 + index * h
    return [x1 + pad, top + pad, x2 - pad, top + h - pad]


def build_task(
    task_id,
    app,
    instruction,
    expected,
    *,
    target,
    sensitive_items,
    extra_top=None,
):
    """Assemble a task with a 4-container layout.

    target: dict describing the goal control (role/text/desc/clickable/editable).
    sensitive_items: list of (text, desc) placed in the content band as sensitive.
    extra_top: optional list of (role, text, desc) neutral items in the top band.
    """
    elements = [el("root", None, "FrameLayout", rid="root", bounds=SCREEN)]

    # Four first-level containers under root.
    elements += [
        el("top_bar", "root", "LinearLayout", rid="top_bar", bounds=BANDS["top"]),
        el("content_panel", "root", "LinearLayout", rid="content", bounds=BANDS["content"]),
        el("action_area", "root", "LinearLayout", rid="action_area", bounds=BANDS["action"]),
        el("nav_bar", "root", "LinearLayout", rid="nav_bar", bounds=BANDS["nav"]),
    ]

    # Top band: app title + optional neutral items.
    elements.append(
        el("title", "top_bar", "text", text=app, bounds=_row("top", 0, 2))
    )
    extra_top = extra_top or []
    for i, (role, text, desc) in enumerate(extra_top, start=1):
        elements.append(
            el(f"top_item_{i}", "top_bar", role, text=text, desc=desc, bounds=_row("top", 1, 2))
        )

    # Content band: sensitive distractors (private user data the cloud must not see).
    n = max(len(sensitive_items), 1)
    for i, (text, desc) in enumerate(sensitive_items):
        elements.append(
            el(
                f"sensitive_{i}",
                "content_panel",
                "text",
                text=text,
                desc=desc,
                bounds=_row("content", i, n),
                sensitive=True,
            )
        )

    # Action band: the target control (its own block).
    elements.append(
        el(
            target["id"],
            "action_area",
            target["role"],
            text=target.get("text", ""),
            desc=target.get("desc", ""),
            rid=target.get("rid", target["id"]),
            bounds=_row("action", 0, 1),
            clickable=target.get("clickable", False),
            editable=target.get("editable", False),
        )
    )

    # Nav band: neutral bottom navigation (clickable, non-sensitive).
    elements.append(
        el("nav_home", "nav_bar", "button", desc="Home", bounds=_row("nav", 0, 1))
    )

    return {
        "id": task_id,
        "instruction": instruction,
        "expected_action": expected,
        "ui_state": {
            "id": f"{task_id}_screen",
            "app": app,
            "root_id": "root",
            "elements": elements,
        },
    }


def click_target(eid, label, role="button"):
    return {"id": eid, "role": role, "text": label, "desc": label, "clickable": True}


def input_target(eid, hint, role="input"):
    return {
        "id": eid,
        "role": role,
        "text": hint,
        "desc": hint,
        "clickable": True,
        "editable": True,
    }


NEW_TASKS = [
    # ---- Browser (3) ----------------------------------------------------
    build_task(
        "browser_search", "Browser", "Search 'climate news' in the browser",
        {"action": "input", "element_id": "search_box"},
        target=input_target("search_box", "Search or type URL"),
        sensitive_items=[
            ("oliver.kim@gmail.com", "signed-in account"),
            ("Visited: private-banking.example.com", "browsing history"),
        ],
    ),
    build_task(
        "browser_open_bookmark", "Browser", "Open 'GitHub' bookmark",
        {"action": "click", "element_id": "bm_github"},
        target=click_target("bm_github", "GitHub"),
        sensitive_items=[
            ("Bookmark: health-records.example.com", "saved bookmark"),
            ("oliver.kim@gmail.com", "signed-in account"),
        ],
    ),
    build_task(
        "browser_new_tab", "Browser", "Tap 'New tab'",
        {"action": "click", "element_id": "new_tab_btn"},
        target=click_target("new_tab_btn", "New tab"),
        sensitive_items=[
            ("Open tab: my-tax-return.example.com", "open tab title"),
        ],
    ),
    # ---- Music player (3) ----------------------------------------------
    build_task(
        "music_play_song", "Music", "Tap 'Play'",
        {"action": "click", "element_id": "play_btn"},
        target=click_target("play_btn", "Play"),
        sensitive_items=[
            ("Recently played by Oliver", "listening history"),
        ],
    ),
    build_task(
        "music_skip_track", "Music", "Tap 'Next'",
        {"action": "click", "element_id": "next_btn"},
        target=click_target("next_btn", "Next"),
        sensitive_items=[
            ("Your liked songs", "personal library"),
        ],
    ),
    build_task(
        "music_toggle_shuffle", "Music", "Tap 'Shuffle'",
        {"action": "click", "element_id": "shuffle_btn"},
        target=click_target("shuffle_btn", "Shuffle"),
        sensitive_items=[
            ("Daily mix for Oliver Kim", "personalized playlist"),
        ],
    ),
    # ---- File manager (3) ----------------------------------------------
    build_task(
        "files_create_folder", "Files", "Tap 'New folder'",
        {"action": "click", "element_id": "new_folder_btn"},
        target=click_target("new_folder_btn", "New folder"),
        sensitive_items=[
            ("Passport_scan.pdf", "private file"),
            ("Salary_2025.xlsx", "private file"),
        ],
    ),
    build_task(
        "files_rename_file", "Files", "Tap 'Rename'",
        {"action": "click", "element_id": "rename_btn"},
        target=click_target("rename_btn", "Rename"),
        sensitive_items=[
            ("Medical_report.pdf", "selected private file"),
        ],
    ),
    build_task(
        "files_delete_item", "Files", "Tap 'Delete'",
        {"action": "click", "element_id": "delete_btn"},
        target=click_target("delete_btn", "Delete"),
        sensitive_items=[
            ("Bank_statement_March.pdf", "selected private file"),
        ],
    ),
    # ---- Weather (3) ----------------------------------------------------
    build_task(
        "weather_search_city", "Weather", "Search 'London' in weather",
        {"action": "input", "element_id": "search_box"},
        target=input_target("search_box", "Search city"),
        sensitive_items=[
            ("Home: 14 Maple Street", "saved location"),
            ("Work: 88 King Road", "saved location"),
        ],
    ),
    build_task(
        "weather_switch_unit", "Weather", "Tap 'Fahrenheit'",
        {"action": "click", "element_id": "unit_f_btn"},
        target=click_target("unit_f_btn", "Fahrenheit"),
        sensitive_items=[
            ("Home: 14 Maple Street", "saved location"),
        ],
    ),
    build_task(
        "weather_check_forecast", "Weather", "Tap 'Hourly forecast'",
        {"action": "click", "element_id": "hourly_btn"},
        target=click_target("hourly_btn", "Hourly forecast"),
        sensitive_items=[
            ("Current location: 14 Maple Street", "GPS location"),
        ],
    ),
    # ---- Camera (2) -----------------------------------------------------
    build_task(
        "camera_take_photo", "Camera", "Tap 'Shutter'",
        {"action": "click", "element_id": "shutter_btn"},
        target=click_target("shutter_btn", "Shutter"),
        sensitive_items=[
            ("Last photo: IMG_home_kitchen.jpg", "gallery thumbnail"),
        ],
    ),
    build_task(
        "camera_switch_video", "Camera", "Tap 'Video'",
        {"action": "click", "element_id": "video_mode_btn"},
        target=click_target("video_mode_btn", "Video"),
        sensitive_items=[
            ("Geotag: 37.42, -122.08", "embedded photo location"),
        ],
    ),
    # ---- Social media (4) ----------------------------------------------
    build_task(
        "social_compose_post", "Social", "Tap 'New post'",
        {"action": "click", "element_id": "new_post_btn"},
        target=click_target("new_post_btn", "New post"),
        sensitive_items=[
            ("DM from Sarah: see you at 14 Maple St", "private message preview"),
            ("oliver.kim@gmail.com", "signed-in account"),
        ],
    ),
    build_task(
        "social_like_post", "Social", "Tap 'Like'",
        {"action": "click", "element_id": "like_btn"},
        target=click_target("like_btn", "Like"),
        sensitive_items=[
            ("Sarah Chen tagged you in a photo", "friend activity"),
        ],
    ),
    build_task(
        "social_follow_user", "Social", "Tap 'Follow'",
        {"action": "click", "element_id": "follow_btn"},
        target=click_target("follow_btn", "Follow"),
        sensitive_items=[
            ("Suggested from your contacts: Mom", "contact-based suggestion"),
        ],
    ),
    build_task(
        "social_open_dm", "Social", "Tap 'Messages'",
        {"action": "click", "element_id": "dm_btn"},
        target=click_target("dm_btn", "Messages"),
        sensitive_items=[
            ("Unread from Mom: call me tonight", "private message preview"),
        ],
    ),
    # ---- Phone / Dialer (3) --------------------------------------------
    build_task(
        "phone_dial_number", "Phone", "Tap 'Call'",
        {"action": "click", "element_id": "call_btn"},
        target=click_target("call_btn", "Call"),
        sensitive_items=[
            ("Recent: Mom +1 555 0142", "call log entry"),
            ("Recent: Dr. Lee +1 555 0199", "call log entry"),
        ],
    ),
    build_task(
        "phone_save_contact", "Phone", "Tap 'Save contact'",
        {"action": "click", "element_id": "save_contact_btn"},
        target=click_target("save_contact_btn", "Save contact"),
        sensitive_items=[
            ("Number to save: +1 555 0142", "contact phone number"),
        ],
    ),
    build_task(
        "phone_open_recents", "Phone", "Tap 'Recents'",
        {"action": "click", "element_id": "recents_btn"},
        target=click_target("recents_btn", "Recents"),
        sensitive_items=[
            ("Missed call: Sarah +1 555 0177", "call log entry"),
        ],
    ),
    # ---- Additional settings (3) ---------------------------------------
    build_task(
        "settings_brightness", "Settings", "Tap 'Brightness'",
        {"action": "click", "element_id": "brightness_btn"},
        target=click_target("brightness_btn", "Brightness"),
        sensitive_items=[
            ("Signed in as oliver.kim@gmail.com", "account row"),
        ],
    ),
    build_task(
        "settings_font_size", "Settings", "Tap 'Font size'",
        {"action": "click", "element_id": "font_size_btn"},
        target=click_target("font_size_btn", "Font size"),
        sensitive_items=[
            ("Device owner: Oliver Kim", "owner row"),
        ],
    ),
    build_task(
        "settings_language", "Settings", "Tap 'Language'",
        {"action": "click", "element_id": "language_btn"},
        target=click_target("language_btn", "Language"),
        sensitive_items=[
            ("Backup account: oliver.kim@gmail.com", "account row"),
        ],
    ),
]


def main():
    data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    existing = data["tasks"]
    existing_ids = {t["id"] for t in existing}

    added = 0
    for task in NEW_TASKS:
        if task["id"] in existing_ids:
            continue
        existing.append(task)
        existing_ids.add(task["id"])
        added += 1

    TASKS_PATH.write_text(
        json.dumps({"tasks": existing}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Added {added} tasks. Total now {len(existing)}.")


if __name__ == "__main__":
    main()
