"""
Script para inicializar la base de datos en Neon PostgreSQL
Ejecuta este script una vez para crear todas las tablas y vistas
"""

import sys
import os
from db.database import DatabaseManager

def main():
    print("="*80)
    print("INICIALIZACIÓN DE BASE DE DATOS - NEON POSTGRESQL")
    print("="*80)
    print()
    
    # Verificar que existe el archivo .env
    if not os.path.exists('.env'):
        print("⚠️  No se encontró archivo .env")
        print("   Copia .env.example a .env y configura tu DATABASE_URL")
        print()
        
        # Solicitar connection string manualmente
        connection_string = input("Ingresa tu Neon connection string (o presiona Enter para salir): ").strip()
        if not connection_string:
            print("Operación cancelada")
            return
    else:
        connection_string = None
        print("✓ Archivo .env encontrado")
    
    print()
    print("Conectando a Neon PostgreSQL...")
    
    try:
        with DatabaseManager(connection_string) as db:
            print("✓ Conexión establecida")
            print()
            print("Inicializando esquema de base de datos...")
            db.initialize_schema()
            print()
            print("="*80)
            print("✅ BASE DE DATOS INICIALIZADA EXITOSAMENTE")
            print("="*80)
            print()
            print("Tablas creadas:")
            print("  - companies: Compañías")
            print("  - routes: Rutas configuradas")
            print("  - simulations: Metadata de simulaciones")
            print("  - segments: Tramos de ruta con estadísticas")
            print("  - stops: Paradas e inventarios")
            print("  - sensor_data: Lecturas de temperatura")
            print()
            print("Vistas creadas para Power BI:")
            print("  - vw_powerbi_master: Vista consolidada con toda la información")
            print()
            print("¡Listo para empezar a guardar simulaciones!")
            
    except Exception as e:
        print()
        print("="*80)
        print("❌ ERROR AL INICIALIZAR BASE DE DATOS")
        print("="*80)
        print(f"Error: {e}")
        print()
        print("Verifica:")
        print("  1. Que tu connection string sea correcto")
        print("  2. Que tengas permisos para crear tablas")
        print("  3. Que tu conexión a internet funcione")
        sys.exit(1)

if __name__ == "__main__":
    main()
