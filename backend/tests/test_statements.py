"""Workbook upload endpoint tests independent of the trained ML artifact."""
from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from backend.app.main import app


def workbook_bytes():
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        archive.writestr('xl/workbook.xml', """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>""")
        archive.writestr('xl/_rels/workbook.xml.rels', """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>""")
        archive.writestr('xl/worksheets/sheet1.xml', """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Date</t></is></c><c r="B1" t="inlineStr"><is><t>Amount</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>2026-11-01</t></is></c><c r="B2"><v>100</v></c></row></sheetData></worksheet>""")
    return buffer.getvalue()


def test_valid_workbook():
    with TestClient(app) as client:
        response = client.post('/api/statement/workbook', content=workbook_bytes())
    assert response.status_code == 200, response.text
    assert response.json()['sheets'][0]['rows'][0]['cells'] == ['Date','Amount']
    assert response.json()['sheets'][0]['rows'][1]['cells'] == ['2026-11-01','100']


def test_non_excel_file_is_rejected():
    with TestClient(app) as client:
        response = client.post('/api/statement/workbook', content=b'not a workbook')
    assert response.status_code == 422


def test_oversized_workbook_is_rejected():
    with TestClient(app) as client:
        response = client.post('/api/statement/workbook', content=b'x' * 5_000_001)
    assert response.status_code == 413
