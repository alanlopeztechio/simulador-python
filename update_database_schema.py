"""
Script to update database schema with companies and routes tables.
Run this to migrate the database to the new structure.
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import DatabaseManager

def main():
    """Update database schema."""
    print("=" * 60)
    print("ACTUALIZACIÓN DE ESQUEMA DE BASE DE DATOS")
    print("=" * 60)
    print()
    print("Este script actualizará la base de datos con:")
    print("  • Tabla de compañías (companies)")
    print("  • Tabla de rutas (routes)")
    print("  • Actualización de tabla de simulaciones (simulations)")
    print()
    
    # Load environment
    load_dotenv()
    
    # Check for database connection
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ ERROR: DATABASE_URL no está configurada en el archivo .env")
        print()
        print("Por favor, crea un archivo .env con tu string de conexión:")
        print("DATABASE_URL=postgresql://user:password@host/database")
        return 1
    
    print(f"✓ DATABASE_URL encontrada")
    print()
    
    # Ask for confirmation
    response = input("¿Deseas continuar con la actualización? (s/n): ")
    if response.lower() not in ['s', 'si', 'y', 'yes']:
        print("Actualización cancelada.")
        return 0
    
    print()
    print("Conectando a la base de datos...")
    
    try:
        # Connect to database
        db = DatabaseManager()
        db.connect()
        
        print("✓ Conectado exitosamente")
        print()
        print("Aplicando cambios al esquema...")
        print()
        
        # Initialize schema (will create new tables and update existing ones)
        schema_file = os.path.join(os.path.dirname(__file__), 'db', 'schema.sql')
        db.initialize_schema(schema_file)
        
        print()
        print("=" * 60)
        print("✅ ACTUALIZACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        print()
        print("Las siguientes tablas están ahora disponibles:")
        print("  • companies - Gestión de compañías")
        print("  • routes - Gestión de rutas vinculadas a compañías")
        print("  • simulations - Actualizada con referencias a companies y routes")
        print()
        print("Ahora puedes usar la aplicación para:")
        print("  1. Registrar compañías en la pestaña 'Compañías'")
        print("  2. Crear rutas vinculadas a compañías en 'Rutas'")
        print("  3. Seleccionar compañía y ruta para ejecutar simulaciones")
        print()
        
        db.disconnect()
        return 0
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR DURANTE LA ACTUALIZACIÓN")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()
        print("Por favor, revisa:")
        print("  • Que la URL de conexión sea correcta")
        print("  • Que tengas permisos para modificar la base de datos")
        print("  • Que la base de datos esté accesible")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
