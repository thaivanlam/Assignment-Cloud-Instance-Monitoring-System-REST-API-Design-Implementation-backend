"""Drive Swagger UI with a real browser and screenshot every executed API call.

Unlike a hosted screenshot service, this runs against http://127.0.0.1:8000 (no tunnel,
no credits) and actually clicks **Authorize -> Try it out -> Execute**, so each PNG shows
the live response body and status code — including the 409 / 403 / 404 / 401 cases.

Setup (once):

    pip install -r requirements-dev.txt
    playwright install chromium

Run:

    uvicorn app.main:app --reload          # terminal 1
    python scripts/capture_swagger_ui.py   # terminal 2

Output: docs/screenshots/NN_<name>.png, one per scenario, cropped to the operation block.

Notes
-----
* Scenarios run in a deliberate order: the monitoring endpoints must run before the alert
  endpoints, because they are what create the alerts.
* Side effects on the demo database: each run adds one client ("Screenshot Demo Co") and
  resolves one alert. The demo instance it creates is deleted again by the last scenario,
  and instance 1 survives the DELETE because the RUNNING rule blocks it (that is the point).
  Delete monitoring.db and restart to get a pristine seed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sys.exit("playwright is not installed. Run: pip install -r requirements-dev.txt")

ADMIN = ("admin@techvalley.vn", "admin123!")
MANAGER = ("lam@techvalley.vn", "manager123!")

# Swagger caps code blocks at ~400px and scrolls them internally, which silently truncates
# long response bodies (the monitor report, instance lists, the LLM diagnosis) mid-JSON.
# A screenshot cannot scroll, so the cap has to go.
RESPONSE_CSS = """
.swagger-ui .highlight-code > .microlight,
.opblock-body pre.microlight { max-height: none !important; overflow: visible !important; }
"""

# Trims the two things that dominate the height of a capture without adding information:
# the oversized empty request-body editor, and the static documented-responses table that
# repeats below the actual server response. Pure CSS, so React's DOM is left untouched.
COMPACT_CSS = """
.opblock-body textarea.body-param__text { field-sizing: content; min-height: 4.5em; }
.opblock-body table.responses-table:not(.live-responses-table) { display: none; }
/* The heading for that table is the trailing child of the live-response block, not a
   sibling of the table itself, so it has to be matched separately. */
