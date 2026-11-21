import io
from pathlib import Path
from PIL import Image
from flask import g
from conftest import login_as,post
from psb.db import one,all_rows,transaction
from psb.domain import documents_complete,participant
from psb.drive_sync import sync_uploads
from test_system import paid_participant,accepted_files,PDF
from test_drive_sync import FakeDrive


def image():
    out=io.BytesIO(); Image.new('RGB',(60,80),'green').save(out,format='PNG'); out.seek(0); return out


def test_photo_versions_profile_permissions_and_drive(app):
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid,_,_=paid_participant(account=True)
            other,_,_=paid_participant(account=True)
            username=participant(pid)['number']; othername=participant(other)['number']
            accepted_files(pid)
    c=app.test_client(); login_as(app,c,username)
    assert post(c,f'/peserta/{pid}/photo',{'file':(image(),'foto.png')}).status_code==302
    with app.app_context():
        first=one("SELECT id FROM uploads WHERE category='foto' ORDER BY id DESC LIMIT 1")['id']
        assert not documents_complete(pid)
    assert c.get(f'/foto/{first}').status_code==200
    assert f'/foto/{first}' in c.get('/akun').get_data(as_text=True)
    assert post(c,f'/peserta/{pid}/photo',{'file':(image(),'baru.png')}).status_code==302
    with app.app_context():
        photos=all_rows("SELECT * FROM uploads WHERE category='foto' AND status<>'Diterima' ORDER BY id")
        assert len(photos)==2 and photos[0]['status']=='Menunggu pemeriksaan'
        latest=photos[-1]['id']
        for row in all_rows("SELECT storage_name FROM uploads WHERE status='Diterima'"):
            (Path(app.config['UPLOAD_DIR'])/row['storage_name']).write_bytes(b'x')
        client=FakeDrive(); sync_uploads(client)
        objects=all_rows("SELECT * FROM drive_objects WHERE upload_id IN (?,?)",(first,latest))
        assert len(objects)==2 and objects[0]['parent_id']==objects[1]['parent_id']
        assert all(o['state']=='ready' for o in objects)
    assert f'/foto/{latest}' in c.get('/akun').get_data(as_text=True)
    assert c.get(f'/foto/{first}').status_code==200
    login_as(app,c,othername)
    assert c.get(f'/foto/{latest}').status_code==403
    assert post(c,f'/peserta/{pid}/photo',{'file':(image(),'x.png')}).status_code==403
    for user,expected in [('admin',200),('berkas',200),('bendahara',403)]:
        login_as(app,c,user); assert c.get(f'/foto/{latest}').status_code==expected
    assert app.test_client().get(f'/foto/{latest}').status_code in (302,401)


def test_photo_rejects_pdf_and_fake_images(app):
    with app.app_context():
        g.user=one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid,_,_=paid_participant(account=True); username=participant(pid)['number']
    c=app.test_client();login_as(app,c,username)
    for content,filename in [(PDF,'x.pdf'),(PDF,'x.jpg'),(b'bad','x.png')]:
        assert post(c,f'/peserta/{pid}/photo',{'file':(io.BytesIO(content),filename)}).status_code==400
    with app.app_context():
        assert one("SELECT COUNT(*) AS n FROM uploads WHERE category='foto'")['n']==0
