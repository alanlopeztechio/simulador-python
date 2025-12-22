"""
Script simple para subir archivos JSON de simulación a Neon PostgreSQL
Los segmentos se generan automáticamente desde los inventories
"""

import json
import sys
import os
from db.database import save_simulation_to_neon


def main():
    """Función principal del script"""
    if len(sys.argv) < 2:
        print("="*80)
        print("SUBIR JSON A NEON POSTGRESQL")
        print("="*80)
        print("\nUso:")
        print(f"  python {sys.argv[0]} <archivo.json>")
        print("\nEjemplo:")
        print(f"  python {sys.argv[0]} simulation_outputs/20s2_000001_1_20251215_131010.json")
        print("\nNota: Asegúrate de tener configurado el archivo .env con DATABASE_URL")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    if not os.path.exists(json_file):
        print(f"❌ Error: Archivo no encontrado: {json_file}")
        sys.exit(1)
    
    print("="*80)
    print("SUBIR SIMULACIÓN A NEON POSTGRESQL")
    print("="*80)
    print()
    print(f"📂 Archivo: {json_file}")
    print()
    
    try:
        # La función save_simulation_to_neon ya maneja todo
        # incluyendo la generación automática de segmentos desde inventories
        simulation_id = save_simulation_to_neon(json_file=json_file)
        
        print()
        print("="*80)
        print("✅ SIMULACIÓN GUARDADA EXITOSAMENTE")
        print("="*80)
        print(f"   ID: {simulation_id}")
        print()
        print("   Tablas pobladas:")
        print("      ✓ simulations")
        print("      ✓ segments (generados desde inventories)")
        print("      ✓ stops")
        print("      ✓ sensor_data")
        print()
        print("   Vistas disponibles en Power BI:")
        print("      ✓ vw_segment_analytics")
        print("      ✓ vw_simulations_summary")
        print("      ✓ vw_temperature_violations")
        print("      ✓ vw_stop_timeline")
        print("      ✓ vw_sensor_data_enriched")
        print()
        print("="*80)
        return 0
        
    except Exception as e:
        print()
        print("="*80)
        print("❌ ERROR AL GUARDAR EN BASE DE DATOS")
        print("="*80)
        print(f"   {e}")
        print()
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
