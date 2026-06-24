// ===== 初始化 =====
document.addEventListener("DOMContentLoaded", () => {
    setToday();
    initUpload();
    initSettings();
    initGenerate();
    initLogs();
});

function setToday() {
    document.getElementById("log-date").value = new Date().toISOString().split("T")[0];
}

// ===== 文件上传 =====
let uploadedFiles = [];

function initUpload() {
    const area = document.getElementById("upload-area");
    const input = document.getElementById("file-input");
    const hint = document.getElementById("upload-hint");

    area.addEventListener("click", () => input.click());
    area.addEventListener("dragover", e => { e.preventDefault(); area.classList.add("dragover"); });
    area.addEventListener("dragleave", () => area.classList.remove("dragover"));
    area.addEventListener("drop", e => {
        e.preventDefault();
        area.classList.remove("dragover");
        handleFiles(e.dataTransfer.files);
    });
    input.addEventListener("change", () => {
        handleFiles(input.files);
        input.value = "";
    });
}

async function handleFiles(fileList) {
    const formData = new FormData();
    for (let f of fileList) {
        formData.append("files", f);
    }

    try {
        const resp = await fetch("/api/upload", { method: "POST", body: formData });
        const data = await resp.json();
        if (data.files) {
            uploadedFiles.push(...data.files);
            renderFileList();
        }
    } catch (err) {
        console.error("上传失败:", err);
    }
}

function escapeHtml(s) {
    const d = document.createElement("div");
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
}

function renderFileList() {
    const list = document.getElementById("file-list");
    const hint = document.getElementById("upload-hint");
    list.innerHTML = uploadedFiles.map((f, i) => `
        <li>
            <span>${iconFor(f.original_name)} ${escapeHtml(f.original_name)}</span>
            <span class="remove-file" data-idx="${i}">✕</span>
        </li>
    `).join("");
    hint.style.display = uploadedFiles.length ? "none" : "";

    list.querySelectorAll(".remove-file").forEach(el => {
        el.addEventListener("click", e => {
            e.stopPropagation();
            const idx = parseInt(el.dataset.idx);
            uploadedFiles.splice(idx, 1);
            renderFileList();
        });
    });
}

function iconFor(name) {
    const ext = name.split(".").pop().toLowerCase();
    const icons = { jpg: "🖼", jpeg: "🖼", png: "🖼", webp: "🖼", gif: "🖼", pdf: "📄", pptx: "📊", docx: "📝", xlsx: "📊", txt: "📃", m4a: "🎙", mp3: "🎙", wav: "🎙", flac: "🎙", ogg: "🎙" };
    return icons[ext] || "📎";
}

// ===== 生成日志 =====
let currentLogText = "";   // 当前日志纯文本
let currentLogDate = "";

function initGenerate() {
    document.getElementById("btn-generate").addEventListener("click", generate);
    document.getElementById("btn-regenerate").addEventListener("click", generate);
}

async function generate() {
    const points = document.getElementById("work-points").value.trim();
    if (!points) {
        alert("请输入今日工作要点");
        return;
    }
    currentLogDate = document.getElementById("log-date").value;

    // 隐藏已加载的历史工作要点
    document.getElementById("work-points-header").style.display = "none";

    const preview = document.getElementById("preview-content");
    const empty = document.getElementById("preview-empty");
    const actions = document.getElementById("preview-actions");
    const editBtn = document.getElementById("btn-edit");

    const genBtn = document.getElementById("btn-generate");
    const regenBtn = document.getElementById("btn-regenerate");

    empty.style.display = "none";
    preview.style.display = "block";
    preview.innerHTML = '<span class="spinner"></span> AI 正在生成中...';
    actions.style.display = "none";
    genBtn.style.display = "none";
    regenBtn.style.display = "none";

    try {
        const resp = await fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                date: currentLogDate,
                work_points: points,
                files: uploadedFiles.map(f => f.path)
            })
        });

        if (!resp.ok) {
            preview.textContent = "生成失败: " + (await resp.text());
            return;
        }

        // 流式读取
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        preview.textContent = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = decoder.decode(value, { stream: true });
            preview.textContent += text;
        }

        currentLogText = preview.textContent;
        switchToEditMode();  // 生成完直接进入编辑模式
        actions.style.display = "flex";
        document.getElementById("btn-regenerate").style.display = "";

    } catch (err) {
        preview.textContent = "生成失败: " + err.message;
    }
}

