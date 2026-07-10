// front/app.js
const { createApp, ref, computed, onMounted, onUnmounted, watch } = Vue;
const {
  Monitor, Refresh, Download, Upload, Sunny, Moon, Sunrise,
  WarningFilled, CircleCheckFilled, Clock, Connection, DataLine,
} = ElementPlusIconsVue;

const API_BASE_URL = '';
const REFRESH_INTERVAL = 3000;
const STALE_AFTER = REFRESH_INTERVAL * 3;
const MAX_SAMPLES = 20;

const app = createApp({
  components: {
    Monitor, Download, Upload, Sunny, Moon, Sunrise,
    WarningFilled, CircleCheckFilled, Clock, Connection, DataLine,
  },
  setup() {
    const RefreshIcon = Refresh;
    const localeMap = {
      zh: { label: '中文', htmlLang: 'zh-CN' },
      en: { label: 'English', htmlLang: 'en' },
      ja: { label: '日本語', htmlLang: 'ja' },
    };

    const translations = {
      zh: {
        appTitle: 'GPU 集群监控', appSubtitle: '实时掌握节点资源、GPU 负载与计算进程',
        node: '计算节点', selectServer: '选择节点', language: '语言', themeLabel: '外观',
        autoRefresh: '自动刷新', refresh: '立即刷新', retry: '重新连接', updatedAt: '更新于',
        status: { live: '数据在线', refreshing: '正在刷新', stale: '数据已过期', error: '连接异常', loading: '正在连接', idle: '等待数据' },
        relative: { now: '刚刚', seconds: (n) => `${n} 秒前`, minutes: (n) => `${n} 分钟前` },
        theme: { auto: '自动', light: '白天', dark: '夜间' },
        themeMenu: { auto: '跟随系统', light: '白天模式', dark: '夜间模式' },
        resources: { title: '系统资源', subtitle: '当前负载与累计网络流量', cpu: 'CPU', memory: '内存', totalReceived: '累计接收', totalSent: '累计发送', recentRate: '近期速率', collecting: '正在收集样本', cores: (n) => `${n} 核`, frequency: '当前频率' },
        trend: { title: '利用率', subtitle: '本次浏览会话 · 最近 20 个采样点', cpu: 'CPU', memory: '内存', gpu: 'GPU 平均', waiting: '至少需要 2 个样本，趋势将在下次刷新后显示', details: '查看采样数据', time: '时间', ranges: { session: '实时', '10m': '10分钟', '30m': '30分钟', '1h': '1小时', '6h': '6小时', '12h': '12小时' }, historySubtitle: (range) => `历史数据 · 最近 ${range}`, loadingHistory: '正在加载历史数据...' },
        gpu: { title: 'GPU 设备', subtitle: '逐卡负载、热状态与进程', emptyTitle: '当前节点未检测到 GPU', emptyDesc: '系统资源仍可正常查看，请确认 NVIDIA 驱动与 NVML 状态。', utilization: '核心利用率', vram: '显存占用', temperature: '温度', power: '实时功耗', powerLimit: '功耗上限', fan: '风扇转速', memoryUtil: '显存控制器', normal: '温度正常', warm: '温度偏高', critical: '温度危险', unknown: '温度未知' },
        process: { title: '计算进程', count: (n) => `${n} 个进程`, pid: 'PID', user: '用户', name: '进程名', memory: '显存占用', command: '命令', empty: '该 GPU 暂无活跃计算进程' },
        units: { cards: (n) => `${n} 张`, unavailable: '不可用' },
        errors: { noConfigTitle: '未配置计算节点', noConfigDesc: '未找到服务器配置，请检查 front/config.json。', configFailedTitle: '无法加载节点配置', loadServerList: '无法加载服务器列表，请确认 Dashboard 服务正在运行。', nodeFailedTitle: '无法获取当前节点数据', nodeFailedDesc: '已保留最近一次有效数据。请检查节点网络或 Agent 服务后重试。', fetchFailed: (m) => `获取数据失败：${m}` },
        footer: { line1: '© 2026 GPU 集群监控面板 · Shushu Internet Center, Anhui University'},
      },
      en: {
        appTitle: 'GPU Cluster Monitor', appSubtitle: 'Live node resources, GPU workloads, and compute processes',
        node: 'Compute node', selectServer: 'Select node', language: 'Language', themeLabel: 'Appearance',
        autoRefresh: 'Auto refresh', refresh: 'Refresh now', retry: 'Reconnect', updatedAt: 'Updated',
        status: { live: 'Data online', refreshing: 'Refreshing', stale: 'Data is stale', error: 'Connection issue', loading: 'Connecting', idle: 'Waiting for data' },
        relative: { now: 'just now', seconds: (n) => `${n}s ago`, minutes: (n) => `${n}m ago` },
        theme: { auto: 'Auto', light: 'Light', dark: 'Dark' },
        themeMenu: { auto: 'Follow system', light: 'Light mode', dark: 'Dark mode' },
        resources: { title: 'System resources', subtitle: 'Current load and cumulative network traffic', cpu: 'CPU', memory: 'Memory', totalReceived: 'Total received', totalSent: 'Total sent', recentRate: 'Recent rate', collecting: 'Collecting samples', cores: (n) => `${n} cores`, frequency: 'Current frequency' },
        trend: { title: 'Utilization', subtitle: 'This browser session · latest 20 samples', cpu: 'CPU', memory: 'Memory', gpu: 'GPU average', waiting: 'At least 2 samples are needed. The trend will appear after the next refresh.', details: 'View sample data', time: 'Time', ranges: { session: 'Live', '10m': '10min', '30m': '30min', '1h': '1h', '6h': '6h', '12h': '12h' }, historySubtitle: (range) => `History · last ${range}`, loadingHistory: 'Loading history...' },
        gpu: { title: 'GPU devices', subtitle: 'Per-device workload, thermal state, and processes', emptyTitle: 'No GPU detected on this node', emptyDesc: 'System resources remain available. Check the NVIDIA driver and NVML status.', utilization: 'Core utilization', vram: 'VRAM used', temperature: 'Temperature', power: 'Live power', powerLimit: 'Power limit', fan: 'Fan speed', memoryUtil: 'Memory controller', normal: 'Temperature normal', warm: 'Temperature high', critical: 'Temperature critical', unknown: 'Temperature unavailable' },
        process: { title: 'Compute processes', count: (n) => `${n} processes`, pid: 'PID', user: 'User', name: 'Process', memory: 'GPU memory', command: 'Command', empty: 'No active compute process on this GPU' },
        units: { cards: (n) => `${n} cards`, unavailable: 'Unavailable' },
        errors: { noConfigTitle: 'No compute nodes configured', noConfigDesc: 'No server configuration was found. Check front/config.json.', configFailedTitle: 'Unable to load node configuration', loadServerList: 'Unable to load the server list. Make sure Dashboard is running.', nodeFailedTitle: 'Unable to retrieve node data', nodeFailedDesc: 'The latest valid data is preserved. Check the node network or Agent service and retry.', fetchFailed: (m) => `Failed to fetch data: ${m}` },
        footer: { line1: '© 2026 GPU Cluster Monitor · Shushu Internet Center, Anhui University' },
      },
      ja: {
        appTitle: 'GPU クラスターモニター', appSubtitle: 'ノード資源、GPU 負荷、計算プロセスをリアルタイム監視',
        node: '計算ノード', selectServer: 'ノードを選択', language: '言語', themeLabel: '外観',
        autoRefresh: '自動更新', refresh: '今すぐ更新', retry: '再接続', updatedAt: '更新',
        status: { live: 'データオンライン', refreshing: '更新中', stale: 'データが古くなっています', error: '接続異常', loading: '接続中', idle: 'データ待機中' },
        relative: { now: 'たった今', seconds: (n) => `${n} 秒前`, minutes: (n) => `${n} 分前` },
        theme: { auto: '自動', light: 'ライト', dark: 'ダーク' },
        themeMenu: { auto: 'システムに従う', light: 'ライトモード', dark: 'ダークモード' },
        resources: { title: 'システムリソース', subtitle: '現在の負荷と累積ネットワーク通信量', cpu: 'CPU', memory: 'メモリ', totalReceived: '累積受信', totalSent: '累積送信', recentRate: '直近の速度', collecting: 'サンプル収集中', cores: (n) => `${n} コア`, frequency: '現在の周波数' },
        trend: { title: '使用率', subtitle: 'このブラウザーセッション · 最新 20 サンプル', cpu: 'CPU', memory: 'メモリ', gpu: 'GPU 平均', waiting: '2 件以上のサンプルが必要です。次回更新後に表示されます。', details: 'サンプルデータを表示', time: '時刻', ranges: { session: 'リアルタイム', '10m': '10分', '30m': '30分', '1h': '1時間', '6h': '6時間', '12h': '12時間' }, historySubtitle: (range) => `履歴データ · 直近 ${range}`, loadingHistory: '履歴データを読み込み中...' },
        gpu: { title: 'GPU デバイス', subtitle: 'デバイス別の負荷、温度、プロセス', emptyTitle: 'このノードで GPU が検出されません', emptyDesc: 'システムリソースは表示できます。NVIDIA ドライバーと NVML を確認してください。', utilization: 'コア使用率', vram: 'VRAM 使用量', temperature: '温度', power: '現在の電力', powerLimit: '電力上限', fan: 'ファン速度', memoryUtil: 'メモリコントローラー', normal: '温度正常', warm: '温度高め', critical: '温度危険', unknown: '温度不明' },
        process: { title: '計算プロセス', count: (n) => `${n} プロセス`, pid: 'PID', user: 'ユーザー', name: 'プロセス', memory: 'GPU メモリ', command: 'コマンド', empty: 'この GPU にアクティブな計算プロセスはありません' },
        units: { cards: (n) => `${n} 枚`, unavailable: '利用不可' },
        errors: { noConfigTitle: '計算ノードが未設定です', noConfigDesc: 'サーバー設定がありません。front/config.json を確認してください。', configFailedTitle: 'ノード設定を読み込めません', loadServerList: 'サーバー一覧を読み込めません。Dashboard の起動状態を確認してください。', nodeFailedTitle: 'ノードデータを取得できません', nodeFailedDesc: '直近の有効データを保持しています。ネットワークまたは Agent を確認して再試行してください。', fetchFailed: (m) => `データ取得失敗：${m}` },
        footer: { line1: '© 2026 GPU クラスターモニター · 安徽大学 Shushu Internet Center'},
      },
    };

    const servers = ref([]);
    const selectedServerId = ref(null);
    const currentData = ref(null);
    const loading = ref(true);
    const configLoading = ref(true);
    const configError = ref('');
    const nodeError = ref('');
    const lastUpdateAt = ref(null);
    const autoRefresh = ref(false);
    const refreshTimer = ref(null);
    const currentLocale = ref('zh');
    const currentTheme = ref('auto');
    const requestController = ref(null);
    const requestSequence = ref(0);
    const samplesByServer = ref({});
    const dataByServer = ref({});
    const freshnessTick = ref(0);
    const activeTrendIndex = ref(null);
    const trendRange = ref('session');
    const trendSliderValue = ref(100);
    const historySamples = ref([]);
    const historyLoading = ref(false);
    let savedAutoRefresh = false;
    let historyAbortController = null;
    let freshnessTimer = null;
    let themeMediaQuery = null;
    let themeMediaListener = null;

    const trendRanges = { session: { seconds: null }, '10m': { seconds: 600 }, '30m': { seconds: 1800 }, '1h': { seconds: 3600 }, '6h': { seconds: 21600 }, '12h': { seconds: 43200 } };

    const translate = (key, ...args) => {
      const locale = translations[currentLocale.value] || translations.zh;
      const value = key.split('.').reduce((acc, part) => acc?.[part], locale);
      return typeof value === 'function' ? value(...args) : (value ?? key);
    };
    const localeText = computed(() => localeMap[currentLocale.value]?.label || '中文');
    const themeText = computed(() => translate(`theme.${currentTheme.value}`));
    const themeIcon = computed(() => currentTheme.value === 'light' ? Sunny : currentTheme.value === 'dark' ? Moon : Sunrise);
    const selectedServer = computed(() => servers.value.find((server) => server.id === selectedServerId.value));
    const gpuList = computed(() => currentData.value?.gpu?.gpus || []);

    const finiteNumber = (value, fallback = null) => {
      if (value === '' || value === null || value === undefined) return fallback;
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    };
    const safeNumber = (value) => finiteNumber(value, 0);
    const clampPercent = (value) => Math.min(100, Math.max(0, safeNumber(value)));
    const formatNumber = (value, digits = 0) => {
      const number = finiteNumber(value);
      return number === null ? translate('units.unavailable') : number.toLocaleString(localeMap[currentLocale.value].htmlLang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
    };
    const formatPercent = (value, digits = 0) => finiteNumber(value) === null ? translate('units.unavailable') : `${formatNumber(value, digits)}%`;
    const formatBytes = (bytes, perSecond = false) => {
      const number = finiteNumber(bytes);
      if (number === null || number < 0) return translate('units.unavailable');
      if (number === 0) return `0 B${perSecond ? '/s' : ''}`;
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
      const index = Math.min(Math.floor(Math.log(number) / Math.log(1024)), sizes.length - 1);
      const value = number / Math.pow(1024, index);
      return `${formatNumber(value, value >= 10 ? 0 : 1)} ${sizes[index]}${perSecond ? '/s' : ''}`;
    };
    const formatFrequency = (mhz) => finiteNumber(mhz) === null ? translate('units.unavailable') : `${formatNumber(mhz / 1000, 1)} GHz`;
    const formatPower = (milliwatts) => finiteNumber(milliwatts) === null ? translate('units.unavailable') : `${formatNumber(milliwatts / 1000, 0)} W`;
    const formatTemperature = (value) => finiteNumber(value) === null ? translate('units.unavailable') : `${formatNumber(value, 0)} °C`;
    const calcMemoryPercent = (gpu) => {
      if (!gpu?.memory || !finiteNumber(gpu.memory.total)) return 0;
      return Math.round(clampPercent((safeNumber(gpu.memory.used) / gpu.memory.total) * 100));
    };
    const getTempStatus = (temp) => finiteNumber(temp) === null ? 'info' : temp < 65 ? 'success' : temp < 82 ? 'warning' : 'danger';
    const getValColorClass = (value) => value > 85 ? 'text-danger' : value > 60 ? 'text-warning' : 'text-success';
    const getTemperatureState = (temp) => {
      const number = finiteNumber(temp);
      if (number === null) return { key: 'unknown', type: 'info', label: translate('gpu.unknown') };
      if (number < 65) return { key: 'normal', type: 'success', label: translate('gpu.normal') };
      if (number < 82) return { key: 'warm', type: 'warning', label: translate('gpu.warm') };
      return { key: 'critical', type: 'danger', label: translate('gpu.critical') };
    };

    const normalizeStatusData = (raw = {}) => {
      const system = raw.system || {};
      const cpu = system.cpu || {};
      const memory = system.memory || {};
      const network = system.network || {};
      const rawGpus = Array.isArray(raw.gpu?.gpus) ? raw.gpu.gpus : [];
      const gpus = rawGpus.map((gpu, position) => {
        const gpuMemory = gpu?.memory || {};
        const total = finiteNumber(gpuMemory.total, finiteNumber(gpuMemory.total_gb) !== null ? gpuMemory.total_gb * 1024 ** 3 : 0);
        const used = finiteNumber(gpuMemory.used, finiteNumber(gpuMemory.used_gb) !== null ? gpuMemory.used_gb * 1024 ** 3 : 0);
        const processes = Array.isArray(gpu?.processes) ? gpu.processes.map((process) => ({
          pid: process?.pid ?? '—', username: process?.username || '—', name: process?.name || '—',
          gpu_memory: finiteNumber(process?.gpu_memory), command: process?.command || '—',
        })) : [];
        return {
          index: gpu?.index ?? position, uuid: gpu?.uuid || `gpu-${position}`, name: gpu?.name || `GPU ${position}`,
          memory: { used, total, used_gb: used / 1024 ** 3, total_gb: total / 1024 ** 3, percent: total > 0 ? Math.round(clampPercent((used / total) * 100)) : 0 },
          utilization: { gpu: clampPercent(gpu?.utilization?.gpu), memory: clampPercent(gpu?.utilization?.memory) },
          temperature: finiteNumber(gpu?.temperature), power: { usage: finiteNumber(gpu?.power?.usage), limit: finiteNumber(gpu?.power?.limit) },
          fan_speed: finiteNumber(gpu?.fan_speed), processes, process_count: processes.length,
        };
      });
      const derived = {
        avg_gpu_utilization: gpus.length ? Math.round(gpus.reduce((sum, gpu) => sum + gpu.utilization.gpu, 0) / gpus.length) : 0,
        total_memory_used: gpus.reduce((sum, gpu) => sum + safeNumber(gpu.memory.used), 0),
        total_memory_total: gpus.reduce((sum, gpu) => sum + safeNumber(gpu.memory.total), 0),
        total_processes: gpus.reduce((sum, gpu) => sum + gpu.process_count, 0),
      };
      const summary = raw.gpu?.summary || {};
      return {
        system: {
          cpu: { percent: clampPercent(cpu.percent), count: finiteNumber(cpu.count, 0), frequency_current: finiteNumber(cpu.frequency_current) },
          memory: { percent: clampPercent(memory.percent), used: finiteNumber(memory.used, 0), total: finiteNumber(memory.total, 0) },
          network: { bytes_recv: finiteNumber(network.bytes_recv, 0), bytes_sent: finiteNumber(network.bytes_sent, 0) },
        },
        gpu: { gpus, summary: {
          avg_gpu_utilization: finiteNumber(summary.avg_gpu_utilization, derived.avg_gpu_utilization),
          total_memory_used: finiteNumber(summary.total_memory_used, derived.total_memory_used),
          total_memory_total: finiteNumber(summary.total_memory_total, derived.total_memory_total),
          total_processes: finiteNumber(summary.total_processes, derived.total_processes),
        } },
        timestamp: raw.timestamp || new Date().toISOString(),
      };
    };

    const currentSamples = computed(() => samplesByServer.value[selectedServerId.value] || []);
    const networkRates = computed(() => {
      const samples = currentSamples.value;
      if (samples.length < 2) return null;
      const previous = samples[samples.length - 2];
      const latest = samples[samples.length - 1];
      const elapsed = (latest.time - previous.time) / 1000;
      if (elapsed <= 0 || latest.received < previous.received || latest.sent < previous.sent) return null;
      return { received: (latest.received - previous.received) / elapsed, sent: (latest.sent - previous.sent) / elapsed };
    });
    const visibleTrendSamples = computed(() => {
      if (trendRange.value === 'session') return currentSamples.value;
      const all = historySamples.value;
      if (all.length < 2) return all;
      const rangeSec = trendRanges[trendRange.value]?.seconds;
      if (!rangeSec) return all;
      const interval = 30;
      const windowSize = Math.min(Math.ceil(rangeSec / interval), all.length);
      const maxStart = all.length - windowSize;
      const start = Math.round(trendSliderValue.value / 100 * maxStart);
      return all.slice(start, start + windowSize);
    });
    const trendSeries = computed(() => {
      const samples = visibleTrendSamples.value;
      if (samples.length < 2) return [];
      const width = 600;
      const height = 180;
      const pointsFor = (key) => samples.map((sample, index) => `${(index / (samples.length - 1)) * width},${height - clampPercent(sample[key]) / 100 * height}`).join(' ');
      return [
        { key: 'cpu', label: translate('trend.cpu'), points: pointsFor('cpu') },
        { key: 'memory', label: translate('trend.memory'), points: pointsFor('memory') },
        { key: 'gpu', label: translate('trend.gpu'), points: pointsFor('gpu') },
      ];
    });
    const activeTrendSample = computed(() => {
      const samples = visibleTrendSamples.value;
      const index = activeTrendIndex.value;
      if (index === null || !samples[index]) return null;
      const sample = samples[index];
      const x = samples.length > 1 ? index / (samples.length - 1) * 600 : 0;
      return {
        index,
        x,
        position: `${x / 6}%`,
        time: new Date(sample.time).toLocaleTimeString(localeMap[currentLocale.value].htmlLang, { hour12: false }),
        values: trendSeries.value.map((series) => ({
          key: series.key,
          label: series.label,
          value: formatPercent(sample[series.key], 1),
          y: 180 - clampPercent(sample[series.key]) / 100 * 180,
        })),
      };
    });
    const updateTrendHover = (event) => {
      const samples = visibleTrendSamples.value;
      if (samples.length < 2) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const pointerX = event.touches?.[0]?.clientX ?? event.clientX;
      const ratio = Math.min(1, Math.max(0, (pointerX - rect.left) / rect.width));
      activeTrendIndex.value = Math.round(ratio * (samples.length - 1));
    };
    const clearTrendHover = () => { activeTrendIndex.value = null; };
    const trendDisplayRange = computed(() => {
      if (trendRange.value === 'session') return translate('trend.subtitle');
      const label = translate(`trend.ranges.${trendRange.value}`);
      return translate('trend.historySubtitle', label);
    });

    const fetchHistory = async (limit) => {
      const serverId = selectedServerId.value;
      if (!serverId) return;
      if (historyAbortController) historyAbortController.abort();
      historyAbortController = new AbortController();
      historyLoading.value = true;
      try {
        const resp = await fetchApi(`/api/proxy?id=${encodeURIComponent(serverId)}&history=1&limit=${limit}`, { signal: historyAbortController.signal });
        const result = await readResponse(resp);
        if (result.code !== 200) throw new Error(result.msg);
        historySamples.value = (result.data || []).map((row) => ({
          time: new Date(row.timestamp).getTime(),
          cpu: clampPercent(row.cpu_percent),
          memory: clampPercent(row.memory_percent),
          gpu: clampPercent(row.summary?.avg_gpu_utilization ?? 0),
        }));
        trendSliderValue.value = 100;
      } catch (e) {
        if (e.name !== 'AbortError') historySamples.value = [];
      } finally {
        historyLoading.value = false;
      }
    };
    const setTrendRange = (key) => {
      if (trendRange.value === key) return;
      if (key === 'session') {
        trendRange.value = 'session';
        autoRefresh.value = savedAutoRefresh;
        historySamples.value = [];
        activeTrendIndex.value = null;
      } else {
        savedAutoRefresh = autoRefresh.value;
        autoRefresh.value = false;
        clearRefreshTimer();
        trendRange.value = key;
        activeTrendIndex.value = null;
        const rangeSec = trendRanges[key].seconds;
        const limit = Math.min(Math.ceil(rangeSec / 30), 1000);
        fetchHistory(limit);
      }
    };
    const isDataStale = computed(() => {
      freshnessTick.value;
      return !!lastUpdateAt.value && Date.now() - lastUpdateAt.value > STALE_AFTER;
    });
    const relativeUpdate = computed(() => {
      freshnessTick.value;
      if (!lastUpdateAt.value) return '';
      const seconds = Math.max(0, Math.floor((Date.now() - lastUpdateAt.value) / 1000));
      if (seconds < 5) return translate('relative.now');
      if (seconds < 60) return translate('relative.seconds', seconds);
      return translate('relative.minutes', Math.floor(seconds / 60));
    });
    const lastUpdateTime = computed(() => lastUpdateAt.value ? new Date(lastUpdateAt.value).toLocaleTimeString(localeMap[currentLocale.value].htmlLang, { hour12: false }) : '');
    const connectionState = computed(() => {
      if (loading.value && !currentData.value) return { key: 'loading', label: translate('status.loading'), icon: 'clock' };
      if (nodeError.value) return { key: 'error', label: translate('status.error'), icon: 'warning' };
      if (isDataStale.value) return { key: 'stale', label: translate('status.stale'), icon: 'warning' };
      if (loading.value) return { key: 'refreshing', label: translate('status.refreshing'), icon: 'clock' };
      if (currentData.value) return { key: 'live', label: translate('status.live'), icon: 'check' };
      return { key: 'idle', label: translate('status.idle'), icon: 'clock' };
    });

    const applyTheme = (theme) => {
      const resolved = theme === 'auto' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : theme;
      document.documentElement.setAttribute('data-theme', resolved);
    };
    const handleThemeChange = (theme) => { currentTheme.value = theme; localStorage.setItem('theme-preference', theme); applyTheme(theme); };
    const applyLocale = (locale) => {
      const normalized = localeMap[locale] ? locale : 'zh';
      currentLocale.value = normalized;
      document.documentElement.lang = localeMap[normalized].htmlLang;
      localStorage.setItem('locale-preference', normalized);
    };
    const handleLocaleChange = applyLocale;
    watch(currentLocale, () => { document.title = translate('appTitle'); }, { immediate: true });

    const fetchApi = (endpoint, options = {}) => {
      const base = API_BASE_URL.replace(/\/$/, '');
      const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
      return fetch(`${base}${path}`, options);
    };
    const readResponse = async (response) => {
      const text = await response.text();
      let result = null;
      try { result = text ? JSON.parse(text) : null; } catch (_) { /* handled below */ }
      if (!response.ok) throw new Error(result?.msg || `HTTP ${response.status}`);
      if (!result) throw new Error('Invalid JSON response');
      return result;
    };
    const recordSample = (serverId, data) => {
      const sample = {
        time: Date.now(), cpu: data.system.cpu.percent, memory: data.system.memory.percent,
        gpu: data.gpu.summary.avg_gpu_utilization, received: data.system.network.bytes_recv, sent: data.system.network.bytes_sent,
      };
      const existing = samplesByServer.value[serverId] || [];
      samplesByServer.value = { ...samplesByServer.value, [serverId]: [...existing, sample].slice(-MAX_SAMPLES) };
    };
    const clearRefreshTimer = () => {
      if (refreshTimer.value) window.clearTimeout(refreshTimer.value);
      refreshTimer.value = null;
    };
    const scheduleRefresh = () => {
      clearRefreshTimer();
      if (autoRefresh.value) refreshTimer.value = window.setTimeout(() => loadSelectedServerData('auto'), REFRESH_INTERVAL);
    };

    const loadSelectedServerData = async (source = 'manual') => {
      const serverId = selectedServerId.value;
      if (!serverId || !selectedServer.value) return;
      clearRefreshTimer();
      if (requestController.value) requestController.value.abort();
      const controller = new AbortController();
      requestController.value = controller;
      const sequence = ++requestSequence.value;
      loading.value = true;
      nodeError.value = '';
      try {
        const response = await fetchApi(`/api/proxy?id=${encodeURIComponent(serverId)}`, { signal: controller.signal });
        const result = await readResponse(response);
        if (result.code !== 200) throw new Error(result.msg || `API ${result.code}`);
        if (sequence !== requestSequence.value || selectedServerId.value !== serverId) return;
        const normalized = normalizeStatusData(result.data);
        currentData.value = normalized;
        dataByServer.value = { ...dataByServer.value, [serverId]: normalized };
        lastUpdateAt.value = Date.now();
        recordSample(serverId, normalized);
      } catch (error) {
        if (error.name === 'AbortError') return;
        if (sequence !== requestSequence.value || selectedServerId.value !== serverId) return;
        nodeError.value = error.message || translate('errors.nodeFailedTitle');
        if (source === 'manual') ElementPlus.ElMessage.warning(translate('errors.fetchFailed', nodeError.value));
      } finally {
        if (sequence === requestSequence.value) {
          loading.value = false;
          requestController.value = null;
          scheduleRefresh();
        }
      }
    };

    const loadConfig = async () => {
      configLoading.value = true;
      configError.value = '';
      try {
        const response = await fetchApi('/api/config');
        const config = await readResponse(response);
        servers.value = Array.isArray(config.servers) ? config.servers : [];
        const saved = localStorage.getItem('selected-server-id');
        selectedServerId.value = servers.value.some((server) => server.id === saved) ? saved : (servers.value[0]?.id || null);
        if (selectedServerId.value) {
          localStorage.setItem('selected-server-id', selectedServerId.value);
          await loadSelectedServerData('initial');
        } else {
          localStorage.removeItem('selected-server-id');
          loading.value = false;
        }
      } catch (error) {
        configError.value = error.message || translate('errors.loadServerList');
        loading.value = false;
      } finally {
        configLoading.value = false;
      }
    };
    const handleServerChange = () => {
      activeTrendIndex.value = null;
      if (trendRange.value !== 'session') {
        trendRange.value = 'session';
        autoRefresh.value = savedAutoRefresh;
        historySamples.value = [];
      }
      localStorage.setItem('selected-server-id', selectedServerId.value);
      requestSequence.value += 1;
      requestController.value?.abort();
      nodeError.value = '';
      lastUpdateAt.value = null;
      currentData.value = dataByServer.value[selectedServerId.value] || null;
      loadSelectedServerData('initial');
    };
    const refreshCurrent = () => loadSelectedServerData('manual');
    const toggleAutoRefresh = () => autoRefresh.value ? scheduleRefresh() : clearRefreshTimer();

    onMounted(() => {
      currentTheme.value = localStorage.getItem('theme-preference') || 'auto';
      applyTheme(currentTheme.value);
      const browserLocale = (navigator.language || '').toLowerCase();
      applyLocale(localStorage.getItem('locale-preference') || (browserLocale.startsWith('en') ? 'en' : browserLocale.startsWith('ja') ? 'ja' : 'zh'));
      themeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      themeMediaListener = () => { if (currentTheme.value === 'auto') applyTheme('auto'); };
      themeMediaQuery.addEventListener('change', themeMediaListener);
      freshnessTimer = window.setInterval(() => { freshnessTick.value += 1; }, 10000);
      loadConfig();
    });
    onUnmounted(() => {
      clearRefreshTimer();
      requestController.value?.abort();
      if (freshnessTimer) window.clearInterval(freshnessTimer);
      if (themeMediaQuery && themeMediaListener) themeMediaQuery.removeEventListener('change', themeMediaListener);
    });

    return {
      servers, selectedServerId, selectedServer, currentData, gpuList, loading, configLoading, configError, nodeError,
      autoRefresh, currentLocale, currentTheme, localeText, themeText, themeIcon, RefreshIcon,
      currentSamples, networkRates, trendSeries, activeTrendSample, connectionState, relativeUpdate, lastUpdateTime,
      trendRange, trendRanges, historyLoading,
      translate, safeNumber, formatNumber, formatPercent, formatBytes, formatFrequency, formatPower, formatTemperature,
      calcMemoryPercent, getTempStatus, getValColorClass, getTemperatureState,
      updateTrendHover, clearTrendHover, setTrendRange,
      handleThemeChange, handleLocaleChange, handleServerChange, refreshCurrent, toggleAutoRefresh, loadConfig,
    };
  },
});

app.use(ElementPlus);
app.mount('#app');
