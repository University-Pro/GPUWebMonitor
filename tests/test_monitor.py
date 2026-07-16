import os
import sys
import unittest
from collections import namedtuple
from unittest import mock


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as agent_app
import dashboard
import deployment_mode
import gpu_monitor


CpuTimes = namedtuple("CpuTimes", "user system")
MemoryInfo = namedtuple("MemoryInfo", "rss")
VirtualMemory = namedtuple("VirtualMemory", "total available used percent")
NetIO = namedtuple("NetIO", "bytes_sent bytes_recv")
CpuFreq = namedtuple("CpuFreq", "current")


class FakeProcess:
    def __init__(self, pid, name, cpu_time, rss, username="user", cmdline=None):
        self.info = {
            "pid": pid,
            "name": name,
            "username": username,
            "cmdline": cmdline or ["python", f"job-{pid}.py"],
            "create_time": 1000 + pid,
            "cpu_times": CpuTimes(cpu_time, 0),
            "memory_info": MemoryInfo(rss),
        }
        self._username = username
        self._cmdline = self.info["cmdline"]

    def oneshot(self):
        return mock.MagicMock(__enter__=lambda value: value, __exit__=lambda *args: None)

    def username(self):
        return self._username

    def cmdline(self):
        return self._cmdline


class ProcessCollectionTests(unittest.TestCase):
    def setUp(self):
        gpu_monitor._process_cpu_samples = {}

    def test_process_union_supports_cpu_and_memory_sorting(self):
        cpu_heavy = FakeProcess(101, "cpu-heavy", 1, 100)
        memory_heavy = FakeProcess(202, "memory-heavy", 1, 10_000)

        with mock.patch.object(gpu_monitor.psutil, "process_iter", return_value=[cpu_heavy, memory_heavy]), mock.patch.object(gpu_monitor.psutil, "cpu_count", return_value=4), mock.patch.object(gpu_monitor.time, "monotonic", return_value=10):
            gpu_monitor.get_system_processes(limit=1, total_memory=40_000)

        cpu_heavy.info["cpu_times"] = CpuTimes(5, 0)
        memory_heavy.info["cpu_times"] = CpuTimes(1.2, 0)
        with mock.patch.object(gpu_monitor.psutil, "process_iter", return_value=[cpu_heavy, memory_heavy]), mock.patch.object(gpu_monitor.psutil, "cpu_count", return_value=4), mock.patch.object(gpu_monitor.time, "monotonic", return_value=12):
            processes = gpu_monitor.get_system_processes(limit=1, total_memory=40_000)

        self.assertEqual({process["pid"] for process in processes}, {101, 202})
        self.assertEqual(processes[0]["pid"], 101)
        self.assertEqual(processes[0]["cpu_percent"], 50.0)
        self.assertEqual(next(process for process in processes if process["pid"] == 202)["memory_rss"], 10_000)
        self.assertEqual(next(process for process in processes if process["pid"] == 202)["memory_percent"], 25.0)

    def test_identical_commands_are_grouped_and_totals_match(self):
        first = FakeProcess(301, "python", 1, 1_000, cmdline=["python", "train.py"])
        second = FakeProcess(302, "python", 2, 3_000, cmdline=["python", "train.py"])

        with mock.patch.object(gpu_monitor.psutil, "process_iter", return_value=[first, second]), mock.patch.object(gpu_monitor.psutil, "cpu_count", return_value=4), mock.patch.object(gpu_monitor.time, "monotonic", return_value=20):
            gpu_monitor.get_system_processes(total_memory=100_000)

        first.info["cpu_times"] = CpuTimes(2, 0)
        second.info["cpu_times"] = CpuTimes(3, 0)
        with mock.patch.object(gpu_monitor.psutil, "process_iter", return_value=[first, second]), mock.patch.object(gpu_monitor.psutil, "cpu_count", return_value=4), mock.patch.object(gpu_monitor.time, "monotonic", return_value=22):
            processes = gpu_monitor.get_system_processes(total_memory=100_000)

        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0]["pids"], [301, 302])
        self.assertEqual(processes[0]["instance_count"], 2)
        self.assertEqual(processes[0]["cpu_percent"], 25.0)
        self.assertEqual(processes[0]["memory_bytes"], 4_000)
        self.assertEqual(processes[0]["memory_rss"], 4_000)
        self.assertEqual(processes[0]["memory_percent"], 4.0)

    def test_pss_prevents_shared_memory_double_counting_and_builds_user_totals(self):
        first = FakeProcess(401, "worker", 1, 2_000, username="alice", cmdline=["python", "train.py"])
        second = FakeProcess(402, "worker", 1, 2_000, username="alice", cmdline=["python", "train.py"])
        other = FakeProcess(403, "server", 1, 1_000, username="bob", cmdline=["server"])
        snapshot = {
            "401": {"create_time": 1401, "pss": 600},
            "402": {"create_time": 1402, "pss": 700},
            "403": {"create_time": 1403, "pss": 900},
        }

        with mock.patch.object(gpu_monitor, "_load_memory_snapshot", return_value=snapshot), \
                mock.patch.object(gpu_monitor.psutil, "process_iter", return_value=[first, second, other]), \
                mock.patch.object(gpu_monitor.psutil, "cpu_count", return_value=4), \
                mock.patch.object(gpu_monitor.time, "monotonic", return_value=30):
            gpu_monitor.get_system_process_usage(total_memory=10_000)

        first.info["cpu_times"] = CpuTimes(2, 0)
        second.info["cpu_times"] = CpuTimes(2, 0)
        other.info["cpu_times"] = CpuTimes(1.4, 0)
        with mock.patch.object(gpu_monitor, "_load_memory_snapshot", return_value=snapshot), \
                mock.patch.object(gpu_monitor.psutil, "process_iter", return_value=[first, second, other]), \
                mock.patch.object(gpu_monitor.psutil, "cpu_count", return_value=4), \
                mock.patch.object(gpu_monitor.time, "monotonic", return_value=32):
            usage = gpu_monitor.get_system_process_usage(total_memory=10_000)

        alice_process = next(process for process in usage["processes"] if process["username"] == "alice")
        self.assertEqual(alice_process["memory_bytes"], 1_300)
        self.assertEqual(alice_process["memory_rss"], 4_000)
        self.assertEqual(alice_process["memory_metric"], "pss")
        alice = next(user for user in usage["users"] if user["username"] == "alice")
        self.assertEqual(alice["cpu_percent"], 25.0)
        self.assertEqual(alice["memory_bytes"], 1_300)
        self.assertEqual(alice["memory_percent"], 13.0)
        self.assertEqual(alice["process_group_count"], 1)
        self.assertEqual(alice["instance_count"], 2)

    def test_system_totals_use_consistent_cpu_and_memory_percentages(self):
        memory = VirtualMemory(total=1_000, available=350, used=500, percent=50)
        with mock.patch.object(gpu_monitor.psutil, "cpu_percent", return_value=125), \
                mock.patch.object(gpu_monitor.psutil, "virtual_memory", return_value=memory), \
                mock.patch.object(gpu_monitor.psutil, "net_io_counters", return_value=NetIO(10, 20)), \
                mock.patch.object(gpu_monitor.psutil, "cpu_freq", return_value=CpuFreq(2_200)), \
                mock.patch.object(gpu_monitor.psutil, "cpu_count", return_value=8), \
                mock.patch.object(gpu_monitor, "get_system_process_usage", return_value={"processes": [], "users": [], "memory_metric": "pss"}) as get_usage:
            info = gpu_monitor.get_system_info()

        self.assertEqual(info["cpu"]["percent"], 100.0)
        self.assertEqual(info["memory"]["used"], 650)
        self.assertEqual(info["memory"]["percent"], 65.0)
        self.assertEqual(info["users"], [])
        self.assertEqual(info["process_memory_metric"], "pss")
        get_usage.assert_called_once_with(total_memory=1_000)