// ===== 编辑模式 =====
let isEditMode = false;

function switchToEditMode() {
    const preview = document.getElementById("preview-content");
    const editBtn = document.getElementById("btn-edit");

    // 替换为 textarea
    const parent = preview.parentNode;
    const textarea = document.createElement("textarea");
    textarea.id = "preview-editor";
    textarea.className = "textarea editor";
    textarea.style.cssText = "min-height:400px; width:100%; font-size:15px; line-height:2; resize:vertical;";
    textarea.value = preview.textContent;
    parent.replaceChild(textarea, preview);
    isEditMode = true;
    editBtn.textContent = "👁 预览";
}

function switchToPreviewMode() {
    const editor = document.getElementById("preview-editor");
    const editBtn = document.getElementById("btn-edit");
    if (!editor) return;

    currentLogText = editor.value;  // 保存编辑内容

    const parent = editor.parentNode;
    const div = document.createElement("div");
    div.id = "preview-content";
    div.className = "preview-content";
    div.textContent = editor.value;
    parent.replaceChild(div, editor);
    isEditMode = false;
    editBtn.textContent = "✏ 编辑";
}

// ===== 编辑按钮 =====
document.getElementById("btn-edit").addEventListener("click", () => {
    if (isEditMode) {
        switchToPreviewMode();
    } else {
        switchToEditMode();
    }
});

// ===== 保存按钮（后端保存） =====
document.getElementById("btn-save").addEventListener("click", async () => {
    if (isEditMode) {
        currentLogText = document.getElementById("preview-editor").value;
    }

    try {
        const resp = await fetch("/api/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                date: currentLogDate,
                content: currentLogText,
                work_points: document.getElementById("work-points").value.trim()
            })
        });
        const data = await resp.json();
        if (data.ok) {
            showToast("已保存");
        } else {
            showToast("保存失败: " + (data.error || "未知错误"));
        }
    } catch (err) {
        showToast("保存失败: " + err.message);
    }
});

// ===== 一键复制按钮 =====
document.getElementById("btn-copy").addEventListener("click", async () => {
    if (isEditMode) {
        currentLogText = document.getElementById("preview-editor").value;
    }
    try {
        await navigator.clipboard.writeText(currentLogText);
        showToast("已复制到剪贴板");
    } catch {
        // 降级方案
        const ta = document.createElement("textarea");
        ta.value = currentLogText;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        showToast("已复制到剪贴板");
    }
});

// ===== Toast 提示 =====
function showToast(msg) {
    let el = document.getElementById("toast");
    if (!el) {
        el = document.createElement("div");
        el.id = "toast";
        document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.opacity = "1";
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.style.opacity = "0"; }, 2500);
}

