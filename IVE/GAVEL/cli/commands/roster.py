from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from typing import Optional

from GAVEL.app.dtos.roster import RosterRequest
from GAVEL.app_context import AppContext


def handle_roster_list_terms(ctx: AppContext, args: Namespace) -> int:
    try:
        terms = ctx.services.roster_client.list_terms()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not terms:
        print("No terms found (API may require authentication).")
        return 0

    print("\nAvailable terms:\n")
    for t in terms:
        marker = " (default)" if t.default else ""
        print(f"  {t.code}  {t.name}{marker}")
    print()
    return 0


def handle_roster_download(ctx: AppContext, args: Namespace) -> int:
    client = ctx.services.roster_client

    # Resolve class number: direct or via catalog lookup
    if args.class_number:
        request = RosterRequest(term=args.term, class_number=args.class_number)
    elif args.subject and args.catalog_number:
        request = _lookup_and_select(ctx, args)
        if request is None:
            return 1
    else:
        print(
            "ERROR: Provide either --class-number (direct) or "
            "--subject + --catalog-number (lookup).",
            file=sys.stderr,
        )
        return 2

    if args.info_only:
        print(
            f"\n[INFO] Resolved: term={request.term}, "
            f"class_number={request.class_number}"
        )
        return 0

    # Authenticate and download
    try:
        client.authenticate()
        print(
            f"[ROSTER] Downloading roster for term={request.term}, "
            f"class={request.class_number}..."
        )
        csv_text = client.fetch_roster(request)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    if args.output:
        Path(args.output).write_text(csv_text, encoding="utf-8")
        print(f"[ROSTER] Saved to {args.output}")
    else:
        print("\n--- ROSTER CSV ---")
        print(csv_text)
        print("--- END ---")

    return 0


def _lookup_and_select(
    ctx: AppContext, args: Namespace,
) -> Optional[RosterRequest]:
    """Query the catalog API and let the user select a section."""
    client = ctx.services.roster_client

    print(
        f"[LOOKUP] Searching for {args.subject} {args.catalog_number} "
        f"in term {args.term}..."
    )
    try:
        sections = client.find_sections(
            args.term, args.subject, args.catalog_number,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return None

    if not sections:
        print("No sections found.", file=sys.stderr)
        return None

    if len(sections) == 1:
        section = sections[0]
        print(f"[LOOKUP] Found one section: {section.display_label}")
        return RosterRequest(term=args.term, class_number=section.class_number)

    print(f"\nFound {len(sections)} sections:\n")
    for i, s in enumerate(sections, start=1):
        print(f"  {i:>3}. {s.display_label}")
    print()

    while True:
        choice = input(
            f"Select a section (1-{len(sections)}), or 'q' to quit: "
        ).strip()
        if choice.lower() == "q":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sections):
                selected = sections[idx]
                print(f"[LOOKUP] Selected: {selected.display_label}")
                return RosterRequest(
                    term=args.term, class_number=selected.class_number,
                )
        except ValueError:
            pass
        print(f"  Invalid choice. Enter 1-{len(sections)} or 'q'.")
