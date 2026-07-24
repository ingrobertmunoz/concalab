import { db, collection, addDoc, serverTimestamp, doc, getDoc, auth, signInWithEmailAndPassword, onAuthStateChanged, signOut } from './firebase-config.js';

// Estado global de la sesión
let perfilLab  = null;
let rondaActiva = null;

document.addEventListener('DOMContentLoaded', async function () {

    const loginSection = document.getElementById('login-section');
    const resultsForm  = document.getElementById('results-form');
    const userBar      = document.getElementById('user-bar');
    const userEmailSpan = document.getElementById('user-email');
    const loginBtn     = document.getElementById('login-btn');
    const logoutBtn    = document.getElementById('logout-btn');
    const loginError   = document.getElementById('login-error');

    // ── Cargar configuración de ronda activa ──────────────────────────────────
    rondaActiva = await cargarRondaActiva();

    // ── Auth state ────────────────────────────────────────────────────────────
    onAuthStateChanged(auth, async (user) => {
        if (user) {
            perfilLab = await cargarPerfilLab(user.uid);

            loginSection.style.display = 'none';
            userBar.style.display      = 'flex';

            if (perfilLab) {
                userEmailSpan.textContent = `${perfilLab.nombre} (${perfilLab.cod_anonimo})`;
            } else {
                userEmailSpan.textContent = user.email;
            }

            await mostrarEstadoFormulario(user);

        } else {
            perfilLab  = null;
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
                'auth/user-not-found':     'Correo o contraseña incorrectos.',
                'auth/wrong-password':     'Correo o contraseña incorrectos.',
                'auth/invalid-credential': 'Correo o contraseña incorrectos.',
                'auth/too-many-requests':  'Demasiados intentos. Intente más tarde.',
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

// ── Determina qué mostrar según el estado del lab y la ronda ─────────────────
async function mostrarEstadoFormulario(user) {
    const resultsForm = document.getElementById('results-form');
    const container   = document.querySelector('.container');

    // 1. Sin perfil en Firestore
    if (!perfilLab) {
        mostrarBanner('error',
            '⚠ Su cuenta no tiene un perfil registrado.',
            'Contacte a CONCALAB-UASD para regularizar su acceso.'
        );
        return;
    }

    // 2. No hay ronda activa habilitada
    if (!rondaActiva || !rondaActiva.habilitado) {
        const codigo = rondaActiva?.codigo || '—';
        const detalle = rondaActiva?.mensaje_cierre
            || `La próxima ronda es <strong>${codigo}</strong>. CONCALAB-UASD le notificará cuando esté disponible.`;
        mostrarBanner('info',
            `El formulario de reporte no está habilitado en este momento.`,
            detalle
        );
        return;
    }

    // 3. Verificar si el lab ya reportó en esta ronda
    const yaReporto = await verificarReporteExistente(user.uid, rondaActiva.codigo);
    if (yaReporto) {
        mostrarBanner('advertencia',
            `Ya enviaste resultados para <strong>${rondaActiva.codigo}</strong>.`,
            'Si necesitas hacer una corrección, contacta a CONCALAB-UASD: <a href="mailto:concalab@uasd.edu.do">concalab@uasd.edu.do</a>'
        );
        return;
    }

    // 4. Todo OK — mostrar formulario
    resultsForm.style.display = 'block';

    const emailInput = document.getElementById('contact-email');
    if (emailInput && !emailInput.value) {
        emailInput.value = perfilLab.correo || user.email;
    }

    mostrarInfoLab(perfilLab);
    mostrarRondaActiva(rondaActiva);
    generateAnalytesTable('chem');
    generateAnalytesTable('uro');
}

// ── Carga la configuración de ronda desde data/config.json ────────────────────
async function cargarRondaActiva() {
    try {
        const res = await fetch('data/config.json');
        const cfg = await res.json();
        return cfg.ronda_activa || null;
    } catch (e) {
        console.error('Error cargando config.json:', e);
        return null;
    }
}

// ── Carga el perfil del lab desde Firestore ───────────────────────────────────
async function cargarPerfilLab(uid) {
    try {
        const snap = await getDoc(doc(db, 'laboratorios', uid));
        return snap.exists() ? snap.data() : null;
    } catch (e) {
        console.error('Error cargando perfil del laboratorio:', e);
        return null;
    }
}

// ── Verifica si el lab ya tiene un reporte en Firestore para esta ronda ───────
async function verificarReporteExistente(uid, codigoEnsayo) {
    try {
        const { getDocs, query, where } = await import("https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js");
        const q = query(
            collection(db, 'resultados_generales'),
            where('uid_lab', '==', uid),
            where('codigo_ensayo', '==', codigoEnsayo)
        );
        const snap = await getDocs(q);
        return !snap.empty;
    } catch (e) {
        console.error('Error verificando reporte existente:', e);
        return false;
    }
}

// ── Banners de estado ─────────────────────────────────────────────────────────
function mostrarBanner(tipo, titulo, mensaje) {
    const colores = {
        error:       { bg: '#f8d7da', border: '#dc3545', icon: '🔴' },
        advertencia: { bg: '#fff3cd', border: '#ffc107', icon: '⚠️' },
        info:        { bg: '#d1ecf1', border: '#0077b6', icon: 'ℹ️' },
    };
    const c = colores[tipo] || colores.info;
    const banner = document.createElement('div');
    banner.style.cssText = `
        background: ${c.bg};
        border-left: 5px solid ${c.border};
        border-radius: 8px;
        padding: 1.5rem 2rem;
        margin: 0 auto 2rem;
        max-width: 700px;
        text-align: center;
    `;
    banner.innerHTML = `
        <div style="font-size:2rem; margin-bottom:0.5rem;">${c.icon}</div>
        <p style="font-weight:700; font-size:1.1rem; margin-bottom:0.4rem;">${titulo}</p>
        <p style="margin:0; color:#444;">${mensaje}</p>
    `;
    document.querySelector('.container').appendChild(banner);
}

// ── Muestra el nombre y código del lab en solo lectura ────────────────────────
function mostrarInfoLab(perfil) {
    const wrapper = document.getElementById('lab-selector').closest('.form-group');
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
            <span style="font-weight:600; color:var(--primary-color);">${perfil.nombre}</span>
            <span style="
                background: var(--primary-color);
                color: white;
                padding: 0.2rem 0.7rem;
                border-radius: 4px;
                font-size: 0.85rem;
                font-weight: 700;
                letter-spacing: 0.05em;
            ">${perfil.cod_anonimo}</span>
        </div>
    `;
}

// ── Muestra la ronda activa en solo lectura ───────────────────────────────────
function mostrarRondaActiva(ronda) {
    const wrapper = document.getElementById('round-code').closest('.form-group');
    wrapper.innerHTML = `
        <label class="form-label">Código de Ensayo de Intercomparación</label>
        <div style="
            padding: 0.75rem 1rem;
            background: var(--bg-light);
            border: 2px solid var(--secondary-color);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        ">
            <span style="font-weight:700; color:var(--primary-color); font-size:1.1rem; letter-spacing:0.05em;">${ronda.codigo}</span>
            <span style="color:#666; font-size:0.85rem;">${ronda.descripcion}</span>
        </div>
        <input type="hidden" id="round-code" value="${ronda.codigo}">
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
            analytes: ["Bilirrubina", "Sangre", "Glucosa", "Cetonas", "Leucocitos", "Nitritos", "pH", "Proteínas T.", "Densidad", "Urobilinógeno"],
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
            <td><input type="text" class="form-control instrument-input-${type}" placeholder="Marca / modelo del equipo"></td>
            <td><input type="text" class="form-control method-input-${type}" placeholder="Método de análisis"></td>
            <td><input type="${inputType}" class="form-control result-input-${type}" ${inputType === 'number' ? 'step="any"' : ''}></td>
            <td><input type="text" class="form-control unit-input-${type}" placeholder="Ej: mg/dL"></td>
        `;
        tbody.appendChild(row);
    });
}

window.copyDown = function (className) {
    const inputs = document.querySelectorAll(`.${className}`);
    if (!inputs.length) return;
    const firstValue = inputs[0].value;
    inputs.forEach(input => { if (!input.value) input.value = firstValue; });
};

// ── Modal de confirmación ─────────────────────────────────────────────────────
function mostrarModalConfirmacion(datos) {
    return new Promise((resolve) => {
        const modal    = document.getElementById('modal-confirmacion');
        const resumen  = document.getElementById('modal-resumen');
        const btnOk    = document.getElementById('modal-confirmar');
        const btnCancelar = document.getElementById('modal-cancelar');

        // Construir resumen visual para el modal
        let html = `
            <p><strong>Laboratorio:</strong> ${datos.perfilLab.nombre} (${datos.perfilLab.cod_anonimo})</p>
            <p><strong>Ronda:</strong> ${datos.roundCode}</p>
            <p><strong>Fecha:</strong> ${datos.reportDate}</p>
            <p><strong>Correo:</strong> ${datos.email || '—'}</p>
            <hr style="margin:0.8rem 0; border:none; border-top:1px solid #dde3ee;">
        `;

        if (datos.resultsChem.length) {
            html += `<p><strong>Química Clínica (${datos.resultsChem.length} analitos):</strong></p>`;
            datos.resultsChem.forEach(r => {
                html += `<p style="padding-left:0.8rem;">• ${r.analyte}: <strong>${r.result} ${r.unit}</strong></p>`;
            });
        }
        if (datos.resultsUro.length) {
            html += `<p style="margin-top:0.5rem;"><strong>Uroanálisis (${datos.resultsUro.length} analitos):</strong></p>`;
            datos.resultsUro.forEach(r => {
                html += `<p style="padding-left:0.8rem;">• ${r.analyte}: <strong>${r.result} ${r.unit}</strong></p>`;
            });
        }

        resumen.innerHTML = html;
        modal.classList.add('active');
        window.scrollTo(0, 0);

        const confirmar = () => {
            cleanup();
            resolve(true);
        };
        const cancelar = () => {
            cleanup();
            resolve(false);
        };
        const cleanup = () => {
            modal.classList.remove('active');
            btnOk.removeEventListener('click', confirmar);
            btnCancelar.removeEventListener('click', cancelar);
        };

        btnOk.addEventListener('click', confirmar);
        btnCancelar.addEventListener('click', cancelar);
    });
}

// ── Envío del formulario ──────────────────────────────────────────────────────
async function handleFormSubmit(e) {
    e.preventDefault();

    if (!perfilLab || !rondaActiva) {
        alert('Error de sesión. Por favor cierre sesión y vuelva a ingresar.');
        return;
    }

    const roundCode  = rondaActiva.codigo;
    const reportDate = document.getElementById('report-date').value;
    const email      = document.getElementById('contact-email').value;
    const comments   = document.getElementById('comments').value;

    if (!reportDate) {
        alert('La fecha del reporte es obligatoria.');
        return;
    }

    const resultsChem = scrapeTable('#analytes-table-chem tbody', 'chem');
    const resultsUro  = scrapeTable('#analytes-table-uro tbody', 'uro');
    const allResults  = [...resultsChem, ...resultsUro];

    if (!allResults.length) {
        alert('No has ingresado ningún resultado en las tablas.');
        return;
    }

    // ── Mostrar modal de confirmación ─────────────────────────────────────────
    const confirmado = await mostrarModalConfirmacion({
        perfilLab, roundCode, reportDate, email, resultsChem, resultsUro
    });

    if (!confirmado) return;

    const submitBtn  = document.getElementById('submit-btn');
    const loadingMsg = document.getElementById('loading-message');
    const successMsg = document.getElementById('success-message');
    const resultsForm = document.getElementById('results-form');

    submitBtn.disabled = true;
    loadingMsg.style.display = 'block';

    try {
        // ── Correo con resumen del reporte (EmailJS) ──────────────────────────
        if (email && window.emailjs) {
            loadingMsg.textContent = '⏳ Enviando correo de confirmación...';
            try {
                await window.emailjs.send('service_80iwfhm', 'template_53vkh45', {
                    name:            perfilLab.nombre,
                    email:           email,
                    lab_name:        perfilLab.nombre,
                    round_code:      roundCode,
                    report_date:     reportDate,
                    entered_email:   email,
                    results_summary: construirResumen(resultsChem, resultsUro),
                });
                console.log('✓ Correo enviado.');
            } catch (emailErr) {
                console.warn('Correo no enviado (no bloquea el guardado):', emailErr);
            }
        }

        // ── Guardar en Firestore ──────────────────────────────────────────────
        loadingMsg.textContent = '⏳ Guardando datos en la base de datos...';

        await Promise.race([
            addDoc(collection(db, 'resultados_generales'), {
                cod_anonimo:    perfilLab.cod_anonimo,
                cod_interno:    perfilLab.cod_interno,
                laboratorio:    perfilLab.nombre,
                uid_lab:        auth.currentUser.uid,
                codigo_ensayo:  roundCode,
                fecha_reporte:  reportDate,
                email_contacto: email,
                comentarios:    comments,
                resultados:     allResults,
                tipos_incluidos: {
                    quimica:     resultsChem.length > 0,
                    uroanalisis: resultsUro.length > 0,
                },
                timestamp: serverTimestamp(),
            }),
            new Promise((_, reject) => setTimeout(() => reject(new Error('Firebase timeout')), 10000))
        ]);

        // ── Éxito: ocultar formulario permanentemente ─────────────────────────
        loadingMsg.style.display = 'none';
        resultsForm.style.display = 'none';
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
