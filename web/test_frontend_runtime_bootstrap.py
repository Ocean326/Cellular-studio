from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


INDEX_HTML_PATH = Path(__file__).resolve().parent / "index.html"


@unittest.skipUnless(shutil.which("node"), "node is required for frontend runtime bootstrap checks")
class FrontendRuntimeBootstrapTest(unittest.TestCase):
	def test_state_script_loads_before_workspace_script(self) -> None:
		html = INDEX_HTML_PATH.read_text(encoding="utf-8")
		state_pos = html.find('./app/runtime/state.js')
		workspace_pos = html.find('./app/features/workspace/workspace.js')
		self.assertNotEqual(state_pos, -1, "missing state.js script tag")
		self.assertNotEqual(workspace_pos, -1, "missing workspace.js script tag")
		self.assertLess(state_pos, workspace_pos, "state.js must load before workspace.js")

	def test_bootstrap_and_uid_click_render_layers(self) -> None:
		project_root = Path(__file__).resolve().parent.parent
		node_script = textwrap.dedent(
			f"""
			const fs = require("fs");
			const path = require("path");
			const vm = require("vm");

			const projectRoot = {json.dumps(str(project_root))};
			const htmlPath = path.join(projectRoot, "web", "index.html");
			const html = fs.readFileSync(htmlPath, "utf8");
			const localScriptMatches = [...html.matchAll(/<script src="(\\.\\/app\\/[^\"]+)"><\\/script>/g)];
			const localScripts = localScriptMatches.map((match) => match[1].replace(/^\\.\\//, "web/"));

			class ClassList {{
				constructor(element) {{
					this.element = element;
					this.names = new Set();
				}}
				add(...names) {{
					names.forEach((name) => this.names.add(name));
					this.sync();
				}}
				remove(...names) {{
					names.forEach((name) => this.names.delete(name));
					this.sync();
				}}
				toggle(name, force) {{
					if (force === undefined) {{
						if (this.names.has(name)) this.names.delete(name);
						else this.names.add(name);
					}} else if (force) {{
						this.names.add(name);
					}} else {{
						this.names.delete(name);
					}}
					this.sync();
					return this.names.has(name);
				}}
				contains(name) {{
					return this.names.has(name);
				}}
				sync() {{
					this.element.className = [...this.names].join(" ");
				}}
			}}

			class ElementMock {{
				constructor(id = "", tag = "div") {{
					this.id = id;
					this.tagName = String(tag || "div").toUpperCase();
					this.textContent = "";
					this.value = "";
					this.innerHTML = "";
					this.dataset = {{}};
					this.disabled = false;
					this.checked = false;
					this.className = "";
					this.attributes = {{}};
					this.listeners = {{}};
					this.files = [];
					this.title = "";
					this.placeholder = "";
					this.clientWidth = 800;
					this.clientHeight = 80;
					this.offsetWidth = 800;
					this.offsetHeight = 80;
					this.style = {{
						setProperty(key, value) {{
							this[key] = value;
						}},
					}};
					this.classList = new ClassList(this);
				}}
				addEventListener(type, handler) {{
					(this.listeners[type] ||= []).push(handler);
				}}
				removeEventListener(type, handler) {{
					this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== handler);
				}}
				setAttribute(name, value) {{
					this.attributes[name] = String(value);
				}}
				getAttribute(name) {{
					return this.attributes[name];
				}}
				contains(target) {{
					return target === this;
				}}
				closest(selector) {{
					if (selector === ".triage-card[data-uid]" && this.dataset.uid) return this;
					if (selector === ".load-more-btn[data-column]" && this.dataset.column) return this;
					if (selector === ".triage-tab[data-column]" && this.dataset.column) return this;
					if (selector === "button[data-studio-action]" && this.dataset.studioAction) return this;
					if (selector === ".reviewer-known-btn[data-reviewer-id]" && this.dataset.reviewerId) return this;
					if (selector === ".time-scrubber-menu-item[data-action]" && this.dataset.action) return this;
					if (selector === ".date-window-group" && this.dataset.edge) return this;
					return null;
				}}
				querySelector(selector) {{
					if (selector.includes('[data-opt="visible"]')) return this.visibleInput || null;
					if (selector.includes('[data-opt="show-labels"]')) return this.showLabelsInput || null;
					if (selector.includes('[data-opt="color"]')) return this.colorInput || null;
					if (selector.includes('[data-opt="opacity"]')) return this.opacityInput || null;
					if (selector.includes(".opacity-val")) return this.opacityValue || null;
					if (selector.includes('[data-opt="size"]')) return this.sizeInput || null;
					if (selector.includes(".size-val")) return this.sizeValue || null;
					return null;
				}}
				querySelectorAll() {{
					return [];
				}}
				getBoundingClientRect() {{
					return {{ left: 0, top: 0, width: 800, height: 80 }};
				}}
				getContext() {{
					return {{
						clearRect() {{}},
						beginPath() {{}},
						moveTo() {{}},
						lineTo() {{}},
						stroke() {{}},
						fill() {{}},
						arc() {{}},
						rect() {{}},
						roundRect() {{}},
						closePath() {{}},
						fillRect() {{}},
						strokeRect() {{}},
						setLineDash() {{}},
						setTransform() {{}},
						fillText() {{}},
						save() {{}},
						restore() {{}},
						measureText(text) {{
							return {{ width: String(text || "").length * 8 }};
						}},
					}};
				}}
				focus() {{}}
				select() {{}}
				setPointerCapture() {{}}
				releasePointerCapture() {{}}
			}}

			const elements = new Map();
			function getElement(id) {{
				if (!elements.has(id)) elements.set(id, new ElementMock(id));
				return elements.get(id);
			}}

			const reviewDecisionButtons = ["accept", "reject", "skip"].map((decision) => {{
				const element = new ElementMock("", "button");
				element.dataset.decision = decision;
				return element;
			}});
			const dateWindowGroups = ["start", "end"].map((edge) => {{
				const element = new ElementMock("", "div");
				element.dataset.edge = edge;
				return element;
			}});

			const document = {{
				body: new ElementMock("body", "body"),
				getElementById(id) {{
					return getElement(id);
				}},
				querySelectorAll(selector) {{
					if (selector === ".review-decision-btn") return reviewDecisionButtons;
					if (selector === ".date-window-group") return dateWindowGroups;
					if (selector === "#layer-controls .layer-row[data-layer]") {{
						const html = getElement("layer-controls").innerHTML || "";
						const matches = [...html.matchAll(/data-layer="([^"]+)"/g)].map((match) => match[1]);
						return matches.map((layer) => {{
							const row = new ElementMock("", "div");
							row.dataset.layer = layer;
							row.visibleInput = new ElementMock("", "input");
							row.visibleInput.checked = true;
							row.showLabelsInput = new ElementMock("", "input");
							row.showLabelsInput.checked = false;
							row.colorInput = new ElementMock("", "input");
							row.colorInput.value = "#000000";
							row.opacityInput = new ElementMock("", "input");
							row.opacityInput.value = "0.7";
							row.opacityValue = new ElementMock("", "span");
							return row;
						}});
					}}
					if (selector === "#status-style-controls .status-style-row") {{
						const html = getElement("status-style-controls").innerHTML || "";
						const matches = [...html.matchAll(/data-mt="([^"]+)"/g)].map((match) => match[1]);
						return matches.map((name) => {{
							const row = new ElementMock("", "div");
							row.dataset.mt = name;
							row.colorInput = new ElementMock("", "input");
							row.sizeInput = new ElementMock("", "input");
							row.sizeValue = new ElementMock("", "span");
							return row;
						}});
					}}
					if (selector === "#annotation-tag-list .annotation-tag-name") return [];
					return [];
				}},
				addEventListener() {{}},
			}};

			const localStorageStore = new Map();
			const localStorage = {{
				getItem(key) {{
					return localStorageStore.has(key) ? localStorageStore.get(key) : null;
				}},
				setItem(key, value) {{
					localStorageStore.set(key, String(value));
				}},
				removeItem(key) {{
					localStorageStore.delete(key);
				}},
			}};

			function makeLayer(base = {{}}) {{
				return Object.assign(
					{{
						_tooltip: null,
						addTo(target) {{
							if (target && typeof target.addLayer === "function") target.addLayer(this);
							return this;
						}},
						bindPopup() {{
							return this;
						}},
						bindTooltip(content) {{
							this._tooltip = {{
								content,
								getElement() {{
									return new ElementMock("", "div");
								}},
							}};
							return this;
						}},
						getTooltip() {{
							return this._tooltip;
						}},
						setTooltipContent(content) {{
							if (this._tooltip) this._tooltip.content = content;
						}},
						on() {{
							return this;
						}},
						getElement() {{
							return new ElementMock("", "div");
						}},
					}},
					base,
				);
			}}

			function flattenLatLngs(list, output = []) {{
				if (!Array.isArray(list)) return output;
				for (const item of list) {{
					if (!item) continue;
					if (Array.isArray(item)) flattenLatLngs(item, output);
					else output.push(item);
				}}
				return output;
			}}

			const mapMock = {{
				_layers: new Set(),
				_zoom: 11,
				on() {{}},
				getZoom() {{
					return this._zoom;
				}},
				getContainer() {{
					return getElement("map");
				}},
				addLayer(layer) {{
					this._layers.add(layer);
				}},
				removeLayer(layer) {{
					this._layers.delete(layer);
				}},
				hasLayer(layer) {{
					return this._layers.has(layer);
				}},
				fitBounds(bounds) {{
					this.lastBounds = bounds;
				}},
				invalidateSize() {{}},
			}};

			const L = {{
				map() {{
					return mapMock;
				}},
				tileLayer() {{
					return makeLayer();
				}},
				control: {{
					scale() {{
						return {{
							addTo() {{
								return this;
							}},
						}};
					}},
				}},
				layerGroup() {{
					return {{
						_layers: [],
						addLayer(layer) {{
							this._layers.push(layer);
							return this;
						}},
						addTo(target) {{
							if (target && typeof target.addLayer === "function") target.addLayer(this);
							return this;
						}},
						eachLayer(handler) {{
							this._layers.forEach(handler);
						}},
					}};
				}},
				circleMarker(latlng, options) {{
					return makeLayer({{
						latlng: {{ lat: latlng[0], lng: latlng[1] }},
						options,
						getLatLng() {{
							return this.latlng;
						}},
					}});
				}},
				polyline(latlngs, options) {{
					const flat = flattenLatLngs(latlngs).map((item) =>
						item && typeof item.lat === "number" ? item : {{ lat: item[0], lng: item[1] }}
					);
					return makeLayer({{
						latlngs: flat,
						options,
						getLatLngs() {{
							return flat;
						}},
					}});
				}},
				marker(latlng, options) {{
					return makeLayer({{
						latlng: {{ lat: latlng[0], lng: latlng[1] }},
						options,
						getLatLng() {{
							return this.latlng;
						}},
						setLatLng(value) {{
							this.latlng = {{ lat: value[0], lng: value[1] }};
						}},
						setIcon(icon) {{
							this.options.icon = icon;
						}},
					}});
				}},
				divIcon(options) {{
					return options;
				}},
				latLngBounds(points) {{
					return {{ points }};
				}},
			}};

			function simpleCsvParse(text) {{
				const lines = String(text || "").trim().split(/\\r?\\n/).filter(Boolean);
				if (!lines.length) return {{ data: [] }};
				const header = lines[0].split(",");
				return {{
					data: lines.slice(1).map((line) => {{
						const cols = line.split(",");
						const row = {{}};
						header.forEach((key, index) => {{
							row[key] = cols[index] ?? "";
						}});
						return row;
					}}),
				}};
			}}

			function responseFor(status, body = "") {{
				return {{
					ok: status >= 200 && status < 300,
					status,
					async text() {{
						return typeof body === "string" ? body : JSON.stringify(body);
					}},
					async json() {{
						return typeof body === "string" ? JSON.parse(body) : body;
					}},
				}};
			}}

			const batchesRoot = path.join(projectRoot, "data", "batches");
			const preferredBatchName = "traj-round1-v15-tierrefresh-pilot30-test-hidden";
			const batchDirectories = fs.readdirSync(batchesRoot).filter((name) =>
				fs.existsSync(path.join(batchesRoot, name, "result", "manifest.json"))
			);
			const selectedBatchName = batchDirectories.includes(preferredBatchName) ? preferredBatchName : batchDirectories[0];
			if (!selectedBatchName) throw new Error("no local studio batch with result/manifest.json found");
			const batchFixtures = batchDirectories.map((name) => {{
				const batchRoot = path.join(batchesRoot, name);
				const manifest = JSON.parse(fs.readFileSync(path.join(batchRoot, "result", "manifest.json"), "utf8"));
				return {{
					name,
					label: name,
					data_base: `/batch-data/${{name}}`,
					batch_root: batchRoot,
					result_root: path.join(batchRoot, "result"),
					review_root: path.join(batchRoot, "review"),
					export_root: path.join(batchRoot, "accepted_assets"),
					version: "runtime-test",
					status: "prepared",
					visibility_scope: "public",
					annotation_mode: "annotatable",
					uid_count: Array.isArray(manifest.uids) ? manifest.uids.length : 0,
					ui_config: {{}},
				}};
			}});
			const selectedBatchRoot = path.join(batchesRoot, selectedBatchName);
			const alternateBatchName = batchDirectories.find((name) => name !== selectedBatchName) || "";
			const currentBatchPayload = {{
				current_batch: selectedBatchName,
				batches: batchFixtures,
			}};

			async function fetchMock(rawUrl, options = {{}}) {{
				const method = String(options.method || "GET").toUpperCase();
				const url = new URL(String(rawUrl), "http://localhost");
				if (url.pathname === "/api/batches") return responseFor(200, currentBatchPayload);
				if (url.pathname === "/api/reviewers") return responseFor(200, {{ reviewers: [] }});
				if (url.pathname === "/api/reviews") {{
					if (url.searchParams.get("uid")) return responseFor(200, {{ review: null }});
					return responseFor(200, {{ reviews: {{}}, counts: {{}}, aggregate_counts_by_uid: {{}} }});
				}}
				if (url.pathname === "/api/reviews/aggregate") return responseFor(200, {{ aggregate: null }});
				if (url.pathname === "/api/timeline-annotations") return responseFor(200, {{ annotations: {{ pins: [], segments: [] }} }});
				const batchPrefixMatch = url.pathname.match(/^\\/batch-data\\/([^/]+)\\/(.+)$/);
				if (batchPrefixMatch) {{
					const [, batchName, relative] = batchPrefixMatch;
					const target = path.join(batchesRoot, batchName, "result", relative);
					if (!fs.existsSync(target)) return responseFor(404, "");
					if (method === "HEAD") return responseFor(200, "");
					return responseFor(200, fs.readFileSync(target, "utf8"));
				}}
				throw new Error(`unexpected fetch: ${{method}} ${{url.pathname}}`);
			}}

			const context = vm.createContext({{
				console,
				URL,
				URLSearchParams,
				document,
				localStorage,
				window: null,
				self: null,
				globalThis: null,
				location: {{
					origin: "http://localhost",
					search: "",
					href: "http://localhost/web/index.html",
				}},
				navigator: {{ userAgent: "node-runtime-harness" }},
				HTMLElement: ElementMock,
				Element: ElementMock,
				Node: ElementMock,
				Papa: {{ parse: simpleCsvParse }},
				L,
				fetch: fetchMock,
				confirm() {{
					return true;
				}},
				alert() {{}},
				requestAnimationFrame(handler) {{
					return setTimeout(handler, 0);
				}},
				cancelAnimationFrame(id) {{
					clearTimeout(id);
				}},
				setTimeout,
				clearTimeout,
				setInterval,
				clearInterval,
				XMLHttpRequest: function XMLHttpRequestStub() {{
					throw new Error("XMLHttpRequest should not be used in runtime harness");
				}},
			}});
			context.window = context;
			context.self = context;
			context.globalThis = context;
			context.window.location = context.location;
			context.window.document = document;
			context.window.localStorage = localStorage;
			context.window.fetch = fetchMock;
			context.window.Papa = context.Papa;
			context.window.L = L;
			context.window.console = console;
			context.window.addEventListener = () => {{}};
			context.document.addEventListener = () => {{}};

			[
				"search-box","batch-select","save-review-btn","refresh-review-btn","reviewer-open-session-btn","reviewer-switch-btn",
				"reviewer-session-cancel","reviewer-session-submit","reviewer-session-input","reviewer-session-known","reviewer-session-overlay",
				"reference-source-input","review-tag-select","review-notes","status-filter-row","filter-mode","filter-toggle-btn",
				"review-aggregate-toggle","review-panel-toggle","prev-pending-btn","next-pending-btn","triage-board","triage-column-tabs",
				"map-tools-toggle","map-view-follow-cb","time-plus8-cb","time-scrubber-control","time-scrubber-canvas","time-scrubber-overview-canvas",
				"time-scrubber-layer-select","time-scrubber-step-prev","time-scrubber-step-next","time-scrubber-left","time-scrubber-right",
				"time-scrubber-zoom-out","time-scrubber-zoom-in","time-scrubber-context-menu","annotation-settings-entry",
				"annotation-settings-overlay","annotation-settings-close","annotation-category-add","annotation-tag-add",
				"annotation-focus-opacity","annotation-idle-opacity","studio-management-entry","studio-management-overlay",
				"studio-management-close","studio-management-refresh-btn","studio-management-upload-btn",
				"studio-management-upload-process-btn","studio-management-reset-btn","studio-management-uploads-list",
				"studio-management-upload-type","studio-management-custom-fields-toggle","studio-management-custom-fields",
				"studio-management-help-anchor","studio-management-help-trigger","theme-mode-toggle","theme-mode-label",
				"date-window-control","date-window-start","date-window-end",
				"date-window-start-decrease","date-window-start-increase","date-window-end-decrease","date-window-end-increase",
				"date-window-fixed-span","date-window-quick-category","date-window-quick-toggle","help-panel","help-toggle-btn",
				"help-header","sidebar-toggle","sidebar","sidebar-resize","current-reviewer-chip","reviewer-identity-value",
				"review-meta","review-current","layer-controls","status-style-controls","layer-status","sidebar-title",
				"filter-panel-title","status-style-title","review-panel","review-aggregate-panel","annotation-settings-panel",
				"annotation-focus-opacity-value","annotation-idle-opacity-value","annotation-preview-segment","filter-summary",
				"review-status","review-dirty-status","review-aggregate-summary","review-aggregate-list","time-scrubber-status",
				"time-scrubber-range","studio-management-progress","studio-management-progress-title","studio-management-progress-percent",
				"studio-management-progress-bar","studio-management-progress-detail","studio-management-flash",
				"studio-management-help-popover","studio-management-help-trigger-text","studio-management-actor-badge",
				"studio-management-actor-name","studio-management-actor-description","studio-management-actor-id",
				"studio-management-actor-role","studio-management-upload-count","studio-management-last-refresh","batch-status",
				"filter-status","triage-board-summary","map","map-tools-dock",
			].forEach(getElement);
			getElement("time-plus8-cb").checked = true;
			getElement("filter-mode").value = "any";

			for (const relativePath of localScripts) {{
				const absolutePath = path.join(projectRoot, relativePath);
				const code = fs.readFileSync(absolutePath, "utf8");
				vm.runInContext(code, context, {{ filename: relativePath }});
			}}

			(async () => {{
				await new Promise((resolve) => setTimeout(resolve, 50));
				const firstUid = vm.runInContext("currentUid", context);
				const filteredUidList = vm.runInContext("filteredUidList.slice()", context);
				const secondUid = filteredUidList.find((uid) => uid !== firstUid) || filteredUidList[0] || "";
				if (!firstUid) throw new Error("bootstrap did not auto-select a uid");
				const bootstrapLayerCount = vm.runInContext("activeGroup?._layers?.length ?? 0", context);
				if (bootstrapLayerCount <= 0) throw new Error("bootstrap did not render any trajectory layers");
				const scrubberTotal = vm.runInContext("timeScrubberState.allPoints.length", context);
				const initialVisibleCount = vm.runInContext("getTimeScrubberVisibleCount()", context);
				const initialVisibleStartIndex = vm.runInContext("timeScrubberState.visibleStartIndex", context);
				const initialDisplaySignature = vm.runInContext("getCurrentMapDisplaySignature()", context);
				const initialSelectedLayer = vm.runInContext("timeScrubberState.selectedLayer", context);
				const initialSelectedLayerFullCount = vm.runInContext("(currentFilteredDataByLayer[timeScrubberState.selectedLayer] || []).length", context);
				const initialSelectedLayerMapCount = vm.runInContext("(getCurrentMapDisplayDataByLayer()[timeScrubberState.selectedLayer] || []).length", context);
				let clickedUid = firstUid;

				if (secondUid && secondUid !== firstUid) {{
					const target = new ElementMock("", "button");
					target.dataset.uid = secondUid;
					const board = getElement("triage-board");
					for (const handler of board.listeners.click || []) {{
						await handler({{
							target,
							currentTarget: board,
							preventDefault() {{}},
							stopPropagation() {{}},
						}});
					}}
					await new Promise((resolve) => setTimeout(resolve, 20));
					clickedUid = vm.runInContext("currentUid", context);
					if (clickedUid !== secondUid) {{
						throw new Error(`uid click did not switch selection: expected ${{secondUid}}, got ${{clickedUid}}`);
					}}
					const clickedLayerCount = vm.runInContext("activeGroup?._layers?.length ?? 0", context);
					if (clickedLayerCount <= 0) throw new Error("uid click cleared trajectory layers");
				}}

				const minVisible = vm.runInContext("Math.min(TIME_SCRUBBER_MIN_VISIBLE_POINTS, timeScrubberState.allPoints.length)", context);
				let zoomedVisibleCount = vm.runInContext("getTimeScrubberVisibleCount()", context);
				let zoomedDisplaySignature = vm.runInContext("getCurrentMapDisplaySignature()", context);
				let zoomedSelectedLayerMapCount = vm.runInContext("(getCurrentMapDisplayDataByLayer()[timeScrubberState.selectedLayer] || []).length", context);
				if (scrubberTotal > minVisible) {{
					vm.runInContext("zoomTimeScrubberWindow(1 - TIME_SCRUBBER_ZOOM_STEP)", context);
					await new Promise((resolve) => setTimeout(resolve, 20));
					zoomedVisibleCount = vm.runInContext("getTimeScrubberVisibleCount()", context);
					zoomedDisplaySignature = vm.runInContext("getCurrentMapDisplaySignature()", context);
					zoomedSelectedLayerMapCount = vm.runInContext("(getCurrentMapDisplayDataByLayer()[timeScrubberState.selectedLayer] || []).length", context);
					if (zoomedVisibleCount >= initialVisibleCount) {{
						throw new Error(`time scrubber zoom-in did not narrow visible count: before=${{initialVisibleCount}}, after=${{zoomedVisibleCount}}`);
					}}
					if (zoomedDisplaySignature === initialDisplaySignature) {{
						throw new Error("time scrubber zoom-in did not change map display signature");
					}}
					const zoomedLayerCount = vm.runInContext("activeGroup?._layers?.length ?? 0", context);
					if (zoomedLayerCount <= 0) throw new Error("time scrubber zoom-in cleared trajectory layers");
				}}

				let pannedVisibleStartIndex = vm.runInContext("timeScrubberState.visibleStartIndex", context);
				let pannedDisplaySignature = vm.runInContext("getCurrentMapDisplaySignature()", context);
				let pannedSelectedLayerMapCount = vm.runInContext("(getCurrentMapDisplayDataByLayer()[timeScrubberState.selectedLayer] || []).length", context);
				const maxStartAfterZoom = vm.runInContext("getTimeScrubberMaxStart()", context);
				if (maxStartAfterZoom > 0) {{
					vm.runInContext("panTimeScrubberWindow(1)", context);
					await new Promise((resolve) => setTimeout(resolve, 20));
					pannedVisibleStartIndex = vm.runInContext("timeScrubberState.visibleStartIndex", context);
					pannedDisplaySignature = vm.runInContext("getCurrentMapDisplaySignature()", context);
					pannedSelectedLayerMapCount = vm.runInContext("(getCurrentMapDisplayDataByLayer()[timeScrubberState.selectedLayer] || []).length", context);
					if (pannedVisibleStartIndex <= initialVisibleStartIndex) {{
						throw new Error(`time scrubber pan-right did not move visible window: before=${{initialVisibleStartIndex}}, after=${{pannedVisibleStartIndex}}`);
					}}
					if (pannedDisplaySignature === zoomedDisplaySignature) {{
						throw new Error("time scrubber pan-right did not change map display signature");
					}}
					const pannedLayerCount = vm.runInContext("activeGroup?._layers?.length ?? 0", context);
					if (pannedLayerCount <= 0) throw new Error("time scrubber pan-right cleared trajectory layers");
				}}

				let switchedBatchName = vm.runInContext("currentBatchName", context);
				let switchedUid = vm.runInContext("currentUid", context);
				let switchedLayerCount = vm.runInContext("activeGroup?._layers?.length ?? 0", context);
				if (alternateBatchName) {{
					await vm.runInContext(`switchBatch(${{
						JSON.stringify(alternateBatchName)
					}}, {{ skipDirtyCheck: true, preserveUid: false }})`, context);
					await new Promise((resolve) => setTimeout(resolve, 20));
					switchedBatchName = vm.runInContext("currentBatchName", context);
					switchedUid = vm.runInContext("currentUid", context);
					switchedLayerCount = vm.runInContext("activeGroup?._layers?.length ?? 0", context);
					if (switchedBatchName !== alternateBatchName) {{
						throw new Error(`batch switch did not update currentBatchName: expected ${{alternateBatchName}}, got ${{switchedBatchName}}`);
					}}
					if (!switchedUid) throw new Error("batch switch did not select a uid");
					if (switchedLayerCount <= 0) throw new Error("batch switch did not render any trajectory layers");
				}}

				const result = {{
					localScripts,
					selectedBatchName,
					alternateBatchName,
					firstUid,
					secondUid,
					clickedUid,
					currentUid: vm.runInContext("currentUid", context),
					filteredUidListLength: vm.runInContext("filteredUidList.length", context),
					bootstrapLayerCount,
					activeGroupLayerCount: vm.runInContext("activeGroup?._layers?.length ?? 0", context),
					mapLayerCount: mapMock._layers.size,
					scrubberTotal,
					initialVisibleCount,
					initialVisibleStartIndex,
					initialDisplaySignature,
					initialSelectedLayer,
					initialSelectedLayerFullCount,
					initialSelectedLayerMapCount,
					zoomedVisibleCount,
					zoomedDisplaySignature,
					zoomedSelectedLayerMapCount,
					pannedVisibleStartIndex,
					pannedDisplaySignature,
					pannedSelectedLayerMapCount,
					switchedBatchName,
					switchedUid,
					switchedLayerCount,
					layerStatus: getElement("layer-status").textContent,
				}};
				console.log(JSON.stringify(result));
			}})().catch((error) => {{
				console.error(error && error.stack ? error.stack : String(error));
				process.exit(1);
			}});
			"""
		)
		try:
			result = subprocess.run(
				["node", "-e", node_script],
				check=True,
				capture_output=True,
				text=True,
				cwd=project_root,
			)
		except subprocess.CalledProcessError as exc:
			self.fail(f"node runtime harness failed:\\nSTDOUT:\\n{exc.stdout}\\nSTDERR:\\n{exc.stderr}")
		payload = json.loads(result.stdout.strip())
		self.assertIn("web/app/runtime/state.js", payload["localScripts"])
		self.assertIn("web/app/features/workspace/workspace.js", payload["localScripts"])
		self.assertGreater(payload["filteredUidListLength"], 0)
		self.assertTrue(payload["firstUid"])
		self.assertTrue(payload["currentUid"])
		self.assertGreater(payload["bootstrapLayerCount"], 0)
		self.assertGreater(payload["activeGroupLayerCount"], 0)
		self.assertGreater(payload["mapLayerCount"], 0)
		self.assertIn(payload["currentUid"], payload["layerStatus"])
		self.assertIn("地图显示", payload["layerStatus"])
		self.assertGreater(payload["scrubberTotal"], 0)
		self.assertGreater(payload["initialVisibleCount"], 0)
		self.assertGreater(payload["initialSelectedLayerFullCount"], 0)
		self.assertGreater(payload["initialSelectedLayerMapCount"], 0)
		self.assertEqual(payload["initialVisibleCount"], payload["scrubberTotal"])
		self.assertEqual(payload["initialSelectedLayerMapCount"], payload["initialSelectedLayerFullCount"])
		self.assertLessEqual(payload["initialSelectedLayerMapCount"], payload["initialSelectedLayerFullCount"])
		if payload["scrubberTotal"] > min(payload["scrubberTotal"], 24):
			self.assertLess(payload["zoomedVisibleCount"], payload["initialVisibleCount"])
			self.assertNotEqual(payload["zoomedDisplaySignature"], payload["initialDisplaySignature"])
			self.assertLessEqual(payload["zoomedSelectedLayerMapCount"], payload["initialSelectedLayerMapCount"])
		if payload["pannedVisibleStartIndex"] > payload["initialVisibleStartIndex"]:
			self.assertNotEqual(payload["pannedDisplaySignature"], payload["zoomedDisplaySignature"])
			self.assertGreater(payload["pannedSelectedLayerMapCount"], 0)
		if payload["secondUid"] and payload["secondUid"] != payload["firstUid"]:
			self.assertEqual(payload["clickedUid"], payload["secondUid"])
		if payload["alternateBatchName"]:
			self.assertEqual(payload["switchedBatchName"], payload["alternateBatchName"])
			self.assertTrue(payload["switchedUid"])
			self.assertGreater(payload["switchedLayerCount"], 0)


if __name__ == "__main__":
	unittest.main()
