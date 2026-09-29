from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.dtos.roster import ClassSection
from GAVEL.app.usecases.download_roster import DownloadRosterRequest, DownloadRosterUseCase
from GAVEL.app.workspace.layout import CourseFolder, CourseKey
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder, workspace_from_args


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
    # Resolve class number: direct or via catalog lookup
    section: ClassSection | None = None
    if args.class_number:
        class_number = args.class_number
    elif args.subject and args.catalog_number:
        section = _lookup_and_select(ctx, args)
        if section is None:
            return 1
        class_number = section.class_number
    else:
        print(
            "ERROR: Provide either --class-number (direct) or "
            "--subject + --catalog-number (lookup).",
            file=sys.stderr,
        )
        return 2

    if args.info_only:
        print(f"\n[INFO] Resolved: term={args.term}, class_number={class_number}")
        return 0

    folder = _course_folder(ctx, args, section)
    if folder is None:
        return 2

    try:
        print(f"[ROSTER] Downloading roster for term={args.term}, class={class_number}...")
        result = DownloadRosterUseCase(ctx.services.roster_client).execute(
            DownloadRosterRequest(
                term=args.term,
                class_number=class_number,
                folder=folder,
                overwrite=args.overwrite,
            )
        )
    except ArtifactExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"[ROSTER] {result.message}")
    return 0


def _course_folder(
    ctx: AppContext, args: Namespace, section: ClassSection | None
) -> CourseFolder | None:
    """``--course-folder`` when given; otherwise named from the term and the looked-up section."""
    if args.course_folder:
        return resolve_course_folder(ctx, args)
    if section is None:
        print(
            "Error: --course-folder is required with --class-number (a class number alone "
            "cannot name the course folder). Use --subject + --catalog-number to look the "
            "section up, or pass --course-folder like ser222_25sc_12345.",
            file=sys.stderr,
        )
        return None
    try:
        key = CourseKey.from_roster(args.term, section)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return None
    return workspace_from_args(args).course(key)


def _lookup_and_select(
    ctx: AppContext,
    args: Namespace,
) -> ClassSection | None:
    """Query the catalog API and let the user select a section."""
    client = ctx.services.roster_client

    print(f"[LOOKUP] Searching for {args.subject} {args.catalog_number} in term {args.term}...")
    try:
        sections = client.find_sections(
            args.term,
            args.subject,
            args.catalog_number,
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
        return section

    print(f"\nFound {len(sections)} sections:\n")
    for i, s in enumerate(sections, start=1):
        print(f"  {i:>3}. {s.display_label}")
    print()

    while True:
        choice = input(f"Select a section (1-{len(sections)}), or 'q' to quit: ").strip()
        if choice.lower() == "q":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sections):
                selected = sections[idx]
                print(f"[LOOKUP] Selected: {selected.display_label}")
                return selected
        except ValueError:
            pass
        print(f"  Invalid choice. Enter 1-{len(sections)} or 'q'.")
