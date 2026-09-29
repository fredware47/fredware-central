// ============================================================
// FREDWARE UNIFIED - NÚCLEO COMPARTIDO v3
// Fecha: 2026-09-29
// ============================================================
// Cambios respecto a v2:
//   ✅ Nuevo módulo fredware.productos (para inventario full)
//      - cargarProductos()
//      - buscarProducto()
//      - crearProducto()
//      - comboboxEstricto()
//      - mostrarModalCrearProducto()
// ============================================================

class FredwareUnified {
    constructor() {
        // ============================================================
        // CONFIGURACIÓN
        // ============================================================
        this.SUPABASE_URL = "https://bhyprsjokwgazzzlfnbf.supabase.co";
        this.SUPABASE_KEY = "sb_publishable_i-g5o4tO1R8u6Fe7Fc2Q8Q_V_FV271y";

        this.supabase = supabase.createClient(
            this.SUPABASE_URL,
            this.SUPABASE_KEY
        );

        // ============================================================
        // ESTADO GLOBAL
        // ============================================================
        this.state = {
            // Datos crudos
            recepciones: [],
            statsDia: [],
            comprasMes: [],
            escandallos: [],
            inventario: [],
            productos: [],          // 🆕 productos de productos_raciones

            // Estadísticas calculadas
            estadisticas: {
                totalHoy: 0,
                totalSemana: 0,
                totalMes: 0,
                mermaPromedio: 0,
                productosCriticos: [],
                alertas: [],
                ultimaRecepcion: null,
                fechaCalculo: null
            },

            // Meta
            ultimaActualizacion: null,
            version: '3.0',
            inicializado: false
        };

        this.subscribers = [];
        this.channel = null;
        this._pollingInterval = null;

        this.inicializar();
    }

    // ============================================================
    // INICIALIZACIÓN
    // ============================================================
    async inicializar() {
        try {
            console.log('🚀 [Core v3] Iniciando Fredware Unified...');

            this.setupBroadcast();
            await this.recargarTodo();
            this.iniciarPolling();

            this.state.inicializado = true;
            console.log('✅ [Core v3] Fredware Unified inicializado correctamente');
        } catch (error) {
            console.error('❌ [Core v3] Error inicializando:', error);
        }
    }

    setupBroadcast() {
        console.log('📡 [Core v3] Configurando canal fredware-unified...');
        this.channel = this.supabase.channel('fredware-unified', {
            config: { broadcast: { self: true } }
        });

        this.channel
            .on('broadcast', { event: 'actualizar' }, ({ payload }) => {
                console.log('📨 [Core v3] Broadcast recibido:', payload);
                this.handleBroadcast(payload);
            })
            .on('postgres_changes', {
                event: 'INSERT',
                schema: 'public',
                table: 'recepciones'
            }, (payload) => {
                console.log('🆕 [Core v3] Nueva recepción detectada:', payload.new?.producto);
                this.recargarTodo();
            })
            .subscribe((status) => {
                console.log('📡 [Core v3] Estado canal:', status);
            });
    }

    handleBroadcast(payload) {
        const { tipo, data } = payload || {};

        switch (tipo) {
            case 'nueva_recepcion':
            case 'nuevo_pedido':
            case 'cierre_inventario':
                this.recargarTodo();
                break;

            case 'etiqueta_impresa':
                // Solo informativo
                break;

            case 'producto_nuevo':
                console.log('🆕 [Core v3] Producto nuevo creado:', data?.nombre);
                this.recargarTodo();
                break;

            default:
                console.log('ℹ️ [Core v3] Evento desconocido:', tipo);
        }
    }

    // ============================================================
    // CARGA DE DATOS
    // ============================================================
    async recargarTodo() {
        try {
            await Promise.all([
                this.cargarRecepciones(),
                this.cargarStatsDia(),
                this.cargarComprasMes(),
                this.cargarEscandallos(),
                this.cargarInventario(),
                this.cargarProductos()    // 🆕
            ]);

            this.calcularEstadisticas();
            this.state.ultimaActualizacion = new Date();
            this.notifySubscribers();

            return this.state;
        } catch (error) {
            console.error('❌ [Core v3] Error en recargarTodo:', error);
            throw error;
        }
    }

