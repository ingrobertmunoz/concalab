document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('charts-container');

    if (!container) return; // Exit if no container

    fetch('../data/ensayos_aptitud.json')
        .then(response => response.json())
        .then(data => {
            renderCharts(data, container);
        })
        .catch(error => {
            console.error('Error loading data:', error);
            container.innerHTML = '<p class="error">Error cargando los datos de los gráficos.</p>';
        });
});

function renderCharts(data, container) {
    const analitos = data.analitos;

    // Add Metadata header
    const header = document.createElement('div');
    header.className = 'report-header';
    header.innerHTML = `<h3>Ronda: ${data.meta.ronda} (Fecha: ${data.meta.fecha_informe})</h3>`;
    container.appendChild(header);

    analitos.forEach(analito => {
        // Wrapper for this analyte
        const wrapper = document.createElement('div');
        wrapper.className = 'analito-wrapper section-light';
        wrapper.style.marginBottom = '3rem';
        wrapper.style.padding = '2rem';
        wrapper.style.borderRadius = '12px';

        const title = document.createElement('h3');
        title.innerText = `${analito.nombre} (${analito.unidades})`;
        title.style.color = 'var(--primary-color)';
        title.style.marginBottom = '1rem';
        wrapper.appendChild(title);

        const chartDiv = document.createElement('div');
        chartDiv.id = `chart-${analito.id}`;
        chartDiv.style.height = '400px';
        wrapper.appendChild(chartDiv);

        container.appendChild(wrapper);

        // Prepare Data for Plotly
        const labs = analito.resultados.map(r => r.lab);
        const zScores = analito.resultados.map(r => r.z_score);

        // Color logic based on Z-Score
        const colors = zScores.map(z => {
            const absZ = Math.abs(z);
            if (absZ > 3) return '#dc3545'; // Red - Unsatisfactory
            if (absZ > 2) return '#ffc107'; // Yellow - Warning
            return '#28a745'; // Green - Satisfactory
        });

        const trace = {
            x: labs,
            y: zScores,
            type: 'bar',
            marker: {
                color: colors
            },
            text: zScores.map(z => `Z: ${z}`),
            hoverinfo: 'x+y+text'
        };

        const layout = {
            title: `Desempeño (Z-Score) - ${analito.nombre}`,
            yaxis: {
                title: 'Z-Score',
                range: [-4, 4],
                zeroline: true,
                zerolinecolor: '#999',
                zerolinewidth: 2
            },
            shapes: [
                // Green Zone (-2 to 2)
                {
                    type: 'rect',
                    xref: 'paper',
                    yref: 'y',
                    x0: 0,
                    y0: -2,
                    x1: 1,
                    y1: 2,
                    fillcolor: 'rgba(40, 167, 69, 0.1)',
                    line: { width: 0 }
                },
                // Yellow Lines (+/- 2, +/- 3)
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 2, y1: 2, line: { color: 'orange', dash: 'dash' } },
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: -2, y1: -2, line: { color: 'orange', dash: 'dash' } },
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 3, y1: 3, line: { color: 'red', dash: 'dot' } },
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: -3, y1: -3, line: { color: 'red', dash: 'dot' } }
            ]
        };

        const config = { responsive: true };

        Plotly.newPlot(chartDiv.id, [trace], layout, config);
    });
}
