// front/app.js
const { createApp, ref, computed, onMounted, onUnmounted, watch } = Vue;
const { Monitor, Refresh, Loading, Download, Upload, Sunny, Moon, Sunrise } = ElementPlusIconsVue;

// --- 配置区域 ---
// 如果你直接打开 html 文件，请将下面地址改为 dashboard.py 运行的地址
// 例如: const API_BASE_URL = 'http://127.0.0.1:8080';
// 如果 dashboard.py 和 html 在同一个 web server 下（通过 nginx 反代），可以留空
const API_BASE_URL = ''; 

const app = createApp({
  components: { Monitor, Loading, Download, Upload, Sunny, Moon, Sunrise },
  setup() {
    const RefreshIcon = Refresh;

    const localeMap = {
      zh: { label: '中文', htmlLang: 'zh-CN' },
      en: { label: 'English', htmlLang: 'en' },
      ja: { label: '日本語', htmlLang: 'ja' },
    };

    const translations = {
      zh: {
        appTitle: 'GPU 监控看板',
        appSubtitle: '实时可视化 GPU、CPU、内存与进程状态',
        updatedAt: '更新于',
        selectServer: '选择节点',
        language: '语言',
        autoRefresh: '自动刷新',
        theme: {
          auto: '自动',
          light: '白天',
          dark: '夜间',
        },
        themeMenu: {
          auto: '自动切换',
          light: '白天模式',
          dark: '夜间模式',
        },
        metrics: {
          cpu: 'CPU 负载',
          memory: '内存使用',
          networkDown: '网络下行',
          networkUp: '网络上行',
          gpuOnline: 'GPU 在线数量',
          vram: '显存 (VRAM)',
          utilization: '核心利用率',
          power: '实时功耗',
          fan: '风扇转速',
          memoryUsage: '显存占比',
          activeProcesses: '活跃进程',
        },
        table: {
          pid: 'PID',
          user: '用户',
          processName: '进程名',
          memory: '显存占用',
          command: '命令',
          empty: '无活跃进程',
        },
        errors: {
          noConfigTitle: '无法连接',
          noConfigDesc: '未找到服务器配置，请检查 config.json',
          loadServerList: '无法加载服务器列表，请检查 Dashboard 是否运行',
          fetchFailed: (message) => `获取数据失败: ${message}`,
        },
        footer: {
          line1: '© 2026 GPU 集群监控面板 | Powered by Shushu Internet Center in Anhui University',
          line2: 'Designed for AI Researchers and Developers',
        },
      },
      en: {
        appTitle: 'GPU Monitor Dashboard',
        appSubtitle: 'Live telemetry for GPU, CPU, memory, and processes',
        updatedAt: 'Updated at',
        selectServer: 'Select node',
        language: 'Language',
        autoRefresh: 'Auto refresh',
        theme: {
          auto: 'Auto',
          light: 'Light',
          dark: 'Dark',
        },
        themeMenu: {
          auto: 'Auto switch',
          light: 'Light mode',
          dark: 'Dark mode',
        },
        metrics: {
          cpu: 'CPU Load',
          memory: 'Memory Usage',
          networkDown: 'Network In',
          networkUp: 'Network Out',
          gpuOnline: 'Online GPUs',
          vram: 'VRAM',
          utilization: 'Core Utilization',
          power: 'Live Power',
          fan: 'Fan Speed',
          memoryUsage: 'VRAM Usage',
          activeProcesses: 'Active Processes',
        },
        table: {
          pid: 'PID',
          user: 'User',
          processName: 'Process',
          memory: 'GPU Memory',
          command: 'Command',
          empty: 'No active processes',
        },
        errors: {
          noConfigTitle: 'Connection failed',
          noConfigDesc: 'No server configuration found. Check config.json.',
          loadServerList: 'Unable to load server list. Check whether Dashboard is running.',
          fetchFailed: (message) => `Failed to fetch data: ${message}`,
        },
        footer: {
          line1: '© 2026 GPU Monitor Dashboard | Powered by Shushu Internet Center in Anhui University',
          line2: 'Designed for AI Researchers and Developers',
        },
      },
      ja: {
        appTitle: 'GPU モニターダッシュボード',
        appSubtitle: 'GPU、CPU、メモリ、プロセスの状態をリアルタイム表示',
        updatedAt: '更新時刻',
        selectServer: 'ノードを選択',
        language: '言語',
        autoRefresh: '自動更新',
        theme: {
          auto: '自動',
          light: 'ライト',
          dark: 'ダーク',
        },
        themeMenu: {
          auto: '自動切替',
          light: 'ライトモード',
          dark: 'ダークモード',
        },
        metrics: {
          cpu: 'CPU 使用率',
          memory: 'メモリ使用量',
          networkDown: '受信トラフィック',
          networkUp: '送信トラフィック',
          gpuOnline: '稼働中 GPU 数',
          vram: 'VRAM',
          utilization: 'コア使用率',
          power: 'リアルタイム消費電力',
          fan: 'ファン回転数',
          memoryUsage: 'VRAM 使用率',
          activeProcesses: 'アクティブプロセス',
        },
        table: {
          pid: 'PID',
          user: 'ユーザー',
          processName: 'プロセス名',
          memory: 'GPU メモリ',
          command: 'コマンド',
          empty: 'アクティブなプロセスはありません',
        },
        errors: {
          noConfigTitle: '接続できません',
          noConfigDesc: 'サーバー設定が見つかりません。config.json を確認してください。',
          loadServerList: 'サーバー一覧を読み込めません。Dashboard の起動状態を確認してください。',
          fetchFailed: (message) => `データ取得に失敗しました: ${message}`,
        },
        footer: {
          line1: '© 2026 GPU モニターダッシュボード | Anhui University Shushu Internet Center',
          line2: 'AI 研究者と開発者のために設計',
        },
      },
    };
    
    // 核心数据
    const servers = ref([]);
    const selectedServerId = ref(null);
    const currentData = ref(null);
    const loading = ref(true);
    const lastUpdateTime = ref('');
    const autoRefresh = ref(false);
    const refreshTimer = ref(null);
    const currentLocale = ref('zh');

    // 夜间模式相关
    const currentTheme = ref('auto'); // 'auto', 'light', 'dark'
    const themeIcon = computed(() => {
      if (currentTheme.value === 'light') return Sunny;
      if (currentTheme.value === 'dark') return Moon;
      return Sunrise;
    });
    const translate = (key, fallback = '') => {
      const locale = translations[currentLocale.value] || translations.zh;
      const value = key.split('.').reduce((accumulator, segment) => accumulator?.[segment], locale);
      return value ?? fallback ?? key;
    };
    const themeText = computed(() => translate(`theme.${currentTheme.value}`));
    const localeText = computed(() => localeMap[currentLocale.value]?.label || '中文');

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

    // 夜间模式相关函数
    const applyTheme = (theme) => {
      if (theme === 'auto') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
      } else {
        document.documentElement.setAttribute('data-theme', theme);
      }
    };

    const applyLocale = (locale) => {
      const normalizedLocale = localeMap[locale] ? locale : 'zh';
      currentLocale.value = normalizedLocale;
      document.documentElement.lang = localeMap[normalizedLocale].htmlLang;
      localStorage.setItem('locale-preference', normalizedLocale);
    };

    const handleThemeChange = (command) => {
      currentTheme.value = command;
      localStorage.setItem('theme-preference', command);
      applyTheme(command);
    };

    const handleLocaleChange = (command) => {
      applyLocale(command);
    };

    const initializeTheme = () => {
      const savedTheme = localStorage.getItem('theme-preference');
      if (savedTheme) {
        currentTheme.value = savedTheme;
      } else {
        currentTheme.value = 'auto';
      }
      applyTheme(currentTheme.value);

      // 监听系统主题变化（仅在自动模式下）
      if (window.matchMedia) {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
          if (currentTheme.value === 'auto') {
            document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
          }
        });
      }
    };

    const initializeLocale = () => {
      const savedLocale = localStorage.getItem('locale-preference');
      const browserLocale = (navigator.language || '').toLowerCase();
      const defaultLocale = browserLocale.startsWith('en') ? 'en' : browserLocale.startsWith('ja') ? 'ja' : 'zh';
      applyLocale(savedLocale || defaultLocale);
    };

    watch(currentLocale, () => {
      document.title = translate('appTitle');
    }, { immediate: true });

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
        ElementPlus.ElMessage.error(translate('errors.loadServerList'));
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
          lastUpdateTime.value = new Date().toLocaleTimeString(localeMap[currentLocale.value].htmlLang, { hour12: false });
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
      initializeTheme();
      initializeLocale();
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
      // 夜间模式相关
      currentTheme,
      themeIcon,
      themeText,
      localeText,
      currentLocale,
      handleThemeChange,
      handleLocaleChange,
      translate,
      // 工具函数
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