    async cargarRecepciones() {
        try {
            const { data, error } = await this.supabase
                .from('v_recepciones_recientes')
                .select('*')
                .limit(500);

            if (error) throw error;

            this.state.recepciones = data || [];
            console.log(`✅ [Core v3] ${this.state.recepciones.length} recepciones cargadas`);
        } catch (error) {
            console.error('❌ [Core v3] Error cargando recepciones:', error);
            this.state.recepciones = [];
        }
    }

    async cargarStatsDia() {
        try {
            const { data, error } = await this.supabase
                .from('v_recepciones_por_dia')
                .select('*')
                .limit(30);

            if (error) throw error;

            this.state.statsDia = data || [];
            console.log(`✅ [Core v3] ${this.state.statsDia.length} días de estadísticas`);
        } catch (error) {
            console.error('❌ [Core v3] Error cargando stats:', error);
            this.state.statsDia = [];
        }
    }

    async cargarComprasMes() {
        try {
            const { data, error } = await this.supabase
                .from('v_compras_por_mes')
                .select('*')
                .limit(200);

            if (error) throw error;

            this.state.comprasMes = data || [];
            console.log(`✅ [Core v3] ${this.state.comprasMes.length} filas de compras`);
        } catch (error) {
            console.error('❌ [Core v3] Error cargando compras:', error);
            this.state.comprasMes = [];
        }
    }

    async cargarEscandallos() {
        try {
            const { data, error } = await this.supabase
                .from('maestro_escandallos')
                .select('*')
                .order('nombre_articulo', { ascending: true });

            if (error) throw error;

            this.state.escandallos = data || [];
            console.log(`✅ [Core v3] ${this.state.escandallos.length} escandallos`);
        } catch (error) {
            console.error('❌ [Core v3] Error cargando escandallos:', error);
            this.state.escandallos = [];
        }
    }

    async cargarInventario() {
        try {
            const { data, error } = await this.supabase
                .from('inventario_mensual')
                .select('*, maestro_escandallos(*)')
                .order('mes_anio', { ascending: false })
                .limit(100);

            if (error) throw error;

            this.state.inventario = data || [];
            console.log(`✅ [Core v3] ${this.state.inventario.length} filas de inventario`);
        } catch (error) {
            console.error('❌ [Core v3] Error cargando inventario:', error);
            this.state.inventario = [];
        }
    }

    // 🆕 Cargar productos de productos_raciones
    async cargarProductos() {
        try {
            const { data, error } = await this.supabase
                .from('productos_raciones')
                .select('*')
                .order('nombre_articulo', { ascending: true });

            if (error) throw error;

            this.state.productos = data || [];
            console.log(`✅ [Core v3] ${this.state.productos.length} productos cargados`);
        } catch (error) {
            console.error('❌ [Core v3] Error cargando productos:', error);
            this.state.productos = [];
        }
    }

    // ============================================================
    // ESTADÍSTICAS
    // ============================================================
    calcularEstadisticas() {
        const hoy = new Date().toISOString().split('T')[0];

        let totalHoy = 0;
        this.state.recepciones.forEach(r => {
            const fecha = (r.fecha_registro || '').split('T')[0];
            if (fecha === hoy) totalHoy++;
        });

        let totalSemana = 0;
        const hace7dias = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
        this.state.recepciones.forEach(r => {
            const fecha = new Date(r.fecha_registro || 0);
            if (fecha >= hace7dias) totalSemana++;
        });

        let totalMes = 0;
        const mesActual = new Date().getMonth();
        const añoActual = new Date().getFullYear();
        this.state.recepciones.forEach(r => {
            const fecha = new Date(r.fecha_registro || 0);
            if (fecha.getMonth() === mesActual && fecha.getFullYear() === añoActual) {
                totalMes++;
            }
        });

        const ultimaRecepcion = this.state.recepciones[0] || null;

        let mermaTotal = 0, countMerma = 0;
        this.state.escandallos.forEach(e => {
            if (e.porcentaje_merma != null) {
                mermaTotal += parseFloat(e.porcentaje_merma) || 0;
                countMerma++;
            }
        });

        const productosCriticos = this.state.escandallos
            .filter(e => (parseFloat(e.porcentaje_merma) || 0) > 20)
            .map(e => e.nombre_articulo);

        const alertas = this.generarAlertas();

        this.state.estadisticas = {
            totalHoy,
            totalSemana,
            totalMes,
            mermaPromedio: countMerma > 0 ? mermaTotal / countMerma : 0,
            productosCriticos,
            alertas,
            ultimaRecepcion,
            fechaCalculo: new Date().toISOString()
        };
    }

