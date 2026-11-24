#!/usr/bin/env python3
"""Koperasi Server"""
from app import create_app

app = create_app()

@app.teardown_appcontext
def teardown_db(exception):
    from app.models import close_db
    close_db(exception)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8290, debug=False)
