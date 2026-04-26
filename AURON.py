# AURON-Artificial Utility Responses and Operation Networks 

import os
import threading
import datetime
import requests
import wikipedia
import pyttsx3
import webbrowser
import speech_recognition as sr
import customtkinter as ctk
from tkinter import messagebox, filedialog, Toplevel
from PIL import Image, ImageTk
from customtkinter import CTkImage
import pytesseract
import fitz  # PyMuPDF
from voice_login import authenticate_user
import sympy
from sympy import symbols, Eq, solve, simplify, expand, diff, integrate
import json
import re
import shutil
import subprocess
import time
import psutil  # pip install psutil
import getpass
from pathlib import Path

# --------------------- Configuration ---------------------
CITY = "Mumbai"
API_KEY = "cf0eb027cd86daacbd64cee1064a6aea"   # provide valid openweathermap key
VOICE_RATE = 170
VOICE_INDEX = 1
IMAGE_PATH = "AURON/AURON 1.png"
CHAT_HISTORY_FILE = "chat_history.txt"
EXTRACTED_FILE = "uploaded_file_text.txt"
NOTES_FILE = "AURON_notes.txt"

TODO_FILE = "AURON_todo.txt"
REMINDERS_FILE = "AURON_reminders.json"        # stores reminders + schedule info
STICKY_STORAGE = os.path.join(os.getenv("APPDATA") or ".", "AURON")
STICKY_SCRIPT = os.path.join(STICKY_STORAGE, "auron_sticky_note.py")
STICKY_STARTUP_BAT = os.path.join(os.getenv("APPDATA") or ".", "Microsoft\\Windows\\Start Menu\\Programs\\Startup", "auron_sticky_start.bat")

# tesseract path - update if different
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Battery alert threshold (percent)
BATTERY_ALERT_THRESHOLD = 45

# Voice mode: Full voice (you requested full voice)
VOICE_MODE = "full"  # values: "full", "smart", "silent"

# Time check interval for reminders (seconds)
REMINDER_CHECK_INTERVAL = 60

# --------------------- Voice Utilities ---------------------
def speak(text):
    if VOICE_MODE == "silent":
        return
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", VOICE_RATE)
        voices = engine.getProperty("voices")
        if VOICE_INDEX < len(voices):
            engine.setProperty("voice", voices[VOICE_INDEX].id)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print("[Voice Error]", e)

def speak_async(text):
    if VOICE_MODE == "silent":
        return
    threading.Thread(target=speak, args=(text,), daemon=True).start()

# --------------------- Time / Weather ---------------------
def get_time():
    return datetime.datetime.now().strftime("%I:%M %p")

def get_weather(city):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
        data = requests.get(url).json()
        if str(data.get("cod")) != "200":
            return "Weather unavailable"
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"].capitalize()
        return f"{desc}, {temp}°C"
    except Exception as e:
        return f"Weather error: {e}"

# --------------------- Notes & History ---------------------
def manage_notes(command):
    command = command.lower()
    if "add note" in command:
        note = command.replace("add note", "").strip()
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(f"- {note}\n")
        speak_async(f"Note added: {note}")
        return f"Note added: {note}"
    elif "show notes" in command or "view notes" in command:
        if not os.path.exists(NOTES_FILE):
            return "No notes found."
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return f.read()
    elif any(word in command for word in ["clear notes", "delete all notes", "remove notes"]):
        if os.path.exists(NOTES_FILE):
            os.remove(NOTES_FILE)
        return "All notes cleared."
    return None

def search_chat_history(keyword):
    if not os.path.exists(CHAT_HISTORY_FILE):
        return "No chat history found."
    with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    matches = [line for line in lines if keyword.lower() in line.lower()]
    return "".join(matches) if matches else "No matches found."

# --------------------- TODO & Reminder Management ---------------------
def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, default=str, indent=2)

