/* My Notes — theme, search, filters, pagination, and note actions. */
"use strict";

(() => {
    const $ = (selector, root = document) => root.querySelector(selector);
    const THEME_STORAGE_KEY = "my-notes-theme";
    const DEFAULT_PAGE_SIZE = 10;

    const el = {
        theme: $("#theme-select"),
        addForm: $("#add-note-form"),
        addTitle: $("#note-title"),
        addContent: $("#note-content"),
        search: $("#note-search"),
        created: $("#created-at-filter"),
        updated: $("#updated-at-filter"),
        important: $("#important-filter"),
        updatedStatus: $("#updated-status-filter"),
        sort: $("#note-sort"),
        pageSize: $("#notes-per-page"),
        apply: $("#apply-note-filters"),
        reset: $("#reset-note-filters"),
        notes: $("#notes-container"),
        count: $("#notes-result-count"),
        empty: $("#no-search-results"),
        emptyReset: $("#empty-state-reset"),
        pagination: $("#notes-pagination"),
        previous: $("#notes-previous"),
        next: $("#notes-next"),
        currentPage: $("#notes-current-page"),
        pageInfo: $("#notes-page-info"),
        loading: $("#notes-loading"),
        error: $("#notes-error"),
    };

    const state = {
        page: 1,
        pageSize: DEFAULT_PAGE_SIZE,
        total: 0,
        totalPages: 0,
        sort: "newest",
        q: "",
        createdOn: "",
        updatedDate: "",
        important: "",
        updatedStatus: "",
        requestId: 0,
        controller: null,
        searchTimer: null,
    };

    /* ---------- Safe DOM and display helpers ---------- */

    function node(tag, className = "", text = null) {
        const element = document.createElement(tag);

        if (className) {
            element.className = className;
        }

        if (text !== null && text !== undefined) {
            element.textContent = String(text);
        }

        return element;
    }

    function hide(element, shouldHide) {
        if (element) {
            element.hidden = Boolean(shouldHide);
        }
    }

    function showError(message) {
        if (!el.error) return;

        el.error.replaceChildren();

        el.error.append(
            node("span", "status-message-title", "Something went wrong."),
            node("span", "status-message-description", message)
        );

        el.error.hidden = false;
    }

    function clearError() {
        hide(el.error, true);
    }

    function setLoading(loading) {
        if (el.loading) {
            el.loading.hidden = !loading;
        }

        if (el.notes) {
            el.notes.setAttribute("aria-busy", String(loading));
        }

        if (el.previous) {
            el.previous.disabled = loading || state.page <= 1;
        }

        if (el.next) {
            el.next.disabled =
                loading || state.page >= state.totalPages;
        }
    }

    function boolValue(value) {
        if (value === true || value === 1) return true;

        if (
            value === false ||
            value === 0 ||
            value === null ||
            value === undefined
        ) {
            return false;
        }

        return ["true", "1", "yes", "on"].includes(
            String(value).trim().toLowerCase()
        );
    }

    function noteId(note) {
        return String(note?.id ?? note?._id ?? "");
    }

    function noteTitle(note) {
        return typeof note?.title === "string" ? note.title : "";
    }

    function noteText(note) {
        return typeof note?.note === "string" ? note.note : "";
    }

    function noteImportant(note) {
        return boolValue(note?.important);
    }

    function noteUpdated(note) {
        if (
            note?.updated_status !== undefined &&
            note?.updated_status !== null
        ) {
            return boolValue(note.updated_status);
        }

        return Boolean(note?.updated_date);
    }

    function formatDate(value) {
        if (!value) return "Not available";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return "Not available";
        }

        try {
            return new Intl.DateTimeFormat(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            }).format(date);
        } catch {
            return date.toLocaleString();
        }
    }

    function addBadge(parent, text, className) {
        parent.appendChild(
            node("span", `note-badge ${className}`, text)
        );
    }

    function actionButton(text, action, id, className, title = "") {
        const button = node("button", className, text);

        button.type = "button";
        button.dataset.action = action;
        button.dataset.noteId = id;

        if (title) {
            button.title = title;
        }

        return button;
    }

    function addMeta(parent, label, value) {
        const item = node("span", "note-meta-item");

        item.append(
            node("span", "", `${label}:`),
            node("time", "", value)
        );

        parent.appendChild(item);
    }

    /* ---------- Theme selector ---------- */

    function readThemePreference() {
        try {
            const saved = localStorage.getItem(THEME_STORAGE_KEY);

            return ["system", "light", "dark"].includes(saved)
                ? saved
                : "system";
        } catch {
            return "system";
        }
    }

    function systemTheme() {
        if (typeof window.matchMedia !== "function") {
            return "light";
        }

        return window.matchMedia(
            "(prefers-color-scheme: dark)"
        ).matches
            ? "dark"
            : "light";
    }

    function applyTheme(preference, save = true) {
        const selected = ["system", "light", "dark"].includes(preference)
            ? preference
            : "system";

        const resolved =
            selected === "system" ? systemTheme() : selected;

        const root = document.documentElement;

        /*
         * data-theme:
         *   The actual theme being displayed: light or dark.
         *
         * data-theme-preference:
         *   The selected preference: system, light, or dark.
         *
         * Both attributes are needed by light.css and dark.css.
         */
        root.dataset.theme = resolved;
        root.dataset.themePreference = selected;

        // Tell the browser which native form-control palette to use.
        root.style.colorScheme = resolved;

        if (el.theme && el.theme.value !== selected) {
            el.theme.value = selected;
        }

        if (save) {
            try {
                localStorage.setItem(THEME_STORAGE_KEY, selected);
            } catch {
                // The selected theme still works if storage is unavailable.
            }
        }
    }

    function initializeTheme() {
        const preference = readThemePreference();

        // Apply the saved theme immediately.
        applyTheme(preference, false);

        if (el.theme) {
            el.theme.value = preference;

            el.theme.addEventListener("change", () => {
                applyTheme(el.theme.value, true);
            });
        }

        if (typeof window.matchMedia === "function") {
            const mediaQuery = window.matchMedia(
                "(prefers-color-scheme: dark)"
            );

            const onSystemThemeChange = () => {
                // Follow OS changes only when System is selected.
                if (readThemePreference() === "system") {
                    applyTheme("system", false);
                }
            };

            if (typeof mediaQuery.addEventListener === "function") {
                mediaQuery.addEventListener(
                    "change",
                    onSystemThemeChange
                );
            } else if (typeof mediaQuery.addListener === "function") {
                // Compatibility with older browsers.
                mediaQuery.addListener(onSystemThemeChange);
            }
        }
    }

    /* ---------- Filters and search API ---------- */

    function readControls() {
        state.q = el.search?.value.trim() || "";
        state.createdOn = el.created?.value.trim() || "";
        state.updatedDate = el.updated?.value.trim() || "";
        state.important = el.important?.value || "";
        state.updatedStatus = el.updatedStatus?.value || "";
        state.sort = el.sort?.value || "newest";

        const requestedSize = Number.parseInt(
            el.pageSize?.value || DEFAULT_PAGE_SIZE,
            10
        );

        state.pageSize =
            Number.isFinite(requestedSize) && requestedSize > 0
                ? requestedSize
                : DEFAULT_PAGE_SIZE;
    }

    function searchUrl() {
        const params = new URLSearchParams();

        if (state.q) {
            params.set("q", state.q);
        }

        if (state.createdOn) {
            params.set("created_on", state.createdOn);
        }

        if (state.updatedDate) {
            params.set("updated_date", state.updatedDate);
        }

        if (state.important !== "") {
            params.set("important", state.important);
        }

        if (state.updatedStatus !== "") {
            params.set("updated_status", state.updatedStatus);
        }

        params.set("page", String(state.page));
        params.set("page_size", String(state.pageSize));
        params.set("sort", state.sort);

        return `/notes/search?${params.toString()}`;
    }

    async function readResponse(response) {
        if (
            response.status === 401 ||
            response.status === 403 ||
            (response.redirected && response.url.includes("/login"))
        ) {
            window.location.assign("/login");

            throw new Error(
                "Your session has expired. Please sign in again."
            );
        }

        const contentType =
            response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    data.message ||
                    `Request failed (${response.status}).`
                );
            }

            return data;
        }

        const body = await response.text();

        if (!response.ok) {
            throw new Error(`Request failed (${response.status}).`);
        }

        return body;
    }

    async function loadNotes() {
        if (!el.notes) return;

        const requestId = ++state.requestId;

        if (state.controller) {
            state.controller.abort();
        }

        const controller = new AbortController();
        state.controller = controller;

        clearError();
        setLoading(true);
        hide(el.empty, true);

        try {
            const response = await fetch(searchUrl(), {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                signal: controller.signal,
            });

            const data = await readResponse(response);

            if (requestId !== state.requestId) return;

            if (!data || !Array.isArray(data.items)) {
                throw new Error(
                    "The notes endpoint returned an unexpected response."
                );
            }

            state.total = Number(data.total) || 0;
            state.page = Number(data.page) || state.page;
            state.pageSize =
                Number(data.page_size) || state.pageSize;
            state.totalPages = Number(data.total_pages) || 0;
            state.sort = data.sort || state.sort;

            renderNotes(data.items);
            updateCount();
            updatePagination();

            hide(
                el.empty,
                data.items.length > 0 || state.total > 0
            );
        } catch (error) {
            if (
                error.name === "AbortError" ||
                requestId !== state.requestId
            ) {
                return;
            }

            console.error("Failed to load notes:", error);

            el.notes.replaceChildren();
            hide(el.pagination, true);
            hide(el.empty, true);

            showError(
                error.message ||
                "Your notes could not be loaded. Please try again."
            );
        } finally {
            if (requestId === state.requestId) {
                setLoading(false);
            }
        }
    }

    function updateCount() {
        if (!el.count) return;

        el.count.textContent =
            `${state.total} ${state.total === 1 ? "note" : "notes"}`;
    }

    function updatePagination() {
        const pages = Math.max(0, state.totalPages);

        if (el.currentPage) {
            el.currentPage.textContent = String(state.page);
        }

        if (el.pageInfo) {
            el.pageInfo.textContent =
                `Page ${state.page} of ${pages}`;
        }

        if (el.previous) {
            el.previous.disabled =
                state.page <= 1 || state.total === 0;
        }

        if (el.next) {
            el.next.disabled =
                state.page >= pages || state.total === 0;
        }

        if (
            el.pageSize &&
            el.pageSize.value !== String(state.pageSize)
        ) {
            el.pageSize.value = String(state.pageSize);
        }

        hide(
            el.pagination,
            state.total === 0 || pages <= 1
        );
    }

    function renderNotes(notes) {
        if (!el.notes) return;

        const fragment = document.createDocumentFragment();

        notes.forEach((note) => {
            fragment.appendChild(renderNote(note));
        });

        el.notes.replaceChildren(fragment);

        hide(
            el.empty,
            notes.length > 0 || state.total > 0
        );
    }

    /* ---------- Render notes safely ---------- */

    function renderNote(note) {
        const id = noteId(note);
        const title = noteTitle(note);
        const content = noteText(note);
        const important = noteImportant(note);
        const updated = noteUpdated(note);

        const card = node(
            "article",
            `note-card${important ? " is-important" : ""}`
        );

        card.dataset.noteId = id;

        const header = node("div", "note-card-header");
        const heading = node("div", "note-card-heading");

        heading.appendChild(
            node("h3", "note-card-title", title || "Untitled note")
        );

        const badges = node("div", "note-card-badges");

        if (important) {
            addBadge(badges, "★ Important", "note-badge-important");
        }

        addBadge(
            badges,
            updated ? "✓ Updated" : "New",
            updated ? "note-badge-updated" : "note-badge-default"
        );

        heading.appendChild(badges);
        header.appendChild(heading);

        const contentNode = node(
            "p",
            `note-card-content${content ? "" : " is-empty"}`,
            content || "No content added."
        );

        const meta = node("div", "note-card-meta");

        addMeta(meta, "Created", formatDate(note.created_on));

        if (updated && note.updated_date) {
            addMeta(meta, "Updated", formatDate(note.updated_date));
        }

        const footer = node("div", "note-card-footer");
        const actions = node("div", "note-card-actions");

        actions.append(
            actionButton(
                important ? "★ Important" : "☆ Important",
                "toggle-important",
                id,
                `btn btn-outline-secondary note-action-button${important ? " is-active" : ""}`,
                important ? "Remove importance" : "Mark as important"
            ),
            actionButton(
                "Edit",
                "edit",
                id,
                "btn btn-outline-secondary note-action-button",
                `Edit ${title || "note"}`
            ),
            actionButton(
                "Delete",
                "delete",
                id,
                "btn btn-outline-secondary note-action-button note-delete-button",
                `Delete ${title || "note"}`
            )
        );

        footer.append(
            actions,
            node(
                "span",
                "note-updated-label",
                updated ? "Edited" : "Original"
            )
        );

        card.append(header, contentNode, meta, footer);

        return card;
    }

    /* ---------- Form POST helper ---------- */

    async function postForm(url, fields = {}) {
        const body = new URLSearchParams();

        Object.entries(fields).forEach(([key, value]) => {
            body.set(key, String(value));
        });

        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type":
                    "application/x-www-form-urlencoded;charset=UTF-8",
                Accept: "application/json, text/html",
                "X-Requested-With": "XMLHttpRequest",
            },
            body,
        });

        return readResponse(response);
    }

    async function toggleImportant(id) {
        clearError();

        try {
            await postForm(
                `/toggle_important/${encodeURIComponent(id)}`
            );

            await loadNotes();
        } catch (error) {
            console.error("Failed to change importance:", error);

            showError(
                error.message || "Could not update this note."
            );
        }
    }

    async function deleteNote(id) {
        const cards = Array.from(
            el.notes?.querySelectorAll(".note-card") || []
        );

        const card = cards.find(
            (item) => item.dataset.noteId === String(id)
        );

        const title =
            card?.querySelector(".note-card-title")?.textContent ||
            "this note";

        if (
            !window.confirm(
                `Delete "${title}"? This action cannot be undone.`
            )
        ) {
            return;
        }

        clearError();

        try {
            await postForm(
                `/delete_note/${encodeURIComponent(id)}`
            );

            if (
                state.page > 1 &&
                state.total - 1 <=
                    (state.page - 1) * state.pageSize
            ) {
                state.page -= 1;
            }

            await loadNotes();
        } catch (error) {
            console.error("Failed to delete note:", error);

            showError(
                error.message || "Could not delete this note."
            );
        }
    }

    /* ---------- Inline editing ---------- */

    function makeEditForm(note) {
        const id = noteId(note);
        const form = node("form", "note-edit-form");

        form.dataset.noteId = id;

        const titleLabel = node("label", "form-label", "Title");
        const titleInput = node("input", "form-control");

        titleInput.id = `edit-title-${id}`;
        titleInput.name = "title";
        titleInput.type = "text";
        titleInput.maxLength = 200;
        titleInput.required = true;
        titleInput.value = noteTitle(note);

        titleLabel.htmlFor = titleInput.id;

        const contentLabel = node(
            "label",
            "form-label",
            "Note content"
        );

        const contentInput = node(
            "textarea",
            "form-control note-edit-content"
        );

        contentInput.id = `edit-content-${id}`;
        contentInput.name = "note";
        contentInput.rows = 5;
        contentInput.required = true;
        contentInput.value = noteText(note);

        contentLabel.htmlFor = contentInput.id;

        const importantLabel = node(
            "label",
            "form-check important-checkbox"
        );

        const importantInput = node("input", "form-check-input");

        importantInput.type = "checkbox";
        importantInput.name = "important";
        importantInput.checked = noteImportant(note);

        importantLabel.append(
            importantInput,
            node("span", "form-check-label", "Mark as important")
        );

        const actions = node("div", "note-edit-actions");

        const cancel = node(
            "button",
            "btn btn-outline-secondary",
            "Cancel"
        );

        cancel.type = "button";
        cancel.dataset.action = "cancel-edit";
        cancel.dataset.noteId = id;

        const save = node(
            "button",
            "btn btn-primary",
            "Save changes"
        );

        save.type = "submit";

        actions.append(cancel, save);

        form.append(
            titleLabel,
            titleInput,
            contentLabel,
            contentInput,
            importantLabel,
            actions
        );

        return form;
    }

    function beginEdit(id) {
        const cards = Array.from(
            el.notes?.querySelectorAll(".note-card") || []
        );

        const card = cards.find(
            (item) => item.dataset.noteId === String(id)
        );

        if (!card || card.querySelector(".note-edit-form")) {
            return;
        }

        const title =
            card.querySelector(".note-card-title")?.textContent || "";

        const contentNode =
            card.querySelector(".note-card-content");

        const contentText = contentNode?.textContent || "";

        const content =
            contentText === "No content added." ? "" : contentText;

        const badgeText = Array.from(
            card.querySelectorAll(".note-badge")
        )
            .map((badge) => badge.textContent || "")
            .join(" ");

        const important = card.classList.contains("is-important");
        const updated = badgeText.includes("Updated");

        const form = makeEditForm({
            id,
            title: title === "Untitled note" ? "" : title,
            note: content,
            important,
            updated_status: updated,
        });

        card.classList.add("is-editing");
        card.appendChild(form);

        form.querySelector('[name="title"]')?.focus();

        form.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
        });
    }

    async function saveEdit(form) {
        const id = form.dataset.noteId;

        const titleInput = form.querySelector('[name="title"]');
        const contentInput = form.querySelector('[name="note"]');
        const importantInput =
            form.querySelector('[name="important"]');

        const saveButton =
            form.querySelector('button[type="submit"]');

        const title = titleInput?.value.trim() || "";
        const content = contentInput?.value.trim() || "";

        if (!title || !content) {
            showError(
                "Please enter both a title and note content."
            );

            (!title ? titleInput : contentInput)?.focus();

            return;
        }

        clearError();

        if (saveButton) {
            saveButton.disabled = true;
            saveButton.textContent = "Saving...";
        }

        try {
            await postForm(
                `/edit_note/${encodeURIComponent(id)}`,
                {
                    title,
                    note: content,
                    important: importantInput?.checked
                        ? "true"
                        : "false",
                }
            );

            await loadNotes();
        } catch (error) {
            console.error("Failed to save note:", error);

            showError(
                error.message || "Could not save this note."
            );

            if (saveButton) {
                saveButton.disabled = false;
                saveButton.textContent = "Save changes";
            }
        }
    }

    /* ---------- Date validation and filter controls ---------- */

    function validDateFilter(input) {
        if (!input) return true;

        const value = input.value.trim();

        if (!value) {
            input.setCustomValidity("");
            return true;
        }

        const validFormat =
            /^\d{4}$/.test(value) ||
            /^\d{4}-(0[1-9]|1[0-2])$/.test(value) ||
            /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.test(
                value
            );

        if (!validFormat) {
            input.setCustomValidity(
                "Enter a year, YYYY-MM, or YYYY-MM-DD."
            );

            input.reportValidity();

            return false;
        }

        if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            const date = new Date(`${value}T00:00:00Z`);

            if (
                Number.isNaN(date.getTime()) ||
                date.toISOString().slice(0, 10) !== value
            ) {
                input.setCustomValidity(
                    "Enter a valid calendar date."
                );

                input.reportValidity();

                return false;
            }
        }

        input.setCustomValidity("");

        return true;
    }

    function applyFilters(resetPage = true) {
        if (
            !validDateFilter(el.created) ||
            !validDateFilter(el.updated)
        ) {
            return;
        }

        readControls();

        if (resetPage) {
            state.page = 1;
        }

        loadNotes();
    }

    function resetFilters() {
        if (el.search) el.search.value = "";
        if (el.created) el.created.value = "";
        if (el.updated) el.updated.value = "";
        if (el.important) el.important.value = "";
        if (el.updatedStatus) el.updatedStatus.value = "";
        if (el.sort) el.sort.value = "newest";

        if (el.pageSize) {
            el.pageSize.value = String(DEFAULT_PAGE_SIZE);
        }

        state.page = 1;

        readControls();
        clearError();
        loadNotes();
    }

    function scheduleSearch() {
        window.clearTimeout(state.searchTimer);

        state.searchTimer = window.setTimeout(() => {
            applyFilters(true);
        }, 300);
    }

    /* ---------- Event handlers ---------- */

    function initializeEvents() {
        el.search?.addEventListener("input", scheduleSearch);

        el.apply?.addEventListener("click", () => {
            applyFilters(true);
        });

        el.reset?.addEventListener("click", resetFilters);
        el.emptyReset?.addEventListener("click", resetFilters);

        [el.created, el.updated].forEach((input) => {
            input?.addEventListener("keydown", (event) => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    applyFilters(true);
                }
            });
        });

        [
            el.created,
            el.updated,
            el.important,
            el.updatedStatus,
            el.sort,
            el.pageSize,
        ].forEach((control) => {
            control?.addEventListener("change", () => {
                applyFilters(true);
            });
        });

        el.previous?.addEventListener("click", () => {
            if (state.page > 1) {
                state.page -= 1;
                loadNotes();
            }
        });

        el.next?.addEventListener("click", () => {
            if (state.page < state.totalPages) {
                state.page += 1;
                loadNotes();
            }
        });

        // Event delegation for note action buttons.
        el.notes?.addEventListener("click", async (event) => {
            const target = event.target;

            if (!(target instanceof Element)) return;

            const button = target.closest("button[data-action]");

            if (!button || !el.notes.contains(button)) {
                return;
            }

            const action = button.dataset.action;
            const id = button.dataset.noteId;

            if (!id) return;

            if (action === "toggle-important") {
                await toggleImportant(id);
            } else if (action === "edit") {
                beginEdit(id);
            } else if (action === "delete") {
                await deleteNote(id);
            } else if (action === "cancel-edit") {
                const card = button.closest(".note-card");

                card?.querySelector(".note-edit-form")?.remove();
                card?.classList.remove("is-editing");

                clearError();
            }
        });

        el.notes?.addEventListener("submit", async (event) => {
            const target = event.target;

            if (!(target instanceof Element)) return;

            const form = target.closest(".note-edit-form");

            if (!form) return;

            event.preventDefault();

            await saveEdit(form);
        });

        el.addForm?.addEventListener("submit", (event) => {
            const title = el.addTitle?.value.trim() || "";
            const content = el.addContent?.value.trim() || "";

            if (!title || !content) {
                event.preventDefault();

                (!title ? el.addTitle : el.addContent)?.focus();
            }
        });

        window.addEventListener("pageshow", (event) => {
            if (event.persisted) {
                loadNotes();
            }
        });
    }

    /* ---------- Initialize ---------- */

    function initialize() {
        initializeTheme();
        initializeEvents();
        readControls();
        loadNotes();
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initialize,
            { once: true }
        );
    } else {
        initialize();
    }
})();