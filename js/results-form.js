import { db, collection, addDoc, serverTimestamp } from './firebase-config.js';

document.addEventListener('DOMContentLoaded', async function () {
    console.log("Inicializando formulario de resultados...");

    // 1. Cargar Laboratorios
    await loadLaboratories();

    // 2. Generar Tablas de Analitos (Química y Uroanálisis)
    generateAnalytesTable('chem');
    generateAnalytesTable('uro');

    // 3. Manejar Envío
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
        const formData = new FormData(e.target);
        const laboratory = formData.get('laboratory');
        const reportDate = formData.get('date');
        const email = formData.get('email');
        const comments = formData.get('comments');

        if (!laboratory) throw new Error("Debes seleccionar un laboratorio.");

        // Recolectar datos de Química
        const resultsChem = scrapeTable('#analytes-table-chem tbody', 'chem');
        // Recolectar datos de Uroanálisis
        const resultsUro = scrapeTable('#analytes-table-uro tbody', 'uro');

        const allResults = [...resultsChem, ...resultsUro];

        if (allResults.length === 0) throw new Error("No has ingresado ningún resultado.");

        // Guardar en Firestore
        await addDoc(collection(db, "resultados_generales"), {
            laboratorio: laboratory,
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
        });

        // Éxito
        loadingMsg.style.display = 'none';
        successMsg.style.display = 'block';
        window.scrollTo(0, 0);

        setTimeout(() => {
            if (confirm("¿Deseas enviar otro reporte?")) {
                location.reload();
            }
        }, 2000);

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

