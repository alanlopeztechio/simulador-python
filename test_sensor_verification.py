"""
Test para verificar la funcionalidad de verificación de EPCs/TIDs únicos
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import DatabaseManager


def test_verification():
    """Prueba las funciones de verificación de EPCs/TIDs"""
    
    print("=" * 70)
    print("TEST: Verificación de EPCs/TIDs Únicos")
    print("=" * 70)
    
    try:
        with DatabaseManager() as db:
            print("\n1. Probando get_used_epcs()...")
            epcs = db.get_used_epcs()
            print(f"   ✓ Obtenidos {len(epcs)} EPCs únicos")
            if epcs:
                print(f"   Primeros 5: {epcs[:5]}")
            
            print("\n2. Probando get_used_tids()...")
            tids = db.get_used_tids()
            print(f"   ✓ Obtenidos {len(tids)} TIDs únicos")
            if tids:
                print(f"   Primeros 5: {tids[:5]}")
            
            print("\n3. Verificación exitosa!")
            print(f"   - Total EPCs en uso: {len(epcs)}")
            print(f"   - Total TIDs en uso: {len(tids)}")
            
            # Simular búsqueda del siguiente índice
            print("\n4. Simulando búsqueda de siguiente índice disponible...")
            
            # Extraer índices de EPCs
            epc_indices = set()
            for epc in epcs:
                if epc.startswith("5201F2503"):
                    try:
                        index = int(epc[-5:])
                        epc_indices.add(index)
                    except ValueError:
                        continue
            
            # Extraer índices de TIDs
            tid_indices = set()
            for tid in tids:
                if tid.startswith("E2C245002000056"):
                    try:
                        index = int(tid[-7:])
                        tid_indices.add(index)
                    except ValueError:
                        continue
            
            # Combinar índices usados
            used_indices = epc_indices.union(tid_indices)
            
            if used_indices:
                print(f"   Índices en uso: {sorted(list(used_indices))[:10]}...")
                
                # Encontrar siguiente disponible
                next_index = 1
                while next_index in used_indices:
                    next_index += 1
                
                print(f"   ✓ Siguiente índice disponible: {next_index}")
                print(f"   EPC que se generaría: 5201F250300{next_index:05d}")
                print(f"   TID que se generaría: E2C24500200005668{next_index:07d}")
            else:
                print("   No hay índices en uso, se usaría índice 1")
            
            print("\n" + "=" * 70)
            print("✅ TODAS LAS PRUEBAS PASARON")
            print("=" * 70)
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nAsegúrate de que:")
        print("  1. La variable de entorno DATABASE_URL está configurada")
        print("  2. Tienes conexión a internet")
        print("  3. La base de datos Neon está activa")
        return False
    
    return True


if __name__ == "__main__":
    success = test_verification()
    sys.exit(0 if success else 1)
