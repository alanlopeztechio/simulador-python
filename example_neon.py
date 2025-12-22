"""
Script de ejemplo para guardar simulaciones en Neon PostgreSQL
"""

from simulator import LogSimulator, PredefinedUseCases
from db.database import DatabaseManager, save_simulation_to_neon
import os

def ejemplo_basico():
    """Ejemplo básico: Crear simulación y guardarla en Neon"""
    
    print("="*80)
    print("EJEMPLO: GUARDAR SIMULACIÓN EN NEON")
    print("="*80)
    print()
    
    # 1. Crear una simulación usando un caso de uso predefinido
    use_cases = PredefinedUseCases.get_all_cases()
    use_case = use_cases[0]  # Usar el primer caso de uso
    
    print(f"Creando simulación: {use_case.name}")
    simulator = LogSimulator.from_use_case(
        use_case=use_case,
        epc="5201F250300001",
        tid="E2C245002000056680001",
        use_real_route=False
    )
    
    # 2. Generar datos
    print("Generando datos de simulación...")
    data = simulator.generate()
    print(f"✓ {len(data['loggedData'])} muestras generadas")
    
    # 3. Guardar en base de datos usando el método integrado
    print()
    print("Guardando en Neon PostgreSQL...")
    try:
        simulation_id = simulator.save_to_database()
        print(f"✓ Simulación guardada con ID: {simulation_id}")
        print()
        
        # 4. Verificar datos guardados
        print("Verificando datos guardados...")
        with DatabaseManager() as db:
            summary = db.get_simulation_summary(simulation_id)
            if summary:
                sim = summary[0]
                print(f"✓ Simulación recuperada:")
                print(f"  - EPC: {sim['epc']}")
                print(f"  - TID: {sim['tid']}")
                print(f"  - Ruta: {sim['route_name']}")
                print(f"  - Muestras: {sim['sensor_reading_count']}")
                print(f"  - Segmentos: {sim['segment_count']}")
                print(f"  - Paradas: {sim['stop_count']}")
                print(f"  - Compliance: {sim['compliance_rate']:.1f}%")
        
        return simulation_id
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print()
        print("Asegúrate de:")
        print("  1. Haber ejecutado init_database.py primero")
        print("  2. Tener configurado el archivo .env con DATABASE_URL")
        return None


def ejemplo_batch():
    """Ejemplo: Guardar múltiples simulaciones"""
    
    print("="*80)
    print("EJEMPLO: GUARDAR MÚLTIPLES SIMULACIONES")
    print("="*80)
    print()
    
    use_cases = PredefinedUseCases.get_all_cases()[:3]  # Solo primeros 3 casos
    
    simulation_ids = []
    
    for i, use_case in enumerate(use_cases, 1):
        print(f"\n[{i}/{len(use_cases)}] Procesando: {use_case.name}")
        
        simulator = LogSimulator.from_use_case(
            use_case=use_case,
            epc=f"5201F25030000{i}",
            tid=f"E2C24500200005668000{i}",
            use_real_route=False
        )
        
        try:
            simulation_id = simulator.save_to_database()
            simulation_ids.append(simulation_id)
            print(f"✓ Guardado con ID: {simulation_id}")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print()
    print("="*80)
    print(f"✓ {len(simulation_ids)} simulaciones guardadas")
    print(f"IDs: {simulation_ids}")
    print("="*80)
    
    return simulation_ids


