import { db, collection, addDoc, serverTimestamp, auth, signInWithEmailAndPassword, onAuthStateChanged, signOut } from './firebase-config.js';

document.addEventListener('DOMContentLoaded', async function () {
    console.log("Inicializando formulario de resultados...");

    // UI Elements
    const loginSection = document.getElementById('login-section');
    const resultsForm = document.getElementById('results-form');
    const userBar = document.getElementById('user-bar');
    const userEmailSpan = document.getElementById('user-email');
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const loginError = document.getElementById('login-error');

    // --- AUTH STATE LISTENER ---
    onAuthStateChanged(auth, async (user) => {
        if (user) {
            // Usuario autenticado → mostrar formulario
            console.log("✅ Usuario autenticado:", user.email);
            loginSection.style.display = 'none';
            resultsForm.style.display = 'block';
            userBar.style.display = 'flex';
            userEmailSpan.textContent = user.email;

            // Pre-llenar email de contacto
            const emailInput = document.getElementById('contact-email');
            if (emailInput && !emailInput.value) {
                emailInput.value = user.email;
            }

            // Cargar datos del formulario
            await loadLaboratories();
            generateAnalytesTable('chem');
            generateAnalytesTable('uro');
        } else {
            // No autenticado → mostrar login
            console.log("🔒 No autenticado");
            loginSection.style.display = 'block';
            resultsForm.style.display = 'none';
            userBar.style.display = 'none';
        }
    });

    // --- LOGIN ---
    loginBtn.addEventListener('click', async () => {
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;

        if (!email || !password) {
            loginError.textContent = 'Por favor ingrese correo y contraseña.';
            loginError.style.display = 'block';
            return;
        }

        loginBtn.disabled = true;
        loginBtn.textContent = 'Verificando...';
        loginError.style.display = 'none';

        try {
            await signInWithEmailAndPassword(auth, email, password);
            // onAuthStateChanged se encargará de mostrar el formulario
        } catch (error) {
            console.error("Error de autenticación:", error.code);
            if (error.code === 'auth/user-not-found' || error.code === 'auth/wrong-password' || error.code === 'auth/invalid-credential') {
                loginError.textContent = 'Correo o contraseña incorrectos.';
            } else if (error.code === 'auth/too-many-requests') {
                loginError.textContent = 'Demasiados intentos. Intente más tarde.';
            } else {
                loginError.textContent = 'Error al iniciar sesión. Intente de nuevo.';
            }
            loginError.style.display = 'block';
        } finally {
            loginBtn.disabled = false;
            loginBtn.textContent = 'Iniciar Sesión';
        }
    });

    // Enter key en el campo de contraseña
    document.getElementById('login-password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loginBtn.click();
    });

    // --- LOGOUT ---
    logoutBtn.addEventListener('click', async () => {
        await signOut(auth);
        location.reload();
    });

    // Manejar Envío
    const form = document.getElementById('results-form');
    form.addEventListener('submit', handleFormSubmit);
});

async function loadLaboratories() {
    const select = document.getElementById('lab-selector');
    try {
        const response = await fetch('data/laboratorios.json');
        const labs = await response.json();

        // Sort alphabetically
        labs.sort((a, b) => a.nombre.localeCompare(b.nombre));

        labs.forEach((lab, index) => {
            const option = document.createElement('option');
            option.value = lab.nombre;
            option.textContent = lab.nombre;
            select.appendChild(option);
        });
        console.log(`Cargados ${labs.length} laboratorios.`);
    } catch (error) {
        console.error("Error cargando laboratorios:", error);
        alert("Error cargando la lista de laboratorios. Por favor recarga la página.");
    }
}