def add_todo_task(text, when=None, recurring=None):
    """
    Adds a task and creates a reminder entry. `when` is a datetime or None.
    `recurring` can be a dict like {"every": {"hours":2}} or {"daily_at":"09:00"}.
    """
    # Append to plain todo file for compatibility
    with open(TODO_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

    # Create reminder entry
    reminders = load_reminders()
    next_id = max((r.get("id",0) for r in reminders), default=0) + 1
    reminder = {
        "id": next_id,
        "task": text,
        "created_at": datetime.datetime.now().isoformat(),
        "when": when.isoformat() if isinstance(when, datetime.datetime) else None,
        "recurring": recurring,  # keep as serializable dict
        "done": False,
        "snoozed_until": None,
        "last_shown": None
    }
    reminders.append(reminder)
    save_reminders(reminders)
    # Immediately show sticky for every task
    speak_async(f"Task added: {text}")
    show_sticky_for_reminder(reminder)
    return reminder

def complete_task_by_id(rem_id):
    reminders = load_reminders()
    changed = False
    for r in reminders:
        if r.get("id") == rem_id:
            r["done"] = True
            changed = True
            # remove line from TODO_FILE if present
            if os.path.exists(TODO_FILE):
                with open(TODO_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                with open(TODO_FILE, "w", encoding="utf-8") as f:
                    for line in lines:
                        if line.strip().lower() != r.get("task","").lower():
                            f.write(line)
            speak_async(f"Task marked done: {r.get('task')}")
            break
    if changed:
        save_reminders(reminders)
        return True
    return False

def delete_reminder_by_id(rem_id):
    reminders = load_reminders()
    new_rem = [r for r in reminders if r.get("id") != rem_id]
    if len(new_rem) != len(reminders):
        save_reminders(new_rem)
        speak_async("Reminder deleted.")
        return True
    return False

def snooze_reminder(rem_id, minutes=10):
    reminders = load_reminders()
    for r in reminders:
        if r.get("id") == rem_id:
            new_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            r["snoozed_until"] = new_time.isoformat()
            save_reminders(reminders)
            speak_async(f"Reminder delayed by {minutes} minutes")
            return True
    return False

# --------------------- Parsing simple time expressions ---------------------
def parse_time_expression(text):
    """
    Attempt to parse the user's text for time expressions.
    Returns (when: datetime or None, recurring: dict or None)
    Supports:
    - 'at HH:MM' or 'at H PM' or 'at H AM'
    - 'tomorrow at ...'
    - 'in N minutes/hours/days'
    - 'every N hours' or 'every day at HH:MM' or 'every day'
    Basic and defensive — extend if you need more NLP power.
    """
    text = text.lower()
    now = datetime.datetime.now()

    # recurring patterns
    m = re.search(r"every\s+(\d+)\s*(minute|minutes|hour|hours|day|days)", text)
    if m:
        qty = int(m.group(1))
        unit = m.group(2)
        if "minute" in unit:
            return None, {"every": {"minutes": qty}}
        if "hour" in unit:
            return None, {"every": {"hours": qty}}
        if "day" in unit:
            return None, {"every": {"days": qty}}

    m = re.search(r"every\s+day(?:\s+at\s+(\d{1,2}(:\d{2})?\s*(am|pm)?))?", text)
    if m:
        at = m.group(1)
        if at:
            at = at.strip()
            try:
                dt = parse_time_of_day(at, reference=now)
                return None, {"daily_at": dt.strftime("%H:%M")}
            except:
                return None, {"daily": True}
        return None, {"daily": True}

    # relative: in N minutes/hours/days
    m = re.search(r"in\s+(\d+)\s*(minute|minutes|hour|hours|day|days)", text)
    if m:
        qty = int(m.group(1)); unit = m.group(2)
        if "minute" in unit:
            return now + datetime.timedelta(minutes=qty), None
        if "hour" in unit:
            return now + datetime.timedelta(hours=qty), None
        if "day" in unit:
            return now + datetime.timedelta(days=qty), None

    # tomorrow at ...
    m = re.search(r"tomorrow(?:\s+at\s+(.+))", text)
    if m:
        at = m.group(1).strip()
        try:
            dt = parse_time_of_day(at, reference=now + datetime.timedelta(days=1))
            return dt, None
        except:
            pass

    # explicit 'at HH:MM' or 'at H AM/PM'
    m = re.search(r"at\s+(\d{1,2}(:\d{2})?\s*(am|pm)?)", text)
    if m:
        timestr = m.group(1).strip()
        try:
            dt = parse_time_of_day(timestr, reference=now)
            # if parsed time already past today, schedule tomorrow
            if dt < now:
                dt = dt + datetime.timedelta(days=1)
            return dt, None
        except:
            pass

    # date with time e.g. 2025-10-30 09:00 or 30/10/2025 9:00
    m = re.search(r"(\d{1,2}[/\-]\d{1,2}([/\-]\d{2,4})?\s+\d{1,2}:\d{2})", text)
    if m:
        s = m.group(1)
        try:
            dt = datetime.datetime.strptime(s, "%d/%m/%Y %H:%M")
            return dt, None
        except:
            try:
                dt = datetime.datetime.strptime(s, "%d-%m-%Y %H:%M")
                return dt, None
            except:
                pass

    # fallback: no time found
    return None, None

def parse_time_of_day(timestr, reference=None):
    """
    Parse '9', '9:30', '9 am', '9:30 pm' into a datetime on the reference day.
    """
    reference = reference or datetime.datetime.now()
    timestr = timestr.strip().lower()
    m = re.match(r"(\d{1,2})(:(\d{2}))?\s*(am|pm)?", timestr)
    if not m:
        raise ValueError("Cannot parse time")
    hour = int(m.group(1))
    minute = int(m.group(3)) if m.group(3) else 0
    ampm = m.group(4)
    if ampm:
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
    return datetime.datetime(reference.year, reference.month, reference.day, hour, minute)

# --------------------- Sticky Note UI (UPDATED) ---------------------
def show_sticky_for_reminder(reminder):
    """
    Show a sticky note window for the given reminder dict.
    Buttons: Done (completes the task), Delay (snooze 10 minutes), Delete (remove reminder).
    Visual requirements:
    - Yellow background
    - Black text (no extra black backgrounds behind text)
    - Done button: green
    - Delay button: orange
    - Delete button: red
    - Larger buttons and good spacing
    """
    def _show():
        # Ensure not showing done reminders
        if reminder.get("done"):
            return

        top = Toplevel(app)
        top.attributes('-topmost', True)
        # Keep window border for easier movement and closing by user
        top.overrideredirect(False)
        # size and position
        width, height = 360, 160
        # position near bottom-right by default (adjust if many)
        screen_w = app.winfo_screenwidth()
        screen_h = app.winfo_screenheight()
        x = screen_w - width - 40
        y = screen_h - height - 120
        top.geometry(f"{width}x{height}+{x}+{y}")
        # Yellow background
        top.configure(bg="#FFF59D")  # friendly yellow

        # padding frame to keep content away from edges
        pad = ctk.CTkFrame(top, fg_color="#FFF59D", width=width, height=height)
        pad.place(x=0, y=0)

        # Title / Task (black text, no dark rectangle)
        title_text = reminder.get("task", "Reminder")
        # Using a plain tkinter Label for plain black text on yellow to avoid CTk label background issues
        try:
            import tkinter as tk
            title_lbl = tk.Label(top, text=title_text, font=("Segoe UI", 12, "bold"), bg="#FFF59D", fg="#000000", wraplength=320, justify="left")
            title_lbl.place(x=12, y=12)
        except Exception:
            # fallback to CTkLabel with transparent-like bg
            title_lbl = ctk.CTkLabel(pad, text=title_text, font=("Segoe UI", 12, "bold"), text_color="black")
            title_lbl.place(x=12, y=12)

        # Scheduled time / snooze info - black text
        when = reminder.get("when")
        ttxt = "No time set"
        if reminder.get("snoozed_until"):
            try:
                sno = datetime.datetime.fromisoformat(reminder["snoozed_until"])
                ttxt = "Snoozed until " + sno.strftime("%b %d, %I:%M %p")
            except:
                ttxt = "Snoozed"
        elif when:
            try:
                when_dt = datetime.datetime.fromisoformat(when)
                ttxt = "Scheduled at " + when_dt.strftime("%b %d, %I:%M %p")
            except:
                ttxt = "Scheduled"
        # time label (plain tk)
        try:
            import tkinter as tk
            time_lbl = tk.Label(top, text=ttxt, font=("Segoe UI", 10), bg="#FFF59D", fg="#000000")
            time_lbl.place(x=12, y=44)
        except Exception:
            time_lbl = ctk.CTkLabel(pad, text=ttxt, font=("Segoe UI", 10), text_color="black")
            time_lbl.place(x=12, y=44)

        # Buttons frame
        btn_y = 92
        btn_h = 38
        btn_w = 98
        spacing = 12

        # Done - green
        def do_done():
            complete_task_by_id(reminder["id"])
            try:
                top.destroy()
            except:
                pass

        # Delay - orange (snooze 10 minutes)
        def do_delay():
            snooze_reminder(reminder["id"], minutes=10)
            try:
                top.destroy()
            except:
                pass

        # Delete - red (remove reminder completely)
        def do_delete():
            deleted = delete_reminder_by_id(reminder["id"])
            if deleted:
                try:
                    top.destroy()
                except:
                    pass
            else:
                speak_async("Could not delete reminder.")

        # Use CTkButton but place them with absolute positions for consistent spacing
        done_btn = ctk.CTkButton(top, text="Done", width=btn_w, height=btn_h, corner_radius=8,
                                 fg_color="#39A13B", hover_color="#2E8B32", text_color="white",
                                 font=("Segoe UI", 11, "bold"), command=do_done)
        done_btn.place(x=12, y=btn_y)

        delay_btn = ctk.CTkButton(top, text="Delay", width=btn_w, height=btn_h, corner_radius=8,
                                  fg_color="#F29336", hover_color="#E07A1A", text_color="white",
                                  font=("Segoe UI", 11, "bold"), command=do_delay)
        delay_btn.place(x=12 + btn_w + spacing, y=btn_y)

        delete_btn = ctk.CTkButton(top, text="Delete", width=btn_w, height=btn_h, corner_radius=8,
                                   fg_color="#D84315", hover_color="#B71C1C", text_color="white",
                                   font=("Segoe UI", 11, "bold"), command=do_delete)
        delete_btn.place(x=12 + 2*(btn_w + spacing), y=btn_y)

        # Voice announcement
        speak_async(f"Reminder: {title_text}")

        # Keep reference so garbage collector doesn't kill widgets (tkinter handles this, but safe)
        top.lift()
        top.focus_force()

    # Ensure the sticky UI runs in mainloop thread
    try:
        app.after(0, _show)
    except Exception as e:
        print("Sticky show error:", e)

# --------------------- Reminder Scheduler Loop ---------------------
def evaluate_and_fire_reminders():
    """
    Periodically checks reminders for due times (or recurring triggers) and shows stickies.
    - Respects 'snoozed_until'
    - For recurring reminders, computes next due time
    """
    while True:
        try:
            reminders = load_reminders()
            now = datetime.datetime.now()
            changed = False
            for r in reminders:
                if r.get("done"):
                    continue
                # check snooze
                if r.get("snoozed_until"):
                    sno = datetime.datetime.fromisoformat(r["snoozed_until"])
                    if sno <= now:
                        r["snoozed_until"] = None
                        changed = True
                        show_sticky_for_reminder(r)
                    continue
                # explicit when
                when_iso = r.get("when")
                if when_iso:
                    when_dt = datetime.datetime.fromisoformat(when_iso)
                    # due if now >= when_dt and not in future more than a small window
                    if now >= when_dt:
                        show_sticky_for_reminder(r)
                        # handle recurring
                        if r.get("recurring"):
                            rec = r["recurring"]
                            if "every" in rec:
                                # calculate next when based on every interval
                                every = rec["every"]
                                delta = datetime.timedelta(
                                    days=every.get("days",0),
                                    hours=every.get("hours",0),
                                    minutes=every.get("minutes",0)
                                )
                                r["when"] = (when_dt + delta).isoformat()
                                changed = True
                            elif "daily_at" in rec:
                                hhmm = rec["daily_at"]
                                h,m = map(int, hhmm.split(":"))
                                next_dt = datetime.datetime(now.year, now.month, now.day, h, m)
                                if next_dt <= now:
                                    next_dt = next_dt + datetime.timedelta(days=1)
                                r["when"] = next_dt.isoformat()
                                changed = True
                        else:
                            # leave as-is so sticky will show each check until done or snoozed/deleted
                            pass
                else:
                    # No explicit when: show sticky immediately (for task-only entries),
                    # but only show once per run by setting a last_shown timestamp.
                    if not r.get("last_shown"):
                        r["last_shown"] = now.isoformat()
                        changed = True
                        show_sticky_for_reminder(r)
                    else:
                        # if last_shown older than some threshold, allow repeat (optional)
                        last = datetime.datetime.fromisoformat(r["last_shown"])
                        if (now - last).total_seconds() > 3600:  # repeat every hour if still not done
                            r["last_shown"] = now.isoformat()
                            changed = True
                            show_sticky_for_reminder(r)
            if changed:
                save_reminders(reminders)
        except Exception as e:
            print("Reminder loop error:", e)
        time.sleep(REMINDER_CHECK_INTERVAL)

# Start scheduler thread
threading.Thread(target=evaluate_and_fire_reminders, daemon=True).start()

# --------------------- System & App Openers ---------------------
def try_open_with_candidates(candidates):
    for c in candidates:
        try:
            if os.path.exists(c):
                try:
                    os.startfile(c)
                    return True
                except Exception:
                    subprocess.Popen([c], shell=False)
                    return True
            path = shutil.which(c)
            if path:
                try:
                    os.startfile(path)
                    return True
                except:
                    subprocess.Popen([path], shell=False)
                    return True
        except Exception:
            continue
    return False

def confirm_and_execute(command, message, action):
    speak_async(message + " Say yes to confirm.")
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            audio = recognizer.listen(source, timeout=5)
            response = recognizer.recognize_google(audio).lower()
            if "yes" in response:
                os.system(action)
                return f"{command} initiated."
            else:
                return f"{command} cancelled."
    except Exception:
        return f"{command} not confirmed. No valid response."

def open_item(query):
    q = query.lower()
    if "chrome" in q:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            os.startfile(chrome_path)
            return "Opening Chrome."
        webbrowser.open("https://www.google.com")
        return "Opening browser."
    if "downloads" in q:
        os.startfile(os.path.expanduser("~/Downloads"))
        return "Opening Downloads."
    if "krish space" in q:
        if os.path.exists("D:\\Krish Space"):
            os.startfile("D:\\Krish Space")
            return "Opening Krish Space."
        else:
            return "Krish Space folder not found."
    if "shutdown" in q:
        return confirm_and_execute("Shutdown", "Are you sure?", "shutdown /s /t 1")
    if "restart" in q:
        return confirm_and_execute("Restart", "Are you sure?", "shutdown /r /t 1")
    # Office apps
    if any(word in q for word in ["word", "ms word", "microsoft word"]):
        word_candidates = [
            r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
            "winword"
        ]
        if try_open_with_candidates(word_candidates):
            return "Opening Microsoft Word."
        else:
            return "Could not find Microsoft Word automatically. Please open manually."
    if any(word in q for word in ["excel", "ms excel", "microsoft excel"]):
        excel_candidates = [
            r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
            "excel"
        ]
        if try_open_with_candidates(excel_candidates):
            return "Opening Microsoft Excel."
        else:
            return "Could not find Microsoft Excel automatically. Please open manually."
    if any(word in q for word in ["powerpoint", "ppt", "ms powerpoint"]):
        ppt_candidates = [
            r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE",
            "powerpnt"
        ]
        if try_open_with_candidates(ppt_candidates):
            return "Opening Microsoft PowerPoint."
        else:
            return "Could not find Microsoft PowerPoint automatically. Please open manually."
    if any(word in q for word in ["code", "vs code", "vscode", "visual studio code"]):
        code_candidates = [
            rf"C:\Users\{getpass.getuser()}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            "code"
        ]
        if try_open_with_candidates(code_candidates):
            return "Opening VS Code."
        else:
            return "Could not find VS Code automatically. Please open manually."
    # This PC
    if any(word in q for word in ["this pc", "my computer", "computer"]):
        try:
            subprocess.Popen(['explorer', 'shell:MyComputerFolder'])
            return "Opening This PC."
        except:
            return "Could not open This PC."
    # Recycle Bin
    if any(word in q for word in ["recycle bin", "recyclebin", "trash"]):
        try:
            subprocess.Popen(['explorer', 'shell:RecycleBinFolder'])
            return "Opening Recycle Bin."
        except:
            return "Could not open Recycle Bin."
    # Documents / Desktop
    if any(word in q for word in ["documents", "my documents"]):
        os.startfile(os.path.expanduser("~/Documents"))
        return "Opening Documents."
    if any(word in q for word in ["desktop", "my desktop"]):
        os.startfile(os.path.expanduser("~/Desktop"))
        return "Opening Desktop."
    return None

def open_in_chrome(url):
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        rf"C:\Users\{getpass.getuser()}\AppData\Local\Google\Chrome\Application\chrome.exe"
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            try:
                subprocess.Popen([p, url], shell=False)
                return True
            except:
                pass
    webbrowser.open(url)
    return False

# --------------------- Query Processor ---------------------
def process_query(query):
    query = query.strip()
    low = query.lower()
    # greetings
    if low in ["hello", "hi", "hey", "hello auron"]:
        speak_async("Hello! How can I assist you today?")
        return "Hello! How can I assist you today?"
    if "how are you" in low:
        speak_async("I'm functioning perfectly, thank you!")
        return "I'm functioning perfectly, thank you!"
    # theme switching
    if "neon theme" in low or "switch to neon" in low or "enable neon" in low:
        apply_neon_theme()
        speak_async("Neon theme enabled")
        return "Neon theme enabled."
    if "dark theme" in low or "switch to dark" in low or "enable dark" in low:
        change_theme("dark")
        speak_async("Dark theme enabled")
        return "Dark theme enabled."
    # check for todo commands (voice-friendly)
    if low.startswith("add task") or low.startswith("add todo") or low.startswith("add"):
        # extract the task text and try to parse time expressions
        # examples:
        # "Add task submit assignment at 7 pm"
        # "Add task call mom tomorrow at 9"
        # "Add task water plants every day at 8"
        task_text = query
        # remove leading add keywords
        task_text = re.sub(r'^(add (task|todo)\s*)', '', task_text, flags=re.I).strip()
        when, recurring = parse_time_expression(task_text)
        # remove time phrases from displayed task text for clarity (simple heuristic)
        task_clean = re.sub(r'\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b', '', task_text, flags=re.I)
        task_clean = re.sub(r'\btomorrow\b', '', task_clean, flags=re.I)
        task_clean = re.sub(r'\bin\s+\d+\s*(minutes?|hours?|days?)\b', '', task_clean, flags=re.I)
        task_clean = re.sub(r'\bevery\s+\d+\s*(minutes?|hours?|days?)\b', '', task_clean, flags=re.I)
        task_clean = task_clean.strip()
        rem = add_todo_task(task_clean or task_text, when=when, recurring=recurring)
        return f"Task added: {task_clean or task_text}"
    # complete/done commands
    if low.startswith("done") or low.startswith("complete"):
        # "done 2" or "done submit assignment"
        rest = query.split(None,1)
        if len(rest) == 1:
            return "Please say which task to complete (id or text)."
        param = rest[1].strip()
        # try numeric id
        try:
            iid = int(param)
            ok = complete_task_by_id(iid)
            if ok:
                return f"Task {iid} marked done."
        except:
            # match by text
            reminders = load_reminders()
            for r in reminders:
                if param.lower() in r.get("task","").lower():
                    complete_task_by_id(r["id"])
                    return f"Marked done: {r.get('task')}"
        return "Task not found."
    # show todos
    if "show todos" in low or "view todos" in low or "list todos" in low:
        if not os.path.exists(TODO_FILE):
            return "No todos found."
        with open(TODO_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out = "".join(f"{i+1}. {l}" for i,l in enumerate(lines))
        speak_async("Here are your todos.")
        return out or "No todos found."
    # system openers
    res = open_item(low)
    if res:
        speak_async(res)
        return res
    # web services
    if "chatgpt" in low or "openai" in low:
        open_in_chrome("https://chat.openai.com/")
        speak_async("Opening ChatGPT")
        return "Opening ChatGPT in Chrome."
    if "classroom" in low or "google classroom" in low:
        open_in_chrome("https://classroom.google.com/")
        speak_async("Opening Google Classroom")
        return "Opening Google Classroom in Chrome."
    if "gmail" in low or "mail" in low:
        open_in_chrome("https://mail.google.com/")
        speak_async("Opening Gmail")
        return "Opening Gmail in Chrome."
    # search & youtube
    if any(word in low for word in ["google", "search", "find", "tell me about", "show me"]):
        q = low
        for word in ["google", "search", "find", "tell me about", "show me"]:
            q = q.replace(word, "")
        webbrowser.open(f"https://www.google.com/search?q={q.strip()}")
        speak_async("Searching Google")
        return f"Searching Google for: {q.strip()}"
    if any(word in low for word in ["youtube", "play video", "play on youtube", "play"]):
        q = low
        for word in ["youtube", "play video", "play on youtube", "play"]:
            q = q.replace(word, "")
        webbrowser.open(f"https://www.youtube.com/results?search_query={q.strip()}")
        speak_async("Playing on YouTube")
        return f"Playing on YouTube: {q.strip()}"
    # wikipedia
    if "wikipedia" in low:
        try:
            summary = wikipedia.summary(low.replace("wikipedia","").strip(), sentences=2)
            speak_async("Here is the summary from Wikipedia")
            return summary
        except Exception:
            return "Wikipedia result not found."
    # time / weather
    if "time" in low or "clock" in low:
        t = get_time()
        speak_async(f"The time is {t}")
        return t
    if "weather" in low or "temperature" in low:
        w = get_weather(CITY)
        speak_async(f"The weather in {CITY} is {w}")
        return w
    return "I didn't understand that."

# --------------------- Chat logger ---------------------
def log_chat(user_query, reply):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(CHAT_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} You said: {user_query}\n")
        f.write(f"{timestamp} AURON replied: {reply}\n\n")

# --------------------- Authenticate ---------------------
if not authenticate_user():
    exit()

# --------------------- GUI Setup ---------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.geometry("1100x740")
app.title("AURON – Artificial Utility for Response & Operations Network")
app.resizable(False, False)

# Theme helpers
def change_theme(theme):
    ctk.set_appearance_mode(theme)
    menu_frame.place_forget()

def apply_neon_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
    menu_frame.place_forget()

# Weather & time display
info_frame = ctk.CTkFrame(app, fg_color="transparent")
info_frame.pack(pady=(5, 0))

weather_label = ctk.CTkLabel(info_frame, text="", font=("Segoe UI", 16))
weather_label.grid(row=0, column=0, padx=20)

time_label = ctk.CTkLabel(info_frame, text="", font=("Segoe UI", 16))
time_label.grid(row=0, column=1, padx=20)

def update_time_weather():
    weather_label.configure(text=f"🌤  {get_weather(CITY)}")
    time_label.configure(text=f"🕒  {get_time()}")
    app.after(60000, update_time_weather)

# Load image (if present)
try:
    image = Image.open(IMAGE_PATH)
    image = image.resize((240, 120))
    photo = CTkImage(light_image=image, dark_image=image, size=(240, 120))
    image_label = ctk.CTkLabel(app, image=photo, text="")
    image_label.pack(pady=(5, 0))
except Exception as e:
    print("Image load error:", e)

response_box = ctk.CTkTextbox(app, height=330, width=980, wrap="word", font=("Segoe UI", 14))
response_box.pack(pady=(10,5))

entry = ctk.CTkEntry(app, placeholder_text="Type your command...", width=760, height=44, font=("Segoe UI", 14))
entry.pack(pady=(5,5))

# --------------------- Input Handlers ---------------------
def handle_input():
    user_input = entry.get().strip()
    if not user_input:
        messagebox.showwarning("Input Required", "Please enter a query.")
        return
    response = process_query(user_input)
    response_box.insert("end", f"\nYou: {user_input}\nAURON: {response}\n")
    response_box.see("end")
    log_chat(user_input, response)
    entry.delete(0, "end")
    if VOICE_MODE == "full":
        speak_async(response)

def handle_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            speak_async("Listening...")
            audio = recognizer.listen(source, timeout=6)
            user_input = recognizer.recognize_google(audio)
            entry.delete(0, "end")
            entry.insert(0, user_input)
            handle_input()
        except sr.UnknownValueError:
            speak_async("Sorry, I did not understand.")
        except sr.RequestError:
            speak_async("Speech recognition is not available.")
        except Exception as e:
            speak_async("Microphone error.")

def upload_file():
    file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("Image files", "*.png;*.jpg;*.jpeg")])
    if not file_path:
        return
    extracted_text = ""
    try:
        if file_path.lower().endswith(".pdf"):
            with fitz.open(file_path) as doc:
                for page in doc:
                    extracted_text += page.get_text()
        else:
            image = Image.open(file_path)
            extracted_text = pytesseract.image_to_string(image)
    except Exception as e:
        extracted_text = f"Error reading file: {e}"
    if extracted_text:
        with open(EXTRACTED_FILE, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        response_box.insert("end", f"\n[File Uploaded]\n{extracted_text}\n")
        response_box.see("end")
        speak_async("File content uploaded and extracted.")

# Buttons
button_frame = ctk.CTkFrame(app, fg_color="transparent")
button_frame.pack(pady=(0,10))

ask_button = ctk.CTkButton(button_frame, text="Ask AURON", width=180, command=handle_input)
ask_button.grid(row=0, column=0, padx=16)

speak_button = ctk.CTkButton(button_frame, text="Speak", width=140, command=lambda: threading.Thread(target=handle_speech).start())
speak_button.grid(row=0, column=1, padx=8)

upload_button = ctk.CTkButton(button_frame, text="Upload", width=140, command=upload_file)
upload_button.grid(row=0, column=2, padx=8)

# --------------------- Menu & Options ---------------------
def toggle_menu(event=None):
    if menu_frame.winfo_ismapped():
        menu_frame.place_forget()
    else:
        menu_frame.place(x=10, y=60)

def open_chat_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        os.startfile(CHAT_HISTORY_FILE)
    else:
        messagebox.showinfo("Info", "No chat history found.")

def delete_chat_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        os.remove(CHAT_HISTORY_FILE)
        messagebox.showinfo("Info", "Chat history deleted.")
    else:
        messagebox.showinfo("Info", "No chat history to delete.")

def open_notes():
    if os.path.exists(NOTES_FILE):
        os.startfile(NOTES_FILE)
    else:
        messagebox.showinfo("Info", "No notes found.")

def clear_notes():
    if os.path.exists(NOTES_FILE):
        os.remove(NOTES_FILE)
        messagebox.showinfo("Info", "Notes cleared.")
    else:
        messagebox.showinfo("Info", "No notes found.")

menu_btn = ctk.CTkButton(app, text="⋮", width=44, command=toggle_menu, font=("Segoe UI", 20))
menu_btn.place(x=10, y=20)

menu_frame = ctk.CTkFrame(app, width=160)
menu_frame.place_forget()

ctk.CTkButton(menu_frame, text="Light Theme", width=140, command=lambda: change_theme("light")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Dark Theme", width=140, command=lambda: change_theme("dark")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Neon Theme", width=140, command=apply_neon_theme).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open Chat History", width=140, command=open_chat_history).pack(pady=2)
ctk.CTkButton(menu_frame, text="Delete Chat History", width=140, command=delete_chat_history).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open Notes", width=140, command=open_notes).pack(pady=2)
ctk.CTkButton(menu_frame, text="Clear Notes", width=140, command=clear_notes).pack(pady=2)

# quick opens
ctk.CTkButton(menu_frame, text="Open ChatGPT", width=140, command=lambda: open_in_chrome("https://chat.openai.com/")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open Gmail", width=140, command=lambda: open_in_chrome("https://mail.google.com/")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open Classroom", width=140, command=lambda: open_in_chrome("https://classroom.google.com/")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open VS Code", width=140, command=lambda: open_item("vs code")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open Word", width=140, command=lambda: open_item("word")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open Excel", width=140, command=lambda: open_item("excel")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open PowerPoint", width=140, command=lambda: open_item("powerpoint")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open This PC", width=140, command=lambda: open_item("this pc")).pack(pady=2)
ctk.CTkButton(menu_frame, text="Open Recycle Bin", width=140, command=lambda: open_item("recycle bin")).pack(pady=2)

# sticky & todo GUI helpers
def create_sticky_startup_script():
    try:
        os.makedirs(STICKY_STORAGE, exist_ok=True)
        sticky_code = f'''\
import tkinter as tk
import os, json
from tkinter import messagebox
STORAGE = r"{os.path.join(STICKY_STORAGE, 'auron_reminders.json')}"
def load_items():
    if os.path.exists(STORAGE):
        try:
            with open(STORAGE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []
def save_items(items):
    try:
        with open(STORAGE, 'w', encoding='utf-8') as f:
            json.dump(items, f)
    except:
        pass
items = load_items()
if not items:
    items = []
# show first item
if items:
    item = items[0]
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.overrideredirect(True)
    root.geometry("300x140+100+100")
    root.config(bg='#FFF59D')
    tk.Label(root, text=item.get('task','Reminder'), font=('Segoe UI',12,'bold'), bg='#FFF59D').pack(pady=(8,0))
    tk.Label(root, text=item.get('when') or 'No time set', bg='#FFF59D').pack(pady=(6,6))
    def done():
        current = load_items()
        new = [i for i in current if i.get('id') != item.get('id')]
        save_items(new)
        root.destroy()
    def delay():
        root.destroy()
    btnf = tk.Frame(root, bg='#FFF59D'); btnf.pack(pady=(0,8))
    tk.Button(btnf, text='Done', width=8, command=done).pack(side='left', padx=8)
    tk.Button(btnf, text='Delay', width=8, command=delay).pack(side='left', padx=8)
    root.mainloop()
'''
        with open(STICKY_SCRIPT, "w", encoding="utf-8") as f:
            f.write(sticky_code)
        os.makedirs(os.path.dirname(STICKY_STARTUP_BAT), exist_ok=True)
        bat_content = f'@echo off\npythonw "{STICKY_SCRIPT}" || python "{STICKY_SCRIPT}"\n'
        with open(STICKY_STARTUP_BAT, "w", encoding="utf-8") as f:
            f.write(bat_content)
        return True, "Sticky startup script created. It will run at next login (requires Python/pythonw on PATH)."
    except Exception as e:
        return False, f"Failed to create sticky startup script: {e}"

def add_sticky_item(task):
    # Add to reminders JSON for the sticky script
    os.makedirs(STICKY_STORAGE, exist_ok=True)
    storage_file = os.path.join(STICKY_STORAGE, 'auron_reminders.json')
    items = []
    if os.path.exists(storage_file):
        try:
            with open(storage_file, 'r', encoding='utf-8') as f:
                items = json.load(f)
        except:
            items = []
    new_id = (max((i.get("id", 0) for i in items), default=0) + 1) if items else 1
    items.append({"id": new_id, "task": task, "when": None})
    with open(storage_file, 'w', encoding='utf-8') as f:
        json.dump(items, f)
    return f"Sticky note added: {task}"

def create_sticky_startup_handler():
    ok, msg = create_sticky_startup_script()
    messagebox.showinfo("Sticky Startup", msg)

def gui_add_todo_window():
    win = ctk.CTkToplevel(app)
    win.title("Add Todo")
    win.geometry("420x220")
    entry_t = ctk.CTkEntry(win, placeholder_text="Enter todo (optionally: at 7 PM / tomorrow at 9)", width=380)
    entry_t.pack(pady=12)
    def add_it():
        text = entry_t.get().strip()
        if not text:
            messagebox.showwarning("Input required", "Enter a todo item.")
            return
        when, recurring = parse_time_expression(text)
        clean = re.sub(r'\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b','', text, flags=re.I).strip()
        add_todo_task(clean or text, when=when, recurring=recurring)
        messagebox.showinfo("Added", "Todo added.")
        win.destroy()
    ctk.CTkButton(win, text="Add Todo", command=add_it).pack(pady=10)

# Sticky Notes standalone GUI with auto-save & reload
def open_sticky_notes_gui():
    """
    Open a window where user can create, edit, save sticky notes.
    Notes are auto-saved to NOTES_FILE and reloaded on open.
    """
    win = ctk.CTkToplevel(app)
    win.title("AURON Sticky Notes")
    win.geometry("420x420")
    # yellow background for the whole window
    try:
        import tkinter as tk
        win_tk = win
        # CTkToplevel doesn't expose configure('bg') easily; create a canvas/frame to simulate yellow bg
        yellow_frame = ctk.CTkFrame(win, fg_color="#FFF59D")
        yellow_frame.pack(fill="both", expand=True, padx=8, pady=8)
    except:
        yellow_frame = ctk.CTkFrame(win, fg_color="#FFF59D")
        yellow_frame.pack(fill="both", expand=True, padx=8, pady=8)

    title_lbl = ctk.CTkLabel(yellow_frame, text="📝 Sticky Notes", font=("Segoe UI", 18, "bold"), text_color="black")
    title_lbl.pack(pady=(8,4))

    # Textbox area for notes (black text on light yellow)
    notes_box = ctk.CTkTextbox(yellow_frame, width=380, height=260, font=("Segoe UI", 13), text_color="black", fg_color="#FFF59D")
    notes_box.pack(pady=(4,6))

    # load existing notes if any
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = f.read()
            if data:
                notes_box.insert("0.0", data)
        except Exception as e:
            print("Could not load notes:", e)

    # Save / Clear buttons
    btn_frame = ctk.CTkFrame(yellow_frame, fg_color="#FFF59D")
    btn_frame.pack(pady=(6,8))

    def save_notes():
        try:
            os.makedirs(os.path.dirname(NOTES_FILE) or ".", exist_ok=True)
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                f.write(notes_box.get("0.0", "end").strip())
            messagebox.showinfo("Saved", "Notes saved.")
            speak_async("Notes saved")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save notes: {e}")

    def clear_notes_gui():
        if messagebox.askyesno("Confirm", "Clear all notes?"):
            notes_box.delete("0.0", "end")
            if os.path.exists(NOTES_FILE):
                try:
                    os.remove(NOTES_FILE)
                except:
                    pass
            speak_async("Notes cleared")

    save_btn = ctk.CTkButton(btn_frame, text="Save", width=120, height=36, fg_color="#39A13B", hover_color="#2E8B32",
                             text_color="white", command=save_notes)
    save_btn.grid(row=0, column=0, padx=8)

    clear_btn = ctk.CTkButton(btn_frame, text="Clear", width=120, height=36, fg_color="#D84315", hover_color="#B71C1C",
                              text_color="white", command=clear_notes_gui)
    clear_btn.grid(row=0, column=1, padx=8)

ctk.CTkButton(menu_frame, text="Create Sticky Startup", width=140, command=create_sticky_startup_handler).pack(pady=2)
ctk.CTkButton(menu_frame, text="Add Todo (GUI)", width=140, command=gui_add_todo_window).pack(pady=2)
ctk.CTkButton(menu_frame, text="Show Todos", width=140, command=lambda: messagebox.showinfo("Todos", open_todos_text())).pack(pady=2)
ctk.CTkButton(menu_frame, text="Sticky Notes (Open)", width=140, command=open_sticky_notes_gui).pack(pady=2)

def open_todos_text():
    if not os.path.exists(TODO_FILE):
        return "No todos found."
    with open(TODO_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return "No todos found."
    out = "".join(f"{i+1}. {l}" for i,l in enumerate(lines))
    return out

# --------------------- Battery Monitor ---------------------
battery_alerted = False

def battery_monitor_loop():
    global battery_alerted
    while True:
        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                percent = int(batt.percent)
                plugged = batt.power_plugged
                if not plugged and percent <= BATTERY_ALERT_THRESHOLD and not battery_alerted:
                    msg = f"Battery low: {percent} percent. Please plug in the charger."
                    try:
                        app.after(0, lambda m=msg: messagebox.showwarning("Battery Low", m))
                    except:
                        pass
                    speak_async(msg)
                    battery_alerted = True
                if plugged or percent > BATTERY_ALERT_THRESHOLD:
                    battery_alerted = False
            time.sleep(60)
        except Exception as e:
            print("Battery monitor error:", e)
            time.sleep(60)

threading.Thread(target=battery_monitor_loop, daemon=True).start()

# --------------------- Greet & Start ---------------------
def greet_on_start():
    greeting = "Welcome back! AURON is online and ready to assist you."
    response_box.insert("end", f"AURON: {greeting}\n")
    response_box.see("end")
    speak_async(greeting)
    update_time_weather()

app.after(1000, greet_on_start)

app.mainloop()
