// app/static/js/facturacion.js
(function() {
    'use strict';

    const CFG = window.FACTURACION_CONFIG || {};
    const MAX_PESTANAS = 6;
    const STORAGE_KEY = 'michin_facturacion_pestanas';
    const LETRAS = ['A', 'B', 'C', 'D', 'E', 'F'];

    // ==================== ESTADO ====================
    let estado = {
        pestanas: [crearPestanaVacia('A')],
        activa: 0
    };

    let procesandoProducto = false;

    function crearPestanaVacia(id) {
        return {
            id: id,
            carrito: [],
            cliente: { nombre: '', documento: '', telefono: '', direccion: '' },
            metodoPago: 'efectivo',
            bolsas: 0,
            pagos: ['', '', ''],                        
            pagosMetodos: ['efectivo', 'efectivo', 'efectivo'],  
            modoPrecioLibre: false,
        };
    }

    function pestanaActual() {
        return estado.pestanas[estado.activa];
    }

    function contarItems(p) {
        return p.carrito.reduce((s, it) => s + it.cantidad, 0);
    }

    // ==================== PERSISTENCIA ====================
    function guardarEstado() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(estado));
        } catch (e) {
            console.warn('No se pudo guardar en localStorage:', e);
        }
    }

    function cargarEstado() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            const data = JSON.parse(raw);
            if (data && Array.isArray(data.pestanas) && data.pestanas.length > 0) {
                estado = data;
                if (estado.activa >= estado.pestanas.length) {
                    estado.activa = 0;
                }
                estado.pestanas.forEach(p => {
                    if (typeof p.modoPrecioLibre === 'undefined') p.modoPrecioLibre = false;
                    if (!p.cliente) p.cliente = { nombre: '', documento: '', telefono: '', direccion: '' };
                    if (!Array.isArray(p.carrito)) p.carrito = [];
                    if (!Array.isArray(p.pagos)) {
                        p.pagos = ['', '', ''];
                        if (p.valorPagado) p.pagos[0] = String(p.valorPagado);
                        delete p.valorPagado;
                    }
                    if (!Array.isArray(p.pagosMetodos) || p.pagosMetodos.length !== 3) {
                        p.pagosMetodos = ['efectivo', 'efectivo', 'efectivo'];
                    }
                });
            }
        } catch (e) {
            console.warn('No se pudo cargar de localStorage:', e);
        }
    }

    // ==================== HELPERS ====================
    function fmt(n) {
        return '$' + Math.round(n || 0).toLocaleString('es-CO');
    }

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    // ==================== PESTAÑAS (UI) ====================
    function renderPestanas() {
        const container = $('#pestanas-tabs');
        if (!container) return;

        container.innerHTML = '';

        estado.pestanas.forEach((p, idx) => {
            const items = contarItems(p);
            const activa = idx === estado.activa;
            const tieneItems = items > 0;

            const li = document.createElement('li');
            li.className = 'nav-item';

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'nav-link d-flex align-items-center gap-2' + (activa ? ' active' : '');
            btn.setAttribute('data-idx', idx);

            let contenidoHTML = `<span class="fw-bold">${p.id}</span>`;
            if (tieneItems) {
                contenidoHTML += `<span class="badge bg-primary rounded-pill">${items}</span>`;
            }
            if (estado.pestanas.length > 1) {
                contenidoHTML += `<span class="pestana-cerrar ms-1" data-cerrar="${idx}" title="Cerrar pestaña">×</span>`;
            }
            btn.innerHTML = contenidoHTML;

            btn.addEventListener('click', function(e) {
                if (e.target.dataset.cerrar !== undefined) return;
                cambiarPestana(idx);
            });

            li.appendChild(btn);
            container.appendChild(li);
        });

        if (estado.pestanas.length < MAX_PESTANAS) {
            const li = document.createElement('li');
            li.className = 'nav-item';
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'nav-link text-success fw-bold';
            btn.innerHTML = '+';
            btn.title = 'Nueva pestaña';
            btn.addEventListener('click', crearPestana);
            li.appendChild(btn);
            container.appendChild(li);
        }

        container.querySelectorAll('[data-cerrar]').forEach(el => {
            el.addEventListener('click', function(e) {
                e.stopPropagation();
                const idx = parseInt(this.dataset.cerrar);
                cerrarPestana(idx);
            });
        });
    }

    function cambiarPestana(idx) {
        if (idx === estado.activa) return;
        estado.activa = idx;
        guardarEstado();
        renderPestanas();
        cargarPestanaEnUI();
    }

    function crearPestana() {
        if (estado.pestanas.length >= MAX_PESTANAS) return;

        const usadas = new Set(estado.pestanas.map(p => p.id));
        const letraLibre = LETRAS.find(l => !usadas.has(l));
        if (!letraLibre) return;

        const nueva = crearPestanaVacia(letraLibre);
        estado.pestanas.push(nueva);
        estado.activa = estado.pestanas.length - 1;
        guardarEstado();
        renderPestanas();
        cargarPestanaEnUI();
        inputBuscar.focus();
    }

    function cerrarPestana(idx) {
        if (estado.pestanas.length <= 1) return;

        const p = estado.pestanas[idx];
        const items = contarItems(p);

        if (items > 0) {
            const ok = confirm(
                `La pestaña "${p.id}" tiene ${items} producto(s).\n` +
                `¿Seguro que quieres cerrarla? Se perderán los datos.`
            );
            if (!ok) return;
        }

        estado.pestanas.splice(idx, 1);

        if (estado.activa >= estado.pestanas.length) {
            estado.activa = estado.pestanas.length - 1;
        } else if (estado.activa > idx) {
            estado.activa--;
        }

        guardarEstado();
        renderPestanas();
        cargarPestanaEnUI();
    }

    // ==================== CARGAR PESTAÑA EN UI ====================
    function cargarPestanaEnUI() {
        const p = pestanaActual();

        $('#cliente-nombre').value = p.cliente.nombre || '';
        $('#cliente-documento').value = p.cliente.documento || '';
        $('#cliente-telefono').value = p.cliente.telefono || '';
        $('#cliente-direccion').value = p.cliente.direccion || '';
        $('#cliente-info').textContent = '';

        $('#metodo-pago').value = p.metodoPago || 'efectivo';
        $('#bolsas').value = p.bolsas || 0;
        $('#pago-1').value = (p.pagos && p.pagos[0]) || '';
        $('#pago-2').value = (p.pagos && p.pagos[1]) || '';
        $('#pago-3').value = (p.pagos && p.pagos[2]) || '';
        const metodos = p.pagosMetodos || ['efectivo', 'efectivo', 'efectivo'];
        ['#pago-metodo-1', '#pago-metodo-2', '#pago-metodo-3'].forEach((sel, i) => {
            const el = $(sel);
            if (el) el.value = metodos[i] || 'efectivo';
        });

        const sw = $('#switch-precio-libre');
        if (sw) sw.checked = !!p.modoPrecioLibre;

        renderCarrito();
    }

    // ==================== CALCULO DE PRECIO ====================
    function calcularPrecioProducto(prod, cantidad) {
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
        if (!q) { resultados.innerHTML = ''; return; }
        timeoutBuscar = setTimeout(() => buscarProductos(q), 150);
    });

    let indiceActivo = -1;

    function actualizarActivo(items) {
        items.forEach((it, i) => {
            if (i === indiceActivo) {
                it.classList.add('active');
                it.scrollIntoView({ block: 'nearest' });
            } else {
                it.classList.remove('active');
            }
        });
    }

    inputBuscar.addEventListener('keydown', function(e) {
        const items = resultados.querySelectorAll('.list-group-item');

        if (e.key === 'Enter') {
            e.preventDefault();
            if (items.length === 0) return;
            const idx = (indiceActivo >= 0 && indiceActivo < items.length) ? indiceActivo : 0;
            items[idx].click();
            indiceActivo = -1;
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (items.length === 0) return;
            indiceActivo = (indiceActivo + 1) % items.length;
            actualizarActivo(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (items.length === 0) return;
            indiceActivo = indiceActivo <= 0 ? items.length - 1 : indiceActivo - 1;
            actualizarActivo(items);
        } else if (e.key === 'Escape') {
            resultados.innerHTML = '';
            indiceActivo = -1;
        }
    });

    async function buscarProductos(q) {
        try {
            const r = await fetch(CFG.urlBuscarProductos + '?q=' + encodeURIComponent(q));
            const data = await r.json();
            
            // SOLUCIÓN VENTA RÁPIDA: Solo pintar si el buscador TODAVÍA tiene el mismo texto
            if (inputBuscar.value.trim() === q) {
                pintarResultados(data);
            }
        } catch (e) {
            console.error('Error buscando productos:', e);
        }
    }

    function pintarResultados(data) {
        resultados.innerHTML = '';
        indiceActivo = -1;
        
        if (!data.length) {
            resultados.innerHTML = '<div class="list-group-item text-muted">Sin resultados</div>';
            return;
        }

        data.forEach(p => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center py-2';
            
            const imgHtml = p.imagen 
                ? `<img src="/static/img/productos/${p.imagen}" class="foto-clickable" data-img="/facturacion/imagen-hd/${p.id}" data-nombre="${p.nombre}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 5px; margin-right: 12px; cursor: zoom-in;" title="Clic para ampliar foto">` 
                : `<div style="width: 45px; height: 45px; background: #f0f0f0; border-radius: 5px; margin-right: 12px; display: flex; align-items: center; justify-content: center; color: #ccc;"><i class="bi bi-image"></i></div>`;

            item.innerHTML = `
                <div class="d-flex align-items-center text-start">
                    ${imgHtml}
                    <div>
                        <div class="fw-semibold">${p.nombre}</div>
                        <small class="text-muted">${p.codigo || ''}</small>
                    </div>
                </div>
                <div class="text-end">
                    <div class="fw-bold text-success">${fmt(p.precio)}</div>
                    <small class="text-muted">Stock: ${p.stock}</small>
                </div>
            `;

            const foto = item.querySelector('.foto-clickable');
            if (foto) {
                foto.addEventListener('click', function(e) {
                    e.stopPropagation(); // Evita que se agregue al carrito
                    
                    const urlImagen = this.getAttribute('data-img');
                    const nombreProducto = this.getAttribute('data-nombre');
                    
                    Swal.fire({
                        title: `<span style="font-size: 1.6rem; font-weight: bold; color: #333;">${nombreProducto}</span>`,
                        html: `<img src="${urlImagen}" onerror="this.src='/static/img/productos/${p.imagen}'" style="max-width: 100%; max-height: 75vh; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); object-fit: contain;">`,
                        showConfirmButton: false,
                        showCloseButton: true,
                        padding: '1em',
                        width: 'auto',
                        backdrop: `rgba(0,0,0,0.8)`
                    });
                });
            }

            item.addEventListener('click', () => agregarAlCarrito(p));
            resultados.appendChild(item);
        });
    }

    // ==================== AGREGAR AL CARRITO ====================
    async function agregarAlCarrito(prod) {
        if (procesandoProducto) return; // Evita modales dobles si presionan Enter muy rápido
        if (prod.stock <= 0) {
            alert('Producto sin stock');
            return;
        }

        procesandoProducto = true;
        try {
            const cantidad = await window.michinPedirCantidad(prod.nombre, prod.stock, 1);
            if (cantidad === null) return;

            const p = pestanaActual();
            const existente = p.carrito.find(it => it.producto_id === prod.id);

            if (existente) {
                const nuevaCant = existente.cantidad + cantidad;
                if (nuevaCant > prod.stock) {
                    alert(`Solo hay ${prod.stock} unidades en total`);
                    return;
                }
                existente.cantidad = nuevaCant;
                if (!existente.precio_editado) {
                    existente.precio_unitario = calcularPrecioProducto(prod, nuevaCant);
                }
                existente.subtotal = existente.precio_unitario * nuevaCant;
            } else {
                p.carrito.push({
                    producto_id: prod.id,
                    nombre: prod.nombre,
                    cantidad: cantidad,
                    precio_unitario: calcularPrecioProducto(prod, cantidad),
                    subtotal: calcularPrecioProducto(prod, cantidad) * cantidad,
                    stock_max: prod.stock,
                    prod_data: prod,
                    precio_editado: false,
                    _empacado: false,
                });
            }

            inputBuscar.value = '';
            resultados.innerHTML = '';
            inputBuscar.focus();

            guardarEstado();
            renderPestanas();
            renderCarrito();
        } finally {
            procesandoProducto = false;
        }
    }

    // ==================== RENDER CARRITO ====================
    function renderCarrito() {
        const p = pestanaActual();
        const carrito = p.carrito;
        const modoLibre = !!p.modoPrecioLibre;

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
                const empacado = !!item._empacado;
                const checked = empacado ? 'checked' : '';

                const celdaPrecio = modoLibre
                    ? `<input type="number" class="form-control form-control-sm text-end"
                              value="${item.precio_unitario}" min="0" step="50"
                              data-idx="${idx}" data-accion="precio"
                              style="width: 95px; display: inline-block;">`
                    : fmt(item.precio_unitario);

                const tr = document.createElement('tr');
                if (empacado) tr.classList.add('fila-empacada');
                tr.innerHTML = `
                    <td class="text-center" style="width: 40px;">
                        <input type="checkbox" class="form-check-input"
                               data-idx="${idx}" data-accion="empacado" ${checked}>
                    </td>
                    <td>
                        <div class="fw-semibold small nombre-producto">${item.nombre}</div>
                        ${item.precio_editado ? '<small class="text-warning">✏️ precio editado</small>' : ''}
                    </td>
                    <td class="text-center">
                        <input type="number" class="form-control form-control-sm text-center"
                               value="${item.cantidad}" min="1" max="${item.stock_max}"
                               data-idx="${idx}" data-accion="cantidad" style="width: 65px;">
                    </td>
                    <td class="text-end small">${celdaPrecio}</td>
                    <td class="text-end small fw-semibold">${fmt(item.subtotal)}</td>
                    <td>
                        <button type="button" class="btn btn-sm btn-outline-danger" data-idx="${idx}" data-accion="eliminar">
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
                        alert(`Máximo ${item.stock_max} unidades`);
                    }
                    item.cantidad = cant;
                    if (!item.precio_editado) {
                        item.precio_unitario = calcularPrecioProducto(item.prod_data, cant);
                    }
                    item.subtotal = item.precio_unitario * cant;
                    guardarEstado();
                    renderPestanas();
                    renderCarrito();
                    
                    // RESTAURAR FOCO: Para que no toque volver a hacer clic en la casilla
                    const nextInput = document.querySelector(`#carrito-body input[data-accion="cantidad"][data-idx="${idx}"]`);
                    if (nextInput) { nextInput.focus(); nextInput.select(); }
                });
            });

            body.querySelectorAll('input[data-accion="precio"]').forEach(inp => {
                inp.addEventListener('change', function() {
                    const idx = parseInt(this.dataset.idx);
                    let nuevoPrecio = parseFloat(this.value);
                    if (isNaN(nuevoPrecio) || nuevoPrecio < 0) nuevoPrecio = 0;
                    const item = carrito[idx];
                    item.precio_unitario = nuevoPrecio;
                    item.subtotal = nuevoPrecio * item.cantidad;
                    const precioOriginal = calcularPrecioProducto(item.prod_data, item.cantidad);
                    item.precio_editado = (nuevoPrecio !== precioOriginal);
                    guardarEstado();
                    renderPestanas();
                    renderCarrito();

                    // RESTAURAR FOCO
                    const nextInput = document.querySelector(`#carrito-body input[data-accion="precio"][data-idx="${idx}"]`);
                    if (nextInput) { nextInput.focus(); nextInput.select(); }
                });
            });

            body.querySelectorAll('button[data-accion="eliminar"]').forEach(btn => {
                btn.addEventListener('click', function(e) {
                    // MAGIA: Quitamos el foco y la selección de texto para que no quede "pintado"
                    this.blur();
                    if (window.getSelection) {
                        window.getSelection().removeAllRanges();
                    }

                    const idx = parseInt(this.dataset.idx);
                    carrito.splice(idx, 1);
                    guardarEstado();
                    renderPestanas();
                    renderCarrito();
                });
            });

            body.querySelectorAll('input[data-accion="empacado"]').forEach(chk => {
                chk.addEventListener('change', function() {
                    const idx = parseInt(this.dataset.idx);
                    carrito[idx]._empacado = this.checked;
                    guardarEstado();
                    renderCarrito();
                });
            });
        }

        renderTotales();
    }

    // ==================== TOTALES ====================
    function renderTotales() {
        const p = pestanaActual();
        const carrito = p.carrito;

        const subtotal = carrito.reduce((s, it) => s + it.subtotal, 0);
        const metodo = p.metodoPago || 'efectivo';
        const bolsas = parseInt(p.bolsas) || 0;
        const totalBolsas = bolsas * CFG.valorBolsa;

        const metodos = p.pagosMetodos || ['efectivo', 'efectivo', 'efectivo'];
        const hayDigital = metodos.some(m => m === 'nequi' || m === 'daviplata');

        let recargo = 0;
        if (metodo === 'credito') {
            // Credito no aplica
        } else if (hayDigital) {
            recargo = subtotal * (CFG.recargoPorcentaje / 100);
        }

        const total = subtotal + recargo + totalBolsas;

        $('#lbl-subtotal').textContent = fmt(subtotal);
        $('#lbl-total').textContent = fmt(total);

        if (recargo > 0) {
            $('#fila-recargo').classList.remove('d-none');
            $('#lbl-recargo').textContent = fmt(recargo) + ` (${CFG.recargoPorcentaje}%)`;
        } else {
            $('#fila-recargo').classList.add('d-none');
        }

        if (metodo === 'credito') {
            $('#card-pago').classList.add('d-none');
            $('#alerta-credito').classList.remove('d-none');
            $('#credito-monto').textContent = fmt(total);
        } else {
            $('#card-pago').classList.remove('d-none');
            $('#alerta-credito').classList.add('d-none');

            const pagos = p.pagos || ['', '', ''];
            const pagado = (parseFloat(pagos[0]) || 0) + (parseFloat(pagos[1]) || 0) + (parseFloat(pagos[2]) || 0);
            const vueltas = pagado - total;

            const recibidoEl = $('#lbl-total-recibido');
            if (recibidoEl) recibidoEl.textContent = fmt(pagado);

            if (pagado > 0 && vueltas >= 0) {
                $('#lbl-vueltas').innerHTML = `<span class="text-success">Vueltas: ${fmt(vueltas)}</span>`;
            } else if (pagado > 0) {
                $('#lbl-vueltas').innerHTML = `<span class="text-danger">Faltan: ${fmt(-vueltas)}</span>`;
            } else {
                $('#lbl-vueltas').innerHTML = `<span class="text-danger">Faltan: ${fmt(total)}</span>`;
            }
        }
    }

    // ==================== EVENTOS UI ====================
    $('#metodo-pago').addEventListener('change', function() {
        const p = pestanaActual();
        const metodoNuevo = this.value;
        p.metodoPago = metodoNuevo;

        if (metodoNuevo !== 'credito') {
            p.pagosMetodos = [metodoNuevo, metodoNuevo, metodoNuevo];
            ['#pago-metodo-1', '#pago-metodo-2', '#pago-metodo-3'].forEach(sel => {
                const el = $(sel);
                if (el) el.value = metodoNuevo;
            });
        }

        guardarEstado();
        renderTotales();
    });

    $('#bolsas').addEventListener('input', function() {
        pestanaActual().bolsas = parseInt(this.value) || 0;
        guardarEstado();
        renderTotales();
    });

    ['#pago-1', '#pago-2', '#pago-3'].forEach((sel, idx) => {
        const el = $(sel);
        if (!el) return;
        el.addEventListener('input', function() {
            const p = pestanaActual();
            if (!Array.isArray(p.pagos)) p.pagos = ['', '', ''];
            p.pagos[idx] = this.value;
            guardarEstado();
            renderTotales();
        });
    });

    ['#pago-metodo-1', '#pago-metodo-2', '#pago-metodo-3'].forEach((sel, idx) => {
        const el = $(sel);
        if (!el) return;
        el.addEventListener('change', function() {
            const p = pestanaActual();
            if (!Array.isArray(p.pagosMetodos)) p.pagosMetodos = ['efectivo', 'efectivo', 'efectivo'];
            p.pagosMetodos[idx] = this.value;
            guardarEstado();
            renderTotales();
        });
    });

    const switchPrecio = $('#switch-precio-libre');
    if (switchPrecio) {
        switchPrecio.addEventListener('change', function() {
            pestanaActual().modoPrecioLibre = this.checked;
            guardarEstado();
            renderCarrito();
        });
    }

    $('#cliente-nombre').addEventListener('input', function() {
        pestanaActual().cliente.nombre = this.value;
        guardarEstado();
    });
    $('#cliente-documento').addEventListener('input', function() {
        pestanaActual().cliente.documento = this.value;
        guardarEstado();
    });
    $('#cliente-telefono').addEventListener('input', function() {
        pestanaActual().cliente.telefono = this.value;
        guardarEstado();
    });
    $('#cliente-direccion').addEventListener('input', function() {
        pestanaActual().cliente.direccion = this.value;
        guardarEstado();
    });

    // ==================== FINALIZAR ====================
    $('#btn-finalizar').addEventListener('click', async function() {
        const p = pestanaActual();
        const carrito = p.carrito;

        if (carrito.length === 0) {
            alert('El carrito está vacío');
            return;
        }

        const nombre = p.cliente.nombre.trim();
        if (!nombre) {
            alert('Ingresa el nombre del cliente');
            $('#cliente-nombre').focus();
            return;
        }

        const metodo = p.metodoPago || 'efectivo';
        const bolsas = parseInt(p.bolsas) || 0;
        const pagos = p.pagos || ['', '', ''];
        const pagosMetodos = p.pagosMetodos || ['efectivo', 'efectivo', 'efectivo'];
        const valorPagado = (parseFloat(pagos[0]) || 0) + (parseFloat(pagos[1]) || 0) + (parseFloat(pagos[2]) || 0);

        const listaPagos = [];
        for (let i = 0; i < 3; i++) {
            const monto = parseFloat(pagos[i]) || 0;
            if (monto > 0) {
                listaPagos.push({
                    metodo: pagosMetodos[i] || 'efectivo',
                    monto: monto,
                });
            }
        }

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

        const tienePrecioManual = carrito.some(it => it.precio_editado === true);

        const payload = {
            cliente: {
                nombre: nombre,
                documento: p.cliente.documento.trim(),
                telefono: p.cliente.telefono.trim(),
                direccion: p.cliente.direccion.trim(),
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
            pagos: listaPagos,
            precio_manual: tienePrecioManual,
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
                p.carrito = [];
                p.cliente = { nombre: '', documento: '', telefono: '', direccion: '' };
                p.metodoPago = 'efectivo';
                p.bolsas = 0;
                p.pagos = ['', '', ''];
                p.pagosMetodos = ['efectivo', 'efectivo', 'efectivo'];
                p.modoPrecioLibre = false;
                guardarEstado();

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
        const p = pestanaActual();
        if (p.carrito.length > 0 && !confirm('¿Limpiar la venta de esta pestaña?')) return;

        p.carrito = [];
        p.cliente = { nombre: '', documento: '', telefono: '', direccion: '' };
        p.metodoPago = 'efectivo';
        p.bolsas = 0;
        p.pagos = ['', '', ''];
        p.pagosMetodos = ['efectivo', 'efectivo', 'efectivo'];
        p.modoPrecioLibre = false;
        guardarEstado();
        renderPestanas();
        cargarPestanaEnUI();
        inputBuscar.focus();
    });

    // ==================== SELECTOR DE TIENDA ====================
    const selectorTienda = $('#selector-tienda');
    if (selectorTienda) {
        selectorTienda.addEventListener('change', function() {
            if (confirm('Cambiar de tienda cerrará las pestañas actuales. ¿Continuar?')) {
                localStorage.removeItem(STORAGE_KEY);
                const url = new URL(window.location.href);
                url.searchParams.set('tienda', this.value);
                window.location.href = url.toString();
            }
        });
    }

    // Quitar el resaltado (active) de la lista de búsqueda si se hace clic afuera
    document.addEventListener('click', function(e) {
        if (inputBuscar && !inputBuscar.contains(e.target) && !resultados.contains(e.target)) {
            const items = resultados.querySelectorAll('.list-group-item');
            items.forEach(it => it.classList.remove('active'));
            indiceActivo = -1;
        }
    });


    // ==================== INIT ====================
    cargarEstado();
    renderPestanas();
    cargarPestanaEnUI();
    inputBuscar.focus();

})();