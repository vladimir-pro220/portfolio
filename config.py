import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'votre_cle_secrete_super_securisee'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'films_series.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuration Telegram Bot
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'votre_token_bot_telegram'
    ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID') or 'votre_chat_id_admin'
    
    # Configuration des fichiers uploadés
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Types de fichiers autorisés
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Configuration des paiements
    MOBILE_MONEY_NUMBER = os.environ.get('MOBILE_MONEY_NUMBER') or 'votre_numero_mobile_money'
    
    @staticmethod
    def init_app(app):
        # Créer les dossiers d'upload s'ils n'existent pas
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)
        if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'thumbnails')):
            os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'thumbnails'))
        if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'screenshots')):
            os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'screenshots'))

        # ... configurations existantes ...
    
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 1000 * 1024 * 1024  # 100MB max file size
    
    # Types de fichiers autorisés
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mkv', 'mov', 'wmv'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    @staticmethod
    def init_app(app):
        # Créer les dossiers d'upload s'ils n'existent pas
        upload_folders = [
            Config.UPLOAD_FOLDER,
            os.path.join(Config.UPLOAD_FOLDER, 'thumbnails'),
            os.path.join(Config.UPLOAD_FOLDER, 'films'),
            os.path.join(Config.UPLOAD_FOLDER, 'episodes'),
            os.path.join(Config.UPLOAD_FOLDER, 'screenshots')
        ]
        
        for folder in upload_folders:
            if not os.path.exists(folder):
                os.makedirs(folder)
config = Config()