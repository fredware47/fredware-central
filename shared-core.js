// ============================================================
// FREDWARE UNIFIED - NÚCLEO COMPARTIDO
// ============================================================

class FredwareUnified {
    constructor() {
        this.SUPABASE_URL = "https://bhyprsjokwgazzzlfnbf.supabase.co";
        this.SUPABASE_KEY = "sb_publishable_i-g5o4tO1R8u6Fe7Fc2Q8Q_V_FV271y";
        
        this.supabase = supabase.createClient(
            this.SUPABASE_URL,
            this.SUPABASE_KEY
        );
        
        this.state = {
            recepciones: [],
            inventario: [],
            ingredientes: [],
            escandallos: [],
            estadisticas: {
                totalHoy: 0,
                mermaPromedio: 0,
                productosCriticos: [],
                alertas: []
            },
            ultimaActualizacion: null
        };
        
        this.subscribers = [];
        this.inicializado = false;
        
        this.setupBroadcast();
        this.init();
    }
    
    setupBroadcast() {
        console.log('📡 Configurando canal de broadcast...');
        this.channel = this.supabase.channel('fredware-unified', {
            config: { broadcast: { self: true } }
        });
        this.channel.subscribe((status) => {
            console.log('📡 Estado del canal:', status);
        });
        this.channel.on('broadcast', { event: 'actualizar' }, ({ payload }) => {
            console.log('📨 Evento recibido:', payload);
            this.handleBroadcast(payload);
        });
    }
    
    handleBroadcast(payload) {
        switch(payload.tipo) {
            case 'nueva_recepcion':
                this.agregarRecepcion(payload.data);
                break;
            case 'nuevo_ingrediente':
                this.agregarIngrediente(payload.data);
                break;
            case 'cierre_inventario':
                this.actualizarInventario(payload.data);
                break;
            default:
                console.log('ℹ️ Evento desconocido:', payload.tipo);
        }
        this.notifySubscribers();
    }
    
    async init() {
        if (this.inicializado) console.log('🔄 Recargando datos...');
        try {
            await Promise.all([
                this.cargarRecepciones(),
                this.cargarInventario(),
                this.cargarIngredientes(),
                this.cargarEscandallos()
            ]);
            this.calcularEstadisticas();
            this.inicializado = true;
            this.state.ultimaActualizacion = new Date();
            this.notifySubscribers();
            console.log('✅ Fredware Unified inicializado');
        } catch (error) {
            console.error('❌ Error inicializando:', error);
        }
    }
    
    async cargarRecepciones() {
        try {
            const { data, error } = await this.supabase
                .from('respaldo_diario_recepciones')
                .select('*')
                .order('fecha', { ascending: false })
                .limit(50);
            if (error) throw error;
            this.state.recepciones = data || [];
            console.log(`✅ ${this.state.recepciones.length} recepciones`);
        } catch (error) {
            console.error('❌ Error cargando recepciones:', error);
            this.state.recepciones = [];
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
            console.log(`✅ ${this.state.inventario.length} inventario`);
        } catch (error) {
            console.error('❌ Error cargando inventario:', error);
            this.state.inventario = [];
        }
    }
    
    async cargarIngredientes() {
        try {
            const { data, error } = await this.supabase
                .from('ingredientes_maestros')
                .select('*')
                .order('nombre', { ascending: true });
            if (error) throw error;
            this.state.ingredientes = data || [];
            console.log(`✅ ${this.state.ingredientes.length} ingredientes`);
        } catch (error) {
            console.error('❌ Error cargando ingredientes:', error);
            this.state.ingredientes = [];
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
            console.log(`✅ ${this.state.escandallos.length} escandallos`);
        } catch (error) {
            console.error('❌ Error cargando escandallos:', error);
            this.state.escandallos = [];
        }
    }
    
