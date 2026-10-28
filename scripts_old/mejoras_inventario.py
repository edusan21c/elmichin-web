# scripts/mejoras_inventario.py
# Actualiza el sidebar y agrega el modal de stock rapido en la lista.
# Ejecutar UNA VEZ: python scripts\mejoras_inventario.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== SIDEBAR ACTUALIZADO ====================
ARCHIVOS['app/templates/layout/sidebar.html'] = '''<nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar border-end" style="min-height: calc(100vh - 56px);">
    <div class="position-sticky pt-3">
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link {% if request.endpoint == 'dashboard.index' %}active{% endif %}"
                   href="{{ url_for('dashboard.index') }}">
                    <i class="bi bi-house-door"></i> Inicio
                </a>
            </li>

            {% if current_user.rol in ('admin', 'programador') %}
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'inventario' %}active{% endif %}"
                   href="{{ url_for('inventario.lista') }}">
                    <i class="bi bi-box-seam"></i> Inventario
                </a>
            </li>
            {% endif %}

            {% if current_user.rol in ('admin', 'programador', 'operario') %}
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-receipt"></i> Facturación
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-lightning-charge"></i> Venta Rápida
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-graph-up"></i> Reportes
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}

            {% if current_user.rol in ('admin', 'programador') %}
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-bar-chart"></i> Estadísticas
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}

            {% if current_user.rol == 'programador' %}
            <li class="nav-item mt-3">
                <small class="text-muted ps-3">ADMINISTRACIÓN</small>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-people"></i> Usuarios
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-gear"></i> Configuración
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}
        </ul>
    </div>
</nav>
'''

