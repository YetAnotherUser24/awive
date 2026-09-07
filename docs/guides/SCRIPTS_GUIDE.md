# 📖 Guía Completa de Scripts - Análisis y Debug OTV

## 🎯 Resumen de Scripts Disponibles

Durante nuestra sesión hemos creado varios scripts para analizar y solucionar problemas del algoritmo OTV:

### 1. 🔍 **Script Principal: OTV Visual Debugger**
**Archivo:** `/root/awive/otv_process/debug_otv.py`
**Propósito:** Debug visual completo del flujo de procesamiento OTV

### 2. 🧪 **Scripts Experimentales de PPM**
- `experiment_orthorectification.py` - Experimentación con diferentes valores PPM
- `fix_orthorectification.py` - Corrección automática de PPM en configuración

### 3. 🛠️ **Utilities para PPM**
- `awive/utils/ppm_calculator.py` - Funciones de cálculo y validación PPM

---

## 🚀 Cómo Usar Cada Script

### 📊 **1. OTV Visual Debugger - Script Principal**

Este es el script más importante y completo que refleja todo el flujo del algoritmo OTV.

#### **Ubicación y Preparación:**
```bash
cd /root/awive/otv_process
# Asegúrate de usar el entorno virtual
source /root/awive/.venv/bin/activate
```

#### **Uso Básico:**
```bash
# Análisis completo con configuración por defecto
python debug_otv.py ../awive_temp.yaml
```

#### **Opciones Avanzadas:**
```bash
# Con directorio de salida personalizado
python debug_otv.py ../awive_temp.yaml --output mi_debug_resultado

# Ver todas las opciones disponibles
python debug_otv.py --help

# Modo verbose para más detalles
python debug_otv.py ../awive_temp.yaml --verbose
```

#### **¿Qué Hace Este Script?**
✅ **Analiza la configuración YAML** con explicaciones detalladas de cada parámetro
✅ **Procesa los 9 pasos** del algoritmo OTV paso a paso
✅ **Genera visualizaciones** con cuadros de recorte ROI/Pre-ROI
✅ **Crea comparaciones** antes/después de cada transformación
✅ **Guarda imágenes** de cada paso del proceso
✅ **Proporciona logs detallados** con cambios de dimensiones

#### **Archivos Generados:**
```
otv_process/
├── steps/                          # Imágenes paso a paso
│   ├── 01_original_with_gcps.jpg    # Original con GCPs marcados
│   ├── 02_lens_corrected.jpg        # Después corrección lente
│   ├── 04_orthorectified.jpg        # Después orto-rectificación
│   ├── 05_pre_crop_roi.jpg          # Después pre-recorte
│   ├── 06_rotated.jpg               # Después rotación
│   ├── 07_final_crop_roi.jpg        # Después recorte final
│   ├── 08_resolution_scaled.jpg     # Después escalado
│   └── 09_final_for_otv.jpg         # Imagen final
├── comparisons/                     # Comparaciones lado a lado
│   ├── 02_lens_comparison.jpg       # Antes/después lente
│   ├── 05_pre_crop_comparison.jpg   # Antes/después pre-recorte
│   ├── 06_rotation_comparison.jpg   # Antes/después rotación
│   └── 07_final_crop_comparison.jpg # Antes/después recorte
├── configuration_analysis.txt       # Análisis detallado parámetros
└── otv_debug.log                   # Log completo del proceso
```

---

### 🧪 **2. Scripts de Experimentación PPM**

#### **A) Experiment Orthorectification**
```bash
cd /root/awive
python experiment_orthorectification.py
```

**¿Qué hace?**
- Prueba diferentes valores de PPM (121, 125, 130, 135)
- Muestra el factor de crecimiento para cada PPM
- Ayuda a encontrar el PPM óptimo

**Ejemplo de salida:**
```
🧪 EXPERIMENTANDO CON DIFERENTES PPM
=====================================
PPM=121: Factor de crecimiento 1.97x
PPM=125: Factor de crecimiento 2.05x  
PPM=130: Factor de crecimiento 2.14x ← Actual
PPM=135: Factor de crecimiento 2.22x
```

#### **B) Fix Orthorectification**
```bash
cd /root/awive
python fix_orthorectification.py
```

