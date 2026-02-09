from flask import Blueprint, jsonify, request, current_app, g
from werkzeug.security import check_password_hash
from flask_login import current_user
import jwt
import datetime
from functools import wraps
from models import User, Relatorio, Projeto, FotoRelatorio, Visita
from app import db
import os

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Configuração JWT (chaves devem vir do app.config)
def get_jwt_secret():
    return current_app.config.get('SECRET_KEY', 'dev-secret-key')

# Decorator de Auth
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
            current_user_data = db.session.get(User, data['user_id'])
            if not current_user_data:
                raise Exception("User not found")
        except Exception as e:
            return jsonify({'error': 'Token is invalid!', 'details': str(e)}), 401
            
        return f(current_user_data, *args, **kwargs)
    
    return decorated

@api_bp.route('/status', methods=['GET'])
def api_status():
    return jsonify({'status': 'online', 'server_time': datetime.datetime.utcnow().isoformat()})

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing credentials'}), 400
        
    user = User.query.filter_by(username=data['username']).first()
    
    if not user and '@' in data['username']:
        user = User.query.filter_by(email=data['username']).first()
        
    if user and check_password_hash(user.password_hash, data['password']):
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30) # Token de longa duração para app
        }, get_jwt_secret(), algorithm="HS256")
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'nome_completo': user.nome_completo,
                'email': user.email,
                'cargo': user.cargo,
                'is_master': user.is_master
            }
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@api_bp.route('/dashboard', methods=['GET'])
@token_required
def dashboard_data(current_user):
    try:
        # Estatísticas
        obras_ativas = Projeto.query.filter_by(status='Ativo').count()
        relatorios_pendentes = Relatorio.query.filter(
            Relatorio.status.in_(['Aguardando Aprovação', 'Pendente'])
        ).count()
        visitas_agendadas = Visita.query.filter(
            Visita.status == 'Agendada',
            Visita.data_inicio >= datetime.datetime.now()
        ).count()

        # Relatórios Recentes
        if current_user.is_master:
            relatorios_query = Relatorio.query
        else:
            relatorios_query = Relatorio.query.filter_by(autor_id=current_user.id)
            
        relatorios = relatorios_query.order_by(Relatorio.created_at.desc()).limit(10).all()
        
        recent_reports = []
        for r in relatorios:
            recent_reports.append({
                'id': r.id,
                'numero': r.numero,
                'titulo': r.titulo,
                'projeto_nome': r.projeto.nome if r.projeto else 'Sem projeto',
                'status': r.status,
                'data_relatorio': r.data_relatorio.isoformat() if r.data_relatorio else None,
                'autor_nome': r.autor.nome_completo if r.autor else 'Desconhecido'
            })

        return jsonify({
            'obras_ativas': obras_ativas,
            'relatorios_pendentes': relatorios_pendentes,
            'visitas_agendadas': visitas_agendadas,
            'relatorios_recentes': recent_reports
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/projects', methods=['GET'])
@token_required
def get_projects(current_user):
    try:
        projetos = Projeto.query.filter_by(status='Ativo').all()
        output = []
        for p in projetos:
            output.append({
                'id': p.id,
                'numero': p.numero,
                'nome': p.nome,
                'endereco': p.endereco,
                'tipo_obra': p.tipo_obra,
                'construtora': p.construtora,
                'status': p.status,
                'data_inicio': p.data_inicio.isoformat() if p.data_inicio else None
            })
        return jsonify(output)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/reports', methods=['GET'])
@token_required
def get_reports(current_user):
    try:
        if current_user.is_master:
            relatorios = Relatorio.query.all()
        else:
            relatorios = Relatorio.query.filter_by(autor_id=current_user.id).all()
        
        output = []
        for r in relatorios:
            output.append({
                'id': r.id,
                'numero': r.numero,
                'titulo': r.titulo,
                'projeto_id': r.projeto_id,
                'projeto_nome': r.projeto.nome if r.projeto else None,
                'status': r.status,
                'data_relatorio': r.data_relatorio.isoformat() if r.data_relatorio else None,
                'autor_nome': r.autor.nome_completo if r.autor else None,
                'created_at': r.created_at.isoformat() if r.created_at else None
            })
        return jsonify(output)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/visits', methods=['GET'])
@token_required
def get_visits(current_user):
    try:
        if current_user.is_master:
            visitas = Visita.query.all()
        else:
            visitas = Visita.query.filter_by(responsavel_id=current_user.id).all()
        
        output = []
        for v in visitas:
            output.append({
                'id': v.id,
                'numero': v.numero,
                'projeto_id': v.projeto_id,
                'projeto_nome': v.projeto_nome,
                'data_inicio': v.data_inicio.isoformat() if v.data_inicio else None,
                'data_fim': v.data_fim.isoformat() if v.data_fim else None,
                'status': v.status,
                'observacoes': v.observacoes
            })
        return jsonify(output)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/sync/down', methods=['GET'])
@token_required
def sync_down(current_user):
    """
    Endpoint para baixar dados iniciais/incrementais para o app.
    """
    try:
        # Projetos
        projetos = Projeto.query.filter_by(status='Ativo').all()
        projetos_data = [{
            'id': p.id,
            'numero': p.numero,
            'nome': p.nome,
            'endereco': p.endereco,
            'tipo_obra': p.tipo_obra
        } for p in projetos]
        
        # Relatórios do usuário
        relatorios = Relatorio.query.filter_by(autor_id=current_user.id).order_by(Relatorio.created_at.desc()).limit(50).all()
        relatorios_data = [{
            'id': r.id,
            'numero': r.numero,
            'titulo': r.titulo,
            'projeto_id': r.projeto_id,
            'status': r.status,
            'data_relatorio': r.data_relatorio.isoformat() if r.data_relatorio else None
        } for r in relatorios]
        
        # Visitas do usuário
        visitas = Visita.query.filter_by(responsavel_id=current_user.id).order_by(Visita.data_inicio.desc()).limit(50).all()
        visitas_data = [{
            'id': v.id,
            'numero': v.numero,
            'projeto_id': v.projeto_id,
            'data_inicio': v.data_inicio.isoformat() if v.data_inicio else None,
            'status': v.status
        } for v in visitas]
        
        return jsonify({
            'projetos': projetos_data,
            'relatorios': relatorios_data,
            'visitas': visitas_data,
            'sync_time': datetime.datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@api_bp.route('/defaults', methods=['GET'])
@token_required
def get_defaults(current_user):
    """
    Retorna dados padrão para o app (Checklists, Legendas)
    """
    try:
        from models import ChecklistPadrao, LegendaPredefinida
        
        checklists = ChecklistPadrao.query.filter_by(ativo=True).order_by(ChecklistPadrao.ordem).all()
        legendas = LegendaPredefinida.query.filter_by(ativo=True).all()
        
        return jsonify({
            'checklists': [{'id': c.id, 'texto': c.texto, 'ordem': c.ordem} for c in checklists],
            'legendas': [{'id': l.id, 'texto': l.texto, 'categoria': l.categoria} for l in legendas]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/reports/create', methods=['POST'])
@token_required
def create_report(current_user):
    """
    Cria um novo relatório via API.
    Handles auto-numbering and checklist storage.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        if not data.get('projeto_id'):
            return jsonify({'error': 'projeto_id is required'}), 400

        projeto = db.session.get(Projeto, data['projeto_id'])
        if not projeto:
            return jsonify({'error': 'Projeto not found'}), 404

        # Generate Sequential Number
        # Lock this operation in a transaction if high concurrency, but for now simple query is fine
        last_report = Relatorio.query.filter_by(projeto_id=projeto.id).order_by(Relatorio.numero_projeto.desc()).first()
        next_num = (last_report.numero_projeto + 1) if last_report and last_report.numero_projeto else 1
        
        # Format: PROJ-NUM (e.g., P123-1, P123-2)
        report_numero = f"{projeto.numero}-{next_num}"

        # Parse date
        try:
            data_relatorio = datetime.datetime.fromisoformat(data['data_relatorio'].replace('Z', '+00:00')) if data.get('data_relatorio') else datetime.datetime.utcnow()
        except:
            data_relatorio = datetime.datetime.utcnow()

        new_report = Relatorio(
            numero=report_numero,
            numero_projeto=next_num,
            projeto_id=projeto.id,
            autor_id=current_user.id,
            titulo=data.get('titulo', 'Relatório de Visita'),
            descricao=data.get('descricao'),
            observacoes_finais=data.get('observacoes'),
            condicoes_climaticas=data.get('condicoes_climaticas'), # Note: field might need to be added to model if not exists, storing in descricao/obs for now or add column
            data_relatorio=data_relatorio,
            status=data.get('status', 'Aguardando Aprovação'),
            checklist_data=data.get('checklist_data'), # JSON string
            created_at=datetime.datetime.utcnow()
        )
        
        # If 'observacoes_finais' or 'condicoes_climaticas' are not in model yet, append to description
        if not hasattr(Relatorio, 'condicoes_climaticas') and data.get('condicoes_climaticas'):
             new_report.descricao = (new_report.descricao or "") + f"\n\nCondições: {data.get('condicoes_climaticas')}"

        db.session.add(new_report)
        db.session.commit()

        logging.info(f"✅ Report created via API: {new_report.numero} by {current_user.username}")

        return jsonify({
            'message': 'Relatório criado com sucesso',
            'id': new_report.id,
            'numero': new_report.numero,
            'status': new_report.status
        }), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ Error creating report: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/fotos/upload', methods=['POST'])
@token_required
def upload_photo(current_user):
    """
    Upload de foto vinculada a um relatório.
    Expects multipart/form-data with 'photo' file and 'reportId'.
    """
    try:
        if 'photo' not in request.files:
            return jsonify({'error': 'No photo file provided'}), 400
            
        file = request.files['photo']
        report_id = request.form.get('reportId')
        
        if not report_id:
             return jsonify({'error': 'reportId is required'}), 400

        # Find report
        report = db.session.get(Relatorio, report_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        # Verify permission
        if report.autor_id != current_user.id and not current_user.is_master:
            return jsonify({'error': 'Permission denied'}), 403

        # Save file
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file:
            filename = f"report_{report.id}_{int(datetime.datetime.utcnow().timestamp())}_{file.filename}"
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            
            # Ensure folder exists
            os.makedirs(upload_folder, exist_ok=True)
            
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            
            # Create DB Record
            foto = FotoRelatorio(
                relatorio_id=report.id,
                filename=filename,
                url=f"/uploads/{filename}", # Relative URL for frontend
                titulo=request.form.get('titulo', ''),
                legenda=request.form.get('legenda', ''),
                created_at=datetime.datetime.utcnow()
            )
            
            db.session.add(foto)
            db.session.commit()
            
            return jsonify({
                'message': 'Foto enviada com sucesso',
                'id': foto.id,
                'url': foto.url
            }), 201
            
    except Exception as e:
        logging.error(f"❌ Photo upload failed: {e}")
        return jsonify({'error': str(e)}), 500
