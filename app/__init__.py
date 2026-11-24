"""Sistem Koperasi - Core Application"""
from flask import Flask
from flask_login import LoginManager
import os

def create_app():
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    app.config['SECRET_KEY'] = os.urandom(32).hex()
    app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'koperasi.db')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    from .models import init_db, get_user_by_id, get_koperasi_profile
    with app.app_context():
        init_db()
    
    @app.context_processor
    def inject_koperasi_profile():
        return {'koperasi_profile': get_koperasi_profile()}

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))
    
    from .routes import auth, dashboard, anggota, simpanan, pinjaman, transaksi, laporan
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(anggota.bp)
    app.register_blueprint(simpanan.bp)
    app.register_blueprint(pinjaman.bp)
    app.register_blueprint(transaksi.bp)
    app.register_blueprint(laporan.bp)
    
    return app