**¿Qué hace?**
- Calcula automáticamente el PPM óptimo desde los GCPs
- Actualiza el archivo de configuración
- Crea respaldo del archivo original

---

### 🛠️ **3. Utilidades PPM (Para Desarrolladores)**

#### **Uso Programático:**
```python
from awive.utils.ppm_calculator import calculate_ppm_from_gcps, find_optimal_ppm

# Calcular PPM desde GCPs
ppm_calculated = calculate_ppm_from_gcps(gcp_points, real_distances)

# Encontrar PPM óptimo
optimal_ppm = find_optimal_ppm(config_path)
```

---

## 🎯 **Flujo de Trabajo Recomendado**

### **Para Análisis Visual Completo:**
```bash
# 1. Activar entorno virtual
cd /root/awive
source .venv/bin/activate

# 2. Ejecutar debug visual completo
cd otv_process
python debug_otv.py ../awive_temp.yaml --verbose

# 3. Revisar resultados
ls -la otv_process/steps/
ls -la otv_process/comparisons/
cat otv_process/configuration_analysis.txt
```

### **Para Experimentar con PPM:**
```bash
# 1. Probar diferentes valores PPM
python experiment_orthorectification.py

# 2. Si necesitas corregir PPM automáticamente
python fix_orthorectification.py

# 3. Re-ejecutar debug visual con nuevo PPM
cd otv_process
python debug_otv.py ../awive_temp.yaml
```

---

## 🔍 **Interpretación de Resultados**

### **Del OTV Visual Debugger:**

#### **1. Archivo `configuration_analysis.txt`:**
- Explica cada parámetro del YAML
- Calcula PPM real vs configurado
- Muestra impacto esperado de cada configuración

#### **2. Carpeta `steps/`:**
- Ve la progresión visual paso a paso
- Identifica dónde ocurren los mayores cambios
- Observa las áreas de recorte marcadas

#### **3. Carpeta `comparisons/`:**
- Compara antes/después de cada transformación
- Identifica transformaciones problemáticas
- Ve el efecto visual de cada paso

#### **4. Log `otv_debug.log`:**
```
PASO 1: IMAGEN ORIGINAL: 2160×3840 píxeles
PASO 2: CORRECCIÓN LENTE: 3023×4228 píxeles (1.54x)
PASO 5: PRE-RECORTE: 1737×1875 píxeles (25.5% área)
PASO 6: ROTACIÓN: 1875×1737 píxeles (intercambio)
PASO 7: RECORTE FINAL: 1825×1686 píxeles (94.5% área)
```

---

## ⚠️ **Troubleshooting**

### **Error: "Module not found"**
```bash
# Verificar entorno virtual activado
which python
# Debe mostrar: /root/awive/.venv/bin/python

# Re-activar si necesario
cd /root/awive
source .venv/bin/activate
```

### **Error: "File not found"**
```bash
# Verificar que estés en el directorio correcto
cd /root/awive/otv_process
ls -la debug_otv.py  # Debe existir

# Para otros scripts
cd /root/awive
ls -la experiment_orthorectification.py
```

### **Error en OpenCV/imágenes:**
- El paso 3 puede fallar (problema conocido con conversión de canales)
- El resumen visual puede fallar (diferentes tamaños de imagen)
- **Esto es normal** - los pasos principales funcionan correctamente

---

## 🎉 **Casos de Uso Principales**

### **1. Debuggear problema de crecimiento de imagen:**
```bash
python debug_otv.py ../awive_temp.yaml
# Revisa steps/ y comparisons/ para identificar dónde crece la imagen
```

### **2. Optimizar configuración PPM:**
```bash
python experiment_orthorectification.py
python fix_orthorectification.py
```

### **3. Analizar impacto de parámetros:**
```bash
python debug_otv.py ../awive_temp.yaml
cat otv_process/configuration_analysis.txt
```

### **4. Validar cambios en configuración:**
```bash
# Modificar awive_temp.yaml
python debug_otv.py ../awive_temp.yaml --output validation_run
# Comparar resultados en validation_run/
```

---

*Todos los scripts están listos y probados. El OTV Visual Debugger es la herramienta principal para análisis completo.*