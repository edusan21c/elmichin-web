// app/static/js/facturacion.js
(function() {
    'use strict';

    const CFG = window.FACTURACION_CONFIG || {};
    const carrito = [];

    // ==================== HELPERS ====================
    function fmt(n) {
        return '$' + Math.round(n || 0).toLocaleString('es-CO');
    }

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    // ==================== CALCULO DE PRECIO ====================
    function calcularPrecioProducto(prod, cantidad) {
        // Aplicar condiciones por cantidad
        const cant = parseInt(cantidad);
        const c3 = prod.condicion3 ? parseInt(prod.condicion3) : null;
        const c2 = prod.condicion2 ? parseInt(prod.condicion2) : null;
        const c1 = prod.condicion1 ? parseInt(prod.condicion1) : null;

        if (c3 && cant >= c3 && prod.precio3 > 0) return prod.precio3;
        if (c2 && cant >= c2 && prod.precio2 > 0) return prod.precio2;
        if (c1 && cant >= c1 && prod.precio1 > 0) return prod.precio1;
        return prod.precio || 0;
    }

    // ==================== BUSQUEDA DE PRODUCTOS ====================
    const inputBuscar = $('#input-buscar');
    const resultados = $('#resultados');
    let timeoutBuscar = null;

    inputBuscar.addEventListener('input', function() {
        clearTimeout(timeoutBuscar);
        const q = this.value.trim();
        if (q.length < 2) {
            resultados.innerHTML = '';
            return;
        }
        timeoutBuscar = setTimeout(() => buscarProductos(q), 250);
    });

    inputBuscar.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Si hay un solo resultado, agregarlo
            const items = resultados.querySelectorAll('.list-group-item');
            if (items.length === 1) {
                items[0].click();
            } else if (items.length > 0) {
                items[0].click();
            }
        }
    });

    async function buscarProductos(q) {
        try {
            const r = await fetch(CFG.urlBuscarProductos + '?q=' + encodeURIComponent(q));
            const data = await r.json();
            pintarResultados(data);
        } catch (e) {
            console.error('Error buscando productos:', e);
        }
    }

    function pintarResultados(data) {
        resultados.innerHTML = '';
        if (!data.length) {
            resultados.innerHTML = '<div class="list-group-item text-muted">Sin resultados</div>';
            return;
        }
        data.forEach(p => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';

            const stockClass = p.stock === 0 ? 'text-danger' : (p.stock <= 5 ? 'text-warning' : 'text-success');
            const stockIcon = p.stock === 0 ? '🔴' : (p.stock <= 5 ? '🟡' : '🟢');

            item.innerHTML = `
                <div class="text-start">
                    <div class="fw-semibold">${p.nombre}</div>
                    <small class="text-muted">${p.codigo || ''}</small>
                </div>
                <div class="text-end">
                    <div class="fw-bold">${fmt(p.precio)}</div>
                    <small class="${stockClass}">${stockIcon} ${p.stock}</small>
                </div>
            `;
            item.addEventListener('click', () => agregarAlCarrito(p));
            resultados.appendChild(item);
        });
    }

    // ==================== CARRITO ====================
    function agregarAlCarrito(prod) {
        if (prod.stock <= 0) {
            alert('Producto sin stock');
            return;
        }

        // Pedir cantidad
        const cantStr = prompt(`¿Cuántas unidades de "${prod.nombre}"?\n(Máximo disponible: ${prod.stock})`, '1');
        if (cantStr === null) return;

        const cantidad = parseInt(cantStr);
        if (isNaN(cantidad) || cantidad <= 0) {
            alert('Cantidad invalida');
            return;
        }
        if (cantidad > prod.stock) {
            alert(`Solo hay ${prod.stock} unidades disponibles`);
            return;
        }

        // Verificar si ya existe
        const existente = carrito.find(it => it.producto_id === prod.id);
        if (existente) {
            const nuevaCant = existente.cantidad + cantidad;
            if (nuevaCant > prod.stock) {
                alert(`Solo hay ${prod.stock} unidades en total`);
                return;
            }
            existente.cantidad = nuevaCant;
            existente.precio_unitario = calcularPrecioProducto(prod, nuevaCant);
            existente.subtotal = existente.precio_unitario * nuevaCant;
        } else {
            carrito.push({
                producto_id: prod.id,
                nombre: prod.nombre,
                cantidad: cantidad,
                precio_unitario: calcularPrecioProducto(prod, cantidad),
                subtotal: calcularPrecioProducto(prod, cantidad) * cantidad,
                stock_max: prod.stock,
                prod_data: prod,
            });
        }

        // Limpiar busqueda
        inputBuscar.value = '';
        resultados.innerHTML = '';
        inputBuscar.focus();

        renderCarrito();
    }

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
                    <td>
                        <div class="fw-semibold small">${item.nombre}</div>
                    </td>
                    <td class="text-center">
                        <input type="number" class="form-control form-control-sm text-center" 
                               value="${item.cantidad}" min="1" max="${item.stock_max}"
                               data-idx="${idx}" data-accion="cantidad" style="width: 65px;">
                    </td>
                    <td class="text-end small">${fmt(item.precio_unitario)}</td>
                    <td class="text-end small fw-semibold">${fmt(item.subtotal)}</td>
                    <td>
                        <button type="button" class="btn btn-sm btn-outline-danger" data-idx="${idx}" data-accion="eliminar">
                            <i class="bi bi-x"></i>
                        </button>
                    </td>
                `;
                body.appendChild(tr);
            });

            // Listeners
            body.querySelectorAll('input[data-accion="cantidad"]').forEach(inp => {
                inp.addEventListener('change', function() {
                    const idx = parseInt(this.dataset.idx);
                    let cant = parseInt(this.value);
                    const item = carrito[idx];
                    if (isNaN(cant) || cant < 1) cant = 1;
                    if (cant > item.stock_max) {
                        cant = item.stock_max;
                        alert(`Máximo ${item.stock_max} unidades`);
                    }
                    item.cantidad = cant;
                    item.precio_unitario = calcularPrecioProducto(item.prod_data, cant);
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

        renderTotales();
    }

    // ==================== TOTALES ====================
    function renderTotales() {
        const subtotal = carrito.reduce((s, it) => s + it.subtotal, 0);
        const metodo = $('#metodo-pago').value;
        const bolsas = parseInt($('#bolsas').value) || 0;
        const totalBolsas = bolsas * CFG.valorBolsa;

        let recargo = 0;
        if (metodo === 'nequi' || metodo === 'daviplata') {
            recargo = subtotal * (CFG.recargoPorcentaje / 100);
        }

        const total = subtotal + recargo + totalBolsas;

        $('#lbl-subtotal').textContent = fmt(subtotal);
        $('#lbl-total').textContent = fmt(total);

        // Recargo
        if (recargo > 0) {
            $('#fila-recargo').classList.remove('d-none');
            $('#lbl-recargo').textContent = fmt(recargo) + ` (${CFG.recargoPorcentaje}%)`;
        } else {
            $('#fila-recargo').classList.add('d-none');
        }

        // Credito
        if (metodo === 'credito') {
            $('#card-pago').classList.add('d-none');
            $('#alerta-credito').classList.remove('d-none');
            $('#credito-monto').textContent = fmt(total);
        } else {
            $('#card-pago').classList.remove('d-none');
            $('#alerta-credito').classList.add('d-none');

            const pagado = parseFloat($('#valor-pagado').value) || 0;
            const vueltas = pagado - total;
            if (pagado > 0) {
                if (vueltas >= 0) {
                    $('#lbl-vueltas').innerHTML = `<span class="text-success">Vueltas: ${fmt(vueltas)}</span>`;
                } else {
                    $('#lbl-vueltas').innerHTML = `<span class="text-danger">Faltan: ${fmt(-vueltas)}</span>`;
                }
            } else {
                $('#lbl-vueltas').innerHTML = '';
            }
        }
    }

    // ==================== EVENTOS TOTALLES ====================
    $('#metodo-pago').addEventListener('change', renderTotales);
    $('#bolsas').addEventListener('input', renderTotales);
    $('#valor-pagado').addEventListener('input', renderTotales);

    // ==================== FINALIZAR ====================
    $('#btn-finalizar').addEventListener('click', async function() {
        if (carrito.length === 0) {
            alert('El carrito está vacío');
            return;
        }

        const nombre = $('#cliente-nombre').value.trim();
        if (!nombre) {
            alert('Ingresa el nombre del cliente');
            $('#cliente-nombre').focus();
            return;
        }

        const metodo = $('#metodo-pago').value;
        const bolsas = parseInt($('#bolsas').value) || 0;
        const valorPagado = parseFloat($('#valor-pagado').value) || 0;

        const subtotal = carrito.reduce((s, it) => s + it.subtotal, 0);
        let recargo = 0;
        if (metodo === 'nequi' || metodo === 'daviplata') {
            recargo = subtotal * (CFG.recargoPorcentaje / 100);
        }
        const totalBolsas = bolsas * CFG.valorBolsa;
        const total = subtotal + recargo + totalBolsas;

        if (metodo !== 'credito') {
            if (valorPagado < total - 0.01) {
                alert(`Faltan ${fmt(total - valorPagado)} para completar el pago`);
                return;
            }
        }

        const payload = {
            cliente: {
                nombre: nombre,
                documento: $('#cliente-documento').value.trim(),
                telefono: $('#cliente-telefono').value.trim(),
                direccion: $('#cliente-direccion').value.trim(),
            },
            carrito: carrito.map(it => ({
                producto_id: it.producto_id,
                cantidad: it.cantidad,
                precio_unitario: it.precio_unitario,
            })),
            metodo_pago: metodo,
            recargo_porcentaje: CFG.recargoPorcentaje,
            bolsas: bolsas,
            valor_pagado: valorPagado,
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
                window.location.href = data.redirect;
            } else {
                alert('Error: ' + (data.error || 'Desconocido'));
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-check-circle"></i> FINALIZAR VENTA';
            }
        } catch (e) {
            alert('Error de conexión: ' + e.message);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle"></i> FINALIZAR VENTA';
        }
    });

    // ==================== LIMPIAR ====================
    $('#btn-limpiar').addEventListener('click', function() {
        if (!confirm('¿Limpiar toda la venta?')) return;
        carrito.length = 0;
        renderCarrito();
        $('#cliente-nombre').value = '';
        $('#cliente-documento').value = '';
        $('#cliente-telefono').value = '';
        $('#cliente-direccion').value = '';
        $('#valor-pagado').value = '0';
        $('#bolsas').value = '0';
        $('#cliente-info').textContent = '';
        inputBuscar.focus();
    });

    // ==================== AUTOCOMPLETE CLIENTE ====================
    let timeoutCliente = null;
    $('#cliente-nombre').addEventListener('input', function() {
        clearTimeout(timeoutCliente);
        const q = this.value.trim();
        if (q.length < 3) {
            $('#cliente-info').textContent = '';
            return;
        }
        timeoutCliente = setTimeout(async () => {
            try {
                const r = await fetch(CFG.urlBuscarClientes + '?q=' + encodeURIComponent(q));
                const data = await r.json();
                if (data.length > 0) {
                    const c = data[0];
                    $('#cliente-info').innerHTML = `<i class="bi bi-info-circle"></i> Cliente existente - Saldo: ${fmt(c.saldo)}`;
                } else {
                    $('#cliente-info').innerHTML = '<i class="bi bi-plus-circle text-success"></i> Se creará un cliente nuevo';
                }
            } catch (e) {
                console.error(e);
            }
        }, 400);
    });

    // ==================== SELECTOR DE TIENDA ====================
    const selectorTienda = $('#selector-tienda');
    if (selectorTienda) {
        selectorTienda.addEventListener('change', function() {
            const url = new URL(window.location.href);
            url.searchParams.set('tienda', this.value);
            window.location.href = url.toString();
        });
    }

    // ==================== INIT ====================
    inputBuscar.focus();
    renderCarrito();

})();
