import io
from flask import g,template_rendered
from werkzeug.datastructures import FileStorage
from psb.db import one,execute,transaction
from psb.files import save_upload
from test_system import paid_participant,PDF
from conftest import login_as


def test_dashboard_counts_participants_latest_pending_files(app):
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            first,aid,_=paid_participant()
            second,aid2,_=paid_participant()
            def upload(pid,app_id,cat,status):
                uid=save_upload(FileStorage(stream=io.BytesIO(PDF),filename='uji.pdf'),app_id,pid,cat)
                execute('UPDATE uploads SET status=? WHERE id=?',(status,uid))
            upload(first,aid,'akta','Menunggu pemeriksaan')
            upload(first,aid,'kk','Menunggu pemeriksaan')
            upload(second,aid2,'akta','Menunggu pemeriksaan')
            upload(second,aid2,'akta','Diterima')
            upload(second,aid2,'bukti','Menunggu pemeriksaan')
    contexts=[]
    def capture(sender,template,context,**extra): contexts.append(context)
    template_rendered.connect(capture,app)
    try:
        c=app.test_client();login_as(app,c,'berkas')
        page=c.get('/dashboard').get_data(as_text=True)
        assert contexts[-1]['stats']['pending_files']==1
        assert contexts[-1]['stats']['pending']==0
        assert 'Santri menunggu pemeriksaan berkas' in page
        assert 'Pembayaran menunggu verifikasi' not in page
        login_as(app,c,'bendahara')
        page=c.get('/dashboard').get_data(as_text=True)
        assert 'Santri menunggu pemeriksaan berkas' not in page
        assert 'Pembayaran menunggu verifikasi' in page
        login_as(app,c,'admin')
        page=c.get('/dashboard').get_data(as_text=True)
        assert 'Santri menunggu pemeriksaan berkas' in page and 'Pembayaran menunggu verifikasi' in page
        login_as(app,c,'berkas')
        page=c.get('/layanan/berkas?review=pending').get_data(as_text=True)
        assert len(contexts[-1]['rows'])==1
        assert contexts[-1]['rows'][0]['id']==first
        assert contexts[-1]['rows'][0]['pending_files']==2
        assert 'Perlu diperiksa' in page and '2 berkas menunggu' in page
        c.get('/layanan/berkas')
        assert len(contexts[-1]['rows'])==2
        assert contexts[-1]['rows'][0]['id']==first
        c.get('/layanan/berkas?review=pending&q=tidak-ada')
        assert contexts[-1]['rows']==[]
    finally:template_rendered.disconnect(capture,app)