.opblock-body .responses-inner > div > h4:last-child { display: none; }
"""


@dataclass
class Scenario:
    """One screenshot: locate the operation, fill it in, Execute, capture."""

    name: str
    method: str
    path: str
    account: str | None = None  # "admin" | "manager" | None (unauthenticated)
    expect: int | None = None
    path_params: dict[str, Any] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    body: dict | None = None
    timeout: int = 30_000
    note: str = ""


DEMO_INSTANCE = "screenshot-demo-01"


def _demo_instance_id(ctx: "Runner") -> int | None:
    """Id of the instance created earlier in this run (or by a previous run)."""
    data = ctx.api_get("/api/instances", token=ctx.token_for("admin"), params={"size": "100"})
    for item in (data or {}).get("items", []):
        if item["instanceName"] == DEMO_INSTANCE:
            return item["id"]
    return None


def _unresolved_alert_id(ctx: "Runner") -> int | None:
    alerts = ctx.api_get("/api/alerts", token=ctx.token_for("admin"), params={"isResolved": "false"})
    return alerts[0]["id"] if alerts else None


SCENARIOS: list[Scenario] = [
    # ---------- unauthenticated ----------
    Scenario("health", "GET", "/", note="Health check"),
    Scenario(
        "login_admin", "POST", "/api/auth/login", expect=200,
        body={"email": ADMIN[0], "password": ADMIN[1]}, note="JWT issuance",
    ),
    Scenario(
        "login_wrong_password", "POST", "/api/auth/login", expect=401,
        body={"email": ADMIN[0], "password": "wrong-password"}, note="401 invalid credentials",
    ),
    # ---------- ADMIN ----------
    Scenario("clients_list_admin", "GET", "/api/clients", "admin", 200, note="All 10 clients"),
    Scenario(
        "client_create", "POST", "/api/clients", "admin", 201,
        body={"clientName": "Screenshot Demo Co", "contractPlan": "STANDARD", "managerId": 2},
        note="ADMIN-only registration",
    ),
    Scenario(
        "instances_list_sorted", "GET", "/api/instances", "admin", 200,
        query_params={"page": 1, "size": 5, "sort": "-cpuUsage"},
        note="Pagination + sort by CPU desc",
    ),
    Scenario(
        "instances_list_filtered", "GET", "/api/instances", "admin", 200,
        query_params={"status": "RUNNING", "region": "ap-southeast-1", "instanceType": "LARGE"},
        note="Filter by status / region / type",
    ),
    Scenario("instance_get", "GET", "/api/instances/{instance_id}", "admin", 200,
             path_params={"instance_id": 1}),
    Scenario(
        "instance_create", "POST", "/api/instances", "admin", 201,
        body={
            "instanceName": DEMO_INSTANCE,
            "region": "ap-southeast-1",
            "instanceType": "SMALL",
            "status": "STOPPED",
            "cpuUsage": 0,
            "clientId": 1,
        },
        note="Cost auto-derived from instanceType",
    ),
    Scenario(
        "instance_update_status", "PATCH", "/api/instances/{instance_id}/status", "admin", 200,
        path_params={"instance_id": 15}, body={"status": "RUNNING", "cpuUsage": 42.5},
    ),
    Scenario(
        "instance_diagnosis_llm", "GET", "/api/instances/{instance_id}/diagnosis", "admin", 200,
        path_params={"instance_id": 5}, timeout=120_000,
        note="[LLM] hnlog-worker-01 is ERROR in the seed data",
    ),
    # ---------- monitoring (creates the alerts the next block reads) ----------
    Scenario("monitor_warnings", "GET", "/api/monitor/warnings", "admin", 200,
             note="CPU >= 80% + auto-records CPU_HIGH alerts"),
    Scenario("monitor_errors", "GET", "/api/monitor/errors", "admin", 200),
    Scenario("monitor_long_stopped", "GET", "/api/monitor/long-stopped", "admin", 200),
    Scenario("monitor_report", "GET", "/api/monitor/report", "admin", 200),
    # ---------- alerts ----------
    Scenario("alerts_list", "GET", "/api/alerts", "admin", 200),
    Scenario(
        "alerts_list_filtered", "GET", "/api/alerts", "admin", 200,
        query_params={"alertType": "CPU_HIGH", "isResolved": "false"},
        note="Filter by type + resolved state",
    ),
    Scenario("alert_resolve", "PATCH", "/api/alerts/{alert_id}/resolve", "admin", 200,
             path_params={"alert_id": _unresolved_alert_id}),
    # ---------- cost / SLA ----------
    Scenario("client_instances", "GET", "/api/clients/{client_id}/instances", "admin", 200,
             path_params={"client_id": 1}),
    Scenario("client_cost", "GET", "/api/clients/{client_id}/cost", "admin", 200,
             path_params={"client_id": 1}),
    Scenario("client_cost_forecast", "GET", "/api/clients/{client_id}/cost-forecast", "admin", 200,
             path_params={"client_id": 1}),
    Scenario("client_sla", "GET", "/api/clients/{client_id}/sla", "admin", 200,
             path_params={"client_id": 1}, note="VinaSoft is PREMIUM -> 99.9% threshold"),
    # ---------- business-rule failures ----------
    Scenario(
        "delete_running_409", "DELETE", "/api/instances/{instance_id}", "admin", 409,
        path_params={"instance_id": 1}, note="ActiveInstanceException — RUNNING cannot be deleted",
    ),
    Scenario("instance_not_found_404", "GET", "/api/instances/{instance_id}", "admin", 404,
             path_params={"instance_id": 9999}),
    # ---------- CLIENT_MANAGER (role scoping) ----------
    Scenario("clients_list_manager", "GET", "/api/clients", "manager", 200,
             note="Scoped to clients 1-5 only"),
    Scenario(
        "client_sla_forbidden_403", "GET", "/api/clients/{client_id}/sla", "manager", 403,
        path_params={"client_id": 6}, note="Client 6 belongs to the other manager",
    ),
    Scenario(
        "client_create_forbidden_403", "POST", "/api/clients", "manager", 403,
        body={"clientName": "Not Allowed", "contractPlan": "BASIC", "managerId": 2},
        note="ADMIN role required",
    ),
    # ---------- unauthenticated again ----------
    Scenario("instances_unauthorized_401", "GET", "/api/instances", None, 401,
             note="No Bearer token"),
    # ---------- cleanup (also documents the 204 path) ----------
    Scenario(
        "delete_stopped_204", "DELETE", "/api/instances/{instance_id}", "admin", 204,
        path_params={"instance_id": _demo_instance_id},
        note="STOPPED instance deletes normally — also cleans up this run",
    ),
]


class Runner:
    def __init__(self, page, base_url: str, out_dir: str, spec: dict):
        self.page = page
        self.base_url = base_url
        self.out_dir = out_dir
        self.spec = spec
        self._tokens: dict[str, str] = {}
        self._authorized_as: str | None = None

    # ----- API helpers (used to resolve dynamic ids and fetch tokens) -----
    def api_get(self, path: str, token: str, params: dict | None = None):
        response = self.page.request.get(
            f"{self.base_url}{path}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}"},
        )
        return response.json() if response.ok else None

    def token_for(self, account: str) -> str:
        if account not in self._tokens:
            email, password = ADMIN if account == "admin" else MANAGER
            response = self.page.request.post(
                f"{self.base_url}/api/auth/login", data={"email": email, "password": password}
            )
            if not response.ok:
                raise RuntimeError(f"login failed for {email}: {response.status} {response.text()}")
            self._tokens[account] = response.json()["accessToken"]
        return self._tokens[account]

    # ----- Swagger UI interactions -----
    def resolve_operation(self, method: str, path: str) -> tuple[str, str]:
        """Look up (tag, operationId) in the live spec so nothing is hardcoded."""
        operation = self.spec["paths"].get(path, {}).get(method.lower())
        if operation is None:
            raise KeyError(f"{method} {path} is not in openapi.json")
        tag = (operation.get("tags") or ["default"])[0]
        return tag, operation["operationId"]

    def set_auth(self, account: str | None) -> None:
        """Drive the Authorize dialog so the captures show a genuinely authorized call.

        Selectors are class-based on purpose: the apply button carries
        aria-label="Apply credentials", so matching it by its "Authorize" label fails.
        """
        if account == self._authorized_as:
            return
        page = self.page
        page.locator(".scheme-container button.authorize").first.click()
        modal = page.locator(".modal-ux").first
        modal.wait_for(state="visible", timeout=10_000)

        try:
            logout = modal.locator('button:has-text("Logout")')
            if logout.count() > 0:
                logout.first.click()

            if account is not None:
                modal.locator(
                    '#auth-bearer-value, input[aria-label="auth-bearer-value"]'
                ).first.fill(self.token_for(account))
                modal.locator("button.modal-btn.auth.authorize").first.click()

            modal.locator("button.modal-btn.auth.btn-done").first.click()
            modal.wait_for(state="hidden", timeout=10_000)
            self._authorized_as = account
        finally:
            # A modal left open would intercept every later click, so never leave one behind.
            if modal.is_visible():
                self._authorized_as = "__unknown__"
                page.locator(".modal-ux button.close-modal").first.click()
                modal.wait_for(state="hidden", timeout=10_000)

    def _fill_param(self, block, name: str, value: Any) -> None:
        row = block.locator(f'tr[data-param-name="{name}"]').first
        if row.count() == 0:
            print(f"    ! parameter {name!r} not found in the form", file=sys.stderr)
            return
        # Enum / bool parameters render as a <select>; everything else as a text input.
        # `.content-type` selects belong to the media-type picker, not to a parameter.
        select = row.locator("select:not(.content-type)")
        if select.count() > 0:
            select.first.select_option(str(value))
        else:
            row.locator("input").first.fill(str(value))

    def run(self, index: int, scenario: Scenario) -> tuple[bool, str]:
        page = self.page
        tag, operation_id = self.resolve_operation(scenario.method, scenario.path)

        # Resolve callables (ids that only exist at runtime).
        path_params = {}
        for key, value in scenario.path_params.items():
            resolved = value(self) if callable(value) else value
            if resolved is None:
                return False, f"could not resolve path parameter {key!r} — skipped"
            path_params[key] = resolved

        self.set_auth(scenario.account)

        block = page.locator(f"#operations-{tag}-{operation_id}")
        block.scroll_into_view_if_needed()
        if "is-open" not in (block.get_attribute("class") or ""):
            block.locator(".opblock-summary").first.click()
        block.locator(".opblock-body").first.wait_for(state="visible", timeout=10_000)

        # Absent when the operation is already in try-out mode from an earlier scenario,
        # where the button reads "Cancel" instead.
        try_out = block.get_by_role("button", name="Try it out")
        try:
            try_out.first.wait_for(state="visible", timeout=3_000)
            try_out.first.click()
        except PlaywrightTimeout:
            pass

        # A response from a previous scenario on this same operation is still on screen;
        # clear it so the wait below cannot latch onto the stale status code.
        clear = block.get_by_role("button", name="Clear")
        if clear.count() > 0:
            clear.first.click()
            try:
                block.locator("table.live-responses-table").first.wait_for(
                    state="detached", timeout=5_000
                )
            except PlaywrightTimeout:
                pass

        for key, value in path_params.items():
            self._fill_param(block, key, value)
        for key, value in scenario.query_params.items():
            self._fill_param(block, key, value)
        if scenario.body is not None:
            textarea = block.locator("textarea.body-param__text").first
            textarea.wait_for(state="visible", timeout=10_000)
            textarea.fill(json.dumps(scenario.body, indent=2))

        block.get_by_role("button", name="Execute").first.click()

        # ":not(.col_header)" skips the "Code" header cell of the live-response table.
        status_cell = block.locator(
            "table.live-responses-table td.response-col_status:not(.col_header)"
        ).first
        try:
            status_cell.wait_for(state="visible", timeout=scenario.timeout)
        except PlaywrightTimeout:
            return False, f"no response after {scenario.timeout} ms"

        actual = re.sub(r"\D", "", status_cell.inner_text())[:3]
        filename = f"{index:02d}_{scenario.name}.png"
        block.screenshot(path=f"{self.out_dir}/{filename}")

        # Collapse so the next capture is not visually crowded.
        block.locator(".opblock-summary").first.click()

        if scenario.expect is not None and actual != str(scenario.expect):
            return False, f"expected {scenario.expect}, got {actual} (saved {filename})"
        return True, f"{actual} -> {filename}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("-o", "--out", default="docs/screenshots")
    parser.add_argument("--headed", action="store_true", help="Watch the browser work")
    parser.add_argument("--slow-mo", type=int, default=0, help="Delay each action by N ms")
    parser.add_argument("--only", default=None, help="Substring filter on scenario name")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--scale", type=int, default=2, help="Device scale factor (retina)")
    parser.add_argument(
        "--no-compact",
        dest="compact",
        action="store_false",
        help="Keep the empty body editor and the documented-responses table in the capture",
    )
    parser.set_defaults(compact=True)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    # Number by position in the full list, not the filtered one, so `--only` rewrites
    # the same file instead of creating a renumbered duplicate alongside it.
    scenarios = list(enumerate(SCENARIOS, start=1))
    if args.only:
        scenarios = [(i, s) for i, s in scenarios if args.only in s.name]
    if not scenarios:
        print("No scenarios matched --only.", file=sys.stderr)
        return 1

    import os

    os.makedirs(args.out, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed, slow_mo=args.slow_mo)
        context = browser.new_context(
            viewport={"width": args.width, "height": 1000},
            device_scale_factor=args.scale,
        )
        page = context.new_page()

        try:
            spec_response = page.request.get(f"{base_url}/openapi.json")
            if not spec_response.ok:
                raise RuntimeError(f"HTTP {spec_response.status}")
            spec = spec_response.json()
        except (PlaywrightError, RuntimeError) as exc:
            print(
                f"Cannot read {base_url}/openapi.json ({exc}).\n"
                "Is the server running?  uvicorn app.main:app --reload",
                file=sys.stderr,
            )
            browser.close()
            return 2

        page.goto(f"{base_url}/docs", wait_until="domcontentloaded")
        page.wait_for_selector(".opblock", timeout=30_000)
        page.add_style_tag(content=RESPONSE_CSS)
        if args.compact:
            page.add_style_tag(content=COMPACT_CSS)

        runner = Runner(page, base_url, args.out, spec)
        failures = 0
        print(f"{len(scenarios)} scenario(s) -> {args.out}/\n")

        for position, (index, scenario) in enumerate(scenarios, start=1):
            label = f"[{position:>2}/{len(scenarios)}] {scenario.name:<28}"
            try:
                ok, detail = runner.run(index, scenario)
            except Exception as exc:  # noqa: BLE001 — one bad scenario must not stop the run
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            if ok:
                print(f"{label} {detail}", flush=True)
            else:
                failures += 1
                print(f"{label} FAILED: {detail}", file=sys.stderr, flush=True)

        browser.close()

    print(f"\nDone. {len(scenarios) - failures} captured, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
