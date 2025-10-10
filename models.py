from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid
import os


db = SQLAlchemy()
try:
    from moviepy.editor import VideoFileClip
except ImportError:
    # Si moviepy n'est pas installé, on peut utiliser une alternative
    VideoFileClip = None

# Ou utiliser cette alternative si moviepy pose des problèmes :
import subprocess
import json

def get_video_duration_ffprobe(file_path):
    """
    Obtenir la durée d'une vidéo avec ffprobe (plus léger que moviepy)
    """
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return int(duration)
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError, ValueError):
        pass
    
    return None


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(100), unique=True, nullable=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=True)  # Pour l'admin seulement
    is_admin = db.Column(db.Boolean, default=False)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relations
    transactions = db.relationship('Transaction', foreign_keys='Transaction.user_id', backref='client', lazy=True, cascade="all, delete-orphan")
    confirmed_transactions = db.relationship('Transaction', foreign_keys='Transaction.confirmed_by', backref='admin_user', lazy=True, cascade="all, delete-orphan")
    access_tokens = db.relationship('AccessToken', backref='user', lazy=True, cascade="all, delete-orphan")

# Dans models.py, modifier la classe Film :
class Film(db.Model):
    __tablename__ = 'films'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    thumbnail = db.Column(db.String(200), nullable=True)
    chemin = db.Column(db.String(500), nullable=False)
    #is_active = db.Column(db.Boolean, default=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NOUVEAUX CHAMPS
    duration = db.Column(db.Integer, nullable=True)  # Durée en secondes
    genre = db.Column(db.String(50), default='action')  # Genre avec valeur par défaut
    
    # Relations
    transactions = db.relationship('Transaction', backref='film', lazy=True, cascade="all, delete-orphan")
    purchases = db.relationship('TokenPurchase', backref='film', lazy=True, cascade="all, delete-orphan")
    
    # MÉTHODE POUR CALCULER LA DURÉE AUTOMATIQUEMENT
    def calculate_duration(self, app):
        if self.chemin:
            try:
                # Construire le chemin complet du fichier
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'films', self.chemin)
                
                if os.path.exists(file_path):
                    # Essayer d'abord avec moviepy si disponible
                    if VideoFileClip:
                        try:
                            video = VideoFileClip(file_path)
                            self.duration = int(video.duration)
                            video.close()
                            return True
                        except Exception as e:
                            print(f"Erreur avec moviepy: {str(e)}")
                    
                    # Alternative avec ffprobe
                    duration = get_video_duration_ffprobe(file_path)
                    if duration:
                        self.duration = duration
                        return True
                        
            except Exception as e:
                print(f"Erreur lors du calcul de la durée: {str(e)}")
                return False
        return False
    def get_formatted_duration(self):
        if self.duration:
            hours = self.duration // 3600
            minutes = (self.duration % 3600) // 60
            seconds = self.duration % 60
            
            if hours > 0:
                return f"{hours}h {minutes:02d}min"
            else:
                return f"{minutes}min {seconds:02d}s"
        return "Durée non disponible"
    

class Series(db.Model):
    __tablename__ = 'series'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    thumbnail = db.Column(db.String(200), nullable=True)
    # is_active = db.Column(db.Boolean, default=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    seasons = db.relationship('Season', backref='series', lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship('Transaction', backref='series', lazy=True, cascade="all, delete-orphan")
    purchases = db.relationship('TokenPurchase', backref='series', lazy=True, cascade="all, delete-orphan")

class Season(db.Model):
    __tablename__ = 'seasons'
    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=False)
    season_number = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    telegram_file_id = db.Column(db.String(200), nullable=False)
    
    # Relations
    episodes = db.relationship('Episode', backref='season', lazy=True, cascade="all, delete-orphan")
    purchases = db.relationship('TokenPurchase', backref='season', lazy=True, cascade="all, delete-orphan")

# Dans models.py, modifier la classe Episode :
class Episode(db.Model):
    __tablename__ = 'episodes'
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    chemin = db.Column(db.String(500), nullable=False)
    
    # NOUVEAU CHAMP
    duration = db.Column(db.Integer, nullable=True)  # Durée en secondes
    
    # MÉTHODE POUR CALCULER LA DURÉE AUTOMATIQUEMENT
    def calculate_duration(self, app):
        if self.chemin:
            try:
                # Construire le chemin complet du fichier
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', self.chemin)
                
                if os.path.exists(file_path):
                    # Essayer d'abord avec moviepy si disponible
                    if VideoFileClip:
                        try:
                            video = VideoFileClip(file_path)
                            self.duration = int(video.duration)
                            video.close()
                            return True
                        except Exception as e:
                            print(f"Erreur avec moviepy: {str(e)}")
                    
                    # Alternative avec ffprobe
                    duration = get_video_duration_ffprobe(file_path)
                    if duration:
                        self.duration = duration
                        return True
                        
            except Exception as e:
                print(f"Erreur lors du calcul de la durée: {str(e)}")
                return False
        return False    
    def get_formatted_duration(self):
        if self.duration:
            minutes = self.duration // 60
            seconds = self.duration % 60
            return f"{minutes}min {seconds:02d}s"
        return "Durée non disponible"
    
    

