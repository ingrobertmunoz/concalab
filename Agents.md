# Contexto para Agentes - CONCALAB-UASD

## 🎯 Objetivo del Proyecto
CONCALAB-UASD es el organismo de Control de Calidad de Laboratorios de la Universidad Autónoma de Santo Domingo. El objetivo de este repositorio es mantener el sitio web oficial que sirve como:
1.  **Plataforma Informativa**: Para comunicar servicios, misión y visión.
2.  **Portal Educativo**: Ofrecer recursos de capacitación continua.
3.  **Centro de Transparencia**: Publicar resultados de ensayos de aptitud y estadísticas.

## 🏗 Arquitectura Técnica
- **Tipo**: Sitio web estático (Static Site).
- **Hosting**: GitHub Pages.
- **Tecnologías**: HTML5, CSS3, JavaScript (Vanilla).
- **Estilo**: CSS nativo con variables (Custom Properties) para theming institucional.
- **Datos**: Actualmente estáticos en HTML. Se busca integrar visualizaciones de datos.

## 🚀 Objetivos Actuales (Roadmap)
1.  **Directorio de Laboratorios**: Actualizar la sección de miembros con información real de los laboratorios locales participantes.
2.  **Visualización de Datos (Ensayos de Aptitud)**:
    - Crear gráficos interactivos para cada analito (ej. Glucosa, Colesterol, etc.).
    - Permitir a los laboratorios visualizar su desempeño (Z-Score, comparativas).
    - **Nota Técnica**: Dado que es un sitio estático, se prefiere el uso de librerías JS del lado del cliente como **Plotly.js** o **Chart.js**, leyendo datos de archivos JSON/CSV alojados en el mismo repositorio.

## 📂 Estructura de Datos (Tentativa)
Se espera que los datos de los ensayos residan en una carpeta `data/` o `assets/data/` en formato CSV o JSON.
- **Entidades**: Laboratorios, Analitos, Rondas de participación.

## 🎨 Guía de Estilo
- **Colores**: Usar las variables definidas en `css/main.css` (`--primary-color`, etc.).
- **Diseño**: Mantener la consistencia con el diseño "clean" y académico existente.
