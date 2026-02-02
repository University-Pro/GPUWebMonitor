// front/app.js
const { createApp, ref, computed, onMounted, onUnmounted, shallowRef } = Vue;
const { Monitor, Refresh, Loading, Download, Upload } = ElementPlusIconsVue;

// --- 配置区域 ---
// 如果你直接打开 html 文件，请将下面地址改为 dashboard.py 运行的地址
// 例如: const API_BASE_URL = 'http://127.0.0.1:8080';
// 如果 dashboard.py 和 html 在同一个 web server 下（通过 nginx 反代），可以留空
const API_BASE_URL = 'http://127.0.0.1:8080'; 

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

    // 显存百分比计算
    const calcMemoryPercent = (gpu) => {
        if (!gpu || !gpu.memory || !gpu.memory.total) return 0;
        const pct = (gpu.memory.used / gpu.memory.total) * 100;
        return Math.round(Math.min(Math.max(pct, 0), 100));
    };

    // --- 数据逻辑 ---
    
    // 封装 fetch，自动添加 Base URL
    const fetchApi = async (endpoint) => {
        // 处理拼接 / 的问题
        const baseUrl = API_BASE_URL.replace(/\/$/, '');
        const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
        return fetch(`${baseUrl}${url}`);
    };

    const loadConfig = async () => {
      try {
        // 请求 dashboard.py 的 /api/config
        const response = await fetchApi('/api/config');
        if (!response.ok) throw new Error(`Config load error: ${response.status}`);
        const config = await response.json();
        
        servers.value = config.servers || [];
        
        // 自动选择第一个
        if (servers.value.length > 0) {
          selectedServerId.value = servers.value[0].id;
          await loadSelectedServerData();
        }
      } catch (error) {
        console.error(error);
        ElementPlus.ElMessage.error('无法加载服务器列表，请检查 Dashboard 是否运行');
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
        // 请求 dashboard.py 的 /api/proxy
        const url = `/api/proxy?id=${selectedServerId.value}`;
        
        const response = await fetchApi(url);
        const result = await response.json();
        
        if (result.code === 200) {
          currentData.value = result.data;
          lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', {hour12: false});
        } else {
          console.warn(result.msg);
          // 如果是 502/504 等代理错误，提示一下
          if (result.code >= 500) {
             // 静默失败或轻微提示，避免自动刷新时弹窗太多
             console.log("代理请求后端失败:", result.msg);
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
        // 切换服务器时，先清空旧数据，给用户加载中的感觉
        currentData.value = null; 
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