# ==================== LISTA CON MODAL DE STOCK ====================
ARCHIVOS['app/templates/inventario/lista.html'] = '''{% extends 'base.html' %}
{% block titulo %}Inventario{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-box-seam"></i> Inventario
        {% if current_user.es_programador() and tiendas|length > 1 %}
            <small class="text-muted">- Viendo:
                <select id="selector-tienda" class="form-select form-select-sm d-inline-block" style="width:auto;">
                    {% for t in tiendas %}
                        <option value="{{ t.id }}" {% if t.id == tienda_id %}selected{% endif %}>{{ t.nombre }}</option>
                    {% endfor %}
                </select>
            </small>
        {% endif %}
    </h1>
    {% if puede_editar %}
        <a href="{{ url_for('inventario.nuevo') }}" class="btn btn-primary">
            <i class="bi bi-plus-circle"></i> Nuevo producto
        </a>
    {% endif %}
</div>

<!-- Barra de búsqueda -->
<div class="card mb-3">
    <div class="card-body py-2">
        <form method="GET" class="row g-2 align-items-center" id="form-busqueda">
            <div class="col-md-8">
                <div class="input-group">
                    <span class="input-group-text"><i class="bi bi-search"></i></span>
                    <input type="text" name="q" id="input-busqueda" class="form-control"
                           placeholder="Buscar por nombre o código de barras..."
                           value="{{ busqueda }}" autofocus autocomplete="off">
                    {% if busqueda %}
                        <a href="{{ url_for('inventario.lista') }}" class="btn btn-outline-secondary">
                            <i class="bi bi-x"></i> Limpiar
                        </a>
                    {% endif %}
                    <button type="submit" class="btn btn-primary">Buscar</button>
                </div>
            </div>
            <div class="col-md-4 text-end">
                <span class="text-muted small">
                    {{ paginacion.total }} producto{{ 's' if paginacion.total != 1 }}
                </span>
            </div>
        </form>
    </div>
</div>

<!-- Tabla de productos -->
<div class="card">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th style="width: 60px;">ID</th>
                    <th>Producto</th>
                    <th style="width: 120px;">Código</th>
                    <th style="width: 100px;" class="text-end">P. Venta</th>
                    <th style="width: 120px;" class="text-center">Stock</th>
                    <th style="width: 170px;" class="text-end">Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for item in productos %}
                    {% set p = item.producto %}
                    {% set pres = item.presentacion %}
                    {% set stock = item.stock %}
                    <tr>
                        <td class="text-muted small">{{ p.id }}</td>
                        <td>
                            <div class="fw-semibold">{{ p.nombre }}</div>
                            {% if p.categoria %}
                                <span class="badge bg-secondary-subtle text-secondary">{{ p.categoria }}</span>
                            {% endif %}
                        </td>
                        <td class="text-muted small">{{ p.codigo_barras or '-' }}</td>
                        <td class="text-end fw-semibold">
                            {% if pres %}
                                ${{ "{:,.0f}".format(item.precio_venta) }}
                            {% else %}
                                <span class="text-muted">-</span>
                            {% endif %}
                        </td>
                        <td class="text-center">
                            {% if stock == 0 %}
                                <span class="badge bg-danger">🔴 Agotado</span>
                            {% elif stock <= 5 %}
                                <span class="badge bg-warning text-dark">🟡 {{ stock }}</span>
                            {% else %}
                                <span class="badge bg-success">🟢 {{ stock }}</span>
                            {% endif %}
                        </td>
                        <td class="text-end">
                            {% if puede_editar %}
                                <button type="button"
                                        class="btn btn-sm btn-outline-success btn-stock"
                                        title="Actualizar stock"
                                        data-id="{{ p.id }}"
                                        data-nombre="{{ p.nombre }}"
                                        data-stock="{{ stock }}">
                                    <i class="bi bi-plus-slash-minus"></i>
                                </button>
                                <a href="{{ url_for('inventario.editar', producto_id=p.id) }}"
                                   class="btn btn-sm btn-outline-primary" title="Editar">
                                    <i class="bi bi-pencil"></i>
                                </a>
                            {% endif %}
                            {% if current_user.es_programador() %}
                                <form method="POST"
                                      action="{{ url_for('inventario.eliminar', producto_id=p.id) }}"
                                      class="d-inline"
                                      onsubmit="return confirm('¿Eliminar {{ p.nombre }}? Esta acción es irreversible.');">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                    <button type="submit" class="btn btn-sm btn-outline-danger" title="Eliminar">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </form>
                            {% endif %}
                        </td>
                    </tr>
                {% else %}
                    <tr>
                        <td colspan="6" class="text-center py-5 text-muted">
                            <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                            {% if busqueda %}
                                No hay productos que coincidan con "{{ busqueda }}".
                            {% else %}
                                No hay productos todavía. {% if puede_editar %}Crea el primero con el botón "Nuevo producto".{% endif %}
                            {% endif %}
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Paginación -->
{% if paginacion.pages > 1 %}
    <nav class="mt-3">
        <ul class="pagination justify-content-center">
            <li class="page-item {% if not paginacion.has_prev %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('inventario.lista', page=paginacion.prev_num, q=busqueda, tienda=tienda_id) }}">
                    &laquo; Anterior
                </a>
            </li>
            {% for num in paginacion.iter_pages(left_edge=1, left_current=2, right_current=2, right_edge=1) %}
                {% if num %}
                    <li class="page-item {% if num == paginacion.page %}active{% endif %}">
                        <a class="page-link" href="{{ url_for('inventario.lista', page=num, q=busqueda, tienda=tienda_id) }}">{{ num }}</a>
                    </li>
                {% else %}
                    <li class="page-item disabled"><span class="page-link">…</span></li>
                {% endif %}
            {% endfor %}
            <li class="page-item {% if not paginacion.has_next %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('inventario.lista', page=paginacion.next_num, q=busqueda, tienda=tienda_id) }}">
                    Siguiente &raquo;
                </a>
            </li>
        </ul>
        <p class="text-center text-muted small">
            Mostrando {{ productos|length }} de {{ paginacion.total }} productos
            (página {{ paginacion.page }} de {{ paginacion.pages }})
        </p>
    </nav>
{% endif %}

<!-- ==================== MODAL DE STOCK ==================== -->
<div class="modal fade" id="modalStock" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <form method="POST" id="form-stock" action="">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <div class="modal-header bg-success text-white">
                    <h5 class="modal-title">
                        <i class="bi bi-plus-slash-minus"></i> Actualizar stock
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="mb-3">
                        <strong id="stock-nombre"></strong>
                    </p>
                    <label class="form-label">Cantidad en stock</label>
                    <div class="input-group input-group-lg">
                        <span class="input-group-text"><i class="bi bi-box"></i></span>
                        <input type="number" name="cantidad" id="stock-cantidad"
                               class="form-control" min="0" required autofocus>
                    </div>
                    <small class="text-muted">Escribe la cantidad total (no la suma).</small>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                    <button type="submit" class="btn btn-success">
                        <i class="bi bi-check-circle"></i> Guardar
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
// ==================== SELECTOR DE TIENDA ====================
{% if current_user.es_programador() and tiendas|length > 1 %}
document.getElementById('selector-tienda').addEventListener('change', function() {
    const url = new URL(window.location.href);
    url.searchParams.set('tienda', this.value);
    url.searchParams.delete('page');
    window.location.href = url.toString();
});
{% endif %}

// ==================== MODAL DE STOCK ====================
document.querySelectorAll('.btn-stock').forEach(function(btn) {
    btn.addEventListener('click', function() {
        const id = this.dataset.id;
        const nombre = this.dataset.nombre;
        const stock = this.dataset.stock;

        document.getElementById('form-stock').action = '/inventario/' + id + '/stock';
        document.getElementById('stock-nombre').textContent = nombre;
        document.getElementById('stock-cantidad').value = stock;

        const modal = new bootstrap.Modal(document.getElementById('modalStock'));
        modal.show();
    });
});
</script>
{% endblock %}
'''


def main():
    print(f'Actualizando archivos en: {RAIZ}')
    print('-' * 60)
    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')
    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos actualizados.')


if __name__ == '__main__':
    main()