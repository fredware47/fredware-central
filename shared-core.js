// ============================================================
// FREDWARE UNIFIED - NÚCLEO COMPARTIDO v2
// Fecha: 2026-09-27
// ============================================================
// Cambios respecto a v1:
//   ✅ Lee de 'recepciones' (455 filas) en lugar de la fantasma
//   ✅ Interpreta formato plano (no data.productos)
//   ✅ Usa las 3 vistas nuevas (v_recepciones_*, v_compras_por_mes)
//   ✅ Un solo canal de broadcast: 'fredware-unified'
//   ✅ Exporta utilidades UI y util
//   ✅ Un solo polling interno: 60s
//   ✅ Método registrarRecepcion() para escritura centralizada
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
            recepciones: [],       // últimas 500 recepciones (vista normalizada)
            statsDia: [],          // agregados por día
            comprasMes: [],        // compras agregadas por mes/producto
            escandallos: [],       // maestro de mermas
            inventario: [],        // cierre mensual

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
            version: '2.0',
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
            console.log('🚀 [Core v2] Iniciando Fredware Unified...');

            // 1. Configurar canal de broadcast único
            this.setupBroadcast();

            // 2. Cargar todos los datos en paralelo
            await this.recargarTodo();

            // 3. Configurar polling interno (60s)
            this.iniciarPolling();

            this.state.inicializado = true;
            console.log('✅ [Core v2] Fredware Unified inicializado correctamente');
        } catch (error) {
            console.error('❌ [Core v2] Error inicializando:', error);
        }
    }

    setupBroadcast() {
        console.log('📡 [Core v2] Configurando canal fredware-unified...');
        this.channel = this.supabase.channel('fredware-unified', {
            config: { broadcast: { self: true } }
        });

        this.channel
            .on('broadcast', { event: 'actualizar' }, ({ payload }) => {
                console.log('📨 [Core v2] Broadcast recibido:', payload);
                this.handleBroadcast(payload);
            })
            .on('postgres_changes', {
                event: 'INSERT',
                schema: 'public',
                table: 'recepciones'
            }, (payload) => {
                console.log('🆕 [Core v2] Nueva recepción detectada:', payload.new?.producto);
                this.recargarTodo();
            })
            .subscribe((status) => {
                console.log('📡 [Core v2] Estado canal:', status);
            });
    }

    handleBroadcast(payload) {
        const { tipo, data } = payload || {};

        switch (tipo) {
            case 'nueva_recepcion':
                console.log('📦 [Core v2] Nueva recepción vía broadcast');
                this.recargarTodo();
                break;

            case 'nuevo_pedido':
                console.log('🛒 [Core v2] Nuevo pedido vía broadcast');
                this.recargarTodo();
                break;

            case 'cierre_inventario':
                console.log('📊 [Core v2] Cierre de inventario vía broadcast');
                this.recargarTodo();
                break;

            case 'etiqueta_impresa':
                console.log('🏷️ [Core v2] Etiqueta impresa');
                // No recargamos, es solo informativo
                break;

            default:
                console.log('ℹ️ [Core v2] Evento desconocido:', tipo);
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
                this.cargarInventario()
            ]);

            this.calcularEstadisticas();
            this.state.ultimaActualizacion = new Date();
            this.notifySubscribers();

            return this.state;
        } catch (error) {
            console.error('❌ [Core v2] Error en recargarTodo:', error);
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
            console.log(`✅ [Core v2] ${this.state.recepciones.length} recepciones cargadas`);
        } catch (error) {
            console.error('❌ [Core v2] Error cargando recepciones:', error);
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
            console.log(`✅ [Core v2] ${this.state.statsDia.length} días de estadísticas`);
        } catch (error) {
            console.error('❌ [Core v2] Error cargando stats:', error);
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
            console.log(`✅ [Core v2] ${this.state.comprasMes.length} filas de compras`);
        } catch (error) {
            console.error('❌ [Core v2] Error cargando compras:', error);
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
            console.log(`✅ [Core v2] ${this.state.escandallos.length} escandallos`);
        } catch (error) {
            console.error('❌ [Core v2] Error cargando escandallos:', error);
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
            console.log(`✅ [Core v2] ${this.state.inventario.length} filas de inventario`);
        } catch (error) {
            console.error('❌ [Core v2] Error cargando inventario:', error);
            this.state.inventario = [];
        }
    }

    // ============================================================
    // ESTADÍSTICAS
    // ============================================================
    calcularEstadisticas() {
        const hoy = new Date().toISOString().split('T')[0];

        // Total de hoy
        let totalHoy = 0;
        this.state.recepciones.forEach(r => {
            const fecha = (r.fecha_registro || '').split('T')[0];
            if (fecha === hoy) totalHoy++;
        });

        // Total de la semana (últimos 7 días)
        let totalSemana = 0;
        const hace7dias = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
        this.state.recepciones.forEach(r => {
            const fecha = new Date(r.fecha_registro || 0);
            if (fecha >= hace7dias) totalSemana++;
        });

        // Total del mes actual
        let totalMes = 0;
        const mesActual = new Date().getMonth();
        const añoActual = new Date().getFullYear();
        this.state.recepciones.forEach(r => {
            const fecha = new Date(r.fecha_registro || 0);
            if (fecha.getMonth() === mesActual && fecha.getFullYear() === añoActual) {
                totalMes++;
            }
        });

        // Última recepción
        const ultimaRecepcion = this.state.recepciones[0] || null;

        // Merma promedio
        let mermaTotal = 0, countMerma = 0;
        this.state.escandallos.forEach(e => {
            if (e.porcentaje_merma != null) {
                mermaTotal += parseFloat(e.porcentaje_merma) || 0;
                countMerma++;
            }
        });

        // Productos críticos (merma > 20%)
        const productosCriticos = this.state.escandallos
            .filter(e => (parseFloat(e.porcentaje_merma) || 0) > 20)
            .map(e => e.nombre_articulo);

        // Alertas
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

        // Alertas por merma alta
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

        // Alertas por stock bajo (último mes con inventario)
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

            console.log('✅ [Core v2] Recepción registrada:', registro.id);

            // Notificar al resto del ecosistema
            await this.broadcastEvent('nueva_recepcion', data || registro);

            // Recargar
            await this.recargarTodo();

            return data || registro;
        } catch (error) {
            console.error('❌ [Core v2] Error registrando recepción:', error);
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
            console.log(`📡 [Core v2] Broadcast enviado: ${tipo}`);
        } catch (error) {
            console.error('❌ [Core v2] Error enviando broadcast:', error);
        }
    }

    // ============================================================
    // SUBSCRIPCIÓN
    // ============================================================
    subscribe(callback) {
        this.subscribers.push(callback);

        // Llamada inmediata con el estado actual
        try {
            callback(this.state);
        } catch (error) {
            console.error('❌ [Core v2] Error en callback inicial:', error);
        }

        // Devolver función de desuscripción
        return () => {
            this.subscribers = this.subscribers.filter(cb => cb !== callback);
        };
    }

    notifySubscribers() {
        this.subscribers.forEach(callback => {
            try {
                callback(this.state);
            } catch (error) {
                console.error('❌ [Core v2] Error en subscriber:', error);
            }
        });
    }

    // ============================================================
    // POLLING INTERNO (único)
    // ============================================================
    iniciarPolling() {
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
        }
        this._pollingInterval = setInterval(() => {
            if (this.state.inicializado) {
                this.recargarTodo().catch(err => {
                    console.warn('⚠️ [Core v2] Error en polling:', err);
                });
            }
        }, 60000); // 60 segundos
        console.log('⏱️ [Core v2] Polling cada 60s iniciado');
    }

    detenerPolling() {
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
            this._pollingInterval = null;
            console.log('⏱️ [Core v2] Polling detenido');
        }
    }

    // ============================================================
    // GETTERS
    // ============================================================
    getEstadoCompleto() {
        return this.state;
    }

    getRecepciones() {
        return this.state.recepciones;
    }

    getEstadisticas() {
        return this.state.estadisticas;
    }

    // ============================================================
    // UTILIDADES EXPORTADAS
    // ============================================================

    // UI helpers
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

    // Utility helpers
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
}

// ============================================================
// INSTANCIACIÓN
// ============================================================
if (typeof supabase !== 'undefined') {
    window.fredware = new FredwareUnified();
    console.log('✅ [Core v2] Fredware Unified cargado');
} else {
    console.error('❌ [Core v2] Supabase no disponible');
    // Reintentar tras 1s
    setTimeout(() => {
        if (typeof supabase !== 'undefined' && !window.fredware) {
            window.fredware = new FredwareUnified();
            console.log('✅ [Core v2] Fredware Unified cargado (retrasado)');
        }
    }, 1000);
}
