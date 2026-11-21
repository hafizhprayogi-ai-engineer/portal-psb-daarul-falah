import json
import pytest
from flask import g
from psb.db import one, execute, transaction, now
from psb.domain import invoice, invoice_revision_token, revise_invoice, balance, RuleError
from test_system import paid_participant
from conftest import login_as, post


@pytest.fixture
def billed(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant()
            execute("UPDATE participants SET published_result='Lulus' WHERE id=?", (pid,))
            execute("INSERT INTO fee_versions(level,components,total,created_at) VALUES('MI',?,1000000,?)",
                    (json.dumps([{'name':'Kitab','amount':1000000}]), now()))
            inv=invoice(pid)
            token=invoice_revision_token(inv)
        return pid, token


def test_revision_http_history_and_stale_token(app, billed):
    pid, token = billed
    client=app.test_client()
    login_as(app,client,'admin')
    data={'component_name':'Kitab baru','component_amount':'1200000','reason':'Tambahan kitab','confirm':'ya','revision_token':token}
    assert post(client,f'/peserta/{pid}/revisi-tagihan',data).status_code==302
    assert post(client,f'/peserta/{pid}/revisi-tagihan',data).status_code==400
    page=client.get(f'/peserta/{pid}/menu/pembayaran').get_data(as_text=True)
    assert 'Tambahan kitab' in page and 'Simpan revisi tagihan' in page
    with app.app_context():
        assert balance(pid)['remaining']==1200000
        assert one('SELECT total FROM fee_versions')['total']==1000000
        assert one("SELECT COUNT(*) AS n FROM audit WHERE action='Tagihan direvisi'")['n']==1
    for user in ['berkas','bendahara']:
        login_as(app,client,user)
        assert post(client,f'/peserta/{pid}/revisi-tagihan',data).status_code==403


def test_revision_paid_pending_and_installment_limits(app,billed):
    pid,token=billed
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='admin'")
        aid=one('SELECT application_id FROM participants WHERE id=?',(pid,))['application_id']
        with transaction():
            execute("INSERT INTO payments(application_id,participant_id,kind,method,amount,status,idempotency_key,created_at) VALUES(?,?,'daftar_ulang','tunai',600000,'Disahkan','revision-paid',?)",(aid,pid,now()))
            with pytest.raises(RuleError):
                revise_invoice(pid,[{'name':'Kitab','amount':500000}],'Pengurangan biaya',token)
            revise_invoice(pid,[{'name':'Kitab','amount':900000}],'Pengurangan biaya',token)
            assert balance(pid)['paid']==600000 and balance(pid)['remaining']==300000
            token=invoice_revision_token(invoice(pid))
            pending=execute("INSERT INTO payments(application_id,participant_id,kind,method,amount,status,idempotency_key,created_at) VALUES(?,?,'daftar_ulang','transfer',300000,'Menunggu verifikasi','revision-pending',?)",(aid,pid,now())).lastrowid
            with pytest.raises(RuleError):
                revise_invoice(pid,[{'name':'Kitab','amount':800000}],'Pengurangan biaya',token)
            execute("UPDATE payments SET status='Disahkan' WHERE id=?",(pending,))
            with pytest.raises(RuleError):
                revise_invoice(pid,[{'name':'Kitab','amount':1000000}],'Tambahan biaya',token)
            revise_invoice(pid,[{'name':'Kitab baru','amount':900000}],'Perbaiki nama',token)
            assert balance(pid)['remaining']==0

def test_revision_refreshes_completion_document(app,billed):
    from test_system import accepted_files
    from psb.domain import sync_completion, participant
    pid,token=billed
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            accepted_files(pid)
            aid=participant(pid)['application_id']
            execute("INSERT INTO payments(application_id,participant_id,kind,method,amount,status,idempotency_key,created_at) VALUES(?,?,'daftar_ulang','tunai',1000000,'Disahkan','revision-full',?)",(aid,pid,now()))
            sync_completion(pid)
            original=one("SELECT id FROM documents WHERE kind='daftar_ulang' AND valid=1")['id']
            revise_invoice(pid,[{'name':'Nama diperbaiki','amount':1000000}],'Perbaikan rincian',token)
            assert participant(pid)['completed']==1
            assert one('SELECT valid FROM documents WHERE id=?',(original,))['valid']==0
            replacement=one("SELECT id FROM documents WHERE kind='daftar_ulang' AND valid=1")['id']
            token=invoice_revision_token(invoice(pid))
            revise_invoice(pid,[{'name':'Tambahan kitab','amount':1200000}],'Penambahan kitab',token)
            assert participant(pid)['completed']==0
            assert one('SELECT valid FROM documents WHERE id=?',(replacement,))['valid']==0
            assert balance(pid)['paid']==1000000 and balance(pid)['remaining']==200000