// ===== 设置弹窗 =====
function initSettings() {
    const dialog = document.getElementById("settings-dialog");
    const providerEl = document.getElementById("setting-asr-provider");

    // 切换 ASR 提供商时显隐对应字段
    providerEl.addEventListener("change", () => {
        const val = providerEl.value;
        document.getElementById("asr-aliyun-fields").style.display = val === "aliyun" ? "" : "none";
        document.getElementById("asr-tencent-fields").style.display = val === "tencent" ? "" : "none";
    });

    document.getElementById("btn-settings").addEventListener("click", async () => {
        const resp = await fetch("/api/config");
        const config = await resp.json();
        document.getElementById("setting-apikey").value = config.deepseek_api_key || "";
        document.getElementById("setting-baseurl").value = config.deepseek_base_url || "https://api.deepseek.com";
        providerEl.value = config.asr_provider || "";
        document.getElementById("setting-asr-app-key").value = config.asr_app_key || "";
        document.getElementById("setting-asr-access-key-id").value = config.asr_access_key_id || "";
        document.getElementById("setting-asr-access-key-secret").value = config.asr_access_key_secret || "";
        document.getElementById("setting-asr-secret-id").value = config.asr_secret_id || "";
        document.getElementById("setting-asr-secret-key").value = config.asr_secret_key || "";
        document.getElementById("setting-cos-secret-id").value = config.cos_secret_id || "";
        document.getElementById("setting-cos-secret-key").value = config.cos_secret_key || "";
        document.getElementById("setting-cos-region").value = config.cos_region || "ap-guangzhou";
        document.getElementById("setting-cos-bucket").value = config.cos_bucket || "";
        providerEl.dispatchEvent(new Event("change"));
        dialog.showModal();
    });

    document.getElementById("btn-settings-cancel").addEventListener("click", () => dialog.close());
    document.getElementById("btn-settings-save").addEventListener("click", async () => {
        const body = {
            deepseek_api_key: document.getElementById("setting-apikey").value,
            deepseek_base_url: document.getElementById("setting-baseurl").value,
            asr_provider: document.getElementById("setting-asr-provider").value,
            asr_app_key: document.getElementById("setting-asr-app-key").value,
            asr_access_key_id: document.getElementById("setting-asr-access-key-id").value,
            asr_access_key_secret: document.getElementById("setting-asr-access-key-secret").value,
            asr_secret_id: document.getElementById("setting-asr-secret-id").value,
            asr_secret_key: document.getElementById("setting-asr-secret-key").value,
            cos_secret_id: document.getElementById("setting-cos-secret-id").value,
            cos_secret_key: document.getElementById("setting-cos-secret-key").value,
            cos_region: document.getElementById("setting-cos-region").value,
            cos_bucket: document.getElementById("setting-cos-bucket").value,
        };
        await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        dialog.close();
    });
}

// ===== 历史日志列表 =====
function initLogs() {
    const btn = document.getElementById("btn-toggle-logs");
    const list = document.getElementById("logs-list");

    btn.addEventListener("click", async () => {
        if (list.style.display !== "none") {
            list.style.display = "none";
            return;
        }
        if (list.dataset.loaded) {
            list.style.display = "";
            return;
        }
        list.textContent = "加载中...";
        list.style.display = "";
        try {
            const resp = await fetch("/api/logs");
            const data = await resp.json();
            if (!data.logs || data.logs.length === 0) {
                list.textContent = "暂无历史日志";
                return;
            }
            list.textContent = "";
            const ul = document.createElement("ul");
            ul.style.cssText = "list-style:none;padding:0;margin:0;max-height:300px;overflow-y:auto";
            for (const log of data.logs) {
                const li = document.createElement("li");
                li.style.cssText = "padding:6px 8px;cursor:pointer;border-radius:4px;font-size:13px;color:var(--text);transition:background .15s";
                li.onmouseover = () => li.style.background = "var(--bg-secondary)";
                li.onmouseout = () => li.style.background = "";
                li.textContent = `📄 ${log.date}  ${log.filename}`;
                li.dataset.date = log.date;
                li.addEventListener("click", () => loadLog(log.date));
                ul.appendChild(li);
            }
            list.appendChild(ul);
            list.dataset.loaded = "1";
        } catch (err) {
            list.textContent = "加载失败: " + err.message;
        }
    });
}

async function loadLog(date) {
    // 如果当前在编辑模式，先切回预览模式（重建 #preview-content）
    if (isEditMode) {
        switchToPreviewMode();
    }

    const preview = document.getElementById("preview-content");
    const wpHeader = document.getElementById("work-points-header");
    const wpText = document.getElementById("work-points-text");
    const empty = document.getElementById("preview-empty");
    const actions = document.getElementById("preview-actions");

    empty.style.display = "none";
    preview.style.display = "block";
    preview.textContent = "加载中...";
    actions.style.display = "none";
    wpHeader.style.display = "none";

    try {
        const resp = await fetch(`/api/logs/${date}`);
        const data = await resp.json();
        if (data.error) {
            preview.textContent = "加载失败: " + data.error;
            return;
        }
        currentLogDate = date;
        currentLogText = data.content;

        // 显示工作要点
        if (data.work_points) {
            wpText.textContent = data.work_points;
            wpHeader.style.display = "";
        }

        preview.textContent = data.content;
        switchToEditMode();
        actions.style.display = "flex";
    } catch (err) {
        preview.textContent = "加载失败: " + err.message;
    }
}
