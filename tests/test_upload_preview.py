import io
import pytest
from flask import g
from werkzeug.datastructures import FileStorage
from conftest import login_as
from psb.db import one,transaction
from psb.files import save_upload
from psb.domain import participant
from test_system import paid_participant,PDF
from test_profile_photo import image


@pytest.mark.parametrize('format',['pdf','image'])
def test_inline_preview_keeps_download_and_private_access(app,format):
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid,aid,_=paid_participant(account=True)
            other,_,_=paid_participant(account=True)
            uid=save_upload(FileStorage(stream=io.BytesIO(PDF) if format=='pdf' else image(),filename='uji.pdf' if format=='pdf' else 'uji.png'),aid,pid,'akta')
            owner=participant(pid)['number'];outsider=participant(other)['number']
    c=app.test_client()
    for user in [owner,'berkas','admin']:
        login_as(app,c,user)
        preview=c.get(f'/berkas/{uid}/lihat');download=c.get(f'/berkas/{uid}')
        assert preview.status_code==download.status_code==200
        assert preview.headers['Content-Disposition'].startswith('inline;')
        assert download.headers['Content-Disposition'].startswith('attachment;')
        assert preview.data==download.data
        assert 'no-store' in preview.headers['Cache-Control']
    for user in [outsider,'bendahara']:
        login_as(app,c,user)
        assert c.get(f'/berkas/{uid}/lihat').status_code==403
    assert app.test_client().get(f'/berkas/{uid}/lihat').status_code==302

def test_transfer_proof_preview_from_finance_keeps_financial_permissions(app):
    from test_system import passed
    from psb.domain import create_payment
    import secrets
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid,aid,_=paid_participant(account=True)
            passed(pid)
            uid=save_upload(FileStorage(stream=io.BytesIO(PDF),filename='transfer.pdf'),aid,pid,'bukti')
            create_payment(aid,'daftar_ulang','transfer',1000000,secrets.token_hex(20),uid)
            owner=participant(pid)['number']
    c=app.test_client()
    login_as(app,c,'bendahara')
    page=c.get('/keuangan/verifikasi').get_data(as_text=True)
    assert f'href="/berkas/{uid}/lihat" target="_blank"' in page
    for user in ['bendahara','admin',owner]:
        login_as(app,c,user)
        result=c.get(f'/berkas/{uid}/lihat')
        assert result.status_code==200
        assert result.headers['Content-Disposition'].startswith('inline;')
    login_as(app,c,'berkas')
    assert c.get(f'/berkas/{uid}/lihat').status_code==403
