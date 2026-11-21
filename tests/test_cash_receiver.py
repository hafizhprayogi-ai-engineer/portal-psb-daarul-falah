import json
from flask import g
from psb.db import one,transaction
from psb.domain import participant
from psb.files import document_lines
from test_system import paid_participant,passed
from conftest import login_as,post


def test_cash_receiver_required_persisted_and_receipt_versions(app):
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid,_,_=paid_participant();passed(pid)
        number=participant(pid)['number']
    c=app.test_client();login_as(app,c,'bendahara')
    data={'action':'cash','number':number,'amount':'1000000','key':'cash-receiver-test'}
    assert post(c,'/keuangan/daftar-ulang',data).status_code==400
    assert post(c,'/keuangan/daftar-ulang',{**data,'receiver_name':'Petugas Contoh'}).status_code==302
    assert post(c,'/keuangan/daftar-ulang',{**data,'receiver_name':'Petugas Contoh'}).status_code==302
    assert post(c,'/keuangan/daftar-ulang',{**data,'receiver_name':'Nama Berbeda'}).status_code==400
    with app.app_context():
        pay=one("SELECT * FROM payments WHERE kind='daftar_ulang'")
        doc=one("SELECT * FROM documents WHERE payment_id=? AND valid=1",(pay['id'],))
        assert json.loads(doc['snapshot'])['payment']['receiver_name']=='Petugas Contoh'
        assert ('Diterima oleh','Petugas Contoh') in document_lines(doc)[2]
        assert one("SELECT COUNT(*) AS n FROM audit WHERE action='Penerima tunai dicatat'")['n']==1
        pay_id=pay['id']
    assert 'Petugas Contoh' in c.get('/keuangan/riwayat').get_data(as_text=True)
    assert post(c,'/keuangan/riwayat',{'action':'correct','payment_id':pay_id,'amount':'900000','reason':'Koreksi nominal uji','confirm':'ya','key':'correct-receiver-test'}).status_code==302
    with app.app_context():
        doc=one("SELECT * FROM documents WHERE payment_id=? AND valid=1",(pay_id,))
        assert json.loads(doc['snapshot'])['payment']['receiver_name']=='Petugas Contoh'
    login_as(app,c,'admin')
    assert post(c,'/keuangan/daftar-ulang',{**data,'receiver_name':'Petugas Contoh'}).status_code==403
