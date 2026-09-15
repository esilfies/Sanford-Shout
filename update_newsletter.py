#!/usr/bin/env python3
"""
Daily maintenance script for The Silfies Select newsletter.

What it does, every time it's run:
1. Looks at every event card (each needs data-start="YYYY-MM-DD" and,
   for multi-day events, data-end="YYYY-MM-DD").
2. Any event whose last day is before today gets pulled out of its month
   section and added as a one-line entry to the "Last Month's Events"
   list at the bottom.
3. Any month header left with zero events under it is removed.
4. The footer's "Last updated" line is stamped with today's date.

Requires: pip install beautifulsoup4 lxml
Run against your published HTML file (see the GitHub Actions workflow
for how this runs automatically every day).
"""

import sys
from datetime import date, datetime

from bs4 import BeautifulSoup

HTML_PATH = "index.html"  # change if your file has a different name


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def format_range(start, end):
    """(date, date) -> 'Sep 5' / 'Sep 5-7' / 'Sep 29-Oct 2'"""
    if end is None or end == start:
        return start.strftime("%b %-d")
    if start.month == end.month:
        return f"{start.strftime('%b %-d')}\u2013{end.day}"
    return f"{start.strftime('%b %-d')}\u2013{end.strftime('%b %-d')}"


def main():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    today = date.today()
    moved = []  # (start_date, li_tag) so we can sort before inserting

    events = soup.select("div.event[data-start]")
    for ev in events:
        start = parse_date(ev["data-start"])
        end = parse_date(ev["data-end"]) if ev.has_attr("data-end") else start

        if end >= today:
            continue  # still upcoming -- leave it alone

        h3 = ev.select_one("h3")
        venue = ev.select_one("p.venue")
        name = h3.get_text(strip=True) if h3 else "Unknown event"
        venue_text = venue.get_text(strip=True) if venue else ""
        date_str = format_range(start, end)

        li = soup.new_tag("li")
        li.string = f"{name} \u2014 {venue_text} "
        span = soup.new_tag("span")
        span.string = f"\u00b7 {date_str}"
        li.append(span)

        moved.append((start, li))
        ev.decompose()  # remove the card entirely

    # Drop any month-divider with no events left under it
    for divider in soup.select("div.month-divider"):
        sib = divider.find_next_sibling()
        has_event = False
        while sib is not None:
            classes = sib.get("class", [])
            if "month-divider" in classes or "past-section" in classes:
                break
            if "event" in classes:
                has_event = True
                break
            sib = sib.find_next_sibling()
        if not has_event:
            divider.decompose()

    # Insert newly-past events into the Just Missed Out! list, newest first
    # (they go at the top so the most recently completed event is always
    # in the top-left position, since the list uses a 2-column CSS layout
    # that fills top-to-bottom, left column first).
    if moved:
        moved.sort(key=lambda pair: pair[0])  # oldest first...
        ul = soup.select_one("div.past-section ul")
        if ul is not None:
            for _, li in moved:
                ul.insert(0, li)  # ...each inserted at position 0, so by
                                   # the time the loop finishes, the newest
                                   # of this batch ends up on top overall.
        else:
            print("WARNING: couldn't find div.past-section ul -- events "
                  "were removed from their month but not archived.", file=sys.stderr)

    # Stamp today's date in the footer (tolerant of "Last updated" /
    # "Last Updated:" / extra whitespace, etc.)
    footer_p = soup.select_one("footer p")
    if footer_p and footer_p.get_text(strip=True).lower().startswith("last updated"):
        # Preserve whatever the existing line used for "Last updated" vs
        # "Last Updated:" isn't worth guessing -- just standardize it.
        footer_p.string = f"Last updated: {today.strftime('%B %-d, %Y')}"

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(str(soup))

    print(f"Pruned {len(moved)} past event(s). Footer stamped {today.isoformat()}.")


if __name__ == "__main__":
    main()
