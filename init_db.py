"""
Database initialization script for Railway deployment
Creates all tables if they don't exist
"""
from app import app, db
from models import (
    User, Projeto, Relatorio, Visita, FotoRelatorio,
    Contato, ContatoProjeto, Reembolso, EnvioRelatorio,
    ChecklistTemplate, ChecklistItem, ComunicacaoVisita,
    EmailCliente, ChecklistPadrao, LogEnvioEmail,
    ConfiguracaoEmail, LegendaPredefinida, FuncionarioProjeto,
    AprovadorPadrao, ProjetoChecklistConfig, ChecklistObra,
    VisitaParticipante, TipoObra, CategoriaObra, Notificacao,
    GoogleDriveToken, RelatorioExpress, FotoRelatorioExpress,
    Lembrete, UserEmailConfig, UserDevice
)
import logging

logging.basicConfig(level=logging.INFO)

def init_database():
    """Initialize database tables"""
    with app.app_context():
        try:
            logging.info("🔄 Creating database tables...")
            db.create_all()
            logging.info("✅ Database tables created successfully!")
            
            # Verify tables were created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logging.info(f"📊 Tables in database: {len(tables)}")
            for table in tables:
                logging.info(f"  - {table}")
            
            return True
        except Exception as e:
            logging.error(f"❌ Error creating database tables: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = init_database()
    exit(0 if success else 1)
