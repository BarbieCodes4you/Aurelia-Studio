"""Ready-made content that saves the client typing: invitation wording and sample programmes per
occasion, plus parsers for a pasted guest list and a pasted caterer's menu.

The same data is exported to the static site (tools/export_preview.py -> data.js), and
preview_site/journey.js has JavaScript versions of the two parsers. Keep them in step.

Wording uses {hosts} and {deadline}; fill them with fill_wording() before showing them in a form.
Programme offsets are minutes from the event's start time.
"""
from __future__ import annotations

import re

WORDING = {
    "white-wedding": [
        {"label": "Classic", "welcome": "Together with their families",
         "invitation": "{hosts} request the pleasure of your company at the celebration of their marriage.",
         "rsvp_note": "Kindly reply by {deadline}.", "closing": "We look forward to celebrating with you."},
        {"label": "Warm and simple", "welcome": "We're getting married!",
         "invitation": "We'd love you to be there as we say \"I do\" and celebrate with the people who mean the most to us.",
         "rsvp_note": "Please let us know by {deadline} if you can make it.", "closing": "With love, {hosts}"},
    ],
    "traditional-wedding": [
        {"label": "Two families", "welcome": "Two families, one celebration",
         "invitation": "The families of {hosts} invite you to join them as they celebrate this union in the tradition of their families.",
         "rsvp_note": "Kindly confirm your attendance by {deadline}.", "closing": "Your presence will be an honour to both families."},
        {"label": "Joyful", "welcome": "Come celebrate with us",
         "invitation": "Bring your singing voice and your dancing shoes. {hosts} are getting married, and the whole family is coming together.",
         "rsvp_note": "Please reply by {deadline} so the families can plan.", "closing": "Thank you for celebrating with us."},
    ],
    "lobola": [
        {"label": "Formal", "welcome": "Lobola negotiations and celebration",
         "invitation": "The families of {hosts} invite you to join them for the lobola negotiations and the celebration that follows.",
         "rsvp_note": "Kindly confirm by {deadline} and tell us which family you are coming with.", "closing": "We look forward to welcoming you."},
        {"label": "Celebration", "welcome": "The families are meeting",
         "invitation": "Join us as two families come together for {hosts}. The negotiations are for the delegations; the celebration afterwards is for everyone.",
         "rsvp_note": "Please reply by {deadline}.", "closing": "Come hungry and ready to celebrate."},
    ],
    "engagement": [
        {"label": "Announcement", "welcome": "We're engaged!",
         "invitation": "{hosts} are engaged, and we'd love to celebrate the news with you.",
         "rsvp_note": "Let us know by {deadline} if you can join us.", "closing": "See you there."},
        {"label": "Relaxed", "welcome": "Raise a glass with us",
         "invitation": "Join {hosts} for drinks, good food and a toast to the next chapter.",
         "rsvp_note": "Please reply by {deadline}.", "closing": "With love."},
    ],
    "multi-day-wedding": [
        {"label": "Weekend", "welcome": "A weekend of celebration",
         "invitation": "{hosts} invite you to spend the weekend with them, from the welcome dinner to the farewell brunch. Every part of the weekend is on this page.",
         "rsvp_note": "Please reply by {deadline} and tell us which parts of the weekend you'll join.", "closing": "We can't wait to spend the weekend with you."},
        {"label": "Classic", "welcome": "Together with their families",
         "invitation": "{hosts} request the pleasure of your company at the celebration of their marriage. Details for each day are below.",
         "rsvp_note": "Kindly reply by {deadline}.", "closing": "With love and gratitude."},
    ],
    "baby-shower": [
        {"label": "Classic", "welcome": "A little one is on the way",
         "invitation": "Please join us for a baby shower in honour of {hosts}.",
         "rsvp_note": "Kindly reply by {deadline}.", "closing": "Gift ideas are on the registry, but your company is the best gift."},
        {"label": "Playful", "welcome": "Oh baby!",
         "invitation": "Come and shower {hosts} with love before the baby arrives. There will be cake, games and lots of laughter.",
         "rsvp_note": "Let us know by {deadline} so we have enough cake.", "closing": "See you there!"},
    ],
    "gender-reveal": [
        {"label": "Guessing game", "welcome": "Boy or girl?",
         "invitation": "{hosts} are finding out, and they want you there when they do.",
         "rsvp_note": "Reply by {deadline}, and leave your guess in your RSVP.", "closing": "Pink or blue, we can't wait to celebrate with you."},
        {"label": "Simple", "welcome": "The big reveal",
         "invitation": "Join {hosts} for the moment we find out if it's a boy or a girl.",
         "rsvp_note": "Please reply by {deadline}.", "closing": "Bring your best guess."},
    ],
    "welcome-baby": [
        {"label": "Meet the baby", "welcome": "Meet our little one",
         "invitation": "{hosts} would love you to come and meet the newest member of the family.",
         "rsvp_note": "Please let us know by {deadline} if you can come.", "closing": "With love and gratitude."},
        {"label": "Welcome home", "welcome": "Welcome to the world",
         "invitation": "Our family has grown. Join {hosts} to celebrate and welcome our baby home.",
         "rsvp_note": "Kindly reply by {deadline}.", "closing": "Thank you for loving us."},
    ],
    "birthday": [
        {"label": "Party", "welcome": "Let's celebrate",
         "invitation": "You're invited to celebrate {hosts}.",
         "rsvp_note": "Reply by {deadline} so we save you a seat.", "closing": "See you there."},
        {"label": "Surprise", "welcome": "It's a surprise!",
         "invitation": "We're throwing a surprise party: {hosts}. Please keep it a secret!",
         "rsvp_note": "Please reply by {deadline}, and don't tell anyone.", "closing": "Arrive on time so you don't spoil the surprise."},
    ],
    "anniversary": [
        {"label": "Classic", "welcome": "Celebrating the years together",
         "invitation": "Please join us to celebrate {hosts}.",
         "rsvp_note": "Kindly reply by {deadline}.", "closing": "Thank you for being part of our story."},
        {"label": "Relaxed", "welcome": "Still celebrating",
         "invitation": "Join us for an evening of good food, old stories and a toast to {hosts}.",
         "rsvp_note": "Let us know by {deadline}.", "closing": "With love."},
    ],
    "private-celebration": [
        {"label": "Simple", "welcome": "You're invited",
         "invitation": "{hosts} would love you to join them.",
         "rsvp_note": "Please reply by {deadline}.", "closing": "We look forward to seeing you."},
        {"label": "Dinner", "welcome": "An evening together",
         "invitation": "Join {hosts} for an evening of good food and great company.",
         "rsvp_note": "Kindly reply by {deadline}.", "closing": "See you there."},
    ],
    "graduation": [
        {"label": "Proud family", "welcome": "Celebrating a graduate",
         "invitation": "{hosts} invite you to celebrate a well-earned graduation.",
         "rsvp_note": "Kindly reply by {deadline}.", "closing": "Thank you for supporting the journey."},
        {"label": "Celebration", "welcome": "The hard work is done",
         "invitation": "Join {hosts} for the ceremony and the celebration afterwards.",
         "rsvp_note": "Please reply by {deadline}.", "closing": "See you there."},
    ],
    "corporate": [
        {"label": "Formal", "welcome": "You're invited",
         "invitation": "{hosts} invite you to join us. The agenda, venue and catering details are below.",
         "rsvp_note": "Please confirm your attendance by {deadline}.", "closing": "We look forward to seeing you."},
        {"label": "Relaxed", "welcome": "Join us",
         "invitation": "Join {hosts} for an afternoon of ideas, conversation and good food.",
         "rsvp_note": "Kindly confirm by {deadline} and tell us about any dietary needs.", "closing": "Thank you."},
    ],
    "family-celebration": [
        {"label": "Reunion", "welcome": "Bringing the family together",
         "invitation": "{hosts} invite you to join the family for a day of catching up, remembering and celebrating together.",
         "rsvp_note": "Please reply by {deadline} so we can plan food and seating.", "closing": "We hope to see everyone there."},
        {"label": "Unveiling", "welcome": "In loving memory",
         "invitation": "{hosts} invite you to join them for the unveiling of the tombstone, followed by a meal together.",
         "rsvp_note": "Kindly let us know by {deadline} if you will attend.", "closing": "Thank you for standing with our family."},
    ],
}

