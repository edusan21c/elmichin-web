// app/static/js/qz-print.js
// Comunicacion con QZ Tray para imprimir tickets.
(function() {
    'use strict';

    let qzConectado = false;
    let qzIntentando = false;

    // ==================== CONEXION ====================
    function conectarQZ() {
        if (qzConectado) return Promise.resolve(true);
        if (qzIntentando) return Promise.resolve(false);
        qzIntentando = true;

        return new Promise((resolve) => {
            try {
                if (typeof qz === 'undefined') {
                    console.warn('Libreria qz-tray.js no cargada');
                    qzIntentando = false;
                    resolve(false);
                    return;
                }

                // Configuracion SIN certificado (uso interno)
                qz.security.setCertificatePromise(function(resolve) {
                    resolve();
                });
                qz.security.setSignaturePromise(function(toSign) {
                    return function(resolve) {
                        resolve();
                    };
                });

                // Conexion insegura (local) - ws://localhost:8181
                qz.websocket.connect({
                    host: 'localhost',
                    port: 8181,
                    usingSecure: false,
                    retries: 1,
                })
                .then(() => {
                    qzConectado = true;
                    qzIntentando = false;
                    console.log('QZ Tray conectado');
                    resolve(true);
                })
                .catch(err => {
                    console.warn('No se pudo conectar a QZ Tray:', err);
                    qzIntentando = false;
                    resolve(false);
                });
            } catch (e) {
                console.error('Error conectando a QZ Tray:', e);
                qzIntentando = false;
                resolve(false);
            }
        });
    }

    // ==================== IMPRIMIR ====================
    async function imprimirTicket(facturaId) {
        const conectado = await conectarQZ();
        if (!conectado) {
            mostrarAlerta('QZ Tray no esta corriendo. Abrelo e intenta de nuevo.', 'warning');
            return false;
        }

        try {
            // 1. Obtener las lineas del ticket
            const r = await fetch(`/api/ticket/${facturaId}/escpos`);
            if (!r.ok) {
                throw new Error('Error HTTP ' + r.status);
            }
            const data = await r.json();

            // 2. Buscar impresoras disponibles
            let printerName = null;
            try {
                const printers = await qz.printers.find();
                if (printers && printers.length > 0) {
                    printerName = printers[0];
                    console.log('Impresora encontrada:', printerName);
                }
            } catch (e) {
                console.warn('No se pudieron listar impresoras:', e);
            }

            if (!printerName) {
                mostrarAlerta('No hay impresora configurada. Conecta una impresora termica.', 'warning');
                return false;
            }

            // 3. Configurar trabajo de impresion
            const config = qz.configs.create(printerName);

            // 4. Contenido del ticket
            const contenido = data.lineas.join('\n') + '\n\n\n\n';
            const dataToPrint = [{
                type: 'raw',
                format: 'plain',
                data: contenido,
                options: { encoding: 'CP850' }
            }];

            // 5. Enviar a imprimir
            await qz.print(config, dataToPrint);
            mostrarAlerta('Ticket enviado a impresora', 'success');
            return true;

        } catch (e) {
            console.error('Error imprimiendo:', e);
            mostrarAlerta('Error al imprimir: ' + e.message, 'danger');
            return false;
        }
    }

    // ==================== ALERTA FLOTANTE ====================
    function mostrarAlerta(mensaje, tipo) {
        const div = document.createElement('div');
        div.className = `alert alert-${tipo} position-fixed top-0 start-50 translate-middle-x mt-3 shadow`;
        div.style.zIndex = '9999';
        div.style.minWidth = '320px';
        div.innerHTML = `<i class="bi bi-info-circle"></i> ${mensaje}`;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 3000);
    }

    // ==================== GLOBAL ====================
    window.MichinPrint = {
        imprimirTicket: imprimirTicket,
        conectar: conectarQZ,
    };

    // Auto-conectar al cargar
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => conectarQZ(), 500);
    });

})();