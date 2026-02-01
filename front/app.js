const { createApp, ref, computed, onMounted, onUnmounted, shallowRef } = Vue;
const { Monitor, Refresh, Loading, Download, Upload } = ElementPlusIconsVue;

const app = createApp({
  components: { Monitor, Loading, Download, Upload },
  setup() {
    const RefreshIcon = shallowRef(Refresh);
    
    // 核心数据
    const servers = ref([]);
    const selectedServerId = ref(null);
    const currentData = ref(null);
    const loading = ref(true);
    const lastUpdateTime = ref('');
    const autoRefresh = ref(false);
    const refreshTimer = ref(null);

    // 颜色阈值
    const colors = [
      { color: '#67c23a', percentage: 60 },
      { color: '#e6a23c', percentage: 85 },
      { color: '#f56c6c', percentage: 100 },
    ];

    // 计算属性
    const selectedServer = computed(() => servers.value.find(s => s.id === selectedServerId.value));
    const gpuList = computed(() => currentData.value?.gpu?.gpus || []);

    // 工具函数
    const safeNumber = (val) => val === undefined || val === null ? 0 : Number(val);
    
    const formatBytes = (bytes) => {
        if (!+bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
    };

    const getTempStatus = (temp) => {
        if (temp < 65) return 'success';
        if (temp < 82) return 'warning';
        return 'danger';
    };

    const getValColorClass = (val) => {
        if (val > 85) return 'text-danger';
        if (val > 60) return 'text-warning';
        return 'text-success';
    };

    // 核心修复：手动计算显存百分比，不依赖 API 的 percent 字段
    const calcMemoryPercent = (gpu) => {
        if (!gpu || !gpu.memory || !gpu.memory.total) return 0;
        // 使用 used / total 计算，确保准确性
        const pct = (gpu.memory.used / gpu.memory.total) * 100;
        // 限制在 0-100 之间
        return Math.round(Math.min(Math.max(pct, 0), 100));
    };

    // 数据逻辑
    const loadConfig = async () => {
      try {
        // 请求本地代理接口
        const response = await fetch('/api/config');
        if (!response.ok) throw new Error('Config load error');
        const config = await response.json();
        servers.value = config.servers || [];
        if (servers.value.length > 0) {
          selectedServerId.value = servers.value[0].id;
          await loadSelectedServerData();
        }
      } catch (error) {
        console.error(error);
        ElementPlus.ElMessage.error('无法加载服务器列表');
      } finally {
        loading.value = false;
      }
    };

    const loadSelectedServerData = async () => {
      if (!selectedServer.value) return;
      
      if (!currentData.value) {
        loading.value = true;
      }

      try {
        // 请求本地代理接口，转发到后端
        const url = `/api/proxy?id=${selectedServerId.value}`;
        
        const response = await fetch(url);
        const result = await response.json();
        
        if (result.code === 200) {
          currentData.value = result.data;
          lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', {hour12: false});
        } else {
          console.warn(result.msg);
          if(result.code === 502) {
              // 代理连接失败
          }
        }
      } catch (error) {
        console.error(error);
        if (!autoRefresh.value) {
            ElementPlus.ElMessage.warning(`获取数据失败: ${error.message}`);
        }
      } finally {
        loading.value = false;
      }
    };

    const handleServerChange = () => {
        if (refreshTimer.value) {
            clearInterval(refreshTimer.value);
            refreshTimer.value = null;
        }
        loadSelectedServerData();
        if (autoRefresh.value) {
            refreshTimer.value = setInterval(loadSelectedServerData, 3000);
        }
    };

    const refreshCurrent = () => {
        loadSelectedServerData();
    };

    const toggleAutoRefresh = (val) => {
        if (refreshTimer.value) {
            clearInterval(refreshTimer.value);
            refreshTimer.value = null;
        }
        if (val) {      
            refreshTimer.value = setInterval(loadSelectedServerData, 3000);
        }
    };

    onMounted(() => {
      loadConfig();
    });

    onUnmounted(() => {
        if (refreshTimer.value) clearInterval(refreshTimer.value);
    });

    return {
      servers,
      selectedServerId,
      currentData,
      loading,
      lastUpdateTime,
      gpuList,
      autoRefresh,
      colors,
      RefreshIcon,
      safeNumber,
      formatBytes,
      getTempStatus,
      getValColorClass,
      calcMemoryPercent,
      refreshCurrent,
      handleServerChange,
      toggleAutoRefresh
    };
  }
});

app.use(ElementPlus);
app.mount('#app');