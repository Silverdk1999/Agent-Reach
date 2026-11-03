"""Offline tests of Agent Reach bridge input and auth restrictions."""
import asyncio
from pathlib import Path
import unittest

source = (Path(__file__).parents[1] / "bridge.py").read_text(encoding="utf-8")
source = source.replace("app = build_app()", "")  # Do not need MCP dependency for policy tests.
namespace = {"__name__": "__main__"}
exec(compile(source, "bridge.py", "exec"), namespace)


class BridgePolicyTests(unittest.TestCase):
    def test_url_allowlist(self):
        check = namespace["_is_approved_url"]
        self.assertTrue(check("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(check("https://github.com/Silverdk1999/Agent-Reach"))
        self.assertFalse(check("http://127.0.0.1/private"))
        self.assertFalse(check("https://localhost/secret"))
        self.assertFalse(check("https://github.com.evil.invalid/x"))
        self.assertFalse(check("https://user:pass@github.com/x"))
        self.assertFalse(check("file:///etc/passwd"))
        self.assertFalse(check("https://github.com:8443/x"))

    def test_cli_command_allowlist(self):
        validate = namespace["_safe_args"]
        self.assertEqual(validate("github", "ComfyUI"), ["github", "search", "ComfyUI"])
        for illegal in ("update", "../github", "shell"):
            with self.assertRaises(ValueError):
                validate(illegal, "anything")
        with self.assertRaises(ValueError):
            validate("github", "--help")

    def test_bearer_auth_missing(self):
        gate = namespace["BearerGate"](lambda *_: None, "x" * 40)
        results = []

        async def send(message):
            results.append(message)

        async def test():
            await gate({"type": "http", "headers": []}, None, send)

        asyncio.run(test())
        self.assertEqual(results[0]["status"], 401)


if __name__ == "__main__":
    unittest.main()
