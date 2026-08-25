"""
Unit tests for catalog API class parsing, focused on the session designator.
"""

from __future__ import annotations

from GAVEL.app.dtos.roster import SESSION_PLACEHOLDER
from GAVEL.infra.roster.catalog_api import CatalogApiClassResolver


def classes_payload(clas: dict) -> dict:
    base = {
        "CLASSNBR": 12345,
        "SUBJECT": "SER",
        "CATALOGNBR": "401",
        "COURSETITLELONG": "Software Enterprise: Project and Process",
        "INSTRUCTORSLIST": "Ruben Acuna",
        "DAYSTIMES": "TTh 12:00PM-1:15PM",
        "CAMPUS": "TEMPE",
        "ENRLCAP": 40,
        "ENRLTOT": 32,
        "COMPONENTPRIMARY": "LEC",
    }
    base.update(clas)
    return {"classes": [{"CLAS": base}]}


def test_parse_classes_carries_session_code_onto_the_dto() -> None:
    sections = CatalogApiClassResolver._parse_classes(classes_payload({"SESSIONCODE": "B"}))

    assert len(sections) == 1
    assert sections[0].session == "B"
    assert sections[0].session_display == "B"


def test_parse_classes_normalizes_padded_session_code() -> None:
    sections = CatalogApiClassResolver._parse_classes(classes_payload({"SESSIONCODE": " C "}))

    assert sections[0].session == "C"


def test_parse_classes_placeholders_a_missing_session_code() -> None:
    sections = CatalogApiClassResolver._parse_classes(classes_payload({}))

    assert sections[0].session == ""
    assert sections[0].session_display == SESSION_PLACEHOLDER