class AuthenticationTests(unittest.TestCase):
    def test_agent_api_requires_bearer_token(self):
        original_token = agent_app.AGENT_TOKEN
        original_mode = agent_app.DEPLOYMENT_MODE
        agent_app.AGENT_TOKEN = "agent-secret"
        agent_app.DEPLOYMENT_MODE = deployment_mode.PUBLIC_MODE
        self.addCleanup(setattr, agent_app, "AGENT_TOKEN", original_token)
        self.addCleanup(setattr, agent_app, "DEPLOYMENT_MODE", original_mode)

        client = agent_app.app.test_client()
        self.assertEqual(client.get("/api/status").status_code, 401)

        payload = {"system": {}, "gpu": {"gpus": [], "summary": {}}}
        with mock.patch.object(agent_app.gpu_monitor, "get_all_info", return_value=payload):
            response = client.get("/api/status", headers={"Authorization": "Bearer agent-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], payload)

    def test_public_agent_fails_closed_without_token(self):
        with mock.patch.object(agent_app, "DEPLOYMENT_MODE", deployment_mode.PUBLIC_MODE), \
                mock.patch.object(agent_app, "AGENT_TOKEN", ""):
            response = agent_app.app.test_client().get("/api/status")
        self.assertEqual(response.status_code, 503)

    def test_lan_agent_does_not_require_token(self):
        payload = {"system": {}, "gpu": {"gpus": [], "summary": {}}}
        with mock.patch.object(agent_app, "DEPLOYMENT_MODE", deployment_mode.LAN_MODE), \
                mock.patch.object(agent_app, "AGENT_TOKEN", "agent-secret"), \
                mock.patch.object(agent_app.gpu_monitor, "get_all_info", return_value=payload):
            response = agent_app.app.test_client().get("/api/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], payload)

    def test_dashboard_auth_and_public_config_redaction(self):
        original_username = dashboard.DASHBOARD_USERNAME
        original_password = dashboard.DASHBOARD_PASSWORD
        original_token = dashboard.AGENT_TOKEN
        original_mode = dashboard.DEPLOYMENT_MODE
        dashboard.DASHBOARD_USERNAME = "monitor"
        dashboard.DASHBOARD_PASSWORD = "strong-password"
        dashboard.AGENT_TOKEN = "agent-secret"
        dashboard.DEPLOYMENT_MODE = deployment_mode.PUBLIC_MODE
        self.addCleanup(setattr, dashboard, "DASHBOARD_USERNAME", original_username)
        self.addCleanup(setattr, dashboard, "DASHBOARD_PASSWORD", original_password)
        self.addCleanup(setattr, dashboard, "AGENT_TOKEN", original_token)
        self.addCleanup(setattr, dashboard, "DEPLOYMENT_MODE", original_mode)

        client = dashboard.app.test_client()
        self.assertEqual(client.get("/api/config").status_code, 401)

        response = client.get(
            "/api/config",
            headers={"Authorization": "Basic bW9uaXRvcjpzdHJvbmctcGFzc3dvcmQ="},
        )
        self.assertEqual(response.status_code, 200)
        servers = response.get_json()["servers"]
        self.assertTrue(servers)
        self.assertNotIn("url", servers[0])

        blocked = client.get(
            "/config.json",
            headers={"Authorization": "Basic bW9uaXRvcjpzdHJvbmctcGFzc3dvcmQ="},
        )
        self.assertEqual(blocked.status_code, 403)

        blocked_named_config = client.get(
            "/config.public.json",
            headers={"Authorization": "Basic bW9uaXRvcjpzdHJvbmctcGFzc3dvcmQ="},
        )
        self.assertEqual(blocked_named_config.status_code, 403)

    def test_public_dashboard_fails_closed_without_credentials(self):
        with mock.patch.object(dashboard, "DEPLOYMENT_MODE", deployment_mode.PUBLIC_MODE), \
                mock.patch.object(dashboard, "DASHBOARD_USERNAME", ""), \
                mock.patch.object(dashboard, "DASHBOARD_PASSWORD", ""):
            response = dashboard.app.test_client().get("/api/config")
        self.assertEqual(response.status_code, 503)

    def test_lan_dashboard_is_login_free_and_returns_full_config(self):
        config = {
            "servers": [
                {"id": "lan-node", "name": "LAN node", "url": "http://192.168.1.10:15896"}
            ]
        }
        agent_response = mock.Mock(status_code=200)
        agent_response.json.return_value = {"code": 200, "data": {}, "msg": "success"}

        with mock.patch.object(dashboard, "DEPLOYMENT_MODE", deployment_mode.LAN_MODE), \
                mock.patch.object(dashboard, "DASHBOARD_USERNAME", "public-user"), \
                mock.patch.object(dashboard, "DASHBOARD_PASSWORD", "public-password"), \
                mock.patch.object(dashboard, "AGENT_TOKEN", "public-agent-token"), \
                mock.patch.object(dashboard, "load_config", return_value=config), \
                mock.patch.object(dashboard.requests, "get", return_value=agent_response) as request_agent:
            client = dashboard.app.test_client()
            response = client.get("/api/config")
            legacy_config = client.get("/config.json")
            proxied = client.get("/api/proxy?id=lan-node")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["deployment_mode"], deployment_mode.LAN_MODE)
        self.assertEqual(response.get_json()["servers"][0]["url"], "http://192.168.1.10:15896")
        self.assertEqual(legacy_config.status_code, 200)
        self.assertEqual(proxied.status_code, 200)
        self.assertEqual(request_agent.call_args.kwargs["headers"], {})
        self.assertFalse(request_agent.call_args.kwargs["verify"])


class DeploymentModeTests(unittest.TestCase):
    def test_modes_are_normalized_and_invalid_values_fail(self):
        self.assertEqual(deployment_mode.load_deployment_mode(" LAN "), deployment_mode.LAN_MODE)
        self.assertEqual(deployment_mode.load_deployment_mode("PUBLIC"), deployment_mode.PUBLIC_MODE)
        with self.assertRaises(RuntimeError):
            deployment_mode.load_deployment_mode("internet")

    def test_unset_mode_preserves_original_lan_behavior(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(deployment_mode.load_deployment_mode(), deployment_mode.LAN_MODE)

    def test_boolean_settings_are_validated(self):
        with mock.patch.dict(os.environ, {"SETTING": "yes"}):
            self.assertTrue(deployment_mode.load_boolean_setting("SETTING", False))
        with mock.patch.dict(os.environ, {"SETTING": "off"}):
            self.assertFalse(deployment_mode.load_boolean_setting("SETTING", True))
        with mock.patch.dict(os.environ, {"SETTING": "maybe"}):
            with self.assertRaises(RuntimeError):
                deployment_mode.load_boolean_setting("SETTING", True)


if __name__ == "__main__":
    unittest.main()
