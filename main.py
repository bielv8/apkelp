from app import app  # noqa: F401
# Models will be imported by routes.py and routes_pwa.py
import routes_pwa  # noqa: F401
import routes  # noqa: F401
import railway_routes_fix  # noqa: F401
# import routes_relatorios_api  # noqa: F401  # API REST para relatórios com autosave
import routes_express  # noqa: F401  # Relatório Express

# Auto-run migrations on Railway deploy
import os
import logging

def clean_orphaned_alembic_versions():
    """Verifica se existe versão órfã e deixa Alembic gerenciar automaticamente"""
    try:
        from sqlalchemy import create_engine, text
        database_url = os.environ.get("DATABASE_URL")
        
        if not database_url:
            return
            
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
        
        # Verificar se tabela alembic_version existe
        with engine.connect() as connection:
            try:
                result = connection.execute(text("SELECT version_num FROM alembic_version")).fetchone()
                if result:
                    current_version = result[0]
                    logging.info(f"🔍 Versão Alembic no banco: {current_version}")
                    logging.info("ℹ️ Alembic irá validar e aplicar migrações se necessário")
            except Exception as check_error:
                logging.debug(f"Tabela alembic_version ainda não existe: {check_error}")
                
    except Exception as e:
        logging.warning(f"⚠️ Erro ao verificar versão Alembic: {e}")

if os.environ.get("RAILWAY_ENVIRONMENT"):
    logging.info("🚂 Railway environment - preparando migrações...")
    
    # Limpar versões órfãs antes de executar migrações
    clean_orphaned_alembic_versions()
    
    logging.info("🔄 Verificando estado das migrações...")
    try:
        from sqlalchemy import create_engine, text, inspect
        import subprocess
        
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            engine = create_engine(database_url)
            inspector = inspect(engine)
            
            # Verificar se as tabelas principais já existem
            tables_exist = 'checklist_padrao' in inspector.get_table_names()
            
            # Verificar se alembic_version tem alguma entrada
            with engine.connect() as conn:
                try:
                    result = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
                    has_version = result is not None
                except:
                    has_version = False
            
            if tables_exist and not has_version:
                # Tabelas existem mas alembic_version está vazio
                # Marcar migração base como aplicada sem executar
                logging.info("📌 Tabelas detectadas - marcando migração base como aplicada...")
                result = subprocess.run(['alembic', 'stamp', '265f97ab88c1'], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    logging.info("✅ Migração base marcada como aplicada")
                else:
                    logging.warning(f"⚠️ Erro ao marcar migração: {result.stderr}")
            
            # Sempre executar upgrade para aplicar migrações pendentes
            logging.info("🔄 Aplicando migrações pendentes...")
            result = subprocess.run(['alembic', 'upgrade', 'head'], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                logging.info("✅ Migrações aplicadas com sucesso")
                if result.stdout:
                    logging.info(f"   {result.stdout.strip()}")
            else:
                logging.warning(f"⚠️ Migração falhou: {result.stderr}")
                
    except Exception as e:
        logging.warning(f"⚠️ Erro nas migrações (continuando): {e}")

# Run the Flask development server
if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