function generateAnalytesTable(type) {
    let analytesList = [];
    let tableId = '';
    let suffix = '';

    if (type === 'chem') {
        tableId = '#analytes-table-chem';
        suffix = 'chem';
        analytesList = [
            "Glucosa", "Ácido Úrico", "Colesterol", "Colesterol HDL", "Triglicéridos",
            "Urea", "Creatinina", "Proteínas Total", "Albúmina", "Bilirrubina Total",
            "Bilirrubina Directa", "Amilasa", "Lipasa", "Fosfatasa Alcalina (ALP)",
            "AST (TGO)", "ALT (TGP)", "Gamma GGT", "LDH", "CK-TOTAL",
            "Calcio", "Fósforo", "Cloruro", "Sodio", "Potasio", "Magnesio", "Hierro"
        ];
    } else if (type === 'uro') {
        tableId = '#analytes-table-uro';
        suffix = 'uro';
        analytesList = [
            "Proteínas",
            "Glucosa",
            "Cuerpos cetónicos",
            "Bilirrubina",
            "Nitritos"
        ];
    }

    const tbody = document.querySelector(`${tableId} tbody`);
    if (!tbody) return;

    analytesList.forEach((analyte, index) => {
        const row = document.createElement('tr');

        // Nombre Analito
        const nameCell = document.createElement('td');
        nameCell.textContent = analyte;
        nameCell.style.fontWeight = "600";
        row.appendChild(nameCell);

        // Instrumento
        const instCell = document.createElement('td');
        const instInput = document.createElement('input');
        instInput.type = "text";
        instInput.className = `form-control instrument-input-${suffix}`;
        instCell.appendChild(instInput);
        row.appendChild(instCell);

        // Metodo
        const methodCell = document.createElement('td');
        const methodInput = document.createElement('input');
        methodInput.type = "text";
        methodInput.className = `form-control method-input-${suffix}`;
        methodCell.appendChild(methodInput);
        row.appendChild(methodCell);

        // Resultado
        const resCell = document.createElement('td');
        const resInput = document.createElement('input');
        if (type === 'chem') {
            resInput.type = "number";
            resInput.step = "any";
        } else {
            resInput.type = "text"; // Uroanálisis puede ser cualitativo (+, ++, neg)
        }
        resInput.className = `form-control result-input-${suffix}`;
        resCell.appendChild(resInput);
        row.appendChild(resCell);

        // Unidades
        const unitCell = document.createElement('td');
        const unitInput = document.createElement('input');
        unitInput.type = "text";
        unitInput.className = `form-control unit-input-${suffix}`;
        unitCell.appendChild(unitInput);
        row.appendChild(unitCell);

        tbody.appendChild(row);
    });
}

// Función mágica para replicar instrumento/método
window.copyDown = function (className) {
    const inputs = document.querySelectorAll(`.${className}`);
    if (inputs.length === 0) return;

    const firstValue = inputs[0].value;
    inputs.forEach(input => {
        if (!input.value) input.value = firstValue;
    });
};