# (minutes from start, title, kind, detail)
PROGRAMMES = {
    "wedding": [(-30, "Guests arrive", "other", "Find your seat for the ceremony"), (0, "Ceremony", "ceremony", ""),
                (45, "Photos and welcome drinks", "activity", "Canapés on the lawn while the couple has photos"),
                (120, "Guests seated for the reception", "reception", ""), (135, "Entrance of the couple", "entertainment", ""),
                (150, "Starters", "meal", ""), (180, "Speeches", "speech", ""), (210, "Main course", "meal", ""),
                (255, "First dance", "entertainment", ""), (270, "Cake and dessert", "meal", ""),
                (285, "Dance floor opens", "entertainment", "")],
    "traditional-wedding": [(0, "Arrival of the families", "other", ""), (30, "Welcome and introductions", "speech", ""),
                            (60, "Traditional ceremony", "ceremony", ""), (120, "Exchange of gifts", "ceremony", ""),
                            (150, "Meal", "meal", ""), (210, "Entertainment and dancing", "entertainment", ""),
                            (300, "Closing and thanks", "speech", "")],
    "lobola": [(0, "Arrival of the delegation", "other", "The visiting family arrives and waits to be welcomed"),
               (30, "Welcome and introductions", "speech", ""), (60, "Negotiations", "ceremony", "Family delegations only"),
               (180, "Agreement and announcement", "speech", ""), (210, "Celebration and meal", "meal", "Everyone is welcome"),
               (300, "Thanks and farewell", "speech", "")],
    "engagement": [(0, "Arrival and drinks", "other", ""), (45, "Welcome", "speech", ""), (60, "A toast to the couple", "speech", ""),
                   (90, "Food is served", "meal", ""), (150, "Music and dancing", "entertainment", "")],
    "baby-shower": [(0, "Guests arrive", "other", ""), (30, "Welcome", "speech", ""), (45, "Games", "activity", ""),
                    (90, "Food and cake", "meal", ""), (120, "Opening the gifts", "activity", ""), (165, "Thank you and goodbyes", "speech", "")],
    "gender-reveal": [(0, "Arrival and snacks", "other", ""), (30, "Place your guess", "activity", ""), (60, "Food", "meal", ""),
                      (90, "The reveal", "entertainment", ""), (105, "Cake and celebration", "meal", "")],
    "welcome-baby": [(0, "Arrival", "other", ""), (30, "Welcome and blessing", "ceremony", ""), (60, "Meet the baby", "activity", ""),
                     (75, "Food and drinks", "meal", ""), (150, "Thank you", "speech", "")],
    "birthday": [(0, "Arrival and drinks", "other", ""), (45, "Food is served", "meal", ""), (105, "Speeches and a toast", "speech", ""),
                 (120, "Cake", "meal", ""), (135, "Dance floor opens", "entertainment", "")],
    "anniversary": [(0, "Arrival and drinks", "other", ""), (30, "Guests seated", "reception", ""), (45, "Welcome", "speech", ""),
                    (60, "Dinner", "meal", ""), (120, "Toasts and stories", "speech", ""), (150, "Cake and dessert", "meal", ""),
                    (165, "Dancing", "entertainment", "")],
    "private-celebration": [(0, "Arrival and drinks", "other", ""), (45, "Welcome", "speech", ""), (60, "Dinner", "meal", ""),
                            (150, "Coffee and dessert", "meal", "")],
    "graduation": [(0, "Graduation ceremony", "ceremony", ""), (150, "Family photos", "activity", ""),
                   (210, "Celebration lunch", "meal", ""), (270, "Speeches and a toast", "speech", ""), (300, "After-party", "entertainment", "")],
    "corporate": [(0, "Registration and coffee", "other", ""), (30, "Welcome and opening", "speech", ""), (45, "Keynote", "speech", ""),
                  (105, "Break", "meal", ""), (120, "Panel discussion", "speech", ""), (180, "Lunch", "meal", ""),
                  (240, "Workshops", "activity", ""), (330, "Closing remarks", "speech", ""), (345, "Networking drinks", "reception", "")],
    "family-celebration": [(0, "Arrival", "other", ""), (30, "Welcome and prayer", "ceremony", ""), (60, "Main programme", "ceremony", ""),
                           (120, "Meal", "meal", ""), (180, "Family photo", "activity", ""), (210, "Thanks and closing", "speech", "")],
}
PROGRAMME_FOR = {"white-wedding": "wedding", "multi-day-wedding": "wedding"}
DEFAULT_START = {"weddings": "14:00", "baby": "11:00", "parties": "18:00", "other": "10:00"}