# 1. Modifier la classe Transaction pour ajouter de nouveaux champs
class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    film_id = db.Column(db.Integer, db.ForeignKey('films.id'), nullable=True)
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True)
    season_id = db.Column(db.Integer, nullable=True)  # Référence à la saison achetée
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # 'mtn_mobile', 'orange_money', 'admin_creation'
    payment_screenshot = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, rejected
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_date = db.Column(db.DateTime, nullable=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)  # NOUVEAU: Description détaillée
    
    def get_total_content_value(self):
        """Calcule la valeur totale du contenu associé à cette transaction"""
        total = 0
        
        if self.film_id:
            film = Film.query.get(self.film_id)
            if film:
                total += film.price
        
        if self.series_id and self.season_id:
            season = Season.query.get(self.season_id)
            if season:
                total += season.price
        
        return total
    
    def get_content_summary(self):
        """Retourne un résumé du contenu de la transaction"""
        content = []
        
        if self.film_id:
            film = Film.query.get(self.film_id)
            if film:
                content.append(f"Film: {film.title} ({film.year})")
        
        if self.series_id and self.season_id:
            series = Series.query.get(self.series_id)
            season = Season.query.get(self.season_id)
            if series and season:
                content.append(f"Série: {series.title} - Saison {season.season_number}")
        
        return content

# 2. Modifier la classe AccessToken pour ajouter le montant total
class AccessToken(db.Model):
    __tablename__ = 'access_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, default=lambda: str(uuid.uuid4()))
    password = db.Column(db.String(100), default=lambda: str(uuid.uuid4())[:8])
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    total_amount = db.Column(db.Float, default=0.0)  # NOUVEAU: Montant total des achats
    
    # Relations
    purchases = db.relationship('TokenPurchase', backref='access_token', lazy=True, cascade="all, delete-orphan")
    
    def calculate_total_value(self):
        """Calcule la valeur totale des contenus associés à ce token"""
        total = 0
        
        for purchase in self.purchases:
            if purchase.film_id:
                film = Film.query.get(purchase.film_id)
                if film:
                    total += film.price
            elif purchase.series_id and purchase.season_id:
                season = Season.query.get(purchase.season_id)
                if season:
                    total += season.price
        
        return total
    
    def get_content_summary(self):
        """Retourne un résumé des contenus associés"""
        films = []
        series = []
        
        for purchase in self.purchases:
            if purchase.film_id:
                film = Film.query.get(purchase.film_id)
                if film:
                    films.append(film)
            elif purchase.series_id and purchase.season_id:
                series_obj = Series.query.get(purchase.series_id)
                season = Season.query.get(purchase.season_id)
                if series_obj and season:
                    series.append(f"{series_obj.title} - Saison {season.season_number}")
        
        return {
            'films': films,
            'series': series,
            'total_films': len(films),
            'total_series': len(series)
        }

# 3. Ajouter une nouvelle classe pour les statistiques
class ClientStats(db.Model):
    __tablename__ = 'client_stats'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_spent = db.Column(db.Float, default=0.0)
    total_films = db.Column(db.Integer, default=0)
    total_series = db.Column(db.Integer, default=0)
    last_purchase_date = db.Column(db.DateTime, nullable=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation
    user = db.relationship('User', backref='stats')
    
    @staticmethod
    def update_client_stats(user_id):
        """Met à jour les statistiques d'un client"""
        stats = ClientStats.query.filter_by(user_id=user_id).first()
        if not stats:
            stats = ClientStats(user_id=user_id)
            db.session.add(stats)
        
        # Calculer les totaux depuis les tokens actifs
        active_tokens = AccessToken.query.filter_by(user_id=user_id).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).all()
        
        total_spent = 0
        total_films = 0
        total_series = 0
        
        for token in active_tokens:
            total_spent += token.calculate_total_value()
            content = token.get_content_summary()
            total_films += content['total_films']
            total_series += content['total_series']
        
        stats.total_spent = total_spent
        stats.total_films = total_films
        stats.total_series = total_series
        stats.updated_date = datetime.utcnow()
        
        # Dernière date d'achat
        last_transaction = Transaction.query.filter_by(
            user_id=user_id, 
            status='confirmed'
        ).order_by(Transaction.confirmed_date.desc()).first()
        
        if last_transaction:
            stats.last_purchase_date = last_transaction.confirmed_date
        
        db.session.commit()
        return stats
    
    
class TokenPurchase(db.Model):
    __tablename__ = 'token_purchases'
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('access_tokens.id'), nullable=False)
    film_id = db.Column(db.Integer, db.ForeignKey('films.id'), nullable=True)
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=True)