async function handleFormSubmit(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('submit-btn');
    const loadingMsg = document.getElementById('loading-message');
    const successMsg = document.getElementById('success-message');

    submitBtn.disabled = true;
    loadingMsg.style.display = 'block';

    try {
        // Leer valores directamente del DOM (más confiable que FormData en Chrome)
        const laboratory = document.getElementById('lab-selector').value;
        const roundCode = document.getElementById('round-code').value.toUpperCase();
        const reportDate = document.getElementById('report-date').value;
        const email = document.getElementById('contact-email').value;
        const comments = document.getElementById('comments').value;

        console.log("Datos del formulario:", { laboratory, roundCode, reportDate, email });

        if (!laboratory || laboratory === "") {
            throw new Error("Debes seleccionar un laboratorio válido.");
        }

        if (!roundCode || !/^EA-\d{3}-\d{4}$/.test(roundCode)) {
            throw new Error("El código de ensayo debe tener el formato EA-001-2025.");
        }

        // Recolectar datos de Química
        const resultsChem = scrapeTable('#analytes-table-chem tbody', 'chem');
        // Recolectar datos de Uroanálisis
        const resultsUro = scrapeTable('#analytes-table-uro tbody', 'uro');

        const allResults = [...resultsChem, ...resultsUro];

        if (allResults.length === 0) throw new Error("No has ingresado ningún resultado en las tablas.");

        // --- PASO 1: ENVIAR CORREO (EmailJS) - INDEPENDIENTE de Firebase ---
        if (email && window.emailjs) {
            loadingMsg.textContent = "⏳ Enviando confirmación al correo...";

            // Generar resumen DETALLADO con los valores reales
            let summaryLines = [];

            if (resultsChem.length > 0) {
                summaryLines.push('--- QUÍMICA CLÍNICA ---');
                resultsChem.forEach(r => {
                    summaryLines.push(`• ${r.analyte}: ${r.result} ${r.unit} (Método: ${r.method || 'N/A'}, Instrumento: ${r.instrument || 'N/A'})`);
                });
            }

            if (resultsUro.length > 0) {
                summaryLines.push('');
                summaryLines.push('--- UROANÁLISIS ---');
                resultsUro.forEach(r => {
                    summaryLines.push(`• ${r.analyte}: ${r.result} ${r.unit} (Método: ${r.method || 'N/A'}, Instrumento: ${r.instrument || 'N/A'})`);
                });
            }

            summaryLines.push('');
            summaryLines.push(`Total: ${allResults.length} analitos reportados.`);

            const summary = summaryLines.join('\n');

            const templateParams = {
                name: laboratory,
                email: email,
                lab_name: laboratory,
                round_code: roundCode,
                report_date: reportDate,
                entered_email: email,
                results_summary: summary
            };

            try {
                await window.emailjs.send('service_80iwfhm', 'template_53vkh45', templateParams);
                console.log('✅ Correo enviado exitosamente!');
            } catch (emailError) {
                console.error('⚠️ Error al enviar correo:', emailError);
            }
        }

        // --- PASO 2: Guardar en Firebase (con timeout de 10s) ---
        loadingMsg.textContent = "⏳ Guardando datos en la base de datos...";
        const firebaseTimeout = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Firebase timeout')), 10000)
        );

        try {
            await Promise.race([
                addDoc(collection(db, "resultados_generales"), {
                    laboratorio: laboratory,
                    codigo_ensayo: roundCode,
                    fecha_reporte: reportDate,
                    email_contacto: email,
                    comentarios: comments,
                    resultados: allResults,
                    tipos_incluidos: {
                        quimica: resultsChem.length > 0,
                        uroanalisis: resultsUro.length > 0
                    },
                    timestamp: serverTimestamp(),
                    userAgent: navigator.userAgent
                }),
                firebaseTimeout
            ]);
            console.log('✅ Datos guardados en Firebase!');
        } catch (fbError) {
            console.warn('⚠️ Firebase no respondió a tiempo (datos pueden sincronizarse después):', fbError.message);
        }

        // Éxito (se muestra sin importar si Firebase respondió o no)
        loadingMsg.style.display = 'none';
        successMsg.style.display = 'block';
        window.scrollTo(0, 0);

    } catch (error) {
        console.error("Error al enviar:", error);
        loadingMsg.style.display = 'none';
        submitBtn.disabled = false;
        alert("Error al enviar: " + error.message);
    }
}

function scrapeTable(tbodySelector, suffix) {
    const results = [];
    const rows = document.querySelectorAll(tbodySelector + ' tr');

    rows.forEach(row => {
        const analyte = row.cells[0].textContent;
        const instrument = row.querySelector(`.instrument-input-${suffix}`).value;
        const method = row.querySelector(`.method-input-${suffix}`).value;
        const result = row.querySelector(`.result-input-${suffix}`).value;
        const unit = row.querySelector(`.unit-input-${suffix}`).value;

        if (result || instrument) {
            results.push({
                categoria: suffix === 'chem' ? 'Química Clínica' : 'Uroanálisis',
                analyte,
                instrument,
                method,
                result,
                unit
            });
        }
    });
    return results;
}

