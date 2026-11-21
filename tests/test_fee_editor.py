import json
import pytest
from werkzeug.datastructures import MultiDict
from conftest import login_as, post
from psb.db import one


def test_fee_rows_store_integer_total(app):
    client = app.test_client()
    login_as(app, client, 'admin')
    data = MultiDict([('action', 'fee'), ('level', 'MA'),
                      ('component_name', 'Kitab'), ('component_amount', '1000000'),
                      ('component_name', 'Seragam'), ('component_amount', '500000')])
    data.add('csrf', 'csrf-test')
    assert client.post('/pengaturan/biaya', data=data).status_code == 302
    with app.app_context():
        fee = one('SELECT * FROM fee_versions')
        assert fee['total'] == 1500000
        assert json.loads(fee['components']) == [
            {'name': 'Kitab', 'amount': 1000000}, {'name': 'Seragam', 'amount': 500000}]
    page = client.get('/pengaturan/biaya').get_data(as_text=True)
    assert 'data-fee-editor' in page and 'name="components"' not in page


@pytest.mark.parametrize('amount', ['Rp 1,000,000', '1.5', '-2', '0', '1000000000'])
def test_fee_rows_reject_invalid_amount_without_writing(app, amount):
    client = app.test_client()
    login_as(app, client, 'admin')
    response = post(client, '/pengaturan/biaya', {
        'action': 'fee', 'level': 'MA', 'component_name': 'Kitab', 'component_amount': amount})
    assert response.status_code == 400
    with app.app_context():
        assert one('SELECT COUNT(*) AS n FROM fee_versions')['n'] == 0