def wording_options(category: str) -> list[dict]:
    return WORDING.get(category) or WORDING["private-celebration"]


def fill_wording(text: str, hosts: str, deadline: str) -> str:
    """Put the names and RSVP date into a suggestion. Without a deadline, drop "by {deadline}"."""
    text = text.replace("{hosts}", hosts or "the hosts")
    if deadline:
        return text.replace("{deadline}", deadline)
    return re.sub(r"\s*by \{deadline\}", "", text).replace("{deadline}", "")


def programme_key(category: str) -> str:
    key = PROGRAMME_FOR.get(category, category)
    return key if key in PROGRAMMES else "private-celebration"


def sample_programme(category: str, start: str = "", group: str = "") -> list[dict]:
    """Programme items with real clock times, counted from the start time (or a sensible default)."""
    start = start if re.match(r"^\d{2}:\d{2}$", start or "") else DEFAULT_START.get(group, "12:00")
    base = int(start[:2]) * 60 + int(start[3:])
    out = []
    for offset, title, kind, detail in PROGRAMMES[programme_key(category)]:
        t = (base + offset) % (24 * 60)
        out.append({"item_time": f"{t // 60:02d}:{t % 60:02d}", "title": title, "kind": kind, "description": detail})
    return out


# --- pasted guest list ---------------------------------------------------------------------------------
_EMAIL = re.compile(r"[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\+?\d[\d ()-]{6,}\d")
_HEADER_WORDS = {"name", "names", "full name", "guest", "guests", "guest name", "first name", "surname", "last name",
                 "phone", "mobile", "cell", "cellphone", "phone number", "whatsapp", "email", "e-mail", "email address"}


