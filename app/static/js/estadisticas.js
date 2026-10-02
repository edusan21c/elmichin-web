// app/static/js/estadisticas.js
(function() {
    'use strict';

    const CFG = window.EST_CONFIG || {};

    function fmt(n) {
        return '$' + Math.round(n || 0).toLocaleString('es-CO');
    }

    async function cargarDatos() {
        try {
            const url = CFG.urlDatos + '?periodo=' + CFG.periodo + '&tienda=' + CFG.tiendaId;
            const r = await fetch(url);
            const data = await r.json();
            render(data);
        } catch (e) {
            console.error('Error cargando datos:', e);
        }
    }

    function render(data) {
        // KPIs
        document.getElementById('kpi-total').textContent = fmt(data.kpis.total_vendido);
        document.getElementById('kpi-facturas').textContent = data.kpis.num_facturas;
        document.getElementById('kpi-ticket').textContent = fmt(data.kpis.ticket_promedio);
        document.getElementById('kpi-productos').textContent = data.kpis.total_productos;

        // Chart: Ventas por día (línea)
        new Chart(document.getElementById('chart-ventas-dia'), {
            type: 'line',
            data: {
                labels: data.ventas_dia.labels,
                datasets: [{
                    label: 'Ventas ($)',
                    data: data.ventas_dia.datos,
                    borderColor: 'rgb(13, 110, 253)',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    fill: true,
                    tension: 0.3,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => fmt(c.parsed.y) } }
                },
                scales: {
                    y: { ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k' } }
                }
            }
        });

        // Chart: Métodos de pago (doughnut)
        new Chart(document.getElementById('chart-metodos'), {
            type: 'doughnut',
            data: {
                labels: data.metodos.labels,
                datasets: [{
                    data: data.metodos.datos,
                    backgroundColor: ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6c757d']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: { callbacks: { label: (c) => c.label + ': ' + fmt(c.parsed) } }
                }
            }
        });

        // Chart: Top productos (horizontal bar)
        new Chart(document.getElementById('chart-top'), {
            type: 'bar',
            data: {
                labels: data.top_productos.labels.map(l => l.length > 30 ? l.substring(0,30) + '...' : l),
                datasets: [{
                    label: 'Unidades vendidas',
                    data: data.top_productos.cantidades,
                    backgroundColor: 'rgb(25, 135, 84)',
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true } }
            }
        });

        // Chart: Ventas por hora (bar)
        new Chart(document.getElementById('chart-horas'), {
            type: 'bar',
            data: {
                labels: data.por_hora.labels,
                datasets: [{
                    label: 'Ventas',
                    data: data.por_hora.datos,
                    backgroundColor: 'rgb(255, 193, 7)',
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => fmt(c.parsed.y) } }
                },
                scales: { y: { ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k' } } }
            }
        });

        // Chart: Comparativa (solo programador)
        const compCanvas = document.getElementById('chart-comparativa');
        if (compCanvas && data.comparativa && Object.keys(data.comparativa).length > 0) {
            new Chart(compCanvas, {
                type: 'bar',
                data: {
                    labels: Object.keys(data.comparativa),
                    datasets: [{
                        label: 'Ventas por tienda',
                        data: Object.values(data.comparativa),
                        backgroundColor: ['#0d6efd', '#198754'],
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (c) => fmt(c.parsed.y) } }
                    }
                }
            });
        }
    }

    // Selector de tienda
    const st = document.getElementById('selector-tienda');
    if (st) {
        st.addEventListener('change', function() {
            const url = new URL(window.location.href);
            url.searchParams.set('tienda', this.value);
            window.location.href = url.toString();
        });
    }

    // Cargar
    cargarDatos();

})();
