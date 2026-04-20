(function attachStudioManagementCore(root) {
	const DEFAULT_UPLOAD_TYPE = "trajectory4";
	const modules = root.TrajectoryStudioModules || (root.TrajectoryStudioModules = {});

	const formatSpecs = Object.freeze({
		trajectory4: {
			title: "4 元组轨迹文件",
			summary: "每行是一个轨迹点，可在同一个文件里包含多个 uid；后端会按 uid 分组并按时间排序。",
			fields: [
				{
					key: "uid",
					name: "uid",
					type: "string",
					required: true,
					description: "轨迹 ID。同一文件可以有多个 uid，但每行只能属于一个 uid。",
					accepted: ["uid"],
					placeholder: "例如 user_id / trajId",
				},
				{
					key: "latitude",
					name: "latitude / lat",
					type: "float",
					required: true,
					description: "纬度，十进制度。",
					accepted: ["latitude", "lat"],
					placeholder: "例如 gps_lat / y",
				},
				{
					key: "longitude",
					name: "longitude / lon",
					type: "float",
					required: true,
					description: "经度，十进制度。",
					accepted: ["longitude", "lon"],
					placeholder: "例如 gps_lon / x",
				},
				{
					key: "timestamp",
					name: "timestamp_ms / timestamp",
					type: "epoch ms | epoch s | ISO-8601",
					required: true,
					description: "时间戳；支持毫秒、秒或 ISO 时间字符串。",
					accepted: ["timestamp_ms", "timestamp"],
					placeholder: "例如 track_time / collectTime",
				},
				{
					key: "status",
					name: "status / state",
					type: "string",
					required: false,
					description: "点状态，可写 stay / walking / bicycling / driving 等。",
					accepted: ["status", "state"],
					placeholder: "例如 motion_state / label",
				},
			],
			rules: [
				"字段名大小写不敏感，常见 snake_case / camelCase 变体会自动兼容，例如 UID、TimestampMS。",
				"同一个文件里不要混用 4 元组轨迹和 6 元组信令格式。",
				"同一 uid 的多条记录会自动按时间排序；建议同一个 uid 的点都放在一个文件内。",
			],
		},
		signal6: {
			title: "6 元组信令文件",
			summary: "每行是一条信令事件，可在同一个文件里包含多个 uid；后端会按 uid 分组，并按 t_in / t_out 排序。",
			fields: [
				{
					key: "uid",
					name: "uid",
					type: "string",
					required: true,
					description: "用户或轨迹 ID。同一文件可以有多个 uid。",
					accepted: ["uid"],
					placeholder: "例如 user_id / subscriberId",
				},
				{
					key: "cid",
					name: "cid",
					type: "string | integer",
					required: true,
					description: "基站 / 小区标识。",
					accepted: ["cid"],
					placeholder: "例如 cell_id / stationId",
				},
				{
					key: "latitude",
					name: "latitude / lat",
					type: "float",
					required: true,
					description: "纬度，且必须落在北京范围内。",
					accepted: ["latitude", "lat"],
					placeholder: "例如 gps_lat / y",
				},
				{
					key: "longitude",
					name: "longitude / lon",
					type: "float",
					required: true,
					description: "经度，且必须落在北京范围内。",
					accepted: ["longitude", "lon"],
					placeholder: "例如 gps_lon / x",
				},
				{
					key: "t_in",
					name: "t_in / start_time",
					type: "epoch ms | epoch s | ISO-8601",
					required: true,
					description: "进入时间。",
					accepted: ["t_in", "start_time", "time in", "procedureStartTime"],
					placeholder: "例如 procedureStartTime / entry_time",
				},
				{
					key: "t_out",
					name: "t_out / end_time",
					type: "epoch ms | epoch s | ISO-8601",
					required: true,
					description: "离开时间，必须大于等于 t_in。",
					accepted: ["t_out", "end_time", "time out", "procedureEndTime", "proceduereEndTime"],
					placeholder: "例如 procedureEndTime / exit_time",
				},
				{
					key: "status",
					name: "status / state",
					type: "string",
					required: false,
					description: "状态标签，可写 road / subway / railway / unmatch 等。",
					accepted: ["status", "state"],
					placeholder: "例如 signal_state / scene",
				},
			],
			rules: [
				"字段名大小写不敏感，常见 snake_case / camelCase 变体会自动兼容，例如 UID、CID、TIn、TOut。",
				"时间字段默认兼容 time in / time out、t_in / t_out、procedureStartTime / procedureEndTime，以及常见拼写变体 proceduereEndTime。",
				"只接受北京范围坐标：lat 39.4~41.1，lon 115.7~117.4。",
				"同一文件里每行只能是一条信令事件；同一 uid 的多条事件建议放在同一个文件内，不要拆散或混入 4 元组轨迹行。",
			],
		},
	});

	function pickFirstString() {
		for (const value of arguments) {
			if (typeof value === "string" && value.trim()) return value.trim();
		}
		return "";
	}

	function firstArray(payload) {
		if (Array.isArray(payload)) return payload;
		if (Array.isArray(payload && payload.items)) return payload.items;
		if (Array.isArray(payload && payload.uploads)) return payload.uploads;
		return [];
	}

	function defaultEscapeHtml(value) {
		return String(value ?? "")
			.replaceAll("&", "&amp;")
			.replaceAll("<", "&lt;")
			.replaceAll(">", "&gt;")
			.replaceAll('"', "&quot;")
			.replaceAll("'", "&#39;");
	}

	function getFormatSpec(uploadType) {
		const normalizedType = String(uploadType || DEFAULT_UPLOAD_TYPE).trim().toLowerCase();
		return formatSpecs[normalizedType] || formatSpecs[DEFAULT_UPLOAD_TYPE];
	}

	function buildHelpHtml(spec, helpers = {}) {
		const escapeHtml = typeof helpers.escapeHtml === "function" ? helpers.escapeHtml : defaultEscapeHtml;
		const normalizedSpec = spec && typeof spec === "object" ? spec : formatSpecs[DEFAULT_UPLOAD_TYPE];
		const fieldsHtml = (normalizedSpec.fields || []).map(field => `
			<li class="studio-management-help-item">
				<div class="studio-management-help-field">${escapeHtml(field.name || "-")} · ${field.required ? "必填" : "可选"}</div>
				<div class="studio-management-help-type">${escapeHtml(field.type || "-")}</div>
				<div class="studio-management-help-desc">${escapeHtml(field.description || field.desc || "-")}</div>
				${Array.isArray(field.accepted) && field.accepted.length ? `
					<div class="studio-management-help-aliases-label">兼容头</div>
					<div class="studio-management-help-aliases">${field.accepted.map(alias => `<span class="studio-management-help-alias">${escapeHtml(alias)}</span>`).join("")}</div>
				` : ""}
			</li>
		`).join("");
		const rulesHtml = (normalizedSpec.rules || []).map(rule => `<li class="studio-management-help-rule">${escapeHtml(rule)}</li>`).join("");
		return `
			<div class="studio-management-help-shell">
				<div class="studio-management-help-head">
					<div class="studio-management-help-kicker">Format Guide</div>
					<div class="studio-management-help-title">${escapeHtml(normalizedSpec.title || "上传说明")}</div>
					<div class="studio-management-help-summary">${escapeHtml(normalizedSpec.summary || "")}</div>
				</div>
				<ul class="studio-management-help-rules">${rulesHtml}</ul>
				<ul class="studio-management-help-grid">${fieldsHtml}</ul>
			</div>
		`;
	}

	function getStatusClass(status) {
		const normalized = String(status || "").toLowerCase();
		if (!normalized) return "status-uploaded";
		if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("delete")) return "status-failed";
		if (normalized.includes("publish") || normalized.includes("complete") || normalized.includes("ready")) return "status-published";
		if (normalized.includes("queue") || normalized.includes("valid") || normalized.includes("process")) return "status-processing";
		return `status-${normalized.replace(/[^a-z0-9_]+/g, "_")}`;
	}

	function resolveActor(payload) {
		const actorPayload = payload && payload.actor && typeof payload.actor === "object"
			? payload.actor
			: (payload && typeof payload === "object" ? payload : {});
		const id = pickFirstString(
			actorPayload.actor_id,
			actorPayload.user_id,
			actorPayload.id,
			actorPayload.username,
			actorPayload.login
		) || "-";
		const name = pickFirstString(
			actorPayload.display_name,
			actorPayload.name,
			actorPayload.username,
			actorPayload.login,
			actorPayload.actor_id,
			actorPayload.user_id
		) || "未识别身份";
		const role = pickFirstString(actorPayload.role, actorPayload.actor_role, actorPayload.type) || "unknown";
		return {
			id,
			name,
			role,
			description: pickFirstString(actorPayload.description, actorPayload.email),
			raw: actorPayload,
		};
	}

	function normalizeUpload(item, helpers = {}) {
		const formatVisibilityScope = typeof helpers.formatVisibilityScope === "function"
			? helpers.formatVisibilityScope
			: (value => String(value || "-"));
		const formatAnnotationMode = typeof helpers.formatAnnotationMode === "function"
			? helpers.formatAnnotationMode
			: (value => String(value || "-"));
		const upload = item && typeof item === "object" ? item : {};
		const uploadId = pickFirstString(upload.upload_id, upload.id);
		const status = pickFirstString(upload.status, upload.lifecycle_status) || "created";
		const visibility = pickFirstString(upload.visibility_scope, upload.visibility, upload.requested_visibility) || "-";
		const annotationMode = pickFirstString(
			upload.annotation_mode,
			upload.annotation,
			upload.annotation_enabled ? "annotatable" : ""
		) || "-";
		const fieldMapping = upload && upload.field_mapping && typeof upload.field_mapping === "object"
			? upload.field_mapping
			: null;
		const batchName = pickFirstString(
			upload.batch_name,
			upload.published_batch_name,
			upload.publication_batch_name,
			upload.publication && upload.publication.batch_name,
			upload.batch && upload.batch.name,
			upload.result && upload.result.batch_name
		);
		return {
			raw: upload,
			uploadId,
			status,
			statusClass: getStatusClass(status),
			displayName: pickFirstString(upload.display_name, upload.original_name, upload.filename, upload.safe_name, uploadId) || "-",
			originalName: pickFirstString(upload.original_name, upload.filename, upload.safe_name) || "-",
			uploadType: pickFirstString(upload.upload_type, upload.source_kind, upload.type) || "-",
			visibility,
			visibilityLabel: formatVisibilityScope(visibility),
			annotationMode,
			annotationModeLabel: formatAnnotationMode(annotationMode),
			fieldMapping,
			hasCustomFieldMapping: !!(fieldMapping && Object.keys(fieldMapping).length),
			customFieldCount: fieldMapping ? Object.keys(fieldMapping).length : 0,
			batchName,
			sizeBytes: Number.isFinite(upload.size_bytes) ? upload.size_bytes : Number(upload.size_bytes),
			createdAt: pickFirstString(upload.created_at, upload.updated_at),
			updatedAt: pickFirstString(upload.updated_at, upload.processed_at, upload.published_at),
			errorText: pickFirstString(upload.error, upload.error_summary, upload.error_message, upload.failure_reason),
			note: pickFirstString(upload.note, upload.validation_summary, upload.message),
		};
	}

	function parseRawPayload(rawText) {
		if (!rawText) return {};
		try {
			return JSON.parse(rawText);
		} catch (_) {
			return { raw: rawText };
		}
	}

	async function createUploadRecord(apiFetchJson, body) {
		const payload = await apiFetchJson("/api/uploads", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		});
		return payload && (payload.upload || payload.item || payload) || {};
	}

	async function fetchActor(apiFetchJson) {
		const payload = await apiFetchJson("/api/me");
		return resolveActor(payload);
	}

	async function fetchUploads(apiFetchJson, helpers = {}) {
		const payload = await apiFetchJson("/api/uploads");
		return firstArray(payload).map(item => normalizeUpload(item, helpers));
	}

	function uploadBlob(deps, uploadId, file, options = {}) {
		const pickString = deps && typeof deps.pickFirstString === "function" ? deps.pickFirstString : pickFirstString;
		const XhrCtor = deps && deps.XMLHttpRequest ? deps.XMLHttpRequest : root.XMLHttpRequest;
		return new Promise((resolve, reject) => {
			const xhr = new XhrCtor();
			xhr.open("POST", `/api/uploads/${encodeURIComponent(uploadId)}/blob`, true);
			xhr.withCredentials = true;
			xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
			xhr.setRequestHeader("X-Upload-Filename", file.name);
			xhr.upload.addEventListener("progress", event => {
				if (typeof options.onProgress === "function") options.onProgress(event);
			});
			xhr.onerror = () => reject(new Error("文件上传失败，网络异常或请求被中断。"));
			xhr.onabort = () => reject(new Error("文件上传已中断。"));
			xhr.onload = () => {
				const payload = parseRawPayload(xhr.responseText || "");
				if (xhr.status >= 200 && xhr.status < 300) {
					resolve(payload);
					return;
				}
				reject(new Error(
					pickString(
						payload && payload.error,
						payload && payload.message,
						payload && payload.detail,
						typeof (payload && payload.raw) === "string" ? payload.raw : "",
						`请求失败: ${xhr.status || "upload"}`
					)
				));
			};
			xhr.send(file);
		});
	}

	modules.studioAdminCore = Object.freeze({
		DEFAULT_UPLOAD_TYPE,
		formatSpecs,
		getFormatSpec,
		buildHelpHtml,
		getStatusClass,
		resolveActor,
		normalizeUpload,
		parseRawPayload,
		createUploadRecord,
		fetchActor,
		fetchUploads,
		uploadBlob,
	});
})(typeof window !== "undefined" ? window : globalThis);
