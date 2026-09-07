# Importamos las librerias necesarias
from sqlalchemy.orm import declarative_base  # Base declarativa de SQLAlchemy

# Creamos el registro declarativo que comparten todos los modelos.
# No declaramos schema en los modelos: lo resuelve el search_path que fija
# DatabaseManager.initialize() a partir de settings.DB_SCHEMA.
Base = declarative_base()
