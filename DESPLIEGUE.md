# Guía Rápida de Despliegue - CONCALAB-UASD

## 🚀 Despliegue en Firebase Hosting

### Paso 1: Instalación de Firebase CLI

```bash
npm install -g firebase-tools
```

### Paso 2: Iniciar Sesión

```bash
firebase login
```

### Paso 3: Crear Proyecto en Firebase

1. Visita: https://console.firebase.google.com
2. Haz clic en "Agregar proyecto"
3. Nombre sugerido: `concalab-uasd`
4. Sigue los pasos de configuración
5. Anota el **Project ID**

### Paso 4: Configurar el Proyecto

Edita el archivo `.firebaserc` y reemplaza con tu Project ID:

```json
{
  "projects": {
    "default": "tu-project-id-aqui"
  }
}
```

### Paso 5: Desplegar

```bash
firebase deploy
```

### Paso 6: Verificar

Tu sitio estará disponible en:
- `https://tu-project-id.web.app`
- `https://tu-project-id.firebaseapp.com`

---

## 🖥️ Servidor Local (Pruebas)

Para probar el sitio localmente antes de desplegar:

```bash
firebase serve
```

El sitio estará disponible en: `http://localhost:5000`

---

## 📋 Comandos Útiles

### Desplegar solo hosting
```bash
firebase deploy --only hosting
```

### Ver canales de hosting
```bash
firebase hosting:channel:list
```

### Crear canal de preview
```bash
firebase hosting:channel:deploy preview-nombre
```

### Eliminar un deployment
```bash
firebase hosting:channel:delete canal-nombre
```

---

## 🔧 Configuración Personalizada

### Dominio Personalizado

1. Ve a Firebase Console > Hosting
2. Haz clic en "Agregar dominio personalizado"
3. Sigue las instrucciones para verificar tu dominio
4. Configura los registros DNS según las indicaciones

Ejemplo para `www.concalab.uasd.edu.do`:
```
Tipo: CNAME
Nombre: www
Valor: [proporcionado por Firebase]
```

### Variables de Entorno (Futuro)

Si necesitas agregar variables de entorno, crea un archivo `.env`:

```env
FIREBASE_API_KEY=tu-api-key
FIREBASE_PROJECT_ID=tu-project-id
```

---

## ⚠️ Antes de Desplegar

### Checklist Pre-Despliegue

- [ ] Verificar que todos los enlaces funcionan correctamente
- [ ] Probar el sitio en diferentes navegadores (Chrome, Firefox, Safari, Edge)
- [ ] Probar la responsividad en móviles y tablets
- [ ] Verificar que las imágenes se cargan correctamente
- [ ] Revisar que el buscador funcione en todas las páginas
- [ ] Probar el formulario de contacto
- [ ] Verificar metadatos SEO en todas las páginas
- [ ] Reemplazar datos de contacto de ejemplo (teléfonos, emails)
- [ ] Actualizar logos y favicons oficiales
- [ ] Revisar ortografía y gramática

### Archivos a Personalizar

1. **Contacto y datos**:
   - Actualizar teléfonos en: `contacto.html`, footers de todas las páginas
   - Actualizar correos electrónicos
   - Actualizar dirección física completa

2. **Imágenes**:
   - `assets/images/logo-concalab.png` - Logo oficial
   - `assets/icons/favicon.ico` - Favicon
   - Agregar fotos institucionales

3. **Documentos**:
   - Colocar PDFs reales de protocolos en `assets/documents/`

4. **Mapa**:
   - Actualizar iframe de Google Maps en `contacto.html` con coordenadas reales

---

## 📱 Pruebas Post-Despliegue

Después de desplegar, verificar:

1. **Velocidad de Carga**:
   - Usar: https://pagespeed.web.dev/
   - Objetivo: Score > 90

2. **Compatibilidad Móvil**:
   - Usar: https://search.google.com/test/mobile-friendly

3. **SEO**:
   - Verificar en Google Search Console
   - Enviar sitemap

4. **Accesibilidad**:
   - Usar: https://wave.webaim.org/

---

## 🔄 Actualizaciones Futuras

### Para actualizar contenido:

1. Editar los archivos HTML localmente
2. Probar con `firebase serve`
3. Desplegar con `firebase deploy`

### Para agregar páginas nuevas:

1. Crear el archivo HTML siguiendo la estructura existente
2. Actualizar la navegación en todas las páginas
3. Actualizar el `sitemap.xml` (si se usa)
4. Desplegar

---

## 🆘 Solución de Problemas

### Error: "No Firebase project"
```bash
firebase use --add
```
Luego selecciona tu proyecto de la lista

### Error: "Permission denied"
```bash
firebase login --reauth
```

### El sitio no se actualiza
- Limpiar caché del navegador
- Esperar 5-10 minutos para propagación
- Verificar que el deployment fue exitoso:
  ```bash
  firebase hosting:channel:list
  ```

### Error 404 en rutas
- Verificar que `firebase.json` tenga la configuración de rewrites
- Verificar que los nombres de archivo coincidan exactamente

---

## 📞 Soporte

Para ayuda adicional:
- **Documentación Firebase**: https://firebase.google.com/docs/hosting
- **Stack Overflow**: https://stackoverflow.com/questions/tagged/firebase-hosting
- **Firebase Support**: https://firebase.google.com/support

---

**Fecha**: Noviembre 2024  
**Versión**: 1.0  
**Mantenido por**: CONCALAB-UASD

