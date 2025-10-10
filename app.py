from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Film, Series, Season, Episode, Transaction, AccessToken, TokenPurchase
from config import config
import os
import uuid
from datetime import datetime, timedelta
from functools import wraps
import json
import re
from flask import Response, abort

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Initialiser les extensions
    db.init_app(app)
    
    # Initialiser le login manager
    login_manager = LoginManager()
    login_manager.login_view = 'admin_login'
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # DÃ©corateur pour vÃ©rifier les droits admin
    def admin_required(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_admin:
                flash('AccÃ¨s rÃ©servÃ© aux administrateurs.', 'danger')
                return redirect(url_for('admin_login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # Route pour la page d'accueil
    @app.route('/')
    def home():
        return redirect(url_for('admin_login'))
    
    # Routes d'authentification admin
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if current_user.is_authenticated and current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
            
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username, is_admin=True).first()
            
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('admin_dashboard'))
            else:
                flash('Identifiants incorrects.', 'danger')
                
        return render_template('auth/admin_login.html')
    
    
    @app.route('/admin/logout')
    @login_required
    def admin_logout():
        logout_user()
        return redirect(url_for('admin_login'))
    
    # Tableau de bord admin
    @app.route('/admin')
    @admin_required
    def admin_dashboard():
        # Statistiques de base
        total_films = Film.query.count()
        total_series = Series.query.count()
        total_seasons = Season.query.count()
        total_episodes = Episode.query.count()
        total_transactions = Transaction.query.count()
        pending_transactions = Transaction.query.filter_by(status='pending').count()
        confirmed_transactions = Transaction.query.filter_by(status='confirmed').count()
        
        # Calcul des revenus
        total_revenue = db.session.query(db.func.sum(Transaction.amount)).filter_by(status='confirmed').scalar() or 0
        monthly_revenue = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.status == 'confirmed',
            Transaction.transaction_date >= datetime.utcnow().replace(day=1)
        ).scalar() or 0
        
        # Transactions rÃ©centes ( derniÃ¨res)
        recent_transactions = Transaction.query.order_by(Transaction.transaction_date.desc()).limit(10).all()
        
        current_time = datetime.utcnow()
        
        return render_template('admin/dashboard.html', 
                            total_films=total_films,
                            total_series=total_series,
                            total_seasons=total_seasons,
                            total_episodes=total_episodes,
                            total_transactions=total_transactions,
                            pending_transactions=pending_transactions,
                            confirmed_transactions=confirmed_transactions,
                            total_revenue=total_revenue,
                            monthly_revenue=monthly_revenue,
                            recent_transactions=recent_transactions,
                            now=current_time)
    
    @app.route('/admin/reset-transactions')
    @admin_required
    def admin_reset_transactions():
        try:
            num_deleted = db.session.query(Transaction).delete()
            db.session.commit()
            flash(f'{num_deleted} transactions ont été supprimées.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la suppression des transactions: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/series')
    @admin_required
    def admin_manage_series():
        series_list = Series.query.order_by(Series.title).all()
        return render_template('admin/series.html', series_list=series_list)

    @app.route('/admin/change-password', methods=['GET', 'POST'])
    @admin_required
    def admin_change_password():
        if request.method == 'POST':
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            if new_password and new_password == confirm_password:
                current_user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash('Votre mot de passe a été mis à jour.', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Les mots de passe ne correspondent pas.', 'veillez recommencer')
        return render_template('admin/change_password.html')
    
    # Route pour la réinitialisation du mot de passe admin (en cas d'oubli)
    @app.route('/admin/forgot-password', methods=['GET', 'POST'])
    def admin_forgot_password():
        if current_user.is_authenticated:
            return redirect(url_for('admin_dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            
            # Vérifier si l'admin existe
            admin = User.query.filter_by(username=username, is_admin=True).first()
            
            if admin:
                # Générer un token de réinitialisation (simplifié pour cet exemple)
                reset_token = str(uuid.uuid4())
                # En production, vous stockeriez ce token dans la base avec une date d'expiration
                
                # Simuler l'envoi d'email (à implémenter réellement)
                flash(f'Un lien de réinitialisation a été envoyé à l\'email administrateur.', 'info')
                return redirect(url_for('admin_login'))
            else:
                flash('Aucun administrateur trouvé avec ces informations.', 'danger')
        
        return render_template('auth/forgot_password.html')

    # Route pour réinitialiser le mot de passe avec token
    @app.route('/admin/reset-password/<token>', methods=['GET', 'POST'])
    def admin_reset_password(token):
        # En production, vérifier la validité du token et son expiration
        if request.method == 'POST':
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password and new_password == confirm_password:
                # Récupérer l'admin associé au token (simplifié)
                # En production, vous récupéreriez l'user_id depuis le token stocké en base
                admin = User.query.filter_by(is_admin=True).first()
                if admin:
                    admin.password_hash = generate_password_hash(new_password)
                    db.session.commit()
                    flash('Votre mot de passe a été réinitialisé avec succès.', 'success')
                    return redirect(url_for('admin_login'))
            else:
                flash('Les mots de passe ne correspondent pas.', 'danger')
        
        return render_template('auth/reset_password.html', token=token)

    @app.route('/admin/rapport/download')
    @admin_required
    def download_report():
        try:
            return send_file('Rapport Complet.pdf', as_attachment=True, download_name='Rapport Complet.pdf', mimetype='application/pdf')
        except FileNotFoundError:
            abort(404)
    

    # Routes client
    @app.route('/client/login', methods=['GET', 'POST'])
    def client_login():
        if request.method == 'POST':
            client_id = request.form.get('client_id')
            password = request.form.get('password')
            
            # Vérifier si c'est un ID client valide
            # Maintenant on cherche directement par username (qui contient l'ID client)
            client = User.query.filter(
                User.username == client_id,  # L'ID client est stocké comme username
                User.is_admin == False
            ).first()
            
            if client and check_password_hash(client.password_hash, password):
                login_user(client)
                client.last_login = datetime.utcnow()
                db.session.commit()
                
                flash('Connexion réussie! Bienvenue dans votre espace client.', 'success')
                return redirect(url_for('client_index'))
            else:
                flash('Identifiants incorrects. Vérifiez votre ID client et mot de passe.', 'danger')
        
        return render_template('client/login.html')
    @app.route('/client')
    @login_required
    def client_index():
        if current_user.is_admin:
            flash('Accès réservé aux clients.', 'warning')
            return redirect(url_for('admin_dashboard'))
        
        # Récupérer le token d'accès actif de l'utilisateur
        active_token = AccessToken.query.filter_by(
            user_id=current_user.id
        ).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).first()
        
        if not active_token:
            flash('Aucun accès actif trouvé.', 'warning')
            return redirect(url_for('client_login'))
        
        # Récupérer les achats associés à ce token
        purchases = TokenPurchase.query.filter_by(token_id=active_token.id).all()
        
        films = []
        series_dict = {}
        
        for purchase in purchases:
            if purchase.film_id:
                film = Film.query.get(purchase.film_id)
                if film and film not in films:
                    films.append(film)
            elif purchase.series_id and purchase.season_id:
                series_obj = Series.query.get(purchase.series_id)
                season = Season.query.get(purchase.season_id)
                
                if series_obj and season:
                    if series_obj.id not in series_dict:
                        series_dict[series_obj.id] = {
                            'series': series_obj,
                            'seasons': {}
                        }
                    
                    # Ajouter la saison
                    if season.id not in series_dict[series_obj.id]['seasons']:
                        series_dict[series_obj.id]['seasons'][season.id] = {
                            'season': season,
                            'episodes': Episode.query.filter_by(season_id=season.id)
                                                    .order_by(Episode.episode_number).all()
                        }
        
        # Convertir le dictionnaire en liste pour le template
        series_list = []
        for series_data in series_dict.values():
            series_list.append({
                'series': series_data['series'],
                'seasons': list(series_data['seasons'].values())
            })
        
        return render_template('client/index_client.html', 
                            films=films, 
                            series=series_list,
                            client=current_user)
    @app.route('/client/logout')
    @login_required
    def client_logout():
        if current_user.is_admin:
            return redirect(url_for('admin_logout'))
        
        logout_user()
        flash('Vous avez Ã©tÃ© dÃ©connectÃ©.', 'info')
        return redirect(url_for('client_login'))
    
    # Route pour crÃ©er un compte client
    # Route pour créer un compte client (version corrigée)
    # Dans app.py, remplacer la route create_client_account par cette version corrigée :

    @app.route('/admin/create-client-account', methods=['GET', 'POST'])
    @admin_required
    def create_client_account():
        if request.method == 'POST':
            try:
                # Récupération des données
                username = request.form.get('username')  # Nom d'affichage
                client_id = request.form.get('client_id')  # ID de connexion généré
                password = request.form.get('password')
                token_duration = int(request.form.get('token_duration', 30))
                
                # Récupérer les films et séries sélectionnés
                selected_films = request.form.getlist('selected_films')
                selected_seasons = request.form.getlist('selected_seasons')
                
                # Validation
                if not username or not client_id or not password:
                    return jsonify({'success': False, 'message': 'Tous les champs requis doivent être remplis'}), 400
                
                # Vérifier si l'utilisateur existe déjà avec cet ID client
                existing_user = User.query.filter_by(username=client_id).first()
                
                if existing_user:
                    return jsonify({'success': False, 'message': 'Un utilisateur avec cet ID client existe déjà'}), 400
                
                # Créer l'utilisateur avec l'ID client comme username
                user = User(
                    username=client_id,  # IMPORTANT: utiliser l'ID client comme username
                    password_hash=generate_password_hash(password),
                    is_admin=False,
                    email=f"{client_id}@client.local"  # Email optionnel basé sur l'ID
                )
                db.session.add(user)
                db.session.flush()
                
                # Créer le token d'accès
                expiry_date = datetime.utcnow() + timedelta(days=token_duration)
                access_token = AccessToken(
                    user_id=user.id,
                    expiry_date=expiry_date
                )
                db.session.add(access_token)
                db.session.flush()
                
                # Associer les contenus achetés
                total_price = 0
                payment_method = request.form.get("payment_method", "admin_creation")
                
                # Films sélectionnés
                for film_id in selected_films:
                    if film_id:
                        film = Film.query.get(int(film_id))
                        if film:
                            purchase = TokenPurchase(
                                token_id=access_token.id,
                                film_id=int(film_id)
                            )
                            db.session.add(purchase)
                            total_price += film.price
                
                # Séries/saisons sélectionnées
                for season_data in selected_seasons:
                    if season_data and '-' in season_data:
                        series_id, season_id = season_data.split('-')
                        season = Season.query.get(int(season_id))
                        if season:
                            purchase = TokenPurchase(
                                token_id=access_token.id,
                                series_id=int(series_id),
                                season_id=int(season_id)
                            )
                            db.session.add(purchase)
                            total_price += season.price
                
                # Mettre à jour le montant total
                access_token.total_amount = total_price
                
                # Créer une transaction
                transaction = Transaction(
                    user_id=user.id,
                    amount=total_price,
                    payment_method=payment_method,
                    status='confirmed',
                    transaction_date=datetime.utcnow(),
                    confirmed_date=datetime.utcnow(),
                    confirmed_by=current_user.id,
                    description=f"Compte créé par admin pour {username} - {len(selected_films)} films, {len(selected_seasons)} saisons"
                )
                db.session.add(transaction)
                
                db.session.commit()
                
                return jsonify({
                    'success': True, 
                    'message': f'Compte client créé avec succès!',
                    'credentials': {
                        'username': username,  # Nom d'affichage
                        'client_id': client_id,  # ID de connexion
                        'password': password
                    },
                    'total_price': total_price
                })
                
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'Erreur: {str(e)}'}), 500
        
        # GET request - afficher le formulaire
        films = Film.query.all()
        series_list = Series.query.all()
        
        series_with_seasons = []
        for series in series_list:
            seasons = Season.query.filter_by(series_id=series.id).order_by(Season.season_number).all()
            series_with_seasons.append({
                'series': series,
                'seasons': seasons
            })
        
        return render_template('admin/create_client.html', 
                            films=films, 
                            series_list=series_with_seasons)
   # Nouvelle route pour les téléchargements
    @app.route('/client/download/<content_type>/<int:content_id>')
    @login_required
    def download_content(content_type, content_id):
        if current_user.is_admin:
            flash('Accès réservé aux clients.', 'warning')
            return redirect(url_for('admin_dashboard'))
        
        # Vérifier que l'utilisateur a bien acheté ce contenu
        has_access = False
        active_token = AccessToken.query.filter_by(
            user_id=current_user.id
        ).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).first()
        
        if active_token:
            if content_type == 'film':
                purchase = TokenPurchase.query.filter_by(
                    token_id=active_token.id,
                    film_id=content_id
                ).first()
                if purchase:
                    has_access = True
                    content = Film.query.get(content_id)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'films', content.chemin)
            elif content_type == 'episode':
                episode = Episode.query.get(content_id)
                if episode:
                    purchase = TokenPurchase.query.filter_by(
                        token_id=active_token.id,
                        series_id=episode.season.series_id,
                        season_id=episode.season_id
                    ).first()
                    if purchase:
                        has_access = True
                        content = episode
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', content.chemin)
        
        if not has_access or not os.path.exists(file_path):
            flash('Vous n\'avez pas accès à ce contenu.', 'danger')
            return redirect(url_for('client_index'))
        
        # Envoyer le fichier pour téléchargement
        return send_file(file_path, as_attachment=True, download_name=content.title + os.path.splitext(file_path)[1])

    # Gestion des films
    @app.route('/admin/films')
    @admin_required
    def admin_films():
        films = Film.query.order_by(Film.title).all()
        return render_template('admin/films.html', films=films)
    
    @app.route('/admin/films/add', methods=['GET', 'POST'])
    @admin_required
    def add_film():
        if request.method == 'POST':
            title = request.form.get('title')
            year = request.form.get('year')
            description = request.form.get('description')
            price = request.form.get('price')
            genre = request.form.get('genre', 'action')
            
            # Validation des donnÃ©es
            if not all([title, year, description, price]):
                flash('Tous les champs obligatoires doivent Ãªtre remplis.', 'danger')
                return render_template('admin/add_film.html')
            
            # Gestion de l'upload de thumbnail
            thumbnail_filename = None
            if 'thumbnail' in request.files:
                file = request.files['thumbnail']
                if file and allowed_file(file.filename, app.config['ALLOWED_IMAGE_EXTENSIONS']):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', unique_filename)
                    file.save(file_path)
                    thumbnail_filename = unique_filename
            
            # Gestion de l'upload du film
            film_filename = None
            if 'film_file' in request.files:
                file = request.files['film_file']
                if file and allowed_file(file.filename, app.config['ALLOWED_VIDEO_EXTENSIONS']):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'films', unique_filename)
                    file.save(file_path)
                    film_filename = unique_filename
                else:
                    flash('Format de fichier vidÃ©o non supportÃ©.', 'danger')
                    return render_template('admin/add_film.html')
            
            if not film_filename:
                flash('Veuillez uploader un fichier film.', 'danger')
                return render_template('admin/add_film.html')
            
            # CrÃ©ation du film
            new_film = Film(
                title=title,
                year=year,
                description=description,
                price=price,
                thumbnail=thumbnail_filename,
                chemin=film_filename,
                genre=genre
            )
            
            try:
                db.session.add(new_film)
                db.session.flush()
                
                # Calculer la durÃ©e automatiquement
                new_film.calculate_duration(app)
                
                db.session.commit()
                flash('Film ajoutÃ© avec succÃ¨s.', 'success')
                return redirect(url_for('admin_films'))
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur lors de l'ajout du film: {str(e)}", 'danger')
                return render_template('admin/add_film.html')
        
        return render_template('admin/add_film.html')
    
    @app.route('/admin/films/edit/<int:film_id>', methods=['GET', 'POST'])
    @admin_required
    def edit_film(film_id):
        film = Film.query.get_or_404(film_id)
        
        if request.method == 'POST':
            film.title = request.form.get('title')
            film.year = request.form.get('year')
            film.description = request.form.get('description')
            film.price = request.form.get('price')
            film.genre = request.form.get('genre', 'action')
            
            # Gestion de l'upload de thumbnail
            if 'thumbnail' in request.files:
                file = request.files['thumbnail']
                if file and allowed_file(file.filename, app.config['ALLOWED_IMAGE_EXTENSIONS']):
                    # Supprimer l'ancienne image si elle existe
                    if film.thumbnail:
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', film.thumbnail)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', unique_filename)
                    file.save(file_path)
                    film.thumbnail = unique_filename
            
            # Gestion de l'upload du nouveau film
            if 'film_file' in request.files:
                file = request.files['film_file']
                if file and allowed_file(file.filename, app.config['ALLOWED_VIDEO_EXTENSIONS']):
                    # Supprimer l'ancien fichier s'il existe
                    if film.chemin:
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'films', film.chemin)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'films', unique_filename)
                    file.save(file_path)
                    film.chemin = unique_filename
                    
                    # Recalculer la durÃ©e aprÃ¨s le changement de fichier
                    film.calculate_duration(app)
            
            db.session.commit()
            flash('Film modifiÃ© avec succÃ¨s.', 'success')
            return redirect(url_for('admin_films'))
        
        return render_template('admin/edit_film.html', film=film)
    
    @app.route('/client/dashboard')
    @login_required
    def client_dashboard():
        # Récupérer les tokens actifs de l'utilisateur
        active_tokens = AccessToken.query.filter_by(user_id=current_user.id).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).all()

        films = []
        series = {}
        
        for token in active_tokens:
            for purchase in token.purchases:
                if purchase.film:
                    films.append(purchase.film)
                if purchase.series:
                    if purchase.series.id not in series:
                        series[purchase.series.id] = {
                            'series': purchase.series,
                            'seasons': {}
                        }
                    # Ajouter la saison et les épisodes
                    if purchase.season:
                        if purchase.season.id not in series[purchase.series.id]['seasons']:
                            series[purchase.series.id]['seasons'][purchase.season.id] = {
                                'season': purchase.season,
                                'episodes': []
                            }
                        if purchase.episode:
                            series[purchase.series.id]['seasons'][purchase.season.id]['episodes'].append(purchase.episode)
        
        # Trier les épisodes par numéro
        for s_id in series:
            for se_id in series[s_id]['seasons']:
                series[s_id]['seasons'][se_id]['episodes'].sort(key=lambda x: x.episode_number)

        return render_template('index_client.html', films=films, series=series.values())

    
    @app.route('/admin/films/delete/<int:film_id>')
    @admin_required
    def delete_film(film_id):
        film = Film.query.get_or_404(film_id)
        
        # Supprimer le thumbnail s'il existe
        if film.thumbnail:
            thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', film.thumbnail)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        
        # Supprimer le fichier film s'il existe
        if film.chemin:
            film_path = os.path.join(app.config['UPLOAD_FOLDER'], 'films', film.chemin)
            if os.path.exists(film_path):
                os.remove(film_path)
        
        db.session.delete(film)
        db.session.commit()
        
        flash('Film supprimÃ© avec succÃ¨s.', 'success')
        return redirect(url_for('admin_films'))
    
    # Gestion des sÃ©ries
    @app.route('/admin/series')
    @admin_required
    def admin_series():
        series_list = Series.query.order_by(Series.title).all()
        return render_template('admin/series.html', series_list=series_list)
    
    @app.route('/admin/series/add', methods=['GET', 'POST'])
    @admin_required
    def add_series():
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            
            # Gestion de l'upload de thumbnail
            thumbnail = None
            if 'thumbnail' in request.files:
                file = request.files['thumbnail']
                if file and allowed_file(file.filename, app.config['ALLOWED_IMAGE_EXTENSIONS']):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', unique_filename)
                    file.save(file_path)
                    thumbnail = unique_filename
            
            new_series = Series(
                title=title,
                description=description,
                thumbnail=thumbnail
            )
            
            db.session.add(new_series)
            db.session.commit()
            
            flash('SÃ©rie ajoutÃ©e avec succÃ¨s.', 'success')
            return redirect(url_for('admin_series'))
        
        return render_template('admin/add_series.html')
    
    # Gestion des sÃ©ries - Route de suppression
    @app.route('/admin/series/delete/<int:series_id>')
    @admin_required
    def delete_series(series_id):
        series = Series.query.get_or_404(series_id)
        
        try:
            # Supprimer le thumbnail s'il existe
            if series.thumbnail:
                thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', series.thumbnail)
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
            
            # Supprimer toutes les saisons et Ã©pisodes associÃ©s
            for season in series.seasons:
                # Supprimer tous les Ã©pisodes de la saison
                for episode in season.episodes:
                    # Supprimer le fichier Ã©pisode s'il existe
                    if episode.chemin:
                        episode_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', episode.chemin)
                        if os.path.exists(episode_path):
                            os.remove(episode_path)
                    db.session.delete(episode)
                
                db.session.delete(season)
            
            db.session.delete(series)
            db.session.commit()
            
            flash('SÃ©rie supprimÃ©e avec succÃ¨s.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la suppression de la sÃ©rie: {str(e)}", 'danger')
        
        return redirect(url_for('admin_series'))
    
    # Gestion des saisons
    @app.route('/admin/series/<int:series_id>/seasons')
    @admin_required
    def admin_seasons(series_id):
        series = Series.query.get_or_404(series_id)
        seasons = Season.query.filter_by(series_id=series_id).order_by(Season.season_number).all()
        return render_template('admin/seasons.html', series=series, seasons=seasons)

    @app.route('/admin/series/<int:series_id>/seasons/add', methods=['GET'])
    @admin_required
    def add_season(series_id):
        series = Series.query.get_or_404(series_id)
        return render_template('admin/add_season.html', series=series)

    @app.route('/admin/series/<int:series_id>/seasons/add', methods=['POST'])
    @admin_required
    def add_season_post(series_id):
        series = Series.query.get_or_404(series_id)
        
        # RÃ©cupÃ©rer les donnÃ©es du formulaire
        season_number = request.form.get('season_number')
        year = request.form.get('year')
        description = request.form.get('description')
        price = request.form.get('price')
        
        # Valider les donnÃ©es de base
        if not all([season_number, year, price]):
            flash('Tous les champs obligatoires doivent Ãªtre remplis.', 'danger')
            return render_template('admin/add_season.html', series=series)
        
        # VÃ©rifier si la saison existe dÃ©jÃ  
        existing_season = Season.query.filter_by(
            series_id=series_id, 
            season_number=season_number
        ).first()
        
        if existing_season:
            flash('Cette saison existe dÃ©jÃ  pour cette sÃ©rie.', 'danger')
            return render_template('admin/add_season.html', series=series)
        
        # CrÃ©er la nouvelle saison
        new_season = Season(
            series_id=series_id,
            season_number=int(season_number),
            year=int(year),
            description=description,
            price=float(price),
            telegram_file_id=""  # On garde pour compatibilitÃ© mais plus utilisÃ©
        )
        
        try:
            db.session.add(new_season)
            db.session.commit()
            flash(f'Saison {season_number} crÃ©Ã©e avec succÃ¨s. Vous pouvez maintenant ajouter des Ã©pisodes.', 'success')
            return redirect(url_for('admin_seasons', series_id=series_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'ajout de la saison: {str(e)}", 'danger')
            return render_template('admin/add_season.html', series=series)
    
    @app.route('/admin/seasons/edit/<int:season_id>', methods=['GET', 'POST'])
    @admin_required
    def edit_season(season_id):
        season = Season.query.get_or_404(season_id)
        
        if request.method == 'POST':
            season.season_number = request.form.get('season_number')
            season.year = request.form.get('year')
            season.description = request.form.get('description')
            season.price = request.form.get('price')
            
            db.session.commit()
            flash('Saison modifiÃ©e avec succÃ¨s.', 'success')
            return redirect(url_for('admin_seasons', series_id=season.series_id))
        
        return render_template('admin/edit_season.html', season=season)
    

    @app.route('/admin/seasons/delete/<int:season_id>')
    @admin_required
    def delete_season(season_id):
        season = Season.query.get_or_404(season_id)
        series_id = season.series_id
        
        try:
            # Supprimer tous les Ã©pisodes de la saison
            episodes = Episode.query.filter_by(season_id=season_id).all()
            for episode in episodes:
                # Supprimer le fichier Ã©pisode s'il existe
                if episode.chemin:
                    episode_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', episode.chemin)
                    if os.path.exists(episode_path):
                        os.remove(episode_path)
                db.session.delete(episode)
            
            db.session.delete(season)
            db.session.commit()
            
            flash('Saison supprimÃ©e avec succÃ¨s.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la suppression de la saison: {str(e)}", 'danger')
        
        return redirect(url_for('admin_seasons', series_id=series_id))
    
    # Gestion des Ã©pisodes
    @app.route('/admin/get_episodes/<int:season_id>')
    @admin_required
    def get_episodes(season_id):
        season = Season.query.get_or_404(season_id)
        episodes = Episode.query.filter_by(season_id=season_id).order_by(Episode.episode_number).all()
        
        episodes_data = []
        for episode in episodes:
            episodes_data.append({
                'id': episode.id,
                'episode_number': episode.episode_number,
                'title': episode.title,
                'chemin': episode.chemin,
                'duration': episode.duration
            })
        
        return jsonify({'episodes': episodes_data})
    
    @app.route('/admin/add_episode')
    @admin_required
    def add_episode():
        season_id = request.args.get('season_id')
        if not season_id:
            flash('ID de saison manquant.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        season = Season.query.get_or_404(season_id)
        return render_template('admin/add_episode.html', season=season)
    
    @app.route('/admin/add_episode', methods=['POST'])
    @admin_required
    def add_episode_post():
        season_id = request.form.get('season_id')
        if not season_id:
            flash('ID de saison manquant.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        season = Season.query.get_or_404(season_id)
        
        # RÃ©cupÃ©rer les donnÃ©es du formulaire
        episode_number = request.form.get('episode_number')
        title = request.form.get('title')
        
        # Valider les donnÃ©es
        if not all([episode_number, title]):
            flash('Tous les champs obligatoires doivent Ãªtre remplis.', 'danger')
            return render_template('admin/add_episode.html', season=season)
        
        # VÃ©rifier si l'Ã©pisode existe dÃ©jÃ  
        existing_episode = Episode.query.filter_by(
            season_id=season_id, 
            episode_number=episode_number
        ).first()
        
        if existing_episode:
            flash('Cet Ã©pisode existe dÃ©jÃ  pour cette saison.', 'danger')
            return render_template('admin/add_episode.html', season=season)
        
        # Gestion de l'upload du fichier Ã©pisode
        episode_filename = None
        if 'episode_file' in request.files:
            file = request.files['episode_file']
            if file and allowed_file(file.filename, app.config['ALLOWED_VIDEO_EXTENSIONS']):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', unique_filename)
                file.save(file_path)
                episode_filename = unique_filename
            else:
                flash('Format de fichier vidÃ©o non supportÃ©.', 'danger')
                return render_template('admin/add_episode.html', season=season)
        
        if not episode_filename:
            flash('Veuillez uploader un fichier Ã©pisode.', 'danger')
            return render_template('admin/add_episode.html', season=season)
        
        # CrÃ©er le nouvel Ã©pisode
        new_episode = Episode(
            season_id=season_id,
            episode_number=int(episode_number),
            title=title,
            chemin=episode_filename
        )
        
        try:
            db.session.add(new_episode)
            db.session.flush()
            
            # Calculer la durÃ©e automatiquement
            new_episode.calculate_duration(app)
            
            db.session.commit()
            flash('Ã‰pisode ajoutÃ© avec succÃ¨s.', 'success')
            return redirect(url_for('admin_seasons', series_id=season.series_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'ajout de l'Ã©pisode: {str(e)}", 'danger')
            return render_template('admin/add_episode.html', season=season)
    
    @app.route('/admin/edit_episode/<int:episode_id>', methods=['GET', 'POST'])
    @admin_required
    def edit_episode(episode_id):
        episode = Episode.query.get_or_404(episode_id)
        season = Season.query.get_or_404(episode.season_id)
        
        if request.method == 'POST':
            episode.episode_number = request.form.get('episode_number')
            episode.title = request.form.get('title')
            
            # Gestion de l'upload du nouveau fichier Ã©pisode
            if 'episode_file' in request.files:
                file = request.files['episode_file']
                if file and allowed_file(file.filename, app.config['ALLOWED_VIDEO_EXTENSIONS']):
                    # Supprimer l'ancien fichier s'il existe
                    if episode.chemin:
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', episode.chemin)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', unique_filename)
                    file.save(file_path)
                    episode.chemin = unique_filename
                    
                    # Recalculer la durÃ©e aprÃ¨s le changement de fichier
                    episode.calculate_duration(app)
            
            db.session.commit()
            flash('Ã‰pisode modifiÃ© avec succÃ¨s.', 'success')
            return redirect(url_for('admin_seasons', series_id=season.series_id))
        
        return render_template('admin/edit_episode.html', episode=episode, season=season)
    
    @app.route('/admin/delete_episode/<int:episode_id>')
    @admin_required
    def delete_episode(episode_id):
        episode = Episode.query.get_or_404(episode_id)
        season_id = episode.season_id
        season = Season.query.get_or_404(season_id)
        
        # Supprimer le fichier Ã©pisode s'il existe
        if episode.chemin:
            episode_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', episode.chemin)
            if os.path.exists(episode_path):
                os.remove(episode_path)
        
        db.session.delete(episode)
        db.session.commit()
        
        flash('Ã‰pisode supprimÃ© avec succÃ¨s.', 'success')
        return redirect(url_for('admin_seasons', series_id=season.series_id))
    
    # Routes pour servir les fichiers
    @app.route('/uploads/episodes/<filename>')
    @login_required
    def get_episode_file(filename):
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', filename))
    
    @app.route('/uploads/thumbnails/<filename>')
    def get_thumbnail(filename):
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', filename))
    
    @app.route('/uploads/films/<filename>')
    @login_required
    def get_film(filename):
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], 'films', filename))
    
    @app.route('/uploads/screenshots/<filename>')
    def get_screenshot(filename):
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], 'screenshots', filename))
    
    # Transactions
    @app.route('/admin/transactions')
    @admin_required
    def admin_transactions():
        # RÃ©cupÃ©rer le filtre de statut depuis les paramÃ¨tres de requÃªte
        status_filter = request.args.get('status', 'all')
        
        # Construire la requÃªte en fonction du filtre
        if status_filter == 'all':
            transactions = Transaction.query.order_by(Transaction.transaction_date.desc()).all()
        else:
            transactions = Transaction.query.filter_by(status=status_filter).order_by(Transaction.transaction_date.desc()).all()
        
        # PrÃ©parer les donnÃ©es pour l'affichage
        transactions_data = []
        for transaction in transactions:
            # RÃ©cupÃ©rer les informations sur le client
            client = User.query.get(transaction.user_id)
            
            # RÃ©cupÃ©rer les informations sur le produit (film ou sÃ©rie)
            product_info = {}
            content_details = []
            
            if transaction.film_id:
                film = Film.query.get(transaction.film_id)
                product_info = {
                    'type': 'film',
                    'title': film.title,
                    'year': film.year,
                    'price': film.price
                }
                content_details = [f"Film: {film.title} ({film.year})"]
            elif transaction.series_id and transaction.season_id:
                series = Series.query.get(transaction.series_id)
                season = Season.query.get(transaction.season_id)
                product_info = {
                    'type': 'sÃ©rie',
                    'title': f"{series.title} - Saison {season.season_number}",
                    'year': season.year,
                    'price': season.price
                }
                content_details = [f"SÃ©rie: {series.title} - Saison {season.season_number} ({season.year})"]
            elif transaction.payment_method == 'admin_creation':
                # Pour les comptes crÃ©Ã©s par l'admin, rÃ©cupÃ©rer les dÃ©tails du contenu
                access_token = AccessToken.query.filter_by(user_id=transaction.user_id).first()
                if access_token:
                    purchases = TokenPurchase.query.filter_by(token_id=access_token.id).all()
                    
                    films_count = len([p for p in purchases if p.film_id])
                    seasons_count = len([p for p in purchases if p.series_id and p.season_id])
                    
                    product_info = {
                        'type': 'compte_admin',
                        'title': f"CrÃ©ation de compte ({films_count} films, {seasons_count} saisons)",
                        'year': datetime.now().year,
                        'price': transaction.amount
                    }
                    
                    # DÃ©tailler le contenu
                    for purchase in purchases:
                        if purchase.film_id:
                            film = Film.query.get(purchase.film_id)
                            if film:
                                content_details.append(f"Film: {film.title} ({film.year}) - {film.price} FCFA")
                        elif purchase.series_id and purchase.season_id:
                            series = Series.query.get(purchase.series_id)
                            season = Season.query.get(purchase.season_id)
                            if series and season:
                                content_details.append(f"SÃ©rie: {series.title} - Saison {season.season_number} ({season.year}) - {season.price} FCFA")
            
            # RÃ©cupÃ©rer les informations sur l'admin qui a confirmÃ© (si applicable)
            confirmed_by_info = None
            if transaction.confirmed_by:
                admin_user = User.query.get(transaction.confirmed_by)
                confirmed_by_info = {
                    'username': admin_user.username,
                    'date': transaction.confirmed_date.strftime('%Y-%m-%d %H:%M') if transaction.confirmed_date else 'N/A'
                }
            
            # PrÃ©parer les donnÃ©es de la transaction
            transaction_data = {
                'id': transaction.id,
                'client': {
                    'username': client.username,
                    'telegram_id': client.telegram_id or 'N/A',
                    'email': client.email or 'N/A'
                },
                'product': product_info,
                'content_details': content_details,
                'amount': transaction.amount,
                'payment_method': transaction.payment_method,
                'status': transaction.status,
                'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d %H:%M'),
                'confirmed_by': confirmed_by_info,
                'payment_screenshot': transaction.payment_screenshot,
                'description': getattr(transaction, 'description', '')
            }
            
            transactions_data.append(transaction_data)
        
        # RÃ©cupÃ©rer les statistiques pour l'affichage
        total_transactions = Transaction.query.count()
        pending_transactions = Transaction.query.filter_by(status='pending').count()
        confirmed_transactions = Transaction.query.filter_by(status='confirmed').count()
        rejected_transactions = Transaction.query.filter_by(status='rejected').count()
        
        # Calculer les revenus
        total_revenue = db.session.query(db.func.sum(Transaction.amount)).filter_by(status='confirmed').scalar() or 0
        admin_created_revenue = db.session.query(db.func.sum(Transaction.amount)).filter_by(
            status='confirmed', 
            payment_method='admin_creation'
        ).scalar() or 0
        
        return render_template('admin/transactions.html', 
                            transactions=transactions_data, 
                            status_filter=status_filter,
                            total_transactions=total_transactions,
                            pending_transactions=pending_transactions,
                            confirmed_transactions=confirmed_transactions,
                            rejected_transactions=rejected_transactions,
                            total_revenue=total_revenue,
                            admin_created_revenue=admin_created_revenue)
    
    @app.route('/admin/transaction/confirm/<int:transaction_id>')
    @admin_required
    def confirm_transaction(transaction_id):
        transaction = Transaction.query.get_or_404(transaction_id)
        
        if transaction.status != 'pending':
            flash('Cette transaction a dÃ©jÃ  Ã©tÃ© traitÃ©e.', 'warning')
            return redirect(url_for('admin_transactions'))
        
        # GÃ©nÃ©rer un token d'accÃ¨s pour l'utilisateur
        access_token = AccessToken(
            user_id=transaction.user_id,
            expiry_date=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(access_token)
        db.session.flush()
        
        # Lier l'achat au token
        if transaction.film_id:
            purchase = TokenPurchase(
                token_id=access_token.id,
                film_id=transaction.film_id
            )
        elif transaction.series_id and transaction.season_id:
            purchase = TokenPurchase(
                token_id=access_token.id,
                series_id=transaction.series_id,
                season_id=transaction.season_id
            )
        
        db.session.add(purchase)
        
        # Mettre Ã  jour la transaction
        transaction.status = 'confirmed'
        transaction.confirmed_date = datetime.utcnow()
        transaction.confirmed_by = current_user.id
        
        db.session.commit()
        
        flash('Transaction confirmÃ©e et token gÃ©nÃ©rÃ©.', 'success')
        return redirect(url_for('admin_transactions'))
    
    @app.route('/admin/transaction/reject/<int:transaction_id>')
    @admin_required
    def reject_transaction(transaction_id):
        transaction = Transaction.query.get_or_404(transaction_id)
        
        if transaction.status != 'pending':
            flash('Cette transaction a dÃ©jÃ  Ã©tÃ© traitÃ©e.', 'warning')
            return redirect(url_for('admin_transactions'))
        
        transaction.status = 'rejected'
        transaction.confirmed_date = datetime.utcnow()
        transaction.confirmed_by = current_user.id
        
        db.session.commit()
        
        flash('Transaction rejetÃ©e.', 'success')
        return redirect(url_for('admin_transactions'))

    @app.route('/api/data/download', methods=['GET'])
    @admin_required
    def download_data_json():
        # Exporter les films
        films = Film.query.all()
        films_data = []
        for film in films:
            films_data.append({
                'id': film.id,
                'title': film.title,
                'year': film.year,
                'description': film.description,
                'price': film.price,
                'genre': film.genre,
                'duration': film.duration
            })

        # Exporter les sÃ©ries, saisons et Ã©pisodes
        series_list = Series.query.all()
        series_data = []
        for series_obj in series_list:
            seasons_data = []
            for season in series_obj.seasons:
                episodes_data = []
                for episode in season.episodes:
                    episodes_data.append({
                        'id': episode.id,
                        'episode_number': episode.episode_number,
                        'title': episode.title,
                        'chemin': episode.chemin,
                        'duration': episode.duration
                    })
                seasons_data.append({
                    'id': season.id,
                    'season_number': season.season_number,
                    'year': season.year,
                    'description': season.description,
                    'price': season.price,
                    'episodes': episodes_data
                })
            series_data.append({
                'id': series_obj.id,
                'title': series_obj.title,
                'description': series_obj.description,
                'seasons': seasons_data
            })

        full_data = {
            'films': films_data,
            'series': series_data
        }
        
        # Enregistre les donnÃ©es JSON dans un fichier temporaire
        file_path = 'data_export.json'
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, ensure_ascii=False, indent=4)
            
        # Envoie le fichier pour tÃ©lÃ©chargement
        return send_file(file_path, as_attachment=True, download_name='films_et_series.json')
    
    # API pour le bot Telegram
    @app.route('/api/bot/films', methods=['GET'])
    def api_get_films():
        films = Film.query.order_by(Film.title).all()
        films_data = []
        
        for film in films:
            films_data.append({
                'id': film.id,
                'title': film.title,
                'year': film.year,
                'description': film.description,
                'price': film.price,
                'thumbnail_url': url_for('get_thumbnail', filename=film.thumbnail, _external=True) if film.thumbnail else None,
                'chemin': film.chemin,
                'genre': film.genre,
                'duration': film.duration,
                'formatted_duration': film.get_formatted_duration()
            })
        
        return jsonify(films_data)
    
    @app.route('/api/bot/series', methods=['GET'])
    def api_get_series():
        series_list = Series.query.order_by(Series.title).all()
        series_data = []
        
        for series in series_list:
            seasons = Season.query.filter_by(series_id=series.id).all()
            seasons_data = []
            
            for season in seasons:
                # RÃ©cupÃ©rer les Ã©pisodes de la saison
                episodes = Episode.query.filter_by(season_id=season.id).order_by(Episode.episode_number).all()
                episodes_data = []
                
                for episode in episodes:
                    episodes_data.append({
                        'id': episode.id,
                        'episode_number': episode.episode_number,
                        'title': episode.title,
                        'chemin': episode.chemin,
                        'duration': episode.duration,
                        'formatted_duration': episode.get_formatted_duration()
                    })
                
                seasons_data.append({
                    'id': season.id,
                    'season_number': season.season_number,
                    'year': season.year,
                    'description': season.description,
                    'price': season.price,
                    'episodes': episodes_data
                })
            
            series_data.append({
                'id': series.id,
                'title': series.title,
                'description': series.description,
                'thumbnail_url': url_for('get_thumbnail', filename=series.thumbnail, _external=True) if series.thumbnail else None,
                'seasons': seasons_data
            })
        
        return jsonify(series_data)
    
    @app.route('/api/bot/transaction', methods=['POST'])
    def api_create_transaction():
        data = request.get_json()
        
        # Valider les donnÃ©es
        required_fields = ['user_id', 'amount', 'payment_method']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Champs manquants'}), 400
        
        # VÃ©rifier si l'utilisateur existe, sinon le crÃ©er
        user = User.query.filter_by(telegram_id=data['user_id']).first()
        if not user:
            user = User(telegram_id=data['user_id'], username=f"user_{data['user_id']}")
            db.session.add(user)
            db.session.commit()
        
        # CrÃ©er la transaction
        transaction = Transaction(
            user_id=user.id,
            film_id=data.get('film_id'),
            series_id=data.get('series_id'),
            season_id=data.get('season_id'),
            amount=data['amount'],
            payment_method=data['payment_method'],
            status='pending'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({'success': True, 'transaction_id': transaction.id})
    


    # Route pour streamer les films
    @app.route('/client/watch/film/<int:film_id>')
    @login_required
    def watch_film(film_id):
        if current_user.is_admin:
            flash('Accès réservé aux clients.', 'warning')
            return redirect(url_for('admin_dashboard'))
        
        # Vérifier que l'utilisateur a accès à ce film
        has_access = False
        active_token = AccessToken.query.filter_by(
            user_id=current_user.id
        ).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).first()
        
        if active_token:
            purchase = TokenPurchase.query.filter_by(
                token_id=active_token.id,
                film_id=film_id
            ).first()
            if purchase:
                has_access = True
        
        if not has_access:
            flash('Vous n\'avez pas accès à ce contenu.', 'danger')
            return redirect(url_for('client_index'))
        
        film = Film.query.get_or_404(film_id)
        return render_template('client/watch_film.html', film=film)

    # Route pour streamer les épisodes
    @app.route('/client/watch/episode/<int:episode_id>')
    @login_required
    def watch_episode(episode_id):
        if current_user.is_admin:
            flash('Accès réservé aux clients.', 'warning')
            return redirect(url_for('admin_dashboard'))
        
        episode = Episode.query.get_or_404(episode_id)
        
        # Vérifier que l'utilisateur a accès à cet épisode
        has_access = False
        active_token = AccessToken.query.filter_by(
            user_id=current_user.id
        ).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).first()
        
        if active_token:
            purchase = TokenPurchase.query.filter_by(
                token_id=active_token.id,
                series_id=episode.season.series_id,
                season_id=episode.season_id
            ).first()
            if purchase:
                has_access = True
        
        if not has_access:
            flash('Vous n\'avez pas accès à ce contenu.', 'danger')
            return redirect(url_for('client_index'))
        
        # Récupérer tous les épisodes de la saison pour la navigation
        all_episodes = Episode.query.filter_by(
            season_id=episode.season_id
        ).order_by(Episode.episode_number).all()
        
        return render_template('client/watch_episode.html', 
                            episode=episode, 
                            all_episodes=all_episodes)

    # Route pour servir les vidéos avec streaming
    @app.route('/stream/film/<int:film_id>')
    @login_required
    def stream_film(film_id):
        if current_user.is_admin:
            return abort(403)
        
        # Vérifier l'accès
        has_access = False
        active_token = AccessToken.query.filter_by(
            user_id=current_user.id
        ).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).first()
        
        if active_token:
            purchase = TokenPurchase.query.filter_by(
                token_id=active_token.id,
                film_id=film_id
            ).first()
            if purchase:
                has_access = True
        
        if not has_access:
            return abort(403)
        
        film = Film.query.get_or_404(film_id)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'films', film.chemin)
        
        if not os.path.exists(file_path):
            return abort(404)
        
        # Supporter le streaming avec range requests
        def generate():
            with open(file_path, 'rb') as f:
                data = f.read(1024)
                while data:
                    yield data
                    data = f.read(1024)
        
        # Déterminer le type MIME
        file_ext = os.path.splitext(film.chemin)[1].lower()
        mime_type = {
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv'
        }.get(file_ext, 'video/mp4')
        
        file_size = os.path.getsize(file_path)
        
        # Gérer les range requests pour le streaming
        range_header = request.headers.get('Range', None)
        if range_header:
            byte_start = 0
            byte_end = file_size - 1
            
            range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                byte_start = int(range_match.group(1))
                if range_match.group(2):
                    byte_end = int(range_match.group(2))
            
            def generate_range():
                with open(file_path, 'rb') as f:
                    f.seek(byte_start)
                    remaining = byte_end - byte_start + 1
                    while remaining:
                        chunk_size = min(1024, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data
            
            response = Response(
                generate_range(),
                206,
                {
                    'Content-Type': mime_type,
                    'Accept-Ranges': 'bytes',
                    'Content-Range': f'bytes {byte_start}-{byte_end}/{file_size}',
                    'Content-Length': str(byte_end - byte_start + 1),
                }
            )
        else:
            response = Response(
                generate(),
                200,
                {
                    'Content-Type': mime_type,
                    'Content-Length': str(file_size),
                }
            )
        
        return response

    @app.route('/stream/episode/<int:episode_id>')
    @login_required
    def stream_episode(episode_id):
        if current_user.is_admin:
            return abort(403)
        
        episode = Episode.query.get_or_404(episode_id)
        
        # Vérifier l'accès
        has_access = False
        active_token = AccessToken.query.filter_by(
            user_id=current_user.id
        ).filter(
            (AccessToken.expiry_date == None) | 
            (AccessToken.expiry_date >= datetime.utcnow())
        ).first()
        
        if active_token:
            purchase = TokenPurchase.query.filter_by(
                token_id=active_token.id,
                series_id=episode.season.series_id,
                season_id=episode.season_id
            ).first()
            if purchase:
                has_access = True
        
        if not has_access:
            return abort(403)
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'episodes', episode.chemin)
        
        if not os.path.exists(file_path):
            return abort(404)
        
        # Même logique de streaming que pour les films
        def generate():
            with open(file_path, 'rb') as f:
                data = f.read(1024)
                while data:
                    yield data
                    data = f.read(1024)
        
        file_ext = os.path.splitext(episode.chemin)[1].lower()
        mime_type = {
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv'
        }.get(file_ext, 'video/mp4')
        
        file_size = os.path.getsize(file_path)
        
        range_header = request.headers.get('Range', None)
        if range_header:
            byte_start = 0
            byte_end = file_size - 1
            
            range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                byte_start = int(range_match.group(1))
                if range_match.group(2):
                    byte_end = int(range_match.group(2))
            
            def generate_range():
                with open(file_path, 'rb') as f:
                    f.seek(byte_start)
                    remaining = byte_end - byte_start + 1
                    while remaining:
                        chunk_size = min(1024, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data
            
            response = Response(
                generate_range(),
                206,
                {
                    'Content-Type': mime_type,
                    'Accept-Ranges': 'bytes',
                    'Content-Range': f'bytes {byte_start}-{byte_end}/{file_size}',
                    'Content-Length': str(byte_end - byte_start + 1),
                }
            )
        else:
            response = Response(
                generate(),
                200,
                {
                    'Content-Type': mime_type,
                    'Content-Length': str(file_size),
                }
            )
        
        return response
    
    # Page de tÃ©lÃ©chargement client
    #@app.route('/client/<token>')
    # def client_access(token):
    #     access_token = AccessToken.query.filter_by(token=token).first()
        
    #     if not access_token or (access_token.expiry_date and access_token.expiry_date < datetime.utcnow()):
    #         return render_template('client/invalid_token.html')
        
    #     # RÃ©cupÃ©rer les achats associÃ©s Ã  ce token
    #     purchases = TokenPurchase.query.filter_by(token_id=access_token.id).all()
        
    #     films = []
    #     series = {}
        
    #     for purchase in purchases:
    #         if purchase.film_id:
    #             film = Film.query.get(purchase.film_id)
    #             if film:
    #                 films.append(film)
    #         elif purchase.series_id and purchase.season_id:
    #             series_obj = Series.query.get(purchase.series_id)
    #             season = Season.query.get(purchase.season_id)
                
    #             if series_obj and season:
    #                 if series_obj.id not in series:
    #                     series[series_obj.id] = {
    #                         'series': series_obj,
    #                         'seasons': []
    #                     }
                    
    #                 # RÃ©cupÃ©rer les Ã©pisodes de la saison
    #                 episodes = Episode.query.filter_by(season_id=season.id).order_by(Episode.episode_number).all()
    #                 series[series_obj.id]['seasons'].append({
    #                     'season': season,
    #                     'episodes': episodes
    #                 })
        
    #     return render_template('client/downloads.html', 
    #                          films=films, 
    #                          series=series.values(),
    #                          token=token)

    
    
    # Fonction utilitaire pour vÃ©rifier les extensions de fichiers
    def allowed_file(filename, allowed_extensions):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # CrÃ©er les tables si elles n'existent pas
    with app.app_context():
        db.create_all()
        
        # CrÃ©er un utilisateur admin par dÃ©faut si aucun n'existe
        if not User.query.filter_by(is_admin=True).first():
            admin_user = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created: username=admin, password=admin123")
    
    app.run(debug=True)


    