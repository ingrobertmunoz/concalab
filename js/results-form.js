import { db, collection, addDoc, serverTimestamp, doc, getDoc, auth, signInWithEmailAndPassword, onAuthStateChanged, signOut } from './firebase-config.js';

// Perfil del laboratorio autenticado (cargado desde Firestore)
let perfilLab = null;

document.addEventListener('DOMContentLoaded', async function () {

    const loginSection = document.getElementById('login-section');
    const resultsForm  = document.getElementById('results-form');
    const userBar      = document.getElementById('user-bar');
    const userEmailSpan = document.getElementById('user-email');
    const loginBtn     = document.getElementById('login-btn');
    const logoutBtn    = document.getElementById('logout-btn');
    const loginError   = document.getElementById('login-error');

    // ── Auth state ────────────────────────────────────────────────────────────
    onAuthStateChanged(auth, async (user) => {
        if (user) {
            perfilLab = await cargarPerfilLab(user.uid);

            loginSection.style.display = 'none';
            resultsForm.style.display  = 'block';
            userBar.style.display      = 'flex';

            if (perfilLab) {
                // Mostrar nombre real del lab en la barra de usuario
                userEmailSpan.textContent = `${perfilLab.nombre} (${perfilLab.cod_anonimo})`;

                // Pre-llenar campos bloqueados
                mostrarInfoLab(perfilLab);
            } else {
                // Lab no encontrado en Firestore (cuenta sin perfil)
                userEmailSpan.textContent = user.email;
                mostrarAdvertenciaPerfilAusente();
            }

            // Pre-llenar correo de contacto
            const emailInput = document.getElementById('contact-email');
            if (emailInput && !emailInput.value) {
                emailInput.value = perfilLab?.correo || user.email;
            }

            generateAnalytesTable('chem');
            generateAnalytesTable('uro');
        } else {
            perfilLab = null;
            loginSection.style.display = 'block';
            resultsForm.style.display  = 'none';
            userBar.style.display      = 'none';
        }
    });

    // ── Login ─────────────────────────────────────────────────────────────────
    loginBtn.addEventListener('click', async () => {
        const email    = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;

        if (!email || !password) {
            mostrarError(loginError, 'Por favor ingrese correo y contraseña.');
            return;
        }

        loginBtn.disabled    = true;
        loginBtn.textContent = 'Verificando...';
        loginError.style.display = 'none';

        try {
            await signInWithEmailAndPassword(auth, email, password);
        } catch (error) {
            const msgs = {
                'auth/user-not-found':    'Correo o contraseña incorrectos.',
                'auth/wrong-password':    'Correo o contraseña incorrectos.',
                'auth/invalid-credential':'Correo o contraseña incorrectos.',
                'auth/too-many-requests': 'Demasiados intentos. Intente más tarde.',
            };
            mostrarError(loginError, msgs[error.code] || 'Error al iniciar sesión. Intente de nuevo.');
        } finally {
            loginBtn.disabled    = false;
            loginBtn.textContent = 'Iniciar Sesión';
        }
    });

    document.getElementById('login-password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loginBtn.click();
    });

    // ── Logout ────────────────────────────────────────────────────────────────
    logoutBtn.addEventListener('click', async () => {
        await signOut(auth);
        location.reload();
    });

    // ── Submit ────────────────────────────────────────────────────────────────
    document.getElementById('results-form').addEventListener('submit', handleFormSubmit);
});

// ── Carga perfil del lab desde Firestore ──────────────────────────────────────
async function cargarPerfilLab(uid) {
    try {
        const snap = await getDoc(doc(db, 'laboratorios', uid));
        if (snap.exists()) {
            return snap.data();
        }
        console.warn('Perfil de laboratorio no encontrado en Firestore para uid:', uid);
        return null;
    } catch (error) {
        console.error('Error cargando perfil del laboratorio:', error);
        return null;
    }
}

