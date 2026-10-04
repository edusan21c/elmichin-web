// app/static/js/michin-modal.js
// Modal reutilizable para pedir cantidad de productos.
// Reemplaza al prompt() feo del navegador.
(function() {
    'use strict';

    let resolveActual = null;
    let modalInstance = null;

    function asegurarModal() {
        if (document.getElementById('michin-modal-cantidad')) return;

        const html = `
            <div class="modal fade" id="michin-modal-cantidad" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered modal-sm">
                    <div class="modal-content">
                        <div class="modal-header bg-primary text-white py-2">
                            <h6 class="modal-title mb-0">
                                <i class="bi bi-box-seam"></i> Cantidad
                            </h6>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-1 small fw-semibold" id="michin-modal-nombre"></p>
                            <p class="mb-3 small text-muted">
                                Disponibles: <strong id="michin-modal-stock">0</strong>
                            </p>
                            <div class="d-flex align-items-center justify-content-center gap-2">
                                <button type="button" class="btn btn-outline-secondary btn-lg" id="michin-modal-menos">
                                    <i class="bi bi-dash-lg"></i>
                                </button>
                                <input type="number" id="michin-modal-cant"
                                       class="form-control form-control-lg text-center fw-bold"
                                       value="1" min="1" style="max-width: 100px;">
                                <button type="button" class="btn btn-outline-secondary btn-lg" id="michin-modal-mas">
                                    <i class="bi bi-plus-lg"></i>
                                </button>
                            </div>
                            <div class="text-center mt-2">
                                <button type="button" class="btn btn-sm btn-link p-0" id="michin-modal-todos">
                                    Usar todo el stock
                                </button>
                            </div>
                        </div>
                        <div class="modal-footer py-2">
                            <button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-primary btn-sm" id="michin-modal-aceptar">
                                <i class="bi bi-check-lg"></i> Agregar
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.insertAdjacentHTML('beforeend', html);

        const modalEl = document.getElementById('michin-modal-cantidad');
        modalInstance = new bootstrap.Modal(modalEl);
        const input = document.getElementById('michin-modal-cant');

        // Botones + / - / todos
        document.getElementById('michin-modal-menos').addEventListener('click', () => {
            let v = parseInt(input.value) || 1;
            if (v > 1) input.value = v - 1;
        });
        document.getElementById('michin-modal-mas').addEventListener('click', () => {
            let v = parseInt(input.value) || 1;
            const max = parseInt(input.max) || 99;
            if (v < max) input.value = v + 1;
        });
        document.getElementById('michin-modal-todos').addEventListener('click', () => {
            input.value = input.max;
        });

        // Aceptar
        document.getElementById('michin-modal-aceptar').addEventListener('click', () => {
            if (!resolveActual) return;
            let v = parseInt(input.value) || 1;
            const max = parseInt(input.max) || 1;
            if (v < 1) v = 1;
            if (v > max) v = max;
            const cb = resolveActual;
            resolveActual = null;
            modalInstance.hide();
            cb(v);
        });

        // Cancelar / cerrar con X o Escape
        modalEl.addEventListener('hidden.bs.modal', () => {
            if (resolveActual) {
                const cb = resolveActual;
                resolveActual = null;
                cb(null);
            }
        });

        // Enter = aceptar
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('michin-modal-aceptar').click();
            }
        });
    }

    // Función pública: michinPedirCantidad(nombre, stockMax, valorInicial) → Promise<number|null>
    window.michinPedirCantidad = function(nombreProducto, stockMax, valorInicial) {
        asegurarModal();
        return new Promise((resolve) => {
            resolveActual = resolve;

            document.getElementById('michin-modal-nombre').textContent = nombreProducto;
            document.getElementById('michin-modal-stock').textContent = stockMax;

            const input = document.getElementById('michin-modal-cant');
            input.value = valorInicial || 1;
            input.max = stockMax;

            modalInstance.show();

            const modalEl = document.getElementById('michin-modal-cantidad');
            modalEl.addEventListener('shown.bs.modal', function focusOnce() {
                input.focus();
                input.select();
                modalEl.removeEventListener('shown.bs.modal', focusOnce);
            });
        });
    };
})();