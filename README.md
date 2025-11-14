# CONCALAB-UASD - Sitio Web Oficial

Sitio web oficial de **CONCALAB-UASD** (Control de Calidad de Laboratorios - Universidad Autónoma de Santo Domingo), institución que realiza pruebas interlaboratoriales y ensayos de aptitud para laboratorios clínicos en República Dominicana.

## 📋 Descripción

Este sitio web presenta los servicios, información educativa y recursos de CONCALAB-UASD para laboratorios clínicos que participan en programas de evaluación externa de calidad.

## 🏗️ Estructura del Proyecto

```
CONCALAB/
├── index.html                          # Página principal
├── contacto.html                       # Página de contacto
├── servicios.html                      # Servicios ofrecidos
├── portal-educativo.html               # Portal educativo
├── miembros.html                       # Laboratorios miembros
├── publicaciones/
│   ├── protocolos.html                # Protocolos de ensayos
│   └── informes.html                  # Informes y reportes
├── sobre-nosotros/
│   ├── quienes-somos.html            # Misión, visión y valores
│   ├── historia.html                 # Historia institucional
│   └── marco-legal.html              # Marco legal y certificaciones
├── css/
│   ├── main.css                       # Estilos principales
│   ├── responsive.css                 # Estilos responsive
│   └── animations.css                 # Animaciones y efectos
├── js/
│   ├── main.js                        # JavaScript principal
│   ├── scroll-reveal.js               # Efectos de scroll
│   └── search.js                      # Buscador del sitio
├── assets/
│   ├── images/                        # Imágenes
│   ├── icons/                         # Iconos
│   └── documents/                     # Documentos PDF
├── firebase.json                       # Configuración de Firebase
└── .firebaserc                        # Proyecto de Firebase
```

## ✨ Características

- ✅ **Diseño Responsive**: Adaptado para dispositivos móviles, tablets y escritorio
- ✅ **Scroll Reveal**: Animaciones dinámicas al desplazarse por la página
- ✅ **Buscador Global**: Búsqueda disponible en todas las páginas
- ✅ **Navegación Intuitiva**: Menú estructurado con dropdowns
- ✅ **Optimizado para SEO**: Meta tags y estructura semántica
- ✅ **Firebase Hosting**: Configurado para despliegue en Firebase

## 🚀 Despliegue en Firebase

### Prerrequisitos

1. Tener Node.js instalado
2. Tener una cuenta de Firebase
3. Instalar Firebase CLI:

```bash
npm install -g firebase-tools
```

### Pasos para Desplegar

1. **Iniciar sesión en Firebase**:
```bash
firebase login
```

2. **Crear un proyecto en Firebase Console**:
   - Ve a [console.firebase.google.com](https://console.firebase.google.com)
   - Crea un nuevo proyecto llamado "concalab-uasd" (o el nombre que prefieras)
   - Copia el ID del proyecto

3. **Actualizar la configuración**:
   - Edita `.firebaserc` y reemplaza `"concalab-uasd"` con tu ID de proyecto

4. **Inicializar Firebase (opcional, solo si no está configurado)**:
```bash
firebase init hosting
```

5. **Desplegar el sitio**:
```bash
firebase deploy
```

6. **Acceder al sitio**:
   - Tu sitio estará disponible en: `https://tu-proyecto.web.app`
   - O en: `https://tu-proyecto.firebaseapp.com`

### Comandos Útiles

- **Ver el sitio localmente**:
```bash
firebase serve
```

- **Solo desplegar hosting**:
```bash
firebase deploy --only hosting
```

- **Ver logs de Firebase**:
```bash
firebase hosting:channel:list
```

## 🎨 Personalización

### Colores Institucionales

Los colores se definen en `css/main.css`:

```css
:root {
    --primary-color: #003f87;    /* Azul UASD */
    --secondary-color: #fdb913;  /* Dorado UASD */
    --accent-color: #0056b3;
    /* ... más variables ... */
}
```

### Imágenes y Logos

- Reemplaza `assets/images/logo-concalab.png` con el logo oficial
- Agrega imágenes institucionales en `assets/images/`
- Actualiza el favicon en `assets/icons/favicon.ico`

### Contenido

- Los textos se encuentran directamente en los archivos HTML
- Los protocolos PDF se colocan en `assets/documents/`
- Los informes y análisis se gestionan en la sección de blog

## 📱 Navegación del Sitio

- **Inicio**: Información general y servicios destacados
- **Publicaciones**:
  - Protocolos: Documentos oficiales para ensayos de aptitud
  - Informes: Reportes y análisis estadísticos
- **Portal Educativo**: Recursos educativos sobre control de calidad
- **Servicios**: Descripción detallada de servicios ofrecidos
- **Miembros**: Laboratorios participantes en la red
- **Sobre Nosotros**:
  - Quiénes Somos: Misión, visión y valores
  - Historia: Cronología institucional
  - Marco Legal: Resoluciones y certificaciones
- **Contacto**: Formulario y datos de contacto

## 🔍 Funcionalidad de Búsqueda

El buscador indexa automáticamente:
- Títulos de sección
- Párrafos de contenido
- Tarjetas (cards)
- Elementos destacados

Los resultados se muestran en tiempo real con resaltado de términos encontrados.

## 📊 Integración Futura - Dashboard Dash

La página de Informes está preparada para integrar una aplicación Dash con:
- Gráficos interactivos de Plotly
- Análisis estadístico en tiempo real
- Filtros dinámicos por fecha y laboratorio
- Exportación de datos

## 🛠️ Mantenimiento

### Actualizar Protocolos

1. Colocar archivos PDF en `assets/documents/`
2. Actualizar `publicaciones/protocolos.html` con la nueva entrada
3. Desplegar cambios: `firebase deploy`

### Agregar Nuevo Laboratorio Miembro

1. Editar `miembros.html`
2. Añadir un nuevo `<div class="member-card">` con los datos
3. Desplegar cambios

### Modificar Contenido Educativo

1. Editar `portal-educativo.html`
2. Añadir/modificar secciones en los acordeones
3. Desplegar cambios

## 📧 Soporte

Para consultas sobre el sitio web o CONCALAB-UASD:
- **Email**: info@concalab.uasd.edu.do
- **Teléfono**: +1 (809) XXX-XXXX
- **Ubicación**: Santo Domingo, República Dominicana

## 📝 Licencia

© 2024 CONCALAB-UASD. Todos los derechos reservados.
Universidad Autónoma de Santo Domingo (UASD)

---

**Desarrollado para**: CONCALAB-UASD  
**Última actualización**: Noviembre 2024

