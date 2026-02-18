# Guía Metrológica para Ensayos de Aptitud (CONCALAB)

## 1. ¿Es suficiente reportar solo la magnitud?
**Definitivamente NO.** En metrología clínica, el "valor" numérico carece de sentido sin su contexto (trazabilidad). Para que un resultado sea comparable y útil, debe ir acompañado de:

1.  **Unidades**: Fundamental. Un resultado de glucosa de `100` puede ser normal en `mg/dL` pero mortal en `mmol/L` (donde lo normal es ~5.5).
2.  **Método Analítico**: El principio químico (ej. *Hexoquinasa* vs *Glucosa Oxidasa*) puede tener sesgos inherentes. Comparar resultados de métodos distintos sin separarlos puede generar falsos rechazos.
3.  **Instrumento/Plataforma**: Los equipos tienen diferentes "Efectos Matriz". Lo ideal es comparar "Pares" (Peer Group) que usen la misma tecnología.
4.  **Reactivo**: A veces el reactivo es de un fabricante distinto al del equipo.
5.  **Temperatura**: En enzimas (AST, ALT), la temperatura de reacción (25°C vs 37°C) cambia radicalmente el resultado.

### Recomendación para CONCALAB
El formulario actual ya captura **Instrumento** y **Método**, lo cual es excelente y esencial. Sin esa información, no podrías calcular un Z-Score justo (no sería justo comparar un método manual antiguo con un analizador robótico de última generación).

---

## 2. El Cálculo del Z-Score

El **Z-Score** (Índice de Desvío) es el estándar de oro en la norma **ISO 17043** para evaluar el desempeño. Mide "cuántas desviaciones estándar se alejó el laboratorio del promedio del grupo".

### La Fórmula
$$ Z = \frac{x - X}{\sigma} $$

Donde:
*   **$x$ (Tu Resultado)**: El valor reportado por el laboratorio participante.
*   **$X$ (Valor Asignado)**: El "valor verdadero" estimado.
    *   *Opción A (Ideal)*: Valor de referencia de un laboratorio primario.
    *   *Opción B (Común)*: La **Media Robusta** de todos los participantes (se excluyen valores extremos/outliers antes de calcular).
*   **$\sigma$ (Desviación Estándar para la Aptitud)**:
    *   *Opción A*: La desviación estándar real del grupo (CV del grupo).
    *   *Opción B*: Un límite preestablecido por expertos (ej. "Aceptamos hasta un 10% de error").

### Interpretación del Z-Score
| Valor Z | Interpretación | Color Semáforo | Acción |
| :--- | :--- | :--- | :--- |
| **\|Z\| ≤ 2.0** | **Satisfactorio** | 🟢 Verde | Resultado Aceptable. Mantener desempeño. |
| **2.0 < \|Z\| < 3.0** | **Cuestionable** | 🟡 Amarillo | Señal de Alerta y Vigilancia. Revisar controles internos. |
| **\|Z\| ≥ 3.0** | **No Satisfactorio** | 🔴 Rojo | **No Conformidad**. Requiere Acción Correctiva inmediata. |

---

## 3. Ejemplo Práctico

Imagina un ensayo de **Colesterol**:
*   Tu laboratorio reportó: **210 mg/dL** ($x$)
*   La media robusta del grupo fue: **200 mg/dL** ($X$)
*   La desviación estándar del grupo fue: **5 mg/dL** ($\sigma$)

$$ Z = \frac{210 - 200}{5} = \frac{10}{5} = \mathbf{+2.0} $$

**Resultado**: Estás justo en el límite de lo aceptable (Satisfactorio/Alerta). Tu resultado fue más alto que el promedio.

## 4. Próximos Pasos en el Sistema
Actualmente, tu sistema **recolecta** los datos ($x$, instrumento, método).
Para generar los reportes automáticos en el futuro, necesitaremos un script (posiblemente en Python o Cloud Functions) que:
1.  Agrupe los resultados por analito y método.
2.  Calcule la Media ($X$) y la Desviación Estándar ($\sigma$) de ese grupo.
3.  Aplique la fórmula a cada laboratorio.
4.  Guarde ese `z_score` en la base de datos para pintar los gráficos.

---

## 5. ¿Y la Incertidumbre de Medición?

Esta es una pregunta de **nivel avanzado**. La norma **ISO 15189** exige que los laboratorios estimen su incertidumbre, pero... **¿Deben reportarla en un Ensayo de Aptitud?**

### La Práctica Común (ISO 17043)
En la mayoría de programas de Química Clínica rutinaria, **NO se solicita reportar la incertidumbre** por cada resultado individual.

**¿Por qué?**
1.  **Complejidad**: Pedirla obligatoriamente puede confundir a laboratorios pequeños o en desarrollo, reduciendo la participación.
2.  **Propósito del Z-Score**: El propio Z-Score ya es una medida estandarizada de cuánto se desvía el laboratorio. Si el Z-Score es aceptable (< 2.0), se asume que el error total (Veracidad + Precisión) está bajo control.
3.  **Evaluación**: La incertidumbre del participante ($u_x$) se compara con la incertidumbre del valor asignado ($u_X$) en análisis muy específicos (ej. Calibración), pero en esquemas cualitativos/cuantitativos masivos suele omitirse para simplificar la logística.

### Conclusión para CONCALAB
Para esta etapa inicial, **no recomendamos llenar el formulario** con un campo extra de incertidumbre (`± U`).
*   **Ideal**: Que el laboratorio la conozca internamente.
*   **Reporte**: Solo reportar el valor medido ($x$).

Si en el futuro CONCALAB desea acreditarse bajo ISO 17043 como proveedor estricto, se podría añadir un campo opcional: *"Incertidumbre Expandida (k=2)"*, pero por ahora mantendría el formulario limpio para maximizar el uso.
