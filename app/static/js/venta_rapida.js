// app/static/js/venta_rapida.js
(function() {
    'use strict';

    const CFG = window.VR_CONFIG || {};
    const carrito = [];
    const historial = [];

    function fmt(n) {
        return '$' + Math.round(n || 0).toLocaleString('es-CO');
    }

    function $(sel) { return document.querySelector(sel); }

    // ==================== CALCULO DE PRECIO ====================
    function calcularPrecio(prod, cantidad) {
        const cant = parseInt(cantidad);
        const c3 = prod.condicion3 ? parseInt(prod.condicion3) : null;
        const c2 = prod.condicion2 ? parseInt(prod.condicion2) : null;
        const c1 = prod.condicion1 ? parseInt(prod.condicion1) : null;

        if (c3 && cant >= c3 && prod.precio3 > 0) return prod.precio3;
        if (c2 && cant >= c2 && prod.precio2 > 0) return prod.precio2;
        if (c1 && cant >= c1 && prod.precio1 > 0) return prod.precio1;
        return prod.precio || 0;
    }

    // ==================== BUSQUEDA ====================
    const inputBuscar = $('#input-buscar');
    const resultados = $('#resultados');
    let timeout = null;

    inputBuscar.addEventListener('input', function() {
        clearTimeout(timeout);
        const q = this.value.trim();
        if (!q) {
            resultados.innerHTML = '';
            return;
        }
        timeout = setTimeout(() => buscar(q), 150);
    });

    inputBuscar.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Si hay resultado único, agregarlo
            const items = resultados.querySelectorAll('.list-group-item');
            if (items.length >= 1) {
                items[0].click();
            }
        }
    });

    async function buscar(q) {
        try {
            const r = await fetch(CFG.urlBuscarProductos + '?q=' + encodeURIComponent(q));
            const data = await r.json();
            pintarResultados(data);
        } catch (e) {
            console.error(e);
        }
    }

    function pintarResultados(data) {
        resultados.innerHTML = '';
        if (!data.length) {
            resultados.innerHTML = '<div class="list-group-item text-muted text-center py-3">Sin resultados o sin stock</div>';
            return;
        }
        data.forEach(p => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center py-2';
            item.innerHTML = `
                <div class="text-start">
                    <div class="fw-semibold">${p.nombre}</div>
                    <small class="text-muted">${p.codigo || ''}</small>
                </div>
                <div class="text-end">
                    <div class="fw-bold text-success">${fmt(p.precio)}</div>
                    <small class="text-muted">Stock: ${p.stock}</small>
                </div>
            `;
            item.addEventListener('click', () => agregarAlCarrito(p));
            resultados.appendChild(item);
        });
    }

    // ==================== AGREGAR AL CARRITO ====================
    function agregarAlCarrito(prod) {
        // Verificar si ya existe
        const existente = carrito.find(it => it.producto_id === prod.id);

        if (existente) {
            const nuevaCant = existente.cantidad + 1;
            if (nuevaCant > prod.stock) {
                alert(`Solo hay ${prod.stock} unidades disponibles`);
                return;
            }
            existente.cantidad = nuevaCant;
            existente.precio_unitario = calcularPrecio(prod, nuevaCant);
            existente.subtotal = existente.precio_unitario * nuevaCant;
        } else {
            // Preguntar cantidad (default 1 si es por codigo de barras)
            let cantidad = 1;
            // Si no es codigo exacto (múltiples resultados), pedir cantidad
            const input = inputBuscar.value.trim();
            if (input !== prod.codigo) {
                const resp = prompt(`¿Cuántas unidades de "${prod.nombre}"?`, '1');
                if (resp === null) return;
                cantidad = parseInt(resp);
                if (isNaN(cantidad) || cantidad <= 0) return;
                if (cantidad > prod.stock) {
                    alert(`Solo hay ${prod.stock} unidades`);
                    return;
                }
            }

            carrito.push({
                producto_id: prod.id,
                nombre: prod.nombre,
                cantidad: cantidad,
                precio_unitario: calcularPrecio(prod, cantidad),
                subtotal: calcularPrecio(prod, cantidad) * cantidad,
                stock_max: prod.stock,
                prod_data: prod,
            });
        }

        // Limpiar búsqueda y volver a enfocar
        inputBuscar.value = '';
        resultados.innerHTML = '';
        inputBuscar.focus();

        renderCarrito();
    }

    // ==================== RENDER CARRITO ====================
    function renderCarrito() {
        const body = $('#carrito-body');
        const tabla = $('#carrito-tabla');
        const vacio = $('#carrito-vacio');
        const count = $('#carrito-count');

        body.innerHTML = '';
        count.textContent = carrito.length;

        if (carrito.length === 0) {
            tabla.classList.add('d-none');
            vacio.classList.remove('d-none');
        } else {
            tabla.classList.remove('d-none');
            vacio.classList.add('d-none');
            carrito.forEach((item, idx) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><div class="fw-semibold small">${item.nombre}</div></td>
                    <td class="text-center">
                        <input type="number" class="form-control form-control-sm text-center"
                               value="${item.cantidad}" min="1" max="${item.stock_max}"
                               data-idx="${idx}" data-accion="cantidad" style="width: 65px;">
                    </td>
                    <td class="text-end small">${fmt(item.precio_unitario)}</td>
                    <td class="text-end small fw-semibold">${fmt(item.subtotal)}</td>
                    <td>
                        <button type="button" class="btn btn-sm btn-outline-danger"
                                data-idx="${idx}" data-accion="eliminar">
                            <i class="bi bi-x"></i>
                        </button>
                    </td>
                `;
                body.appendChild(tr);
            });

            body.querySelectorAll('input[data-accion="cantidad"]').forEach(inp => {
                inp.addEventListener('change', function() {
                    const idx = parseInt(this.dataset.idx);
                    let cant = parseInt(this.value);
                    const item = carrito[idx];
                    if (isNaN(cant) || cant < 1) cant = 1;
                    if (cant > item.stock_max) {
                        cant = item.stock_max;
                        alert(`Máximo ${item.stock_max}`);
                    }
                    item.cantidad = cant;
                    item.precio_unitario = calcularPrecio(item.prod_data, cant);
                    item.subtotal = item.precio_unitario * cant;
                    renderCarrito();
                });
            });

            body.querySelectorAll('button[data-accion="eliminar"]').forEach(btn => {
                btn.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.idx);
                    carrito.splice(idx, 1);
                    renderCarrito();
                });
            });
        }

        renderTotal();
    }

    // ==================== TOTAL + VUELTAS ====================
    function renderTotal() {
        const total = carrito.reduce((s, it) => s + it.subtotal, 0);
        $('#lbl-total').textContent = fmt(total);

        const pagado = parseFloat($('#input-pagado').value) || 0;
        if (pagado > 0) {
            const vueltas = pagado - total;
            if (vueltas >= 0) {
                $('#lbl-vueltas').innerHTML = `<span class="text-success">Vueltas: ${fmt(vueltas)}</span>`;
            } else {
                $('#lbl-vueltas').innerHTML = `<span class="text-danger">Faltan: ${fmt(-vueltas)}</span>`;
            }
        } else {
            $('#lbl-vueltas').innerHTML = '';
        }
    }

    $('#input-pagado').addEventListener('input', renderTotal);

    // ==================== COBRAR ====================
    $('#btn-finalizar').addEventListener('click', async function() {
        if (carrito.length === 0) {
            alert('El carrito está vacío');
            return;
        }

        const total = carrito.reduce((s, it) => s + it.subtotal, 0);
        const pagado = parseFloat($('#input-pagado').value) || 0;

        if (pagado < total - 0.01) {
            alert(`Faltan ${fmt(total - pagado)} para completar el pago`);
            return;
        }

        const payload = {
            carrito: carrito.map(it => ({
                producto_id: it.producto_id,
                cantidad: it.cantidad,
                precio_unitario: it.precio_unitario,
            })),
        };

        const btn = this;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

        try {
            const r = await fetch(CFG.urlCrear, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CFG.csrfToken,
                },
                body: JSON.stringify(payload),
            });
            const data = await r.json();

            if (data.ok) {
                // Guardar en historial
                historial.unshift({
                    factura: data.factura_id,
                    total: total,
                    hora: new Date().toLocaleTimeString('es-CO', {hour: '2-digit', minute: '2-digit'}),
                    items: carrito.length,
                });
                renderHistorial();

                // Limpiar carrito
                carrito.length = 0;
                renderCarrito();
                $('#input-pagado').value = '';
                $('#lbl-vueltas').innerHTML = '';
                inputBuscar.focus();

                // Feedback visual
                mostrarAlerta('✅ Venta registrada', 'success');
            } else {
                alert('Error: ' + (data.error || 'Desconocido'));
            }
        } catch (e) {
            alert('Error de conexión: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle"></i> COBRAR';
        }
    });

    // ==================== LIMPIAR ====================
    $('#btn-limpiar').addEventListener('click', function() {
        if (carrito.length > 0 && !confirm('¿Limpiar toda la venta?')) return;
        carrito.length = 0;
        renderCarrito();
        $('#input-pagado').value = '';
        $('#lbl-vueltas').innerHTML = '';
        inputBuscar.focus();
    });

    // ==================== HISTORIAL ====================
    function renderHistorial() {
        const h = $('#historial');
        if (historial.length === 0) {
            h.innerHTML = '<div class="text-center text-muted py-3 small">Sin ventas todavía</div>';
            return;
        }
        h.innerHTML = historial.slice(0, 10).map(v => `
            <div class="list-group-item d-flex justify-content-between py-2 small">
                <div>
                    <strong>${v.items}</strong> producto${v.items !== 1 ? 's' : ''}
                    <span class="text-muted">· ${v.hora}</span>
                </div>
                <div class="text-success fw-bold">${fmt(v.total)}</div>
            </div>
        `).join('');
    }

    // ==================== ALERTA FLOTANTE ====================
    function mostrarAlerta(msg, tipo) {
        const div = document.createElement('div');
        div.className = `alert alert-${tipo} position-fixed top-0 start-50 translate-middle-x mt-3 shadow`;
        div.style.zIndex = '9999';
        div.innerHTML = msg;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 2000);
    }

    // ==================== SELECTOR DE TIENDA ====================
    const st = $('#selector-tienda');
    if (st) {
        st.addEventListener('change', function() {
            const url = new URL(window.location.href);
            url.searchParams.set('tienda', this.value);
            window.location.href = url.toString();
        });
    }

    // ==================== INICIALIZACION ====================
    inputBuscar.focus();
    renderCarrito();
    renderHistorial();

})();