    calcularEstadisticas() {
        const hoy = new Date().toISOString().split('T')[0];
        let totalHoy = 0;
        this.state.recepciones.forEach(r => {
            if (r.fecha === hoy && r.data?.productos) {
                totalHoy += r.data.productos.length;
            }
        });
        let mermaTotal = 0, countMerma = 0;
        this.state.inventario.forEach(item => {
            if (item.maestro_escandallos?.porcentaje_merma) {
                mermaTotal += item.maestro_escandallos.porcentaje_merma;
                countMerma++;
            }
        });
        const productosCriticos = this.state.escandallos
            .filter(e => e.porcentaje_merma > 20)
            .map(e => e.nombre_articulo);
        this.state.estadisticas = {
            totalHoy,
            mermaPromedio: countMerma > 0 ? mermaTotal / countMerma : 0,
            productosCriticos,
            alertas: this.generarAlertas(),
            fechaCalculo: new Date().toISOString()
        };
    }
    
    generarAlertas() {
        const alertas = [];
        this.state.escandallos.forEach(e => {
            if (e.porcentaje_merma > 30) {
                alertas.push({
                    tipo: 'warning',
                    mensaje: `⚠️ ${e.nombre_articulo} tiene merma del ${e.porcentaje_merma}%`,
                    prioridad: 'alta'
                });
            }
        });
        this.state.inventario.forEach(item => {
            if (item.stock_fisico_final < 10 && item.stock_fisico_final > 0) {
                alertas.push({
                    tipo: 'info',
                    mensaje: `📦 Stock bajo: ${item.articulo_id} (${item.stock_fisico_final} unidades)`,
                    prioridad: 'media'
                });
            }
        });
        return alertas;
    }
    
    async agregarRecepcion(data) {
        this.state.recepciones.unshift(data);
        await this.guardarRecepcion(data);
        this.calcularEstadisticas();
        this.notifySubscribers();
    }
    
    async agregarIngrediente(data) {
        this.state.ingredientes.push(data);
        await this.guardarIngrediente(data);
        this.notifySubscribers();
    }
    
    async actualizarInventario(data) {
        const index = this.state.inventario.findIndex(i => i.id === data.id);
        if (index !== -1) {
            this.state.inventario[index] = data;
        } else {
            this.state.inventario.push(data);
        }
        await this.guardarInventario(data);
        this.calcularEstadisticas();
        this.notifySubscribers();
    }
    
    async guardarRecepcion(data) {
        try {
            await this.supabase.from('respaldo_diario_recepciones').insert([data]);
        } catch (error) {
            console.error('❌ Error guardando recepción:', error);
        }
    }
    
    async guardarIngrediente(data) {
        try {
            await this.supabase.from('ingredientes_maestros').upsert([data], { onConflict: 'nombre' });
        } catch (error) {
            console.error('❌ Error guardando ingrediente:', error);
        }
    }
    
    async guardarInventario(data) {
        try {
            await this.supabase.from('inventario_mensual').upsert([data], { onConflict: 'mes_anio, articulo_id' });
        } catch (error) {
            console.error('❌ Error guardando inventario:', error);
        }
    }
    
    subscribe(callback) {
        this.subscribers.push(callback);
        callback(this.state);
        return () => {
            this.subscribers = this.subscribers.filter(cb => cb !== callback);
        };
    }
    
    notifySubscribers() {
        this.subscribers.forEach(callback => {
            try { callback(this.state); } catch (error) {
                console.error('❌ Error en suscriptor:', error);
            }
        });
    }
    
    async broadcastEvent(tipo, data) {
        try {
            await this.channel.send({
                type: 'broadcast',
                event: 'actualizar',
                payload: { tipo, data }
            });
        } catch (error) {
            console.error('❌ Error enviando broadcast:', error);
        }
    }
    
    async recargarTodo() {
        await this.init();
        return this.getEstadoCompleto();
    }
    
    getEstadoCompleto() { return this.state; }
}

// ============================================================
// INSTANCIAR
// ============================================================
if (typeof supabase !== 'undefined') {
    window.fredware = new FredwareUnified();
    console.log('✅ Fredware Unified Core cargado');
} else {
    console.error('❌ Supabase no está disponible');
    setTimeout(() => {
        if (typeof supabase !== 'undefined' && !window.fredware) {
            window.fredware = new FredwareUnified();
            console.log('✅ Fredware Unified Core cargado (retrasado)');
        }
    }, 1000);
}

setInterval(() => {
    if (window.fredware) window.fredware.recargarTodo();
}, 120000);