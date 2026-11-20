"""Read the table values of a local Excel statement without saving the upload."""
from io import BytesIO
import posixpath
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def read_tables(content):
    with ZipFile(BytesIO(content)) as archive:
        if sum(entry.file_size for entry in archive.infolist()) > 20_000_000:
            raise ValueError("This workbook is too large. Export a shorter statement.")
        def xml(path):
            return ET.fromstring(archive.read(path))
        book = xml("xl/workbook.xml")
        properties = book.find("{*}workbookPr")
        date1904 = properties is not None and properties.get("date1904") in ("1", "true")
        targets = {rel.get("Id"): rel.get("Target") for rel in xml("xl/_rels/workbook.xml.rels")}
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(t.text or "" for t in item.iterfind(".//{*}t"))
                       for item in xml("xl/sharedStrings.xml")]
        sheets = []
        total = 0
        for sheet in book.findall(".//{*}sheet"):
            if sheet.get("state", "visible") != "visible":
                continue
            target = targets[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
            path = posixpath.normpath(posixpath.join("xl", target)).lstrip("/")
            rows = []
            for row in xml(path).iterfind(".//{*}sheetData/{*}row"):
                cells = []
                for cell in row.findall("{*}c"):
                    value = cell.findtext("{*}v", "")
                    kind = cell.get("t")
                    if kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iterfind(".//{*}t"))
                    elif kind == "s":
                        value = strings[int(value)]
                    if not value:
                        continue
                    letters = re.fullmatch(r"([A-Z]+)\d+", cell.attrib["r"])[1]
                    col = 0
                    for letter in letters:
                        col = col * 26 + ord(letter) - 64
                    if col > 128:
                        raise ValueError("Export a worksheet with at most 128 columns.")
                    cells.extend([""] * (col - len(cells)))
                    cells[col-1] = value
                if cells:
                    total += 1
                    if total > 10000:
                        raise ValueError("Export a workbook with fewer than 10,000 populated rows.")
                    rows.append({"number": int(row.attrib["r"]), "cells": cells})
            if rows:
                sheets.append({"name": sheet.attrib["name"], "rows": rows})
        if not sheets:
            raise ValueError("No visible worksheet contains data.")
        return {"sheets": sheets, "date1904": date1904}


@router.post("/statement/workbook")
async def statement_workbook(request: Request):
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > 5_000_000:
            raise HTTPException(413, "Choose an Excel workbook under 5 MB.")
        content.extend(chunk)
    try:
        return read_tables(content)
    except (BadZipFile, KeyError, ET.ParseError, IndexError, TypeError, RuntimeError, OSError):
        raise HTTPException(422, "Open the file in Excel and save an unlocked .xlsx copy.")
    except ValueError as error:
        raise HTTPException(422, str(error))