def ejemplo_consulta():
    """Ejemplo: Consultar datos desde Neon"""
    
    print("="*80)
    print("EJEMPLO: CONSULTAR DATOS DE NEON")
    print("="*80)
    print()
    
    try:
        with DatabaseManager() as db:
            # Obtener resumen de últimas simulaciones
            print("Últimas simulaciones:")
            print("-" * 80)
            summaries = db.get_simulation_summary()
            
            for sim in summaries[:5]:  # Mostrar solo las primeras 5
                print(f"\nID: {sim['id']}")
                print(f"Ruta: {sim['route_name']}")
                print(f"EPC: {sim['epc']}")
                print(f"Fecha: {sim['created_at']}")
                print(f"Muestras: {sim['sensor_reading_count']}")
                print(f"Compliance: {sim['compliance_rate']:.1f}%")
                print(f"Violaciones: {sim['total_violations']}")
            
            print()
            print("="*80)
            
            # Obtener violaciones
            print("Últimas violaciones de temperatura:")
            print("-" * 80)
            violations = db.get_temperature_violations()
            
            for v in violations[:10]:  # Mostrar solo las primeras 10
                print(f"Simulación {v['simulation_id']} ({v['route_name']}): "
                      f"{v['temp_celsius']:.1f}°C - {v['violation_type']} @ {v['timestamp']}")
            
            print("="*80)
            
    except Exception as e:
        print(f"✗ Error consultando: {e}")


def ejemplo_desde_json():
    """Ejemplo: Guardar simulación desde archivo JSON existente"""
    
    print("="*80)
    print("EJEMPLO: GUARDAR DESDE JSON EXISTENTE")
    print("="*80)
    print()
    
    # Primero, generar un JSON de ejemplo
    print("1. Generando JSON de ejemplo...")
    simulator = LogSimulator.from_use_case(
        use_case=PredefinedUseCases.get_all_cases()[0],
        epc="5201F250300999",
        tid="E2C245002000056680999"
    )
    
    json_file = "temp_simulation.json"
    simulator.save_to_file(json_file)
    print(f"✓ JSON guardado en: {json_file}")
    
    # Ahora guardarlo en la base de datos
    print()
    print("2. Guardando JSON en Neon...")
    try:
        # Obtener también los segmentos
        segments_data = simulator.compute_segment_stats()
        
        # Usar función helper
        simulation_id = save_simulation_to_neon(
            json_file=json_file,
            segments_data=segments_data
        )
        
        print(f"✓ JSON guardado en base de datos con ID: {simulation_id}")
        
        # Limpiar archivo temporal
        if os.path.exists(json_file):
            os.remove(json_file)
            print(f"✓ Archivo temporal eliminado")
        
    except Exception as e:
        print(f"✗ Error: {e}")


def menu_principal():
    """Menú interactivo para ejecutar ejemplos"""
    
    while True:
        print("\n" + "="*80)
        print("EJEMPLOS DE USO - SIMULADOR CON NEON")
        print("="*80)
        print("\n1. Ejemplo básico: Guardar una simulación")
        print("2. Ejemplo batch: Guardar múltiples simulaciones")
        print("3. Ejemplo consulta: Ver datos guardados")
        print("4. Ejemplo desde JSON: Guardar archivo JSON existente")
        print("5. Ejecutar todos los ejemplos")
        print("0. Salir")
        print()
        
        opcion = input("Selecciona una opción: ").strip()
        
        if opcion == "1":
            ejemplo_basico()
        elif opcion == "2":
            ejemplo_batch()
        elif opcion == "3":
            ejemplo_consulta()
        elif opcion == "4":
            ejemplo_desde_json()
        elif opcion == "5":
            print("\nEjecutando todos los ejemplos...\n")
            ejemplo_basico()
            input("\nPresiona Enter para continuar...")
            ejemplo_batch()
            input("\nPresiona Enter para continuar...")
            ejemplo_consulta()
            input("\nPresiona Enter para continuar...")
            ejemplo_desde_json()
        elif opcion == "0":
            print("\n¡Hasta luego!")
            break
        else:
            print("\n✗ Opción no válida")


if __name__ == "__main__":
    # Verificar que existe configuración
    if not os.path.exists('.env'):
        print("⚠️  ADVERTENCIA: No se encontró archivo .env")
        print("   Copia .env.example a .env y configura tu DATABASE_URL")
        print()
        continuar = input("¿Deseas continuar de todas formas? (s/n): ").strip().lower()
        if continuar != 's':
            print("Operación cancelada")
            exit(0)
    
    menu_principal()