    generarAlertas() {
        const alertas = [];

        this.state.escandallos.forEach(e => {
            const merma = parseFloat(e.porcentaje_merma) || 0;
            if (merma > 30) {
                alertas.push({
                    tipo: 'warning',
                    mensaje: `⚠️ ${e.nombre_articulo} tiene merma del ${merma}%`,
                    prioridad: 'alta'
                });
            }
        });

        const inventarioReciente = this.state.inventario.slice(0, 20);
        inventarioReciente.forEach(item => {
            const stock = parseFloat(item.stock_fisico_final) || 0;
            if (stock > 0 && stock < 10) {
                alertas.push({
                    tipo: 'info',
                    mensaje: `📦 Stock bajo: ${item.articulo_id} (${stock})`,
                    prioridad: 'media'
                });
            }
        });

        return alertas;
    }

    // ============================================================
    // ESCRITURA — registrarRecepcion()
    // ============================================================
    async registrarRecepcion(datos) {
        if (!datos || !datos.producto) {
            throw new Error('Datos inválidos: producto es obligatorio');
        }

        const ahora = new Date();
        const id = datos.id || `REC_${ahora.getTime()}_${String(datos.producto).substring(0, 6).toUpperCase()}`;

        const registro = {
            id,
            producto: String(datos.producto).toUpperCase(),
            proveedor: String(datos.proveedor || 'S/P').toUpperCase(),
            cantidad: parseInt(datos.cantidad) || 1,
            unidad: String(datos.unidad || 'UN').toUpperCase(),
            fecha_registro: datos.fecha_registro || ahora.toISOString(),
            fecha_recibido: datos.fecha_recibido || ahora.toISOString(),
            observaciones: datos.observaciones || '',
            temperatura: datos.temperatura != null ? parseFloat(datos.temperatura) : null,
            conservacion: datos.conservacion || 'NEVERA',
            autorizado_por: datos.autorizado_por || 'SISTEMA',
            origen: datos.origen || 'COMPRAS',
            metadata: datos.metadata || {}
        };

        try {
            const { data, error } = await this.supabase
                .from('recepciones')
                .insert([registro])
                .select()
                .single();

            if (error) throw error;

            console.log('✅ [Core v3] Recepción registrada:', registro.id);

            await this.broadcastEvent('nueva_recepcion', data || registro);
            await this.recargarTodo();

            return data || registro;
        } catch (error) {
            console.error('❌ [Core v3] Error registrando recepción:', error);
            throw error;
        }
    }

    // ============================================================
    // BROADCAST
    // ============================================================
    async broadcastEvent(tipo, data) {
        try {
            await this.channel.send({
                type: 'broadcast',
                event: 'actualizar',
                payload: { tipo, data, timestamp: new Date().toISOString() }
            });
            console.log(`📡 [Core v3] Broadcast enviado: ${tipo}`);
        } catch (error) {
            console.error('❌ [Core v3] Error enviando broadcast:', error);
        }
    }

    // ============================================================
    // SUBSCRIPCIÓN
    // ============================================================
    subscribe(callback) {
        this.subscribers.push(callback);

        try {
            callback(this.state);
        } catch (error) {
            console.error('❌ [Core v3] Error en callback inicial:', error);
        }

        return () => {
            this.subscribers = this.subscribers.filter(cb => cb !== callback);
        };
    }

    notifySubscribers() {
        this.subscribers.forEach(callback => {
            try {
                callback(this.state);
            } catch (error) {
                console.error('❌ [Core v3] Error en subscriber:', error);
            }
        });
    }