def parse_guest_list(text: str, limit: int = 2000) -> list[dict]:
    """One guest per line, in any order: name, mobile, email (commas, tabs or semicolons between).
    Copying rows from Excel or Google Sheets works too. A header row is skipped."""
    out, seen = [], set()
    for raw in (text or "").splitlines():
        line = raw.strip().strip(",;\t")
        if not line:
            continue
        email = _EMAIL.search(line)
        rest = line.replace(email.group(0), " ") if email else line
        phone = _PHONE.search(rest)
        rest = rest.replace(phone.group(0), " ") if phone else rest
        cells = [c.strip().lower() for c in re.split(r"[,;\t|]+", line) if c.strip()]
        if cells and all(c in _HEADER_WORDS for c in cells):
            continue
        name = re.sub(r"\s+", " ", re.sub(r"[,;\t|]+", " ", rest)).strip(" -")
        if not name:
            continue
        key = (name.lower(), email.group(0).lower() if email else "")
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name[:120], "phone": phone.group(0).strip() if phone else "",
                    "email": email.group(0).lower() if email else ""})
        if len(out) >= limit:
            break
    return out


# --- pasted menu -----------------------------------------------------------------------------------------
_COURSE_WORDS = {
    "Canapés": ("canapé", "canape", "canapés", "canapes", "snacks", "hors d'oeuvres", "on arrival"),
    "Starter": ("starter", "starters", "entrée", "entree", "entrées", "appetiser", "appetisers", "appetizer", "appetizers", "first course"),
    "Main": ("main", "mains", "main course", "main courses", "buffet", "main meal"),
    "Dessert": ("dessert", "desserts", "pudding", "sweet", "sweets"),
    "Late-night": ("late-night", "late night", "late night snack", "midnight snack"),
    "Drinks": ("drinks", "beverages", "bar"),
}


def _course_of(word: str) -> str:
    w = word.strip().strip(":").strip().lower()
    for course, words in _COURSE_WORDS.items():
        if w in words:
            return course
    return ""


def parse_menu(text: str, limit: int = 60) -> list[dict]:
    """Turn a caterer's menu into dishes. A line that is only a course name ("Starters") sets the course
    for the lines below it; "Main: Lamb shank - rosemary jus" sets it inline. Text after " - ", " – " or
    " with " in brackets becomes the description."""
    items, course = [], "Main"
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("•*-·– ").strip()
        if not line:
            continue
        c = _course_of(line)
        if c:
            course = c
            continue
        m = re.match(r"^([^:]{2,30}):\s*(.+)$", line)
        this_course = course
        if m and _course_of(m.group(1)):
            this_course, line = _course_of(m.group(1)), m.group(2).strip()
            course = this_course
        name, desc = line, ""
        for sep in (" - ", " – ", " — ", " | "):
            if sep in line:
                name, desc = (s.strip() for s in line.split(sep, 1))
                break
        else:
            b = re.match(r"^(.+?)\s*\((.+)\)$", line)
            if b:
                name, desc = b.group(1).strip(), b.group(2).strip()
        if name:
            items.append({"course": this_course, "name": name[:120], "description": desc[:240], "tags": [], "selectable": False})
        if len(items) >= limit:
            break
    return items