// ── Muestra el nombre y código del lab en el formulario (solo lectura) ─────────
function mostrarInfoLab(perfil) {
    const labSelector = document.getElementById('lab-selector');

    // Reemplazar el <select> por un campo de solo lectura
    const wrapper = labSelector.closest('.form-group');
    wrapper.innerHTML = `
        <label class="form-label">Laboratorio Participante</label>
        <div style="
            padding: 0.75rem 1rem;
            background: var(--bg-light);
            border: 2px solid var(--border-color);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        ">
            <span style="font-weight: 600; color: var(--primary-color);">${perfil.nombre}</span>
            <span style="
                background: var(--primary-color);
                color: white;
                padding: 0.2rem 0.6rem;
                border-radius: 4px;
                font-size: 0.85rem;
                font-weight: 700;
                letter-spacing: 0.05em;
            ">${perfil.cod_anonimo}</span>
        </div>
        <input type="hidden" id="lab-nombre" value="${perfil.nombre}">
        <input type="hidden" id="lab-cod-anonimo" value="${perfil.cod_anonimo}">
    `;
}

function mostrarAdvertenciaPerfilAusente() {
    const labSelector = document.getElementById('lab-selector');
    const wrapper = labSelector.closest('.form-group');
    wrapper.innerHTML = `
        <label class="form-label">Laboratorio Participante</label>
        <div style="padding: 0.75rem; background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; color: #856404;">
            ⚠ Su cuenta no tiene un perfil registrado. Contacte a CONCALAB-UASD.
        </div>
    `;
}

function mostrarError(el, msg) {
    el.textContent = msg;
    el.style.display = 'block';
}