    // ============================================================
    // POLLING INTERNO
    // ============================================================
    iniciarPolling() {
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
        }
        this._pollingInterval = setInterval(() => {
            if (this.state.inicializado) {
                this.recargarTodo().catch(err => {
                    console.warn('⚠️ [Core v3] Error en polling:', err);
                });
            }
        }, 60000);
        console.log('⏱️ [Core v3] Polling cada 60s iniciado');
    }

    detenerPolling() {
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
            this._pollingInterval = null;
            console.log('⏱️ [Core v3] Polling detenido');
        }
    }

    // ============================================================
    // GETTERS
    // ============================================================
    getEstadoCompleto() { return this.state; }
    getRecepciones() { return this.state.recepciones; }
    getEstadisticas() { return this.state.estadisticas; }
    getProductos() { return this.state.productos; }

    // ============================================================
    // UTILIDADES EXPORTADAS
    // ============================================================

    ui = {
        toast: (mensaje, tipo = 'success') => {
            const colores = {
                success: { bg: '#10b981', icon: '✅' },
                error: { bg: '#ef4444', icon: '❌' },
                warning: { bg: '#f59e0b', icon: '⚠️' },
                info: { bg: '#2563eb', icon: 'ℹ️' }
            };
            const c = colores[tipo] || colores.success;

            let container = document.getElementById('fredware-toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'fredware-toast-container';
                container.style.cssText = 'position:fixed; bottom:20px; right:20px; z-index:100000; display:flex; flex-direction:column; gap:8px; pointer-events:none;';
                document.body.appendChild(container);
            }

            const t = document.createElement('div');
            t.style.cssText = `background:${c.bg}; color:white; padding:12px 18px; border-radius:10px; font-weight:700; font-size:14px; box-shadow:0 4px 12px rgba(0,0,0,0.15); opacity:0; transform:translateY(10px); transition:all 0.3s; font-family:-apple-system,sans-serif; max-width:320px;`;
            t.textContent = `${c.icon} ${mensaje}`;
            container.appendChild(t);

            requestAnimationFrame(() => {
                t.style.opacity = '1';
                t.style.transform = 'translateY(0)';
            });

            setTimeout(() => {
                t.style.opacity = '0';
                t.style.transform = 'translateY(10px)';
                setTimeout(() => t.remove(), 300);
            }, 3500);
        }
    };

    util = {
        escapeHtml: (texto) => {
            if (texto == null) return '';
            const div = document.createElement('div');
            div.textContent = String(texto);
            return div.innerHTML;
        },

        formatearFecha: (fecha) => {
            if (!fecha) return 'S/F';
            try {
                const d = new Date(fecha);
                if (isNaN(d)) return String(fecha);
                return d.toLocaleDateString('es-ES', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } catch { return String(fecha); }
        },

        formatearFechaCorta: (fecha) => {
            if (!fecha) return 'S/F';
            try {
                const d = new Date(fecha);
                if (isNaN(d)) return String(fecha);
                return d.toLocaleDateString('es-ES', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric'
                });
            } catch { return String(fecha); }
        },

        esHoy: (fecha) => {
            if (!fecha) return false;
            const hoy = new Date().toISOString().split('T')[0];
            return String(fecha).startsWith(hoy);
        },

        esEstaSemana: (fecha) => {
            if (!fecha) return false;
            try {
                const f = new Date(fecha);
                const ahora = new Date();
                const inicioSemana = new Date(ahora);
                inicioSemana.setDate(ahora.getDate() - ahora.getDay());
                inicioSemana.setHours(0, 0, 0, 0);
                const finSemana = new Date(inicioSemana);
                finSemana.setDate(inicioSemana.getDate() + 7);
                return f >= inicioSemana && f < finSemana;
            } catch { return false; }
        },

        esEsteMes: (fecha) => {
            if (!fecha) return false;
            try {
                const f = new Date(fecha);
                const ahora = new Date();
                return f.getMonth() === ahora.getMonth() &&
                       f.getFullYear() === ahora.getFullYear();
            } catch { return false; }
        }
    };

    // ============================================================
    // 🆕 MÓDULO: PRODUCTOS
    // Sistema de autocompletado estricto para inputs de producto
    // ============================================================
    productos = {
        // Cache de productos (se rellena al llamar a cargar())
        lista: [],

        // ============================================================
        // Cargar productos desde productos_raciones
        // ============================================================
        async cargar() {
            try {
                const { data, error } = await window.fredware.supabase
                    .from('productos_raciones')
                    .select('id, nombre_articulo, zona, tipo, categoria, unidad_compra, unidad_racion, estado')
                    .order('nombre_articulo', { ascending: true });

                if (error) throw error;

                this.lista = data || [];
                console.log(`📦 [Productos] ${this.lista.length} productos cargados`);
                return this.lista;
            } catch (error) {
                console.error('❌ [Productos] Error cargando:', error);
                this.lista = [];
                return [];
            }
        },

        // ============================================================
        // Buscar producto por nombre usando la función de Supabase
        // ============================================================
        async buscar(texto) {
            if (!texto || texto.trim().length < 2) return null;

            try {
                const { data, error } = await window.fredware.supabase
                    .rpc('buscar_producto_exacto', { p_texto: texto });

                if (error) throw error;
                return data;
            } catch (error) {
                console.error('❌ [Productos] Error buscando:', error);
                return null;
            }
        },

        // ============================================================
        // Filtrar productos de la caché por texto
        // ============================================================
        filtrar(texto, opciones = {}) {
            if (!texto || texto.length < 2) return [];

            const textoUpper = texto.toUpperCase();
            const zonas = opciones.zonas || null;

            let resultados = this.lista.filter(p => 
                p.nombre_articulo.toUpperCase().includes(textoUpper)
            );

            if (zonas) {
                resultados = resultados.filter(p => zonas.includes(p.zona));
            }

            // Ordenar: primero los que empiezan con el texto
            resultados.sort((a, b) => {
                const aStarts = a.nombre_articulo.toUpperCase().startsWith(textoUpper);
                const bStarts = b.nombre_articulo.toUpperCase().startsWith(textoUpper);
                if (aStarts && !bStarts) return -1;
                if (!aStarts && bStarts) return 1;
                return a.nombre_articulo.localeCompare(b.nombre_articulo);
            });

            return resultados.slice(0, 10);
        },

        // ============================================================
        // Crear producto nuevo
        // ============================================================
        async crear(nombre, unidadCompra = 'UNIDADES', unidadRacion = 'UNIDAD') {
            if (!nombre || !nombre.trim()) {
                throw new Error('Nombre obligatorio');
            }

            try {
                const { data, error } = await window.fredware.supabase
                    .rpc('crear_producto_si_no_existe', {
                        p_nombre: nombre.trim().toUpperCase(),
                        p_unidad_compra: unidadCompra,
                        p_unidad_racion: unidadRacion
                    });

                if (error) throw error;

                console.log('✅ [Productos] Producto creado/existente:', data);

                // Recargar la lista
                await this.cargar();

                // Broadcast al núcleo
                await window.fredware.broadcastEvent('producto_nuevo', {
                    id: data,
                    nombre: nombre.trim().toUpperCase()
                });

                return data;
            } catch (error) {
                console.error('❌ [Productos] Error creando:', error);
                throw error;
            }
        },

        // ============================================================
        // Modal para crear producto nuevo
        // ============================================================
        async mostrarModalCrearProducto(nombrePropuesto = '') {
            return new Promise((resolve) => {
                // Crear overlay
                const overlay = document.createElement('div');
                overlay.id = 'fredware-modal-crear-producto';
                overlay.style.cssText = `
                    position: fixed;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background: rgba(0,0,0,0.6);
                    backdrop-filter: blur(4px);
                    z-index: 100001;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                `;

                overlay.innerHTML = `
                    <div style="
                        background: white;
                        border-radius: 16px;
                        padding: 24px;
                        max-width: 500px;
                        width: 100%;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        font-family: -apple-system, sans-serif;
                    ">
                        <h3 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 900; color: #1e293b;">
                            ➕ Crear producto nuevo
                        </h3>
                        <p style="margin: 0 0 20px 0; font-size: 13px; color: #64748b;">
                            Este producto se añadirá al catálogo como <strong>pendiente de configurar</strong>. El jefe lo ajustará después.
                        </p>

                        <label style="display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 4px; text-transform: uppercase;">
                            Nombre del producto *
                        </label>
                        <input 
                            type="text" 
                            id="nuevo-prod-nombre" 
                            value="${window.fredware.util.escapeHtml(nombrePropuesto)}"
                            placeholder="Ej: CROISSANT HOSTELERO"
                            style="
                                width: 100%;
                                padding: 12px 14px;
                                border: 2px solid #cbd5e1;
                                border-radius: 10px;
                                font-size: 15px;
                                font-weight: 700;
                                text-transform: uppercase;
                                margin-bottom: 16px;
                                box-sizing: border-box;
                                outline: none;
                            "
                        >

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
                            <div>
                                <label style="display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 4px; text-transform: uppercase;">
                                    Unidad de compra
                                </label>
                                <select id="nuevo-prod-u-compra" style="
                                    width: 100%;
                                    padding: 10px 12px;
                                    border: 2px solid #cbd5e1;
                                    border-radius: 10px;
                                    font-size: 14px;
                                    background: white;
                                    box-sizing: border-box;
                                    outline: none;
                                ">
                                    <option value="UNIDADES">Unidades</option>
                                    <option value="KG">Kilogramos (kg)</option>
                                    <option value="L">Litros (L)</option>
                                    <option value="CAJAS">Cajas</option>
                                    <option value="BOTES">Botes</option>
                                    <option value="PAQUETES">Paquetes</option>
                                </select>
                            </div>
                            <div>
                                <label style="display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 4px; text-transform: uppercase;">
                                    Unidad de ración
                                </label>
                                <select id="nuevo-prod-u-racion" style="
                                    width: 100%;
                                    padding: 10px 12px;
                                    border: 2px solid #cbd5e1;
                                    border-radius: 10px;
                                    font-size: 14px;
                                    background: white;
                                    box-sizing: border-box;
                                    outline: none;
                                ">
                                    <option value="UNIDAD">Unidad</option>
                                    <option value="RACIÓN">Ración</option>
                                    <option value="PLATO">Plato</option>
                                    <option value="TAPA">Tapa</option>
                                    <option value="PORCIÓN">Porción</option>
                                </select>
                            </div>
                        </div>

                        <div style="display: flex; gap: 12px; justify-content: flex-end;">
                            <button 
                                id="btn-cancelar-crear-producto"
                                style="
                                    padding: 12px 24px;
                                    border: 2px solid #cbd5e1;
                                    background: white;
                                    border-radius: 10px;
                                    font-weight: 700;
                                    font-size: 14px;
                                    color: #475569;
                                    cursor: pointer;
                                "
                            >
                                Cancelar
                            </button>
                            <button 
                                id="btn-crear-producto"
                                style="
                                    padding: 12px 24px;
                                    border: none;
                                    background: #10b981;
                                    color: white;
                                    border-radius: 10px;
                                    font-weight: 700;
                                    font-size: 14px;
                                    cursor: pointer;
                                    box-shadow: 0 2px 8px rgba(16,185,129,0.3);
                                "
                            >
                                ➕ Crear producto
                            </button>
                        </div>

                        <div id="error-crear-producto" style="display: none; margin-top: 12px; padding: 10px; background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; color: #991b1b; font-size: 13px;"></div>
                    </div>
                `;

                document.body.appendChild(overlay);

                const inputNombre = document.getElementById('nuevo-prod-nombre');
                const selectUCompra = document.getElementById('nuevo-prod-u-compra');
                const selectURacion = document.getElementById('nuevo-prod-u-racion');
                const btnCancelar = document.getElementById('btn-cancelar-crear-producto');
                const btnCrear = document.getElementById('btn-crear-producto');
                const errorDiv = document.getElementById('error-crear-producto');

                // Focus en el input
                setTimeout(() => {
                    inputNombre.focus();
                    inputNombre.select();
                }, 100);

                // Botón cancelar
                btnCancelar.onclick = () => {
                    overlay.remove();
                    resolve(null);
                };

                // Botón crear
                btnCrear.onclick = async () => {
                    const nombre = inputNombre.value.trim();
                    if (!nombre) {
                        errorDiv.textContent = '⚠️ El nombre es obligatorio';
                        errorDiv.style.display = 'block';
                        return;
                    }

                    btnCrear.disabled = true;
                    btnCrear.textContent = '⏳ Creando...';

                    try {
                        const idCreado = await this.crear(
                            nombre,
                            selectUCompra.value,
                            selectURacion.value
                        );

                        window.fredware.ui.toast(`✅ Producto "${nombre}" creado`, 'success');
                        overlay.remove();
                        resolve({
                            id: idCreado,
                            nombre: nombre.toUpperCase(),
                            unidad_compra: selectUCompra.value,
                            unidad_racion: selectURacion.value
                        });
                    } catch (error) {
                        errorDiv.textContent = '❌ Error: ' + error.message;
                        errorDiv.style.display = 'block';
                        btnCrear.disabled = false;
                        btnCrear.textContent = '➕ Crear producto';
                    }
                };

                // Cerrar con Escape
                const escHandler = (e) => {
                    if (e.key === 'Escape') {
                        overlay.remove();
                        document.removeEventListener('keydown', escHandler);
                        resolve(null);
                    }
                };
                document.addEventListener('keydown', escHandler);
            });
        },

        // ============================================================
        // Componente: Combobox estricto
        // Uso: 
        //   fredware.productos.comboboxEstricto('mi-input-id', {
        //       zonas: ['CARTA', 'TRANSVERSAL'],
        //       onSelect: (producto) => { ... },
        //       onCrearNuevo: (nombrePropuesto) => { ... }
        //   });
        // ============================================================
        comboboxEstricto(inputId, opciones = {}) {
            const input = document.getElementById(inputId);
            if (!input) {
                console.error(`❌ [Productos] Input #${inputId} no encontrado`);
                return;
            }

            const zonasPermitidas = opciones.zonas || null;
            const onSelect = opciones.onSelect || (() => {});
            const placeholder = opciones.placeholder || 'Escribe para buscar producto...';

            // Asegurar que la lista está cargada
            if (this.lista.length === 0) {
                this.cargar();
            }

            // Configurar input
            input.setAttribute('autocomplete', 'off');
            input.setAttribute('placeholder', placeholder);

            // Crear contenedor del dropdown
            let dropdown = document.getElementById(`${inputId}-dropdown`);
            if (!dropdown) {
                dropdown = document.createElement('div');
                dropdown.id = `${inputId}-dropdown`;
                dropdown.style.cssText = `
                    position: absolute;
                    top: 100%;
                    left: 0;
                    right: 0;
                    background: white;
                    border: 2px solid #cbd5e1;
                    border-radius: 0 0 10px 10px;
                    max-height: 320px;
                    overflow-y: auto;
                    z-index: 1000;
                    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
                    display: none;
                    margin-top: -2px;
                `;

                // Asegurar que el padre tiene position relative
                const padre = input.parentElement;
                if (getComputedStyle(padre).position === 'static') {
                    padre.style.position = 'relative';
                }
                padre.appendChild(dropdown);
            }

            // Estado
            let seleccionado = null;

            // Al escribir
            input.addEventListener('input', () => {
                const texto = input.value.trim();
                seleccionado = null;

                if (texto.length < 2) {
                    dropdown.style.display = 'none';
                    return;
                }

                const resultados = this.filtrar(texto, { zonas: zonasPermitidas });

                if (resultados.length === 0) {
                    // No hay resultados → mostrar opción "Crear nuevo"
                    dropdown.innerHTML = `
                        <div style="padding: 14px; text-align: center;">
                            <div style="font-size: 13px; color: #64748b; margin-bottom: 10px;">
                                🔍 No se encontró "<strong>${window.fredware.util.escapeHtml(texto)}</strong>"
                            </div>
                            <button 
                                type="button"
                                class="btn-crear-desde-combobox"
                                style="
                                    padding: 10px 20px;
                                    background: #f59e0b;
                                    color: white;
                                    border: none;
                                    border-radius: 8px;
                                    font-weight: 700;
                                    font-size: 13px;
                                    cursor: pointer;
                                "
                            >
                                ➕ Crear "${window.fredware.util.escapeHtml(texto)}"
                            </button>
                        </div>
                    `;
                    dropdown.style.display = 'block';

                    // Botón crear
                    dropdown.querySelector('.btn-crear-desde-combobox').onclick = async () => {
                        dropdown.style.display = 'none';
                        const nuevo = await this.mostrarModalCrearProducto(texto);
                        if (nuevo) {
                            input.value = nuevo.nombre;
                            seleccionado = nuevo;
                            onSelect(nuevo);
                        }
                    };
                    return;
                }

                // Mostrar resultados
                dropdown.innerHTML = resultados.map(p => `
                    <div 
                        class="producto-opcion"
                        data-id="${window.fredware.util.escapeHtml(p.id)}"
                        data-nombre="${window.fredware.util.escapeHtml(p.nombre_articulo)}"
                        style="
                            padding: 12px 16px;
                            cursor: pointer;
                            border-bottom: 1px solid #f1f5f9;
                            transition: background 0.15s;
                        "
                        onmouseover="this.style.background='#f0fdf4'"
                        onmouseout="this.style.background='white'"
                    >
                        <div style="font-weight: 700; font-size: 14px; color: #1e293b;">
                            📦 ${window.fredware.util.escapeHtml(p.nombre_articulo)}
                        </div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                            ${window.fredware.util.escapeHtml(p.zona)} · ${window.fredware.util.escapeHtml(p.tipo)} · ${window.fredware.util.escapeHtml(p.categoria || 'OTROS')}
                            ${p.estado === 'PENDIENTE_CONFIGURAR' ? ' · 🟡 PENDIENTE' : ''}
                        </div>
                    </div>
                `).join('');

                dropdown.style.display = 'block';

                // Click en opción
                dropdown.querySelectorAll('.producto-opcion').forEach(el => {
                    el.onclick = () => {
                        const producto = resultados.find(p => p.id === el.dataset.id);
                        if (producto) {
                            input.value = producto.nombre_articulo;
                            seleccionado = producto;
                            dropdown.style.display = 'none';
                            onSelect(producto);
                        }
                    };
                });
            });

            // Al perder el foco, cerrar dropdown (con delay)
            input.addEventListener('blur', () => {
                setTimeout(() => {
                    dropdown.style.display = 'none';
                }, 200);
            });

            // Al recuperar el foco, reabrir si hay texto
            input.addEventListener('focus', () => {
                if (input.value.trim().length >= 2) {
                    input.dispatchEvent(new Event('input'));
                }
            });

            // Al pulsar Enter → intentar buscar/matchear
            input.addEventListener('keypress', async (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const texto = input.value.trim();
                    if (!texto) return;

                    // Si no hay selección, intentar matchear en servidor
                    if (!seleccionado) {
                        const matchId = await this.buscar(texto);
                        if (matchId) {
                            const producto = this.lista.find(p => p.id === matchId);
                            if (producto) {
                                input.value = producto.nombre_articulo;
                                seleccionado = producto;
                                onSelect(producto);
                                dropdown.style.display = 'none';
                                return;
                            }
                        }
                        // No matcheado → preguntar
                        window.fredware.ui.toast('⚠️ Selecciona un producto de la lista o pulsa Enter para crear', 'warning');
                    }
                }
            });

            // Exponer métodos
            input.fredwareGetSeleccionado = () => seleccionado;
            input.fredwareReset = () => {
                input.value = '';
                seleccionado = null;
                dropdown.style.display = 'none';
            };

            console.log(`✅ [Productos] Combobox estricto configurado en #${inputId}`);
            return input;
        }
    };
}

// ============================================================
// INSTANCIACIÓN
// ============================================================
if (typeof supabase !== 'undefined') {
    window.fredware = new FredwareUnified();
    console.log('✅ [Core v3] Fredware Unified cargado');
} else {
    console.error('❌ [Core v3] Supabase no disponible');
    setTimeout(() => {
        if (typeof supabase !== 'undefined' && !window.fredware) {
            window.fredware = new FredwareUnified();
            console.log('✅ [Core v3] Fredware Unified cargado (retrasado)');
        }
    }, 1000);
}
