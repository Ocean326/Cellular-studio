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
					this.hidden = false;
					this.className = "";
					this.attributes = {{}};
					this.listeners = {{}};
					this.children = [];
					this.parentNode = null;
					this.isContentEditable = false;
					this.files = [];
					this.title = "";
					this.placeholder = "";
					this.clientWidth = 800;
					this.clientHeight = 80;
					this.offsetWidth = 800;
					this.offsetHeight = 80;
					this.scrollTop = 0;
					this.scrollLeft = 0;
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
				appendChild(child) {{
					if (!child) return child;
					child.parentNode = this;
					this.children.push(child);
					return child;
				}}
				contains(target) {{
					return target === this || this.children.includes(target);
				}}
				closest(selector) {{
					if (String(selector || "").includes("input") && this.tagName === "INPUT") return this;
					if (String(selector || "").includes("textarea") && this.tagName === "TEXTAREA") return this;
					if (String(selector || "").includes("select") && this.tagName === "SELECT") return this;
					if (String(selector || "").includes("button") && this.tagName === "BUTTON") return this;
					if (String(selector || "").includes("label") && this.tagName === "LABEL") return this;
					if (String(selector || "").includes("a") && this.tagName === "A") return this;
					if (String(selector || "").includes("[role='button']") && this.attributes.role === "button") return this;
					if (String(selector || "").includes("[role='menuitem']") && this.attributes.role === "menuitem") return this;
					if (String(selector || "").includes("[contenteditable") && this.isContentEditable) return this;
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
				scrollTo(options = {{}}) {{
					this.scrollTop = Number(options.top || 0);
					this.scrollLeft = Number(options.left || 0);
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
				focus() {{
					document.activeElement = this;
				}}
				click() {{
					for (const handler of this.listeners.click || []) {{
						handler({{
							target: this,
							currentTarget: this,
							preventDefault() {{}},
							stopPropagation() {{}},
						}});
					}}
				}}
				remove() {{
					if (!this.parentNode) return;
					this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
					this.parentNode = null;
				}}
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
				documentElement: {{ clientWidth: 1280, clientHeight: 720 }},
				activeElement: null,
				listeners: {{}},
				getElementById(id) {{
					return getElement(id);
				}},
				createElement(tag) {{
					return new ElementMock("", tag);
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
				addEventListener(type, handler) {{
					(this.listeners[type] ||= []).push(handler);
				}},
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
						listeners: {{}},
						addTo(target) {{
							if (target && typeof target.addLayer === "function") target.addLayer(this);
							return this;
						}},
						bindPopup(content) {{
							this._popupBound = true;
							this._popupContent = content;
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
						on(type, handler) {{
							(this.listeners[type] ||= []).push(handler);
							return this;
						}},
						fire(type, payload = {{}}) {{
							for (const handler of this.listeners[type] || []) {{
								handler(Object.assign({{ target: this }}, payload));
							}}
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

			function makeMapHandler() {{
				return {{
					enabledState: true,
					enable() {{
						this.enabledState = true;
					}},
					disable() {{
						this.enabledState = false;
					}},
				}};
			}}

			const mapMock = {{
				_layers: new Set(),
				_zoom: 11,
				_center: {{ lat: 39.9, lng: 116.4 }},
				lastPanTarget: null,
				dragging: makeMapHandler(),
				scrollWheelZoom: makeMapHandler(),
				boxZoom: makeMapHandler(),
				doubleClickZoom: makeMapHandler(),
				touchZoom: makeMapHandler(),
				on() {{}},
				getZoom() {{
					return this._zoom;
				}},
				getCenter() {{
					return this._center;
				}},
				setView(latlng, zoom) {{
					this._center = {{ lat: latlng[0], lng: latlng[1] }};
					if (typeof zoom === "number") this._zoom = zoom;
					return this;
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
				panTo(latlng) {{
					this.lastPanTarget = latlng;
					this._center = {{ lat: latlng[0], lng: latlng[1] }};
				}},
				invalidateSize() {{}},
			}};

			const L = {{
				map(_id, options = {{}}) {{
					if (Array.isArray(options.center) && options.center.length >= 2) {{
						mapMock._center = {{ lat: options.center[0], lng: options.center[1] }};
					}}
					if (typeof options.zoom === "number") {{
						mapMock._zoom = options.zoom;
					}}
					return mapMock;
				}},
				tileLayer(url, options) {{
					return makeLayer({{ url, options }});
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
			const trackEditsStore = new Map();
			const trackEditFetchFailureState = {{
				getStoreKeys: new Set(),
				postStoreKeys: new Set(),
			}};

			async function fetchMock(rawUrl, options = {{}}) {{
				const method = String(options.method || "GET").toUpperCase();
				const url = new URL(String(rawUrl), "http://localhost");
				if (url.pathname === "/api/batches") return responseFor(200, currentBatchPayload);
				if (url.pathname === "/api/me") {{
					return responseFor(200, {{
						actor: {{
							actor_id: "runtime-harness",
							display_name: "Runtime Harness",
							role: "annotator",
						}},
					}});
				}}
				if (url.pathname === "/api/uploads") return responseFor(200, {{ uploads: [], items: [] }});
				if (url.pathname === "/api/reviewers") return responseFor(200, {{ reviewers: [] }});
				if (url.pathname === "/api/reviews") {{
					if (url.searchParams.get("uid")) return responseFor(200, {{ review: null }});
					return responseFor(200, {{ reviews: {{}}, counts: {{}}, aggregate_counts_by_uid: {{}} }});
				}}
				if (url.pathname === "/api/reviews/aggregate") return responseFor(200, {{ aggregate: null }});
				if (url.pathname === "/api/timeline-annotations") return responseFor(200, {{ annotations: {{ pins: [], segments: [] }} }});
				if (url.pathname === "/api/export/reviewer-bundle") {{
					const payload = JSON.parse(String(options.body || "{{}}"));
					const isDatasetExport = String(payload.export_mode || "").trim().toLowerCase() === "segment_label_dataset";
					if (isDatasetExport) {{
						await new Promise((resolve) => setTimeout(resolve, 40));
					}}
					return responseFor(200, {{
						bundle_name: payload.bundle_name || "runtime_export_bundle",
						download_name: `${{payload.bundle_name || "runtime_export_bundle"}}.zip`,
						download_url: "/downloads/runtime_export_bundle.zip",
						sample_count: 3,
						export_mode: isDatasetExport ? "segment_label_dataset" : "reviewer_bundle",
						reviewer_profile: {{
							reviewer_id: payload.reviewer_id || "runtime-agent",
						}},
					}});
				}}
				if (url.pathname === "/api/track-edits") {{
					const reviewerId = url.searchParams.get("reviewer_id") || "";
					const uid = url.searchParams.get("uid") || "";
					const requestPayload = method === "POST"
						? JSON.parse(String(options.body || "{{}}"))
						: null;
					const effectiveReviewerId = reviewerId || String(requestPayload?.reviewer_id || "");
					const effectiveUid = uid || String(requestPayload?.uid || requestPayload?.sample_id || "");
					const storeKey = `${{effectiveReviewerId}}::${{effectiveUid}}`;
					if (method === "GET" && trackEditFetchFailureState.getStoreKeys.has(storeKey)) {{
						trackEditFetchFailureState.getStoreKeys.delete(storeKey);
						return responseFor(500, {{ error: "forced get failure" }});
					}}
					if (method === "POST" && trackEditFetchFailureState.postStoreKeys.has(storeKey)) {{
						trackEditFetchFailureState.postStoreKeys.delete(storeKey);
						return responseFor(500, {{ error: "forced post failure" }});
					}}
					if (method === "GET") {{
						return responseFor(200, {{
							track_edits: trackEditsStore.get(storeKey) || {{
								schema_version: 1,
								uid: effectiveUid,
								sample_id: effectiveUid,
								reviewer_id: effectiveReviewerId,
								reviewer_name: effectiveReviewerId,
								patches: [],
								updated_at: "",
							}},
						}});
					}}
					if (method === "POST") {{
						const payload = requestPayload || {{}};
						const nextRecord = {{
							schema_version: 1,
							uid: payload.uid || payload.sample_id || "",
							sample_id: payload.sample_id || payload.uid || "",
							reviewer_id: payload.reviewer_id || effectiveReviewerId,
							reviewer_name: payload.reviewer_name || payload.reviewer_id || effectiveReviewerId,
							patches: Array.isArray(payload.patches) ? payload.patches : [],
							updated_at: "2026-04-27T12:34:56Z",
						}};
						trackEditsStore.set(`${{nextRecord.reviewer_id}}::${{nextRecord.uid}}`, nextRecord);
						return responseFor(200, {{ track_edits: nextRecord }});
					}}
				}}
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
			context.window.innerWidth = 1280;
			context.window.innerHeight = 720;
			context.window.Papa = context.Papa;
			context.window.L = L;
			context.window.console = console;
			const windowEventListeners = {{}};
			context.window.addEventListener = (type, handler) => {{
				(windowEventListeners[type] ||= []).push(handler);
			}};
			context.document.addEventListener = document.addEventListener.bind(document);

			function dispatchDocumentEvent(type, payload = {{}}) {{
				for (const handler of document.listeners[type] || []) {{
					handler(Object.assign({{
						type,
						target: document.body,
						currentTarget: document,
						defaultPrevented: false,
						preventDefault() {{ this.defaultPrevented = true; }},
						stopPropagation() {{}},
					}}, payload));
				}}
			}}

			function dispatchWindowEvent(type, payload = {{}}) {{
				for (const handler of windowEventListeners[type] || []) {{
					handler(Object.assign({{
						type,
						target: context.window,
						currentTarget: context.window,
					}}, payload));
				}}
			}}

			[
				"search-box","batch-select","save-review-btn","refresh-review-btn","reviewer-open-session-btn","reviewer-switch-btn",
				"reviewer-session-cancel","reviewer-session-submit","reviewer-session-input","reviewer-session-known","reviewer-session-overlay",
				"reference-source-input","review-tag-select","review-notes","status-filter-row","filter-mode","filter-toggle-btn",
				"review-aggregate-toggle","review-panel-toggle","prev-pending-btn","next-pending-btn","triage-board","triage-column-tabs",
				"basemap-mode-controls","basemap-mode-status",
				"map-tools-toggle","map-view-follow-cb","time-plus8-cb","review-mode-annotation-btn",
				"track-edit-panel","track-edit-toggle","track-edit-clear-selection","track-edit-undo-btn","track-edit-redo-btn",
				"track-edit-save-btn","track-edit-save-options-btn","track-edit-save-menu","track-edit-save-overwrite",
				"track-edit-save-download","track-edit-show-coordinates","track-edit-coordinate-summary",
				"track-edit-status","track-edit-selection","track-edit-context-menu","track-edit-context-title",
				"track-edit-context-subtitle","track-edit-context-field-label","track-edit-context-value",
				"track-edit-context-apply","track-edit-context-close","time-scrubber-control","time-scrubber-canvas","time-scrubber-overview-canvas",
				"time-scrubber-layer-select","time-scrubber-step-prev","time-scrubber-step-next","time-scrubber-left","time-scrubber-right",
				"time-scrubber-zoom-out","time-scrubber-zoom-in","time-scrubber-context-menu","annotation-settings-entry",
				"annotation-settings-overlay","annotation-settings-close","annotation-category-add","annotation-tag-add",
				"annotation-focus-opacity","annotation-idle-opacity","studio-management-entry","studio-export-entry","studio-management-overlay",
				"studio-management-body","studio-management-sidebar","studio-upload-section","studio-export-section",
				"studio-management-close","studio-management-refresh-btn","studio-management-upload-btn",
				"studio-management-upload-process-btn","studio-management-reset-btn","studio-management-uploads-list",
				"studio-management-upload-type","studio-management-custom-fields-toggle","studio-management-custom-fields",
				"studio-management-help-anchor","studio-management-help-trigger","theme-mode-toggle","theme-mode-label",
				"studio-export-batch-select","studio-export-uid-select","studio-export-tag-select","studio-export-download-btn",
				"studio-export-summary","studio-export-decision-group","studio-export-decision-accept","studio-export-decision-reject","studio-export-decision-skip",
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
			getElement("track-edit-save-menu").appendChild(getElement("track-edit-save-overwrite"));
			getElement("track-edit-save-menu").appendChild(getElement("track-edit-save-download"));
			getElement("time-plus8-cb").checked = true;
			getElement("filter-mode").value = "any";
			getElement("studio-export-decision-accept").checked = true;
			getElement("studio-export-decision-reject").checked = true;
			getElement("studio-export-decision-skip").checked = true;

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
				const initialSelectedTime = vm.runInContext("getActiveTimeScrubberPoint()?.time ?? null", context);
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

				let followStepSelectedTime = initialSelectedTime;
				if (scrubberTotal > 1) {{
					vm.runInContext("mapViewFollowScrubber = true", context);
					const followStepDirection = vm.runInContext(
						"timeScrubberState.selectedIndex >= Math.max(0, timeScrubberState.allPoints.length - 1) ? -1 : 1",
						context,
					);
					vm.runInContext(`stepTimeScrubberSelection(${{followStepDirection}})`, context);
					await new Promise((resolve) => setTimeout(resolve, 20));
					followStepSelectedTime = vm.runInContext("getActiveTimeScrubberPoint()?.time ?? null", context);
					if (followStepSelectedTime == null) {{
						throw new Error("time scrubber step did not keep an active point");
					}}
					if (!mapMock.lastPanTarget) {{
						throw new Error("time scrubber step with focus enabled did not pan the map");
					}}
				}}

				const markerCandidates = vm.runInContext(`
					(activeGroup?._layers || []).filter((layer) => Array.isArray(layer.__studioBucket?.rows) && (layer.listeners?.click || []).length)
				`, context);
				const markerBeforeTime = vm.runInContext("getActiveTimeScrubberPoint()?.time ?? null", context);
				let markerTargetTime = null;
				let markerAlignedTime = markerBeforeTime;
				let markerAlignedLayer = vm.runInContext("timeScrubberState.selectedLayer", context);
				if (markerCandidates.length) {{
					let targetMarker = markerCandidates[0];
					for (const candidate of markerCandidates) {{
						context.__testMarker = candidate;
						const candidateTargetTime = vm.runInContext(`
							pickTimeScrubberTargetTimeFromRows(
								__testMarker.__studioBucket?.rows || [],
								getActiveTimeScrubberPoint()?.time ?? null
							)
						`, context);
						if (candidateTargetTime == null) continue;
						targetMarker = candidate;
						markerTargetTime = candidateTargetTime;
						if (markerBeforeTime == null || Math.abs(candidateTargetTime - markerBeforeTime) > 1) break;
					}}
					context.__testMarker = targetMarker;
					if (markerTargetTime == null) {{
						markerTargetTime = vm.runInContext(`
							pickTimeScrubberTargetTimeFromRows(
								__testMarker.__studioBucket?.rows || [],
								getActiveTimeScrubberPoint()?.time ?? null
							)
						`, context);
					}}
					targetMarker.fire("click");
					await new Promise((resolve) => setTimeout(resolve, 20));
					markerAlignedTime = vm.runInContext("getActiveTimeScrubberPoint()?.time ?? null", context);
					markerAlignedLayer = vm.runInContext("timeScrubberState.selectedLayer", context);
				}}
				if (markerCandidates.length && markerTargetTime != null) {{
					if (markerAlignedTime == null) {{
						throw new Error("marker click did not keep an active time scrubber point");
					}}
					if (Math.abs(markerAlignedTime - markerTargetTime) > 1) {{
						throw new Error(`marker click did not align the time scrubber: expected≈${{markerTargetTime}}, got=${{markerAlignedTime}}`);
					}}
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

				const studioExportEntryEl = getElement("studio-export-entry");
				const studioUploadEntryEl = getElement("studio-management-entry");
				for (const handler of studioExportEntryEl.listeners.click || []) {{
					await handler({{
						target: studioExportEntryEl,
						currentTarget: studioExportEntryEl,
						preventDefault() {{}},
						stopPropagation() {{}},
					}});
				}}
				await new Promise((resolve) => setTimeout(resolve, 20));
				const studioExportState = vm.runInContext(`({{
					open: document.getElementById("studio-management-overlay").classList.contains("open"),
					activeWorkspace: studioManagementState.exportActiveWorkspace,
					selectedBatch: studioManagementState.exportSelectedBatch,
					uploadHidden: !!document.getElementById("studio-upload-section").hidden,
					exportHidden: !!document.getElementById("studio-export-section").hidden
				}})`, context);
				if (!studioExportState.open || studioExportState.activeWorkspace !== "export") {{
					throw new Error("studio export entry did not open export workspace");
				}}
				if (studioExportState.selectedBatch !== vm.runInContext("currentBatchName", context)) {{
					throw new Error("studio export workspace did not default to current batch");
				}}
				if (!studioExportState.uploadHidden || studioExportState.exportHidden) {{
					throw new Error("studio workspaces are not mutually exclusive in export mode");
				}}

				for (const handler of studioUploadEntryEl.listeners.click || []) {{
					await handler({{
						target: studioUploadEntryEl,
						currentTarget: studioUploadEntryEl,
						preventDefault() {{}},
						stopPropagation() {{}},
					}});
				}}
				await new Promise((resolve) => setTimeout(resolve, 20));
				const studioUploadState = vm.runInContext(`({{
					open: document.getElementById("studio-management-overlay").classList.contains("open"),
					activeWorkspace: studioManagementState.exportActiveWorkspace,
					selectedBatch: studioManagementState.exportSelectedBatch,
					uploadHidden: !!document.getElementById("studio-upload-section").hidden,
					exportHidden: !!document.getElementById("studio-export-section").hidden
				}})`, context);
				if (!studioUploadState.open || studioUploadState.activeWorkspace !== "upload") {{
					throw new Error("studio upload entry did not switch back to upload workspace");
				}}
				if (studioUploadState.selectedBatch !== vm.runInContext("currentBatchName", context)) {{
					throw new Error("studio upload workspace did not preserve current batch default");
				}}
					if (studioUploadState.uploadHidden || !studioUploadState.exportHidden) {{
						throw new Error("studio workspaces are not mutually exclusive in upload mode");
					}}
					vm.runInContext("closeStudioManagement()", context);

					const currentUidBeforeExclusiveCheck = vm.runInContext("currentUid", context);
					vm.runInContext(`
						currentReviewerSession = {{
							reviewer_id: "runtime-agent",
							reviewer_name: "Runtime Agent",
							display_name: "Runtime Agent",
						}};
					`, context);
					const trackEditLayer = vm.runInContext(`
						Object.keys(trackEditState.pointIdsByLayer || {{}}).find(
							(layer) => Array.isArray(trackEditState.pointIdsByLayer[layer]) && trackEditState.pointIdsByLayer[layer].length >= 3
						) || Object.keys(trackEditState.pointIdsByLayer || {{}})[0] || ""
					`, context);
					let trackEditModeState = null;
					let trackEditSelection = [];
					let trackEditPatchCount = 0;
					let trackEditPatchedLatitude = null;
					let trackEditPatchedFieldValue = "";
					let trackEditUndoDepth = 0;
					let trackEditRedoDepth = 0;
					let trackEditCoordinateSummary = "";
					let trackEditCoordinateSummaryVisible = false;
					let trackEditSaveMenuOpened = false;
					let trackEditSaveMenuClosed = false;
					let trackEditSpaceInputGuard = false;
					let trackEditSpaceSelectGuard = null;
					let trackEditSpaceActiveState = null;
					let trackEditSpaceReleasedState = null;
					let trackEditUndoPatchCount = 0;
					let trackEditRedoPatchCount = 0;
					let trackEditSaveState = null;
					let trackEditDownloadFilename = "";
					let trackEditAnnotationModeState = null;
					let trackEditDragState = null;
					let trackEditPopupSuppressed = null;
					let trackEditReviewShortcutGuard = null;
					let trackEditRevertState = null;
					let trackEditSaveFailureState = null;
					let trackEditReviewerIsolationState = null;
					let trackEditNoReviewerGateState = null;
					let datasetExportPendingState = null;
					let datasetExportCompletedState = null;
					let datasetExportSettledState = null;
					if (trackEditLayer) {{
						context.__trackEditLayer = trackEditLayer;
						const trackEditPointIds = JSON.parse(
							vm.runInContext("JSON.stringify((trackEditState.pointIdsByLayer[__trackEditLayer] || []).slice(0, 3))", context)
						);
						context.__trackEditPointIds = trackEditPointIds;
						if (trackEditPointIds.length) {{
							vm.runInContext("setTrackEditModeEnabled(true)", context);
							trackEditModeState = JSON.parse(vm.runInContext(`JSON.stringify({{
								enabled: trackEditState.enabled,
								editPressed: document.getElementById("track-edit-toggle").getAttribute("aria-pressed"),
								annotationPressed: document.getElementById("review-mode-annotation-btn").getAttribute("aria-pressed"),
								mapLocked: document.getElementById("map").classList.contains("track-edit-map-locked"),
								draggingEnabled: !!map.dragging.enabledState,
								scrollWheelEnabled: !!map.scrollWheelZoom.enabledState
							}})`, context));
							trackEditPopupSuppressed = JSON.parse(vm.runInContext(`JSON.stringify((() => {{
								const markerIds = Object.keys(trackEditState.renderedMarkersByPointId || {{}});
								return {{
									markerCount: markerIds.length,
									hasPopup: markerIds.some((pointId) => !!trackEditState.renderedMarkersByPointId[pointId]?._popupBound),
								}};
							}})())`, context));
							dispatchDocumentEvent("keydown", {{
								key: "1",
								code: "Digit1",
								target: document.body,
								metaKey: false,
								ctrlKey: false,
								altKey: false,
								shiftKey: false,
							}});
							trackEditReviewShortcutGuard = JSON.parse(vm.runInContext(`JSON.stringify({{
								selectedDecision,
								reviewDirty: reviewFormDirty
							}})`, context));
							vm.runInContext("selectTrackEditPoint(__trackEditPointIds[0])", context);
							if (trackEditPointIds.length >= 2) {{
								vm.runInContext("selectTrackEditPoint(__trackEditPointIds[1], {{ toggle: true }})", context);
							}}
							if (trackEditPointIds.length >= 3) {{
								vm.runInContext("selectTrackEditPoint(__trackEditPointIds[2], {{ range: true }})", context);
							}}
							trackEditSelection = JSON.parse(vm.runInContext("JSON.stringify(trackEditState.selectedPointIds)", context));
							trackEditDragState = JSON.parse(vm.runInContext(`
								JSON.stringify((() => {{
									const selectedIds = (trackEditState.selectedPointIds || []).slice();
									if (!selectedIds.length) return null;
									const markerMap = {{}};
									selectedIds.forEach((pointId) => {{
										const pointRef = trackEditState.pointRefsById[pointId];
										if (!pointRef?.position) return;
										const [displayLat, displayLon] = toGcj(
											pointRef.position.latitude,
											pointRef.position.longitude,
										);
										const marker = L.marker([displayLat, displayLon], {{
											draggable: true,
											keyboard: false,
										}});
										bindTrackEditMarkerEvents(marker, pointRef);
										markerMap[pointId] = marker;
									}});
									trackEditState.renderedMarkersByPointId = {{
										...(trackEditState.renderedMarkersByPointId || {{}}),
										...markerMap,
									}};
									const primaryId = selectedIds[0];
									const primaryMarker = trackEditState.renderedMarkersByPointId[primaryId];
									const secondaryMarker = selectedIds.length > 1
										? trackEditState.renderedMarkersByPointId[selectedIds[1]]
										: null;
									const primaryBefore = primaryMarker?.getLatLng?.();
									const secondaryBefore = secondaryMarker?.getLatLng?.() || null;
									if (!primaryMarker || !primaryBefore) return null;
									const deltaLat = 0.0012;
									const deltaLon = 0.0014;
									primaryMarker.fire("dragstart");
									primaryMarker.setLatLng([primaryBefore.lat + deltaLat, primaryBefore.lng + deltaLon]);
									primaryMarker.fire("drag");
									const secondaryDuring = secondaryMarker?.getLatLng?.() || null;
									primaryMarker.fire("dragend");
									return {{
										selectionCount: selectedIds.length,
										patchCount: getCurrentTrackEdits().pointPatches.length,
										dirty: trackEditState.dirty,
										saveDisabled: !!document.getElementById("track-edit-save-btn").disabled,
										dragSuppressActive: trackEditState.dragSuppressClickUntil > 0,
										secondaryDeltaMatches: !secondaryBefore || !secondaryDuring
											? true
											: Math.abs((secondaryDuring.lat - secondaryBefore.lat) - deltaLat) <= 1e-9
												&& Math.abs((secondaryDuring.lng - secondaryBefore.lng) - deltaLon) <= 1e-9,
									}};
								}})())
							`, context));
							trackEditRevertState = JSON.parse(vm.runInContext(`
								JSON.stringify((() => {{
									const revertPatches = (getCurrentTrackEdits().pointPatches || [])
										.map((patch) => {{
											const pointRef = trackEditState.pointRefsById[patch.pointId];
											const baseRow = getBaseTrackEditRowForPatch(patch);
											const baseCoord = getRowCoordinate(baseRow);
											const metadata = {{}};
											Object.keys(patch.metadata || {{}}).forEach((key) => {{
												metadata[key] = String(baseRow?.[key] ?? "").trim();
											}});
											return buildTrackEditPatchFromRef(pointRef, {{
												position: baseCoord ? {{
													latitude: baseCoord.lat,
													longitude: baseCoord.lon,
												}} : undefined,
												metadata: Object.keys(metadata).length ? metadata : undefined,
											}});
										}})
										.filter(Boolean);
									if (!revertPatches.length) return null;
									upsertCurrentTrackEditPatches(revertPatches, {{
										persist: false,
										statusMessage: "runtime revert",
										preserveScrubberTime: true,
									}});
									renderTrackEditPanel();
									return {{
										patchCount: getCurrentTrackEdits().pointPatches.length,
										dirty: trackEditState.dirty,
										saveDisabled: !!document.getElementById("track-edit-save-btn").disabled,
										status: document.getElementById("track-edit-status").textContent || "",
									}};
								}})())
							`, context));
							const patchPayload = JSON.parse(vm.runInContext(`
								JSON.stringify((() => {{
									const pointId = __trackEditPointIds[0];
									const pointRef = trackEditState.pointRefsById[pointId];
									if (!pointRef) return null;
									const metadataField = getTrackEditMetadataFieldForLayer(pointRef.layerKey);
									const metadata = metadataField ? {{ [metadataField]: "road" }} : {{}};
									upsertCurrentTrackEditPatches([
										{{
											pointId,
											layerKey: pointRef.layerKey,
											rowIndex: pointRef.rowIndex,
											timestamp: pointRef.timestamp,
											position: {{
												latitude: (pointRef.position?.latitude || 0) + 0.0005,
												longitude: (pointRef.position?.longitude || 0) + 0.0005,
											}},
											metadata,
										}},
									], {{
										persist: false,
										statusMessage: "runtime patch",
										preserveScrubberTime: true,
									}});
									return {{
										patchCount: getCurrentTrackEdits().pointPatches.length,
										latitude: trackEditState.pointRefsById[pointId]?.position?.latitude ?? null,
										fieldValue: metadataField ? (trackEditState.pointRefsById[pointId]?.row?.[metadataField] ?? "") : "",
										undoDepth: trackEditState.undoStack.length,
										redoDepth: trackEditState.redoStack.length,
									}};
								}})())
							`, context));
							trackEditPatchCount = patchPayload?.patchCount || 0;
							trackEditPatchedLatitude = patchPayload?.latitude ?? null;
							trackEditPatchedFieldValue = patchPayload?.fieldValue || "";
							trackEditUndoDepth = patchPayload?.undoDepth || 0;
							trackEditRedoDepth = patchPayload?.redoDepth || 0;
							vm.runInContext("trackEditState.showCoordinates = true; renderTrackEditPanel();", context);
							const coordinatePayload = JSON.parse(vm.runInContext(`JSON.stringify({{
								summary: document.getElementById("track-edit-coordinate-summary").textContent || "",
								hidden: !!document.getElementById("track-edit-coordinate-summary").hidden
							}})`, context));
							trackEditCoordinateSummary = coordinatePayload.summary || "";
							trackEditCoordinateSummaryVisible = coordinatePayload.hidden === false;
							vm.runInContext(`
								openTrackEditSaveMenu(document.getElementById("track-edit-save-options-btn"));
								renderTrackEditPanel();
							`, context);
							trackEditSaveMenuOpened = vm.runInContext(
								'trackEditState.saveMenuOpen && document.getElementById("track-edit-save-options-btn").getAttribute("aria-expanded") === "true"',
								context,
							);
							dispatchDocumentEvent("click", {{ target: document.body }});
							trackEditSaveMenuClosed = vm.runInContext(
								'!trackEditState.saveMenuOpen && document.getElementById("track-edit-save-options-btn").getAttribute("aria-expanded") === "false"',
								context,
							);
							dispatchDocumentEvent("keydown", {{
								key: " ",
								code: "Space",
								target: new ElementMock("", "input"),
								metaKey: false,
								ctrlKey: false,
								altKey: false,
							}});
							trackEditSpaceInputGuard = vm.runInContext("trackEditState.spaceModifierActive === false", context);
							const selectTarget = new ElementMock("", "button");
							selectTarget.focus();
							dispatchDocumentEvent("keydown", {{
								key: " ",
								code: "Space",
								target: selectTarget,
								metaKey: false,
								ctrlKey: false,
								altKey: false,
							}});
							trackEditSpaceSelectGuard = JSON.parse(vm.runInContext(`JSON.stringify({{
								spaceModifierActive: trackEditState.spaceModifierActive,
								overlayOpen: document.getElementById("studio-management-overlay").classList.contains("open"),
								editEnabled: trackEditState.enabled,
								activeElementTag: document.activeElement?.tagName || "",
								draggingEnabled: !!map.dragging.enabledState,
								scrollWheelEnabled: !!map.scrollWheelZoom.enabledState
							}})`, context));
							dispatchDocumentEvent("keyup", {{
								key: " ",
								code: "Space",
								target: selectTarget,
							}});
							vm.runInContext("setTrackEditSpaceModifierActive(true)", context);
							trackEditSpaceActiveState = JSON.parse(vm.runInContext(`JSON.stringify({{
								spaceModifierActive: trackEditState.spaceModifierActive,
								mapLocked: document.getElementById("map").classList.contains("track-edit-map-locked"),
								draggingEnabled: !!map.dragging.enabledState,
								scrollWheelEnabled: !!map.scrollWheelZoom.enabledState
							}})`, context));
							vm.runInContext("setTrackEditSpaceModifierActive(false)", context);
							trackEditSpaceReleasedState = JSON.parse(vm.runInContext(`JSON.stringify({{
								spaceModifierActive: trackEditState.spaceModifierActive,
								mapLocked: document.getElementById("map").classList.contains("track-edit-map-locked"),
								draggingEnabled: !!map.dragging.enabledState,
								scrollWheelEnabled: !!map.scrollWheelZoom.enabledState
							}})`, context));
							vm.runInContext("undoTrackEditChange()", context);
							trackEditUndoPatchCount = vm.runInContext("getCurrentTrackEdits().pointPatches.length", context);
							vm.runInContext("redoTrackEditChange()", context);
							trackEditRedoPatchCount = vm.runInContext("getCurrentTrackEdits().pointPatches.length", context);
							await vm.runInContext("saveCurrentTrackEdits()", context);
							trackEditSaveState = JSON.parse(vm.runInContext(`JSON.stringify({{
								dirty: trackEditState.dirty,
								lastSavedAt: trackEditState.lastSavedAt || "",
								patchCount: getCurrentTrackEdits().pointPatches.length,
								saveDisabled: !!document.getElementById("track-edit-save-btn").disabled
							}})`, context));
							vm.runInContext("downloadCurrentTrackEditsAsJson()", context);
							trackEditDownloadFilename = vm.runInContext("window.__lastTrackEditDownloadFilename || ''", context);
							vm.runInContext("setTrackEditModeEnabled(false)", context);
							trackEditAnnotationModeState = JSON.parse(vm.runInContext(`JSON.stringify({{
								enabled: trackEditState.enabled,
								editPressed: document.getElementById("track-edit-toggle").getAttribute("aria-pressed"),
								annotationPressed: document.getElementById("review-mode-annotation-btn").getAttribute("aria-pressed"),
								mapLocked: document.getElementById("map").classList.contains("track-edit-map-locked"),
								draggingEnabled: !!map.dragging.enabledState,
								scrollWheelEnabled: !!map.scrollWheelZoom.enabledState
							}})`, context));
							vm.runInContext("setTrackEditModeEnabled(true)", context);
							vm.runInContext(`
								(() => {{
									const pointId = __trackEditPointIds[0];
									const pointRef = trackEditState.pointRefsById[pointId];
									if (!pointRef) return;
									upsertCurrentTrackEditPatches([
										{{
											pointId,
											layerKey: pointRef.layerKey,
											rowIndex: pointRef.rowIndex,
											timestamp: pointRef.timestamp,
											position: {{
												latitude: (pointRef.position?.latitude || 0) + 0.0007,
												longitude: (pointRef.position?.longitude || 0) + 0.0004,
											}},
										}},
									], {{
										persist: false,
										statusMessage: "runtime save failure patch",
										preserveScrubberTime: true,
									}});
								}})();
							`, context);
							const failingPostStoreKey = vm.runInContext("String(getCurrentReviewerId() || '') + '::' + String(currentUid || '')", context);
							const failingGetStoreKey = vm.runInContext("String(getCurrentReviewerId() || '') + '::' + String(currentUid || '')", context);
							trackEditFetchFailureState.postStoreKeys.add(failingPostStoreKey);
							await vm.runInContext("saveCurrentTrackEdits()", context);
							trackEditSaveFailureState = JSON.parse(vm.runInContext(`JSON.stringify({{
								dirty: trackEditState.dirty,
								patchCount: getCurrentTrackEdits().pointPatches.length,
								saveDisabled: !!document.getElementById("track-edit-save-btn").disabled,
								status: document.getElementById("track-edit-status").textContent || ""
							}})`, context));
							vm.runInContext(`
								currentReviewerSession = {{
									reviewer_id: "runtime-other",
									reviewer_name: "Runtime Other",
									display_name: "Runtime Other",
								}};
							`, context);
							await vm.runInContext("loadTrackEditsForUid(currentUid)", context);
							vm.runInContext("applyCurrentTrackEditsToCurrentData({{ preserveScrubberTime: true, forceFit: false }});", context);
							const otherReviewerTrackEditState = JSON.parse(vm.runInContext(`JSON.stringify({{
								patchCount: getCurrentTrackEdits().pointPatches.length,
								dirty: trackEditState.dirty
							}})`, context));
							vm.runInContext(`
								currentReviewerSession = {{
									reviewer_id: "runtime-agent",
									reviewer_name: "Runtime Agent",
									display_name: "Runtime Agent",
								}};
							`, context);
							trackEditFetchFailureState.getStoreKeys.add(failingGetStoreKey);
							await vm.runInContext("loadTrackEditsForUid(currentUid)", context);
							vm.runInContext("applyCurrentTrackEditsToCurrentData({{ preserveScrubberTime: true, forceFit: false }}); renderTrackEditPanel();", context);
							const restoredReviewerTrackEditState = JSON.parse(vm.runInContext(`JSON.stringify({{
								patchCount: getCurrentTrackEdits().pointPatches.length,
								dirty: trackEditState.dirty,
								status: document.getElementById("track-edit-status").textContent || ""
							}})`, context));
							trackEditReviewerIsolationState = {{
								otherPatchCount: otherReviewerTrackEditState.patchCount,
								otherDirty: otherReviewerTrackEditState.dirty,
								restoredPatchCount: restoredReviewerTrackEditState.patchCount,
								restoredDirty: restoredReviewerTrackEditState.dirty,
								restoredStatus: restoredReviewerTrackEditState.status,
							}};
							vm.runInContext(`
								currentReviewerSession = {{
									reviewer_id: "runtime-agent",
									reviewer_name: "Runtime Agent",
									display_name: "Runtime Agent",
								}};
								openStudioManagement("export");
								studioManagementState.exportSelectedBatch = currentBatchName;
								studioManagementState.exportSelectedDecisions = ["accept", "reject", "skip"];
								renderStudioExportBatchOptions();
								renderStudioExportReviewFilters();
								window.__datasetExportPromise = submitStudioExportAction({{ exportMode: "segment_label_dataset" }});
							`, context);
							await new Promise((resolve) => setTimeout(resolve, 15));
							datasetExportPendingState = JSON.parse(vm.runInContext(`JSON.stringify({{
								busy: studioManagementState.busy,
								label: document.getElementById("studio-export-dataset-btn").textContent || "",
								progressActive: document.getElementById("studio-export-dataset-btn").dataset.progressActive || "false",
							}})`, context));
							await vm.runInContext("window.__datasetExportPromise", context);
							datasetExportCompletedState = JSON.parse(vm.runInContext(`JSON.stringify({{
								busy: studioManagementState.busy,
								label: document.getElementById("studio-export-dataset-btn").textContent || "",
								progressActive: document.getElementById("studio-export-dataset-btn").dataset.progressActive || "false",
								summary: document.getElementById("studio-export-summary").textContent || "",
							}})`, context));
							await new Promise((resolve) => setTimeout(resolve, 760));
							datasetExportSettledState = JSON.parse(vm.runInContext(`JSON.stringify({{
								busy: studioManagementState.busy,
								label: document.getElementById("studio-export-dataset-btn").textContent || "",
								progressActive: document.getElementById("studio-export-dataset-btn").dataset.progressActive || "false",
								summary: document.getElementById("studio-export-summary").textContent || "",
							}})`, context));
							vm.runInContext("setTrackEditModeEnabled(false)", context);
							vm.runInContext("currentReviewerSession = null; renderTrackEditPanel();", context);
							trackEditNoReviewerGateState = JSON.parse(vm.runInContext(`JSON.stringify((() => {{
								const entered = setTrackEditModeEnabled(true);
								renderTrackEditPanel();
								return {{
									entered,
									enabled: trackEditState.enabled,
									buttonDisabled: !!document.getElementById("track-edit-toggle").disabled,
									selection: document.getElementById("track-edit-selection").textContent || "",
									status: document.getElementById("track-edit-status").textContent || ""
								}};
							}})())`, context));
							vm.runInContext(`
								currentReviewerSession = {{
									reviewer_id: "runtime-agent",
									reviewer_name: "Runtime Agent",
									display_name: "Runtime Agent",
								}};
								renderTrackEditPanel();
							`, context);
						}}
					}}
					vm.runInContext(`
						annotationSettings.exclusiveSegments = true;
						currentReviewerSession = {{
							reviewer_id: "runtime-agent",
							reviewer_name: "Runtime Agent",
							display_name: "Runtime Agent",
						}};
					currentUid = "__exclusive_boundary__";
					timelineSegmentsByTrack[getCurrentTimelinePinStoreKey()] = [
						{{ id: "left", categoryId: "stay", categoryName: "驻留", startTime: 10, endTime: 20 }},
						{{ id: "right", categoryId: "road_car", categoryName: "驾车", startTime: 20, endTime: 30 }},
					];
				`, context);
				const exclusiveBoundaryHits = JSON.parse(
					vm.runInContext("JSON.stringify(getTimelineSegmentsAtTime(20).map(segment => segment.id))", context)
				);
				const exclusiveLaneIndexes = JSON.parse(
					vm.runInContext("JSON.stringify(assignTimelineSegmentLanes(getCurrentTimelineSegments(), 2).map(segment => segment.laneIndex))", context)
				);
				const exclusiveCanonicalized = JSON.parse(
					vm.runInContext(`JSON.stringify(normalizeExclusiveTimelineSegments([
						{{ id: "stay", categoryId: "stay", categoryName: "驻留", startTime: 10, endTime: 20 }},
						{{ id: "road", categoryId: "road_car", categoryName: "驾车", startTime: 15, endTime: 30 }}
					]))`, context)
				);
				if (exclusiveBoundaryHits.length !== 1 || exclusiveBoundaryHits[0] !== "left") {{
					throw new Error(`exclusive boundary hit test failed: ${{exclusiveBoundaryHits.join(",")}}`);
				}}
				if (exclusiveLaneIndexes.length !== 2 || exclusiveLaneIndexes[0] !== exclusiveLaneIndexes[1]) {{
					throw new Error(`exclusive lane assignment drifted: ${{exclusiveLaneIndexes.join(",")}}`);
				}}
				if (
					exclusiveCanonicalized.length !== 2
					|| exclusiveCanonicalized[0].endTime !== 20
					|| exclusiveCanonicalized[1].startTime !== 20
				) {{
					throw new Error(`exclusive canonicalization drifted: ${{JSON.stringify(exclusiveCanonicalized)}}`);
				}}

				const result = {{
					localScripts,
					selectedBatchName,
					alternateBatchName,
					firstUid,
					secondUid,
					clickedUid,
					currentUid: currentUidBeforeExclusiveCheck,
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
					initialSelectedTime,
					zoomedVisibleCount,
					zoomedDisplaySignature,
					zoomedSelectedLayerMapCount,
					pannedVisibleStartIndex,
					pannedDisplaySignature,
					pannedSelectedLayerMapCount,
					followStepSelectedTime,
					lastPanTarget: mapMock.lastPanTarget,
					markerTargetTime,
					markerAlignedTime,
					markerAlignedLayer,
						switchedBatchName,
						switchedUid,
						switchedLayerCount,
						studioExportState,
						studioUploadState,
						trackEditLayer,
						trackEditModeState,
						trackEditSelection,
						trackEditPatchCount,
						trackEditPatchedLatitude,
						trackEditPatchedFieldValue,
						trackEditUndoDepth,
						trackEditRedoDepth,
						trackEditCoordinateSummary,
						trackEditCoordinateSummaryVisible,
						trackEditSaveMenuOpened,
						trackEditSaveMenuClosed,
						trackEditSpaceInputGuard,
						trackEditSpaceSelectGuard,
						trackEditSpaceActiveState,
						trackEditSpaceReleasedState,
						trackEditUndoPatchCount,
						trackEditRedoPatchCount,
						trackEditSaveState,
						trackEditDownloadFilename,
						trackEditAnnotationModeState,
						trackEditDragState,
						trackEditPopupSuppressed,
						trackEditReviewShortcutGuard,
						trackEditRevertState,
						trackEditSaveFailureState,
						trackEditReviewerIsolationState,
						trackEditNoReviewerGateState,
						datasetExportPendingState,
						datasetExportCompletedState,
						datasetExportSettledState,
						exclusiveBoundaryHits,
						exclusiveLaneIndexes,
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
		if payload["scrubberTotal"] > 1:
			self.assertIsNotNone(payload["followStepSelectedTime"])
			self.assertNotEqual(payload["followStepSelectedTime"], payload["initialSelectedTime"])
			self.assertIsNotNone(payload["lastPanTarget"])
		if payload["markerTargetTime"] is not None:
			self.assertIsNotNone(payload["markerAlignedTime"])
			self.assertAlmostEqual(payload["markerAlignedTime"], payload["markerTargetTime"], delta=1.0)
		if payload["secondUid"] and payload["secondUid"] != payload["firstUid"]:
			self.assertEqual(payload["clickedUid"], payload["secondUid"])
		self.assertEqual(payload["studioExportState"]["activeWorkspace"], "export")
		self.assertTrue(payload["studioExportState"]["open"])
		self.assertEqual(payload["studioUploadState"]["activeWorkspace"], "upload")
		self.assertTrue(payload["studioUploadState"]["open"])
		if payload["trackEditLayer"]:
			self.assertIsNotNone(payload["trackEditModeState"])
			self.assertTrue(payload["trackEditModeState"]["enabled"])
			self.assertEqual(payload["trackEditModeState"]["editPressed"], "true")
			self.assertEqual(payload["trackEditModeState"]["annotationPressed"], "false")
			self.assertTrue(payload["trackEditModeState"]["mapLocked"])
			self.assertFalse(payload["trackEditModeState"]["draggingEnabled"])
			self.assertTrue(payload["trackEditModeState"]["scrollWheelEnabled"])
			self.assertIsNotNone(payload["trackEditPopupSuppressed"])
			self.assertGreater(payload["trackEditPopupSuppressed"]["markerCount"], 0)
			self.assertFalse(payload["trackEditPopupSuppressed"]["hasPopup"])
			self.assertIsNotNone(payload["trackEditReviewShortcutGuard"])
			self.assertEqual(payload["trackEditReviewShortcutGuard"]["selectedDecision"], "")
			self.assertGreaterEqual(len(payload["trackEditSelection"]), 1)
			self.assertIsNotNone(payload["trackEditDragState"])
			self.assertGreaterEqual(payload["trackEditDragState"]["selectionCount"], 1)
			self.assertEqual(payload["trackEditDragState"]["patchCount"], payload["trackEditDragState"]["selectionCount"])
			self.assertTrue(payload["trackEditDragState"]["dirty"])
			self.assertFalse(payload["trackEditDragState"]["saveDisabled"])
			self.assertTrue(payload["trackEditDragState"]["dragSuppressActive"])
			self.assertTrue(payload["trackEditDragState"]["secondaryDeltaMatches"])
			self.assertIsNotNone(payload["trackEditRevertState"])
			self.assertEqual(payload["trackEditRevertState"]["patchCount"], 0)
			self.assertFalse(payload["trackEditRevertState"]["dirty"])
			self.assertTrue(payload["trackEditRevertState"]["saveDisabled"])
			self.assertGreaterEqual(payload["trackEditPatchCount"], 1)
			self.assertIsNotNone(payload["trackEditPatchedLatitude"])
			self.assertGreaterEqual(payload["trackEditUndoDepth"], 1)
			self.assertEqual(payload["trackEditRedoDepth"], 0)
			self.assertTrue(payload["trackEditCoordinateSummaryVisible"])
			self.assertTrue(payload["trackEditCoordinateSummary"])
			self.assertTrue(payload["trackEditSaveMenuOpened"])
			self.assertTrue(payload["trackEditSaveMenuClosed"])
			self.assertTrue(payload["trackEditSpaceInputGuard"])
			self.assertIsNotNone(payload["trackEditSpaceSelectGuard"])
			self.assertFalse(payload["trackEditSpaceSelectGuard"]["overlayOpen"])
			self.assertTrue(payload["trackEditSpaceSelectGuard"]["editEnabled"])
			self.assertEqual(payload["trackEditSpaceSelectGuard"]["activeElementTag"], "BUTTON")
			self.assertFalse(payload["trackEditSpaceSelectGuard"]["draggingEnabled"])
			self.assertTrue(payload["trackEditSpaceSelectGuard"]["scrollWheelEnabled"])
			self.assertIsNotNone(payload["trackEditSpaceActiveState"])
			self.assertTrue(payload["trackEditSpaceActiveState"]["spaceModifierActive"])
			self.assertFalse(payload["trackEditSpaceActiveState"]["mapLocked"])
			self.assertTrue(payload["trackEditSpaceActiveState"]["draggingEnabled"])
			self.assertTrue(payload["trackEditSpaceActiveState"]["scrollWheelEnabled"])
			self.assertIsNotNone(payload["trackEditSpaceReleasedState"])
			self.assertFalse(payload["trackEditSpaceReleasedState"]["spaceModifierActive"])
			self.assertTrue(payload["trackEditSpaceReleasedState"]["mapLocked"])
			self.assertFalse(payload["trackEditSpaceReleasedState"]["draggingEnabled"])
			self.assertTrue(payload["trackEditSpaceReleasedState"]["scrollWheelEnabled"])
			self.assertEqual(payload["trackEditUndoPatchCount"], 0)
			self.assertEqual(payload["trackEditRedoPatchCount"], payload["trackEditPatchCount"])
			self.assertIsNotNone(payload["trackEditSaveState"])
			self.assertFalse(payload["trackEditSaveState"]["dirty"])
			self.assertTrue(payload["trackEditSaveState"]["lastSavedAt"])
			self.assertEqual(payload["trackEditSaveState"]["patchCount"], payload["trackEditPatchCount"])
			self.assertTrue(payload["trackEditSaveState"]["saveDisabled"])
			self.assertTrue(payload["trackEditDownloadFilename"].endswith(".json"))
			self.assertIsNotNone(payload["trackEditAnnotationModeState"])
			self.assertFalse(payload["trackEditAnnotationModeState"]["enabled"])
			self.assertEqual(payload["trackEditAnnotationModeState"]["editPressed"], "false")
			self.assertEqual(payload["trackEditAnnotationModeState"]["annotationPressed"], "true")
			self.assertFalse(payload["trackEditAnnotationModeState"]["mapLocked"])
			self.assertTrue(payload["trackEditAnnotationModeState"]["draggingEnabled"])
			self.assertIsNotNone(payload["trackEditSaveFailureState"])
			self.assertTrue(payload["trackEditSaveFailureState"]["dirty"])
			self.assertGreaterEqual(payload["trackEditSaveFailureState"]["patchCount"], 1)
			self.assertFalse(payload["trackEditSaveFailureState"]["saveDisabled"])
			self.assertIn("保存失败", payload["trackEditSaveFailureState"]["status"])
			self.assertIsNotNone(payload["trackEditReviewerIsolationState"])
			self.assertEqual(payload["trackEditReviewerIsolationState"]["otherPatchCount"], 0)
			self.assertFalse(payload["trackEditReviewerIsolationState"]["otherDirty"])
			self.assertGreaterEqual(payload["trackEditReviewerIsolationState"]["restoredPatchCount"], 1)
			self.assertIsNotNone(payload["trackEditNoReviewerGateState"])
			self.assertFalse(payload["trackEditNoReviewerGateState"]["entered"])
			self.assertFalse(payload["trackEditNoReviewerGateState"]["enabled"])
			self.assertTrue(payload["trackEditNoReviewerGateState"]["buttonDisabled"])
			self.assertIn("请先设置当前标注者", payload["trackEditNoReviewerGateState"]["selection"])
			self.assertIsNotNone(payload["datasetExportPendingState"])
			self.assertTrue(payload["datasetExportPendingState"]["busy"], payload["datasetExportPendingState"])
			self.assertEqual(payload["datasetExportPendingState"]["progressActive"], "true")
			self.assertRegex(payload["datasetExportPendingState"]["label"], r"最小 GPS 导出\s+\d+%")
			self.assertIsNotNone(payload["datasetExportCompletedState"])
			self.assertFalse(payload["datasetExportCompletedState"]["busy"])
			self.assertIn(payload["datasetExportCompletedState"]["progressActive"], {"true", "false"})
			self.assertIn("最小 GPS 导出", payload["datasetExportCompletedState"]["label"])
			self.assertTrue(payload["datasetExportCompletedState"]["summary"])
			self.assertIsNotNone(payload["datasetExportSettledState"])
			self.assertFalse(payload["datasetExportSettledState"]["busy"])
			self.assertEqual(payload["datasetExportSettledState"]["progressActive"], "false")
			self.assertEqual(payload["datasetExportSettledState"]["label"], "最小 GPS 导出")
		self.assertEqual(payload["exclusiveBoundaryHits"], ["left"])
		self.assertEqual(payload["exclusiveLaneIndexes"], [0, 0])
		if payload["alternateBatchName"]:
			self.assertEqual(payload["switchedBatchName"], payload["alternateBatchName"])
			self.assertTrue(payload["switchedUid"])
			self.assertGreater(payload["switchedLayerCount"], 0)


if __name__ == "__main__":
	unittest.main()