// ── Genera las tablas de analitos ─────────────────────────────────────────────
function generateAnalytesTable(type) {
    const config = {
        chem: {
            tableId: '#analytes-table-chem',
            analytes: [
                "Glucosa", "Ácido Úrico", "Colesterol", "Colesterol HDL", "Triglicéridos",
                "Urea", "Creatinina", "Proteínas Total", "Albúmina", "Bilirrubina Total",
                "Bilirrubina Directa", "Amilasa", "Lipasa", "Fosfatasa Alcalina (ALP)",
                "AST (TGO)", "ALT (TGP)", "Gamma GGT", "LDH", "CK-TOTAL",
                "Calcio", "Fósforo", "Cloruro", "Sodio", "Potasio", "Magnesio", "Hierro"
            ],
            inputType: 'number',
        },
        uro: {
            tableId: '#analytes-table-uro',
            analytes: ["Proteínas", "Glucosa", "Cuerpos Cetónicos", "Bilirrubina", "Nitritos"],
            inputType: 'text',
        },
    };

    const { tableId, analytes, inputType } = config[type];
    const tbody = document.querySelector(`${tableId} tbody`);
    if (!tbody) return;

    analytes.forEach(analyte => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td style="font-weight:600;">${analyte}</td>
            <td><input type="text"   class="form-control instrument-input-${type}" placeholder="Ej: Cobas 6000"></td>
            <td><input type="text"   class="form-control method-input-${type}"     placeholder="Ej: Enzimático"></td>
            <td><input type="${inputType}" class="form-control result-input-${type}" ${inputType === 'number' ? 'step="any"' : ''}></td>
            <td><input type="text"   class="form-control unit-input-${type}"       placeholder="Ej: mg/dL"></td>
        `;
        tbody.appendChild(row);
    });
}

// Copia el valor del primer campo a todos los vacíos de la misma clase
window.copyDown = function (className) {
    const inputs = document.querySelectorAll(`.${className}`);
    if (!inputs.length) return;
    const firstValue = inputs[0].value;
    inputs.forEach(input => { if (!input.value) input.value = firstValue; });
};

// ── Envío del formulario ──────────────────────────────────────────────────────
async function handleFormSubmit(e) {
    e.preventDefault();

    if (!perfilLab) {
        alert('No se pudo identificar su laboratorio. Por favor cierre sesión y vuelva a ingresar.');
        return;
    }

    const submitBtn  = document.getElementById('submit-btn');
    const loadingMsg = document.getElementById('loading-message');
    const successMsg = document.getElementById('success-message');

    submitBtn.disabled = true;
    loadingMsg.style.display = 'block';

    try {
        const roundCode  = document.getElementById('round-code').value.toUpperCase();
        const reportDate = document.getElementById('report-date').value;
        const email      = document.getElementById('contact-email').value;
        const comments   = document.getElementById('comments').value;

        if (!roundCode || !/^EA-\d{3}-\d{4}$/.test(roundCode)) {
            throw new Error('El código de ensayo debe tener el formato EA-001-2025.');
        }
        if (!reportDate) {
            throw new Error('La fecha del reporte es obligatoria.');
        }

        const resultsChem = scrapeTable('#analytes-table-chem tbody', 'chem');
        const resultsUro  = scrapeTable('#analytes-table-uro tbody', 'uro');
        const allResults  = [...resultsChem, ...resultsUro];

        if (!allResults.length) {
            throw new Error('No has ingresado ningún resultado en las tablas.');
        }

        // ── Enviar correo de confirmación (EmailJS) ───────────────────────────
        if (email && window.emailjs) {
            loadingMsg.textContent = '⏳ Enviando confirmación al correo...';
            const resumen = construirResumen(resultsChem, resultsUro);
            try {
                await window.emailjs.send('service_80iwfhm', 'template_53vkh45', {
                    name:             perfilLab.nombre,
                    email:            email,
                    lab_name:         perfilLab.nombre,
                    round_code:       roundCode,
                    report_date:      reportDate,
                    entered_email:    email,
                    results_summary:  resumen,
                });
            } catch (emailErr) {
                console.warn('Correo no enviado (no bloquea el guardado):', emailErr);
            }
        }

        // ── Guardar en Firestore ──────────────────────────────────────────────
        loadingMsg.textContent = '⏳ Guardando datos en la base de datos...';

        await Promise.race([
            addDoc(collection(db, 'resultados_generales'), {
                // Identificación anónima (la que va a los informes)
                cod_anonimo:    perfilLab.cod_anonimo,
                cod_interno:    perfilLab.cod_interno,
                // Datos internos (solo visibles para CONCALAB)
                laboratorio:    perfilLab.nombre,
                uid_lab:        auth.currentUser.uid,
                // Datos del reporte
                codigo_ensayo:  roundCode,
                fecha_reporte:  reportDate,
                email_contacto: email,
                comentarios:    comments,
                resultados:     allResults,
                tipos_incluidos: {
                    quimica:     resultsChem.length > 0,
                    uroanalisis: resultsUro.length > 0,
                },
                timestamp:      serverTimestamp(),
            }),
            new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 10000))
        ]);

        loadingMsg.style.display = 'none';
        successMsg.style.display = 'block';
        window.scrollTo(0, 0);

    } catch (error) {
        console.error('Error al enviar:', error);
        loadingMsg.style.display = 'none';
        submitBtn.disabled = false;
        alert('Error al enviar: ' + error.message);
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function scrapeTable(tbodySelector, suffix) {
    const results = [];
    document.querySelectorAll(`${tbodySelector} tr`).forEach(row => {
        const analyte    = row.cells[0].textContent.trim();
        const instrument = row.querySelector(`.instrument-input-${suffix}`)?.value || '';
        const method     = row.querySelector(`.method-input-${suffix}`)?.value || '';
        const result     = row.querySelector(`.result-input-${suffix}`)?.value || '';
        const unit       = row.querySelector(`.unit-input-${suffix}`)?.value || '';
        if (result || instrument) {
            results.push({
                categoria: suffix === 'chem' ? 'Química Clínica' : 'Uroanálisis',
                analyte, instrument, method, result, unit,
            });
        }
    });
    return results;
}

function construirResumen(chem, uro) {
    const lineas = [];
    if (chem.length) {
        lineas.push('--- QUÍMICA CLÍNICA ---');
        chem.forEach(r => lineas.push(`• ${r.analyte}: ${r.result} ${r.unit} | Método: ${r.method || 'N/A'} | Instrumento: ${r.instrument || 'N/A'}`));
    }
    if (uro.length) {
        lineas.push('', '--- UROANÁLISIS ---');
        uro.forEach(r => lineas.push(`• ${r.analyte}: ${r.result} ${r.unit} | Método: ${r.method || 'N/A'} | Instrumento: ${r.instrument || 'N/A'}`));
    }
    lineas.push('', `Total: ${chem.length + uro.length} analitos reportados.`);
    return lineas.join('\n');
